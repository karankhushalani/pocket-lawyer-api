"""Download Indian bare act PDFs from verified sources."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import requests
from urllib3.util.retry import Retry

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "laws")
os.makedirs(DATA_DIR, exist_ok=True)

# Direct URLs - all verified working from India Code or official sources
DIRECT: dict[str, str] = {
    "indian_penal_code": "https://indiacode.nic.in/bitstream/123456789/4219/1/THE-INDIAN-PENAL-CODE-1860.pdf",
    "indian_contract_act": "https://www.indiacode.nic.in/bitstream/123456789/2187/2/A187209.pdf",
    "transfer_of_property_act": "https://www.indiacode.nic.in/bitstream/123456789/2338/1/A1882-04.pdf",
    "negotiable_instruments_act": "https://www.indiacode.nic.in/bitstream/123456789/15327/1/negotiable_instruments_act%2C_1881.pdf",
    "indian_evidence_act": "https://www.indiacode.nic.in/bitstream/123456789/15351/1/iea_1872.pdf",
    "hindu_marriage_act": "https://www.indiacode.nic.in/bitstream/123456789/1560/1/A1955-25.pdf",
    "code_of_criminal_procedure": "https://archive.org/download/1974a/1974a_text.pdf",
    "constitution_of_india": "https://assets.zyrosite.com/m2WBkZgaWaHnqb0E/coi_2024-A1aJNL9LKRUne5LX.pdf",
    "code_of_civil_procedure": "https://www.indiacode.nic.in/bitstream/123456789/11087/1/the_code_of_civil_procedure%2C_1908.pdf",
    "indian_succession_act": "https://www.indiacode.nic.in/bitstream/123456789/2385/1/192539.pdf",
    "hindu_succession_act": "https://www.indiacode.nic.in/bitstream/123456789/1713/1/AAA1956suc___30.pdf",
    "companies_act": "https://www.indiacode.nic.in/bitstream/123456789/2114/5/A2013-18.pdf",
    "right_to_information_act": "https://www.indiacode.nic.in/bitstream/123456789/19840/1/right_yo_information_act.pdf",
    "environment_protection_act": "https://www.indiacode.nic.in/bitstream/123456789/4316/1/ep_act_1986.pdf",
    "industrial_disputes_act": "https://www.indiacode.nic.in/bitstream/123456789/11102/1/industrial-disputes-act-1947.pdf",
    "information_technology_act": "https://www.meity.gov.in/static/uploads/2024/02/ITAct_0-1.pdf",
    "motor_vehicles_act": "https://www.mahapolice.gov.in/uploads/acts_rules/TheMotorVehicleAct%2C1988.pdf",
    "domestic_violence_act": "https://www.indiacode.nic.in/bitstream/123456789/15436/1/protection_of_women_from_domestic_violence_act%2C_2005.pdf",
    "factories_act": "https://www.indiacode.nic.in/bitstream/123456789/15981/1/the_factories_act%2C_1948.pdf",
    "consumer_protection_act": "https://www.indiacode.nic.in/bitstream/123456789/15256/1/eng201935.pdf",
    "arbitration_and_conciliation_act": "https://www.indiacode.nic.in/bitstream/123456789/11799/1/the_arbitration_and_conciliation_act%2C_1996.pdf",
}

# Handle-based URLs requiring session warmup (handle, bitstream_url)
HANDLE_DIRECT: dict[str, tuple[str, str]] = {
    "income_tax_act": ("2435", "https://www.indiacode.nic.in/bitstream/123456789/2435/1/A1961-43.pdf"),
    "specific_relief_act": ("2342", "https://www.indiacode.nic.in/bitstream/123456789/2342/1/A1963-47.pdf"),
    "limitation_act": ("2231", "https://www.indiacode.nic.in/bitstream/123456789/2231/1/A1963-36.pdf"),
    "prevention_of_corruption_act": ("2354", "https://www.indiacode.nic.in/bitstream/123456789/2354/1/A1988-49.pdf"),
    "juvenile_justice_act": ("2104", "https://www.indiacode.nic.in/bitstream/123456789/2104/1/A2015-2.pdf"),
    "special_marriage_act": ("1555", "https://www.indiacode.nic.in/bitstream/123456789/1555/1/A1954-43.pdf"),
    "registration_act": ("2337", "https://www.indiacode.nic.in/bitstream/123456789/2337/1/A1908-16.pdf"),
    "stamp_act": ("2324", "https://www.indiacode.nic.in/bitstream/123456789/2324/1/A1899-2.pdf"),
    "wildlife_protection_act": ("1817", "https://www.indiacode.nic.in/bitstream/123456789/1817/1/A1972-53.pdf"),
    "forest_conservation_act": ("1836", "https://www.indiacode.nic.in/bitstream/123456789/1836/1/A1980-69.pdf"),
    "representation_of_people_act": ("2162", "https://www.indiacode.nic.in/bitstream/123456789/2162/1/A1951-43.pdf"),
    "right_to_education_act": ("2138", "https://www.indiacode.nic.in/bitstream/123456789/2138/1/A2009-35.pdf"),
    "legal_services_authorities_act": ("2136", "https://www.indiacode.nic.in/bitstream/123456789/2136/1/A1987-39.pdf"),
    "partnership_act": ("2268", "https://www.indiacode.nic.in/bitstream/123456789/2268/1/A1932-9.pdf"),
    "employees_provident_fund_act": ("2286", "https://www.indiacode.nic.in/bitstream/123456789/2286/1/A1952-19.pdf"),
    "payment_of_gratuity_act": ("2271", "https://www.indiacode.nic.in/bitstream/123456789/2271/1/A1972-39.pdf"),
    "minimum_wages_act": ("2275", "https://www.indiacode.nic.in/bitstream/123456789/2275/1/A1948-11.pdf"),
    "dowry_prohibition_act": ("2175", "https://www.indiacode.nic.in/bitstream/123456789/2175/1/A1961-28.pdf"),
    "sexual_harassment_at_workplace_act": ("2145", "https://www.indiacode.nic.in/bitstream/123456789/2145/1/A2013-14.pdf"),
}

# Fallback: official Income Tax site
FALLBACK: dict[str, list[str]] = {
    "income_tax_act": [
        "https://incometaxindia.gov.in/Documents/income-tax-act-1961-as-amended-by-finance-act-2025.pdf",
        "https://www.icnl.org/wp-content/uploads/India_IndiaIncomeTax1961.pdf",
    ],
    "specific_relief_act": ["https://www.indiacode.nic.in/bitstream/123456789/21923/1/the_specific_relief_act%2C_1963.pdf"],
    "limitation_act": ["https://www.indiacode.nic.in/bitstream/123456789/2231/2/the_limitation_act%2C_1963.pdf"],
    "prevention_of_corruption_act": ["https://www.indiacode.nic.in/bitstream/123456789/2354/2/the_prevention_of_corruption_act%2C_1988.pdf"],
    "juvenile_justice_act": ["https://www.indiacode.nic.in/bitstream/123456789/2104/2/juvenile_justice_act_2015.pdf"],
    "wildlife_protection_act": ["https://www.indiacode.nic.in/bitstream/123456789/1817/2/the_wildlife_protection_act%2C_1972.pdf"],
    "forest_conservation_act": ["https://www.indiacode.nic.in/bitstream/123456789/1836/2/the_forest_conservation_act%2C_1980.pdf"],
    "employees_provident_fund_act": ["https://www.indiacode.nic.in/bitstream/123456789/2286/2/AAA1952epf.pdf"],
}

session = requests.Session()
retries = Retry(total=2, backoff_factor=1, status_forcelist=[502, 503, 504])
adapter = requests.adapters.HTTPAdapter(max_retries=retries)
session.mount("https://", adapter)
session.mount("http://", adapter)
ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
session.headers.update({"User-Agent": ua})

def dl(url: str, filepath: str, ref: str = "") -> bool:
    try:
        hdrs = {"User-Agent": ua}
        if ref:
            hdrs["Referer"] = ref
        r = session.get(url, timeout=120, stream=True, headers=hdrs)
        ct = r.headers.get("content-type", "").lower()
        if r.status_code == 200 and ("application/pdf" in ct or "application/octet-stream" in ct):
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            sz = os.path.getsize(filepath) / 1024
            print(f"  OK  {os.path.basename(filepath)} ({sz:.0f} KB)")
            return True
        print(f"  FAIL {os.path.basename(filepath)} -> {r.status_code} {ct[:50]}")
        return False
    except Exception as e:
        print(f"  FAIL {os.path.basename(filepath)} -> {e}")
        return False

def main():
    success=0; fail=0; skip=0

    for key, url in DIRECT.items():
        fp = os.path.join(DATA_DIR, f"{key}.pdf")
        if os.path.exists(fp) and os.path.getsize(fp) > 5000:
            sz=os.path.getsize(fp)/1024; print(f"  EXISTS {key}.pdf ({sz:.0f} KB)"); skip+=1; continue
        print(f"  DL {key}.pdf ...")
        if dl(url, fp): success+=1
        else: fail+=1
        time.sleep(0.5)

    for key, (handle, url) in HANDLE_DIRECT.items():
        fp = os.path.join(DATA_DIR, f"{key}.pdf")
        if os.path.exists(fp) and os.path.getsize(fp) > 5000:
            sz=os.path.getsize(fp)/1024; print(f"  EXISTS {key}.pdf ({sz:.0f} KB)"); skip+=1; continue
        handle_url = f"https://www.indiacode.nic.in/handle/123456789/{handle}"
        print(f"  DL {key}.pdf (handle {handle}) ...")
        try: session.get(handle_url, timeout=15)
        except: pass
        if dl(url, fp, ref=handle_url): success+=1
        else: fail+=1
        time.sleep(1)

    for key, urls in FALLBACK.items():
        fp = os.path.join(DATA_DIR, f"{key}.pdf")
        if os.path.exists(fp) and os.path.getsize(fp) > 5000:
            sz=os.path.getsize(fp)/1024; print(f"  EXISTS {key}.pdf ({sz:.0f} KB)"); skip+=1; continue
        ok=False
        for url in urls:
            if ok: break
            print(f"  DL {key}.pdf (fallback) ...")
            if dl(url, fp): ok=True; success+=1
            time.sleep(0.5)
        if not ok: fail+=1

    print(f"\n=== Summary ===\n  OK: {success}  FAIL: {fail}  EXISTS: {skip}")
    print(f"\n=== Files ({len(os.listdir(DATA_DIR))}) ===")
    for f in sorted(os.listdir(DATA_DIR)):
        if f.endswith(".pdf"):
            sz = os.path.getsize(os.path.join(DATA_DIR, f))/1024
            print(f"  {f}: {sz:.0f} KB")

if __name__ == "__main__":
    main()
