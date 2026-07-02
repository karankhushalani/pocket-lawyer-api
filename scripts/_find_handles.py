"""Find correct India Code handles for each act by searching."""
import requests
import re
import sys
import time

ACTS = [
    "Code of Civil Procedure, 1908",
    "Hindu Succession Act, 1956",
    "Indian Succession Act, 1925",
    "Income Tax Act, 1961",
    "Companies Act, 2013",
    "Right to Information Act, 2005",
    "Information Technology Act, 2000",
    "Motor Vehicles Act, 1988",
    "Environment Protection Act, 1986",
    "Industrial Disputes Act, 1947",
    "Arbitration and Conciliation Act, 1996",
    "Specific Relief Act, 1963",
    "Limitation Act, 1963",
    "Consumer Protection Act, 2019",
    "Prevention of Corruption Act, 1988",
    "Protection of Women from Domestic Violence Act, 2005",
    "Juvenile Justice Act, 2015",
    "Special Marriage Act, 1954",
    "Registration Act, 1908",
    "Indian Stamp Act, 1899",
    "Wildlife Protection Act, 1972",
    "Forest Conservation Act, 1980",
    "Representation of the People Act, 1951",
    "Right to Education Act, 2009",
    "Legal Services Authorities Act, 1987",
    "Indian Partnership Act, 1932",
    "Factories Act, 1948",
    "Employees Provident Funds Act, 1952",
    "Payment of Gratuity Act, 1972",
    "Minimum Wages Act, 1948",
    "Dowry Prohibition Act, 1961",
    "Sexual Harassment of Women at Workplace Act, 2013",
]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

for act in ACTS:
    query = requests.utils.quote(act)
    url = f"https://www.indiacode.nic.in/search?q={query}"
    try:
        r = session.get(url, timeout=15, allow_redirects=True)
        if r.status_code == 200:
            html = r.text
            # Look for handle URLs
            handles = re.findall(r'/handle/123456789/(\d+)', html)
            # Also look for bitstream URLs
            bitstreams = re.findall(r'/bitstream/123456789/(\d+)/(\d+)/([^"\'<>]+\.pdf)', html, re.I)
            print(f"\n{act}")
            if handles:
                print(f"  Handle IDs: {list(set(handles))[:3]}")
            if bitstreams:
                for h, s, f in bitstreams[:2]:
                    print(f"  Bitstream: 123456789/{h}/{s}/{f}")
            if not handles and not bitstreams:
                print(f"  No results found")
        else:
            print(f"\n{act} -> {r.status_code}")
    except Exception as e:
        print(f"\n{act} -> Error: {e}")
    time.sleep(1)
