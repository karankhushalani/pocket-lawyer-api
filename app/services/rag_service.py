import asyncio
import json

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentChunk
from app.models.law import LawChunk
from app.services.openai_service import generate_embedding, chat_completion


async def search_law_chunks(
    query: str,
    db: AsyncSession,
    top_k: int = 8,
    act_filter: str | None = None,
) -> list[dict]:
    query_embedding = await generate_embedding(query)
    distance = LawChunk.embedding.cosine_distance(query_embedding)
    stmt = select(
        LawChunk,
        (1 - distance).label("similarity_score"),
    ).order_by(distance).limit(top_k)

    if act_filter:
        stmt = stmt.where(LawChunk.act_short == act_filter.upper())

    result = await db.execute(stmt)
    return [
        {
            "act_name": chunk.act_name,
            "act_short": chunk.act_short,
            "section": chunk.section,
            "chunk_text": chunk.chunk_text,
            "similarity_score": round(float(score), 4),
        }
        for chunk, score in result.all()
    ]


async def search_document_chunks(
    query: str,
    document_id: str,
    db: AsyncSession,
    top_k: int = 5,
) -> list[dict]:
    query_embedding = await generate_embedding(query)
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    stmt = select(
        DocumentChunk,
        (1 - distance).label("similarity_score"),
    ).where(
        DocumentChunk.document_id == document_id
    ).order_by(distance).limit(top_k)

    result = await db.execute(stmt)
    return [
        {
            "chunk_text": chunk.chunk_text,
            "chunk_index": chunk.chunk_index,
            "similarity_score": round(float(score), 4),
        }
        for chunk, score in result.all()
    ]


async def build_legal_context(
    user_query: str,
    db: AsyncSession,
    document_id: str | None = None,
    act_filter: str | None = None,
) -> dict:
    law_task = search_law_chunks(user_query, db, act_filter=act_filter)

    doc_task = None
    if document_id:
        doc_task = search_document_chunks(user_query, document_id, db)

    results = await asyncio.gather(law_task, doc_task) if doc_task else await asyncio.gather(law_task)

    law_results: list[dict] = results[0]
    doc_results: list[dict] = results[1] if doc_task else []

    sections = []
    for r in law_results:
        sections.append(
            f"{r['act_name']} {r['section']}:\n{r['chunk_text']}"
        )
    law_context = "RELEVANT STATUTORY PROVISIONS:\n" + "\n---\n".join(sections) if sections else ""

    doc_chunks = [r["chunk_text"] for r in doc_results]
    doc_context = ""
    if doc_chunks:
        doc_context = "FROM THE UPLOADED DOCUMENT:\n" + "\n---\n".join(doc_chunks)

    sources = []
    for r in law_results:
        sources.append({
            "type": "law",
            "act_name": r["act_name"],
            "act_short": r["act_short"],
            "section": r["section"],
            "relevance": r["similarity_score"],
        })
    for r in doc_results:
        sources.append({
            "type": "document",
            "relevance": r["similarity_score"],
        })

    return {
        "law_context": law_context,
        "document_context": doc_context,
        "sources": sources,
    }


ANALYSIS_SYSTEM_PROMPT = (
    "You are a senior Indian lawyer with expertise in litigation, corporate law, "
    "constitutional law, and legal drafting. Analyze the provided legal document and "
    "return a JSON object with the following fields:\n"
    "  - document_type: str (e.g., 'agreement', 'contract', 'notice', 'pleading', 'affidavit', 'deed', 'will', 'petition', 'order', 'judgment', 'legal notice', 'other')\n"
    "  - summary: str (2-3 sentence plain-language summary of what the document does)\n"
    "  - key_clauses: list of {{'heading': str, 'summary': str, 'risk_level': 'low'|'medium'|'high'}}\n"
    "  - risk_flags: list of str (specific risks, missing elements, deadlines, or unfavorable terms)\n"
    "  - jurisdiction: str (the governing law / court mentioned, or 'Not specified')\n"
    "  - parties: list of str (named parties or 'Not specified')\n"
    "  - dates: list of {{'label': str, 'date': str}} (key dates like execution, expiry, notice period)\n"
    "Return only valid JSON, no markdown, no explanation."
)


async def analyze_document(
    document_text: str,
    document_type: str | None = None,
) -> dict:
    truncated = document_text[:80000]

    messages = [{"role": "system", "content": ANALYSIS_SYSTEM_PROMPT}]
    if document_type:
        messages.append({
            "role": "user",
            "content": f"This document is a {document_type}. Analyze it:\n\n{truncated}",
        })
    else:
        messages.append({
            "role": "user",
            "content": f"Analyze this legal document:\n\n{truncated}",
        })

    content = await chat_completion(
        messages,
        model="gpt-4o",
        temperature=0.1,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )

    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return {
            "document_type": document_type or "unknown",
            "summary": "",
            "key_clauses": [],
            "risk_flags": ["Failed to parse AI response"],
            "jurisdiction": "unknown",
            "parties": [],
            "dates": [],
            "_raw": content,
        }
