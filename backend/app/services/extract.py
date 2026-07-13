"""Extract normalized car records from HTML using LLM when available, else heuristics."""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.config import get_settings
from app.schemas import CarRecord
from app.services.normalize import detect_country, detect_source


EXTRACTION_PROMPT = """Extract car listing fields from the HTML/text below.
Return ONLY valid JSON with keys:
make, model, year, mileage, mileage_unit, vin, damage, price, currency, location, title, photos (array of urls), source_id.
If unknown, use empty string / null / [].
HTML/text:
"""


def _guess_currency(text: str, url: str) -> str:
    t = text.lower()
    if "omr" in t or "ر.ع" in t or "ريال" in t:
        return "OMR"
    if "aed" in t or "د.إ" in t or "dirham" in t:
        return "AED"
    if "¥" in text or "jpy" in t or "yen" in t:
        return "JPY"
    if "€" in text or "eur" in t:
        return "EUR"
    if "£" in text or "gbp" in t:
        return "GBP"
    if "usd" in t or "$" in text:
        return "USD"
    source = detect_source(url)
    return {
        "copart": "USD",
        "iaai": "USD",
        "beforward": "USD",
        "sbt": "USD",
        "dubizzle_uae": "AED",
        "dubizzle_om": "OMR",
        "opensooq": "OMR",
        "sooq_cars": "OMR",
        "encar": "USD",
    }.get(source, "USD")


def _first_price(text: str) -> float | None:
    patterns = [
        r"(?:USD|US\$|\$)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)",
        r"(?:AED|OMR|¥|€|£)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)",
        r"([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?)\s*(?:USD|AED|OMR|\$)",
        r"\b([0-9]{4,7}(?:\.[0-9]+)?)\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def _extract_year(text: str) -> int | None:
    m = re.search(r"\b(19[8-9]\d|20[0-2]\d)\b", text)
    return int(m.group(1)) if m else None


def _extract_vin(text: str) -> str:
    m = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", text.upper())
    return m.group(1) if m else ""


def _extract_mileage(text: str) -> tuple[int | None, str]:
    m = re.search(r"([0-9]{1,3}(?:,[0-9]{3})*)\s*(mi|miles|km|kilometers|كيلو)", text, re.I)
    if not m:
        return None, "km"
    val = int(m.group(1).replace(",", ""))
    unit = m.group(2).lower()
    if unit.startswith("mi"):
        return val, "mi"
    return val, "km"


KNOWN_MAKES = [
    "toyota",
    "lexus",
    "nissan",
    "honda",
    "hyundai",
    "kia",
    "mitsubishi",
    "ford",
    "chevrolet",
    "gmc",
    "mercedes-benz",
    "mercedes",
    "bmw",
    "land rover",
    "mazda",
    "subaru",
    "jeep",
]


def _extract_make_model(title: str) -> tuple[str, str]:
    t = title.strip()
    lower = t.lower()
    for make in KNOWN_MAKES:
        if make in lower:
            idx = lower.find(make)
            rest = t[idx + len(make) :].strip(" -|,/")
            # drop year from rest
            rest = re.sub(r"^(19|20)\d{2}\s*", "", rest)
            rest = re.sub(r"\s+(19|20)\d{2}\b.*$", "", rest)
            model = rest.split()[0:3]
            return make.title() if make != "bmw" else "BMW", " ".join(model).strip(" -")
    parts = t.split()
    if len(parts) >= 2:
        return parts[0], parts[1]
    return t, ""


def heuristic_extract(html: str, url: str) -> CarRecord:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"].strip()

    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)[:12000]

    make, model = _extract_make_model(title or text[:120])
    year = _extract_year(title) or _extract_year(text)
    mileage, mileage_unit = _extract_mileage(text)
    vin = _extract_vin(text)
    price = _first_price(text) or 0.0
    currency = _guess_currency(text, url)

    photos: list[str] = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if src.startswith("//"):
            src = "https:" + src
        if src.startswith("http") and any(x in src.lower() for x in ("jpg", "jpeg", "png", "webp", "image")):
            photos.append(src)
        if len(photos) >= 8:
            break

    # damage keywords
    damage = ""
    for kw in ("front end", "rear end", "side", "flood", "hail", "normal wear", "minor dents", "undercarriage"):
        if kw in text.lower():
            damage = kw
            break

    source = detect_source(url)
    location = ""
    loc_match = re.search(r"(?:Location|Yard|City|موقع)[:\s]+([A-Za-z\u0600-\u06FF ,-]{3,40})", text, re.I)
    if loc_match:
        location = loc_match.group(1).strip()

    return CarRecord(
        make=make,
        model=model,
        year=year,
        mileage=mileage,
        mileage_unit=mileage_unit,
        vin=vin,
        damage=damage,
        price=price,
        currency=currency,
        location=location,
        country=detect_country(source, location),
        photos=photos,
        title=title[:500],
        source=source,
        source_url=url,
        source_id="",
    )


async def llm_extract(html: str, url: str) -> CarRecord | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    try:
        import httpx

        # strip heavy markup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)[:14000]
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You extract structured car listing data. Reply with JSON only."},
                {"role": "user", "content": EXTRACTION_PROMPT + text},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=40.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
        source = detect_source(url)
        return CarRecord(
            make=str(data.get("make") or ""),
            model=str(data.get("model") or ""),
            year=data.get("year"),
            mileage=data.get("mileage"),
            mileage_unit=str(data.get("mileage_unit") or "km"),
            vin=str(data.get("vin") or ""),
            damage=str(data.get("damage") or ""),
            price=float(data.get("price") or 0),
            currency=str(data.get("currency") or _guess_currency(text, url)),
            location=str(data.get("location") or ""),
            country=detect_country(source, str(data.get("location") or "")),
            photos=list(data.get("photos") or [])[:12],
            title=str(data.get("title") or "")[:500],
            source=source,
            source_url=url,
            source_id=str(data.get("source_id") or ""),
        )
    except Exception:
        return None


async def extract_car(html: str, url: str) -> CarRecord:
    llm = await llm_extract(html, url)
    if llm and (llm.make or llm.price):
        return llm
    return heuristic_extract(html, url)


def host_allowed(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    allowed = (
        "copart.com",
        "iaai.com",
        "beforward.jp",
        "be-forward.com",
        "sbtjapan.com",
        "dubizzle.com",
        "opensooq.com",
        "sooq-cars.com",
        "encar.com",
    )
    return any(host.endswith(a) for a in allowed)
