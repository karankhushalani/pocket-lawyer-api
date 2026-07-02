"""Quick test of PDF download URLs"""
import requests

urls = [
    "https://indiacode.nic.in/bitstream/123456789/4219/1/THE-INDIAN-PENAL-CODE-1860.pdf",
    "https://www.indiacode.nic.in/bitstream/123456789/2187/2/A187209.pdf",
]
for url in urls:
    try:
        r = requests.head(url, timeout=10, allow_redirects=True)
        ct = r.headers.get("content-type", "?")
        cl = r.headers.get("content-length", "?")
        print(f"{url} -> {r.status_code} ({ct}) [{cl}]")
    except Exception as e:
        print(f"{url} -> FAILED: {e}")
