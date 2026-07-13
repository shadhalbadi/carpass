import httpx, re, json
from bs4 import BeautifulSoup
from pathlib import Path
h={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
r=httpx.get("https://www.iaai.com/Search?Keyword=toyota%20camry", headers=h, follow_redirects=True, timeout=40)
Path(r"C:\Users\Shadha.albadi\Desktop\carpass\backend\scripts\iaai.html").write_text(r.text, encoding="utf-8", errors="ignore")
print("len", len(r.text))
soup=BeautifulSoup(r.text, "html.parser")
hrefs=sorted({a.get("href") for a in soup.find_all("a", href=True)})
for href in hrefs:
    if href and ("vehicle" in href.lower() or "detail" in href.lower() or "itemid" in href.lower() or "auction" in href.lower()):
        print("H", href[:160])
# json-ld or script
for s in soup.find_all("script"):
    t=s.string or s.get_text() or ""
    if "VehicleDetail" in t or "inventory" in t.lower() or "lotNumber" in t:
        print("SCRIPT hit", t[:200].replace("\n"," "))
        break
print("next", bool(soup.find("script", id="__NEXT_DATA__")))
ms=re.findall(r"/VehicleDetail/[^\"'\s]+", r.text)
print("VehicleDetail count", len(ms), ms[:5])
ms2=re.findall(r"https://www\.iaai\.com/[^\"'\s]+", r.text)
print("abs links sample", [x for x in ms2 if "Vehicle" in x or "vehicle" in x][:8])
