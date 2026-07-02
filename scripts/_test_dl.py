import requests

url = "https://www.indiacode.nic.in/bitstream/123456789/1560/1/A1955-25.pdf"
s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0"})

r1 = s.get("https://www.indiacode.nic.in/handle/123456789/1560", timeout=15)
print(f"Handle page: {r1.status_code}")

r2 = s.get(url, timeout=15, headers={"Referer": "https://www.indiacode.nic.in/handle/123456789/1560"})
print(f"With referer: {r2.status_code} {r2.headers.get('content-type','')[:50]}")

r3 = requests.get(url.replace("www.", ""), timeout=15)
print(f"No www: {r3.status_code} {r3.headers.get('content-type','')[:50]}")
