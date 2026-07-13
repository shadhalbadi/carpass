import httpx
from bs4 import BeautifulSoup
headers={"User-Agent":"Mozilla/5.0","Accept-Language":"en"}
urls=[
 "https://www.beforward.jp/stocklist/?keyword=toyota+camry",
 "https://www.beforward.jp/stocklist/keyword=toyota%20camry",
 "https://www.beforward.jp/stock_list/?keywords=camry",
]
for u in urls:
  try:
    r=httpx.get(u, headers=headers, follow_redirects=True, timeout=25)
    soup=BeautifulSoup(r.text,"html.parser")
    ids=[a["href"] for a in soup.find_all("a", href=True) if "/id/" in a["href"]]
    print(r.status_code, len(r.text), len(ids), u, ids[:2])
  except Exception as e:
    print("FAIL", u, e)
