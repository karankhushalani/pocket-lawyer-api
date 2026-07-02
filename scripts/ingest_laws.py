"""
Ingest PDF law files from /data/laws/*.pdf into the law_chunks table.

Usage:
    python -m scripts.ingest_laws
    python -m scripts.ingest_laws --act ipc
    python -m scripts.ingest_laws --act "indian penal code"
"""

import argparse
import asyncio
import glob
import math
import os
import re
import sys
from collections import defaultdict

# ── path hack so we can import from app ──────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pdfplumber
from tqdm.asyncio import tqdm as async_tqdm
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.config import settings
from app.models.law import LawChunk
from openai import AsyncOpenAI

# ── act mapping ──────────────────────────────────────────────────────────
# filename (stem, lowercase) → (act_name, act_short)
ACT_MAP: dict[str, tuple[str, str]] = {
    # ── criminal law ────────────────────────────────────────────────────
    "indian_penal_code":                      ("Indian Penal Code, 1860", "IPC"),
    "bharatiya_nyaya_sanhita":                ("Bharatiya Nyaya Sanhita, 2023", "BNS"),
    "code_of_criminal_procedure":             ("Code of Criminal Procedure, 1973", "CRPC"),
    "bharatiya_nagarik_suraksha_sanhita":     ("Bharatiya Nagarik Suraksha Sanhita, 2023", "BNSS"),
    "indian_evidence_act":                    ("Indian Evidence Act, 1872", "EVIDENCE"),
    "bharatiya_sakshya_adhiniyam":            ("Bharatiya Sakshya Adhiniyam, 2023", "BSA"),
    # ── civil law ───────────────────────────────────────────────────────
    "code_of_civil_procedure":                ("Code of Civil Procedure, 1908", "CPC"),
    "indian_contract_act":                    ("Indian Contract Act, 1872", "CONTRACT"),
    "transfer_of_property_act":               ("Transfer of Property Act, 1882", "TPA"),
    "specific_relief_act":                    ("Specific Relief Act, 1963", "SRA"),
    "limitation_act":                         ("Limitation Act, 1963", "LIMITATION"),
    "arbitration_and_conciliation_act":       ("Arbitration and Conciliation Act, 1996", "ARB"),
    # ── commercial / corporate ──────────────────────────────────────────
    "companies_act":                          ("Companies Act, 2013", "CO"),
    "negotiable_instruments_act":             ("Negotiable Instruments Act, 1881", "NI"),
    "insolvency_and_bankruptcy_code":         ("Insolvency and Bankruptcy Code, 2016", "IBC"),
    "consumer_protection_act":                ("Consumer Protection Act, 2019", "CPA"),
    "partnership_act":                        ("Indian Partnership Act, 1932", "PARTNERSHIP"),
    # ── taxation ────────────────────────────────────────────────────────
    "income_tax_act":                         ("Income Tax Act, 1961", "IT"),
    "central_goods_and_services_tax_act":     ("Central Goods and Services Tax Act, 2017", "CGST"),
    # ── family / personal ───────────────────────────────────────────────
    "hindu_marriage_act":                     ("Hindu Marriage Act, 1955", "HMA"),
    "hindu_succession_act":                   ("Hindu Succession Act, 1956", "HSA"),
    "indian_succession_act":                  ("Indian Succession Act, 1925", "ISA"),
    "muslim_personal_law":                    ("Muslim Personal Law (Shariat) Application Act, 1937", "MPL"),
    "special_marriage_act":                   ("Special Marriage Act, 1954", "SMA"),
    # ── labour ──────────────────────────────────────────────────────────
    "industrial_disputes_act":                ("Industrial Disputes Act, 1947", "ID"),
    "minimum_wages_act":                      ("Minimum Wages Act, 1948", "MW"),
    "factories_act":                          ("Factories Act, 1948", "FACTORIES"),
    "employees_provident_fund_act":           ("Employees' Provident Funds and Miscellaneous Provisions Act, 1952", "EPF"),
    "payment_of_gratuity_act":                ("Payment of Gratuity Act, 1972", "GRATUITY"),
    # ── property / land ─────────────────────────────────────────────────
    "land_acquisition_act":                   ("Right to Fair Compensation and Transparency in Land Acquisition, Rehabilitation and Resettlement Act, 2013", "LARR"),
    "real_estate_regulation_act":             ("Real Estate (Regulation and Development) Act, 2016", "RERA"),
    "registration_act":                       ("Registration Act, 1908", "REGISTRATION"),
    "stamp_act":                              ("Indian Stamp Act, 1899", "STAMP"),
    # ── constitutional / administrative ─────────────────────────────────
    "constitution_of_india":                  ("Constitution of India, 1950", "CONST"),
    "representation_of_people_act":           ("Representation of the People Act, 1951", "RPA"),
    "right_to_information_act":               ("Right to Information Act, 2005", "RTI"),
    # ── environment ─────────────────────────────────────────────────────
    "environment_protection_act":             ("Environment Protection Act, 1986", "EPA"),
    "wildlife_protection_act":                ("Wildlife Protection Act, 1972", "WPA"),
    "forest_conservation_act":                ("Forest Conservation Act, 1980", "FCA"),
    # ── technology / cyber ──────────────────────────────────────────────
    "information_technology_act":             ("Information Technology Act, 2000", "ITA"),
    # ── women / child ───────────────────────────────────────────────────
    "domestic_violence_act":                  ("Protection of Women from Domestic Violence Act, 2005", "DV"),
    "sexual_harassment_at_workplace_act":     ("Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act, 2013", "POSH"),
    "juvenile_justice_act":                   ("Juvenile Justice (Care and Protection of Children) Act, 2015", "JJ"),
    "dowry_prohibition_act":                  ("Dowry Prohibition Act, 1961", "DPA"),
    # ── other key central acts ──────────────────────────────────────────
    "motor_vehicles_act":                     ("Motor Vehicles Act, 1988", "MVA"),
    "prevention_of_corruption_act":           ("Prevention of Corruption Act, 1988", "PCA"),
    "ndps_act":                               ("Narcotic Drugs and Psychotropic Substances Act, 1985", "NDPS"),
    "right_to_education_act":                 ("Right of Children to Free and Compulsory Education Act, 2009", "RTE"),
    "legal_services_authorities_act":         ("Legal Services Authorities Act, 1987", "LSA"),
    # ── state-level examples (add more by following this pattern) ──────
    "up_municipal_corporation_act":           ("Uttar Pradesh Municipal Corporation Act, 1959", "UP-MUN"),
    "karnataka_land_revenue_act":             ("Karnataka Land Revenue Act, 1964", "KA-LR"),
    "maharashtra_rent_control_act":           ("Maharashtra Rent Control Act, 1999", "MH-RENT"),
    "tamil_nadu_prohibition_act":             ("Tamil Nadu Prohibition of Harassment of Women Act, 1998", "TN-WOMEN"),
    "delhi_agricultural_land_ceiling_act":    ("Delhi Land Reforms Act, 1954", "DL-LAND"),
}

SECTION_RE = re.compile(r"[Ss]ection\s+(\d+[A-Z]?)")
SECTION_SPLIT_RE = re.compile(r"(?=\b[Ss]ection\s+\d+[A-Z]?\b|(?<=\n)\d+\.\s+)")



def extract_act_name(filename: str) -> tuple[str, str] | None:
    stem = os.path.splitext(os.path.basename(filename))[0].lower().strip()
    stem = re.sub(r"[^a-z0-9_]", "", stem.replace(" ", "_").replace("-", "_"))
    if stem in ACT_MAP:
        return ACT_MAP[stem]
    for key, (name, short) in ACT_MAP.items():
        if key in stem or stem in key:
            return (name, short)
    return None


def extract_section_ref(text: str) -> str:
    match = SECTION_RE.search(text)
    return match.group(0) if match else "0"


def split_into_sections(text: str) -> list[str]:
    parts = SECTION_SPLIT_RE.split(text)
    merged: list[str] = []
    for p in parts:
        p = p.strip()
        if p:
            merged.append(p)
    if not merged:
        merged = [text.strip()]
    return merged


def chunk_section(section_text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", section_text.strip())
    chunks: list[str] = []
    buffer = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(buffer) + len(para) <= chunk_size:
            buffer = (buffer + "\n\n" + para).strip() if buffer else para
            continue
        if buffer:
            chunks.append(buffer)
            buffer = _overlap_tail(buffer, overlap)

        sentences = re.split(r"(?<=[.!?])\s+", para)
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            if len(buffer) + len(sent) <= chunk_size:
                buffer = (buffer + " " + sent).strip() if buffer else sent
            else:
                if buffer:
                    chunks.append(buffer)
                buffer = _overlap_tail(buffer, overlap) if buffer else ""
                words = sent.split()
                for i in range(0, len(words), chunk_size):
                    chunks.append(" ".join(words[i:i + chunk_size]))
                buffer = ""

    if buffer:
        chunks.append(buffer)
    return chunks


def _overlap_tail(text: str, overlap: int) -> str:
    words = text.split()
    if len(words) <= overlap:
        return text
    return " ".join(words[-overlap:])


async def ingest_pdf(
    filepath: str,
    openai_client: AsyncOpenAI,
    session: AsyncSession,
    session_existing: set[tuple[str, str, int]],
) -> dict:
    filename = os.path.basename(filepath)
    mapped = extract_act_name(filename)
    if not mapped:
        print(f"  ⚠  Skipping {filename}: unrecognised act name")
        return {}

    act_name, act_short = mapped
    print(f"\n  📄 {act_name} ({act_short})  ← {filename}")

    with pdfplumber.open(filepath) as pdf:
        raw = "\n\n".join(
            page.extract_text() or "" for page in pdf.pages
        )

    if not raw.strip():
        print(f"  ⚠  No text extracted from {filename}")
        return {}

    sections = split_into_sections(raw)
    total_words = 0

    inserts: list[LawChunk] = []
    chunk_index = 0

    for sec_text in sections:
        section_ref = extract_section_ref(sec_text)
        chunks = chunk_section(sec_text)
        for chunk in chunks:
            key = (act_name, section_ref, chunk_index)
            if key not in session_existing:
                inserts.append(LawChunk(
                    act_name=act_name,
                    act_short=act_short,
                    section=section_ref,
                    chunk_index=chunk_index,
                    chunk_text=chunk,
                    embedding=None,
                ))
            chunk_index += 1
            total_words += len(chunk.split())

    print(f"     → {len(inserts)} new chunks ({chunk_index - len(inserts)} already exist)")

    batch_size = 100
    for i in range(0, len(inserts), batch_size):
        batch = inserts[i:i + batch_size]
        texts = [c.chunk_text for c in batch]
        response = await openai_client.embeddings.create(
            input=texts,
            model="text-embedding-3-small",
        )
        for chunk, data in zip(batch, response.data):
            chunk.embedding = data.embedding
        session.add_all(batch)
        await session.commit()

    return {
        "act_name": act_name,
        "act_short": act_short,
        "new_chunks": len(inserts),
        "total_chunks": chunk_index,
        "total_words": total_words,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PDF law files into law_chunks")
    parser.add_argument("--act", type=str, default=None,
                        help="Filter: only ingest acts whose name or short code contains this string (case-insensitive)")
    args = parser.parse_args()

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "laws")
    files = sorted(glob.glob(os.path.join(data_dir, "*.pdf")))

    if not files:
        print(f"No PDFs found in {data_dir}")
        return

    if args.act:
        filt = args.act.lower()
        filtered: list[str] = []
        for f in files:
            mapped = extract_act_name(f)
            if mapped and (filt in mapped[0].lower() or filt in mapped[1].lower()):
                filtered.append(f)
        files = filtered
        if not files:
            print(f"No PDFs match --act '{args.act}'")
            return

    print(f"Found {len(files)} PDFs to process\n")

    openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async with async_session_factory() as session:
        result = await session.execute(
            select(LawChunk.act_name, LawChunk.section, LawChunk.chunk_index)
        )
        existing: set[tuple[str, str, int]] = {
            (r.act_name, r.section, r.chunk_index) for r in result
        }
        print(f"Loaded {len(existing)} existing chunk keys from DB\n")

        results: list[dict] = []
        for filepath in async_tqdm(files, desc="Ingesting"):
            res = await ingest_pdf(filepath, openai_client, session, existing)
            if res:
                results.append(res)

    # ── summary ─────────────────────────────────────────────────────────
    total_chunks = sum(r["total_chunks"] for r in results)
    total_words = sum(r["total_words"] for r in results)
    total_tokens = int(total_words * 0.75)
    embedding_cost = (total_tokens / 1_000_000) * 0.020  # text-embedding-3-small: $0.020/1M tokens

    print(f"\n{'='*60}")
    print(f"{'Act':40s} {'Short':8s} {'Chunks':>8s}")
    print(f"{'-'*40} {'-'*8} {'-'*8}")
    per_act: dict[str, dict] = {}
    for r in results:
        key = f"{r['act_name']} ({r['act_short']})"
        per_act[key] = per_act.get(key, 0) + r["total_chunks"]
    for name, count in sorted(per_act.items()):
        short = name.split("(")[-1].rstrip(")")
        print(f"{name:40s} {short:8s} {count:8d}")
    print(f"{'='*60}")
    print(f"Total chunks:       {total_chunks}")
    print(f"Total words:        {total_words}")
    print(f"Estimated tokens:   {total_tokens:,}")
    print(f"Embedding cost:     ${embedding_cost:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
