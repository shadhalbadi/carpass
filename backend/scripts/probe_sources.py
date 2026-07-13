import json
import re
import httpx
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json,text/html",
    "Accept-Language": "en-US,en;q=0.9",
}

r = httpx.get(
    "https://om.opensooq.com/en/find",
    params={"search": "true", "term": "toyota camry"},
    headers=headers,
    follow_redirects=True,
    timeout=30,
)
text = r.text
print("status", r.status_code, "len", len(text))

m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.S)
print("NEXT_DATA", bool(m))
if m:
    data = json.loads(m.group(1))
    print("keys", list(data.keys()))
    print(str(data)[:800])

for pat in [r'"post_id"\s*:\s*(\d+)', r'"id"\s*:\s*(\d{6,})', r'opensooq\.com/en/\d+']:
    found = re.findall(pat, text)
    print(pat, "count", len(found), "sample", found[:5])

bf_urls = [
    "https://www.beforward.jp/stocklist/?keyword=camry",
    "https://www.beforward.jp/stocklist/make-toyota/model-camry.html",
    "https://www.beforward.jp/cars/toyota/camry/",
]
for u in bf_urls:
    try:
        rr = httpx.get(u, headers=headers, follow_redirects=True, timeout=20)
        soup = BeautifulSoup(rr.text, "html.parser")
        ids = [a["href"] for a in soup.find_all("a", href=True) if "/id/" in a["href"]]
        print("BF", rr.status_code, u, "id_links", len(ids), "sample", ids[:3])
    except Exception as e:
        print("BF FAIL", u, e)

apis = [
    ("https://api.opensooq.com/v2.1/post/search", {"term": "toyota camry", "country": "om"}),
    ("https://api.opensooq.com/post/search", {"term": "toyota camry", "countryId": "15"}),
]
for u, params in apis:
    try:
        rr = httpx.get(u, params=params, headers=headers, timeout=20, follow_redirects=True)
        print("API", rr.status_code, u, rr.headers.get("content-type"), rr.text[:220].replace("\n", " "))
    except Exception as e:
        print("API FAIL", u, e)
