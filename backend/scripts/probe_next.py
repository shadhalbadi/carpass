import json
import re
import httpx

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
r = httpx.get(
    "https://om.opensooq.com/en/find",
    params={"search": "true", "term": "toyota camry"},
    headers=headers,
    follow_redirects=True,
    timeout=30,
)
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
data = json.loads(m.group(1))
with open("scripts/opensooq_next.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("saved opensooq_next.json")

# walk for listing-like dicts
found = []

def walk(obj, path=""):
    if isinstance(obj, dict):
        keys = set(obj.keys())
        if {"price", "title"} <= keys or {"price", "name"} <= keys or "full_url" in keys or "uri" in keys:
            found.append((path, {k: obj.get(k) for k in list(obj)[:12]}))
        for k, v in obj.items():
            walk(v, path + "/" + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:50]):
            walk(v, path + f"[{i}]")

walk(data)
print("candidates", len(found))
for path, sample in found[:8]:
    print("PATH", path)
    print({k: (str(v)[:80] if not isinstance(v, (dict, list)) else type(v).__name__) for k, v in sample.items()})
    print("---")
