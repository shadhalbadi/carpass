"""Live marketplace search — fetch real listings for the user's query only."""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import CarRecord
from app.services.cost_engine import calculate_landed_cost
from app.services.extract import extract_car
from app.services.fetcher import FetchError, fetch_url
from app.services.normalize import apply_normalization, upsert_listing
from app.services.sooq_cars import search_sooq_cars

logger = logging.getLogger(__name__)

BLOCKED_SIGNALS = (
    "request unsuccessful",
    "access denied",
    "captcha",
    "cf-browser-verification",
    "just a moment",
    "attention required",
    "enable javascript and cookies",
    "robot or human",
)

OPENSOOQ_IMG = "https://opensooqui2.os-cdn.com/os_web/previews/"


def _is_blocked(html: str) -> bool:
    lowered = (html or "").lower()
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    # If page already has listing anchors, treat as usable even with challenge strings in scripts
    useful = (
        "/id/" in lowered
        or "vehicledetail" in lowered
        or "/lot/" in lowered
        or "__next_data__" in lowered
        or "serpapiresponse" in lowered
        or "/motors/used-cars/" in lowered
        or "markdown content" in lowered
        or "current bid" in lowered
    )
    if useful and (len(text) > 400 or len(html or "") > 4000):
        if "pardon our interruption" in lowered and "/lot/" not in lowered and re.search(
            r"/motors/used-cars/.+/\d{4}/\d{1,2}/\d{1,2}/", lowered
        ) is None:
            return True
        return False
    if len(text) < 250:
        return True
    strong = (
        "request unsuccessful",
        "cf-browser-verification",
        "attention required",
        "robot or human",
        "verify you are human",
        "pardon our interruption",
    )
    if any(sig in lowered for sig in strong):
        return True
    if "just a moment" in lowered and len(text) < 2000:
        return True
    if "access denied" in lowered and not useful:
        return True
    return False


def build_search_urls(make: str, model: str = "", year_min: int | None = None) -> dict[str, str]:
    make_q = (make or "").strip()
    model_q = (model or "").strip()
    query = " ".join(x for x in [str(year_min or ""), make_q, model_q] if x).strip() or make_q
    q = quote_plus(query)
    make_slug = quote_plus(make_q.lower())
    model_slug = quote_plus(model_q.lower()) if model_q else ""

    urls: dict[str, str] = {}
    if not make_q:
        return urls

    # BE FORWARD — HTML stock list with /id/ links (works without JS)
    urls["beforward"] = f"https://www.beforward.jp/stocklist/?keyword={q}"

    # OpenSooq Oman — Next.js page embeds listings in __NEXT_DATA__
    urls["opensooq"] = f"https://om.opensooq.com/en/find?search=true&term={q}"

    # Dubizzle UAE
    if model_slug:
        urls["dubizzle_uae"] = f"https://uae.dubizzle.com/motors/used-cars/{make_slug}/{model_slug}/"
    else:
        urls["dubizzle_uae"] = f"https://uae.dubizzle.com/motors/used-cars/{make_slug}/"

    # Auctions (often bot-blocked)
    urls["copart"] = f"https://www.copart.com/lotSearchResults/?free=true&query={q}"
    urls["iaai"] = f"https://www.iaai.com/Search?Keyword={q}"

    # Sooq Cars Oman (ready cars) — fetched via API in live_search
    if model_q:
        urls["sooq_cars"] = (
            f"https://sooq-cars.com/om/en/ready/cars?make={quote_plus(make_q)}&model={quote_plus(model_q)}"
        )
    else:
        urls["sooq_cars"] = f"https://sooq-cars.com/om/en/ready/cars?make={quote_plus(make_q)}"
    return urls


def _abs(base: str, href: str) -> str:
    return urljoin(base, href)


def _parse_price_text(text: str) -> tuple[float, str]:
    text = (text or "").replace("\u00a0", " ")
    patterns = [
        (r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*OMR", "OMR"),
        (r"OMR\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)", "OMR"),
        (r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*AED", "AED"),
        (r"(?:AED|Dhs\.?)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)", "AED"),
        (r"(?:USD|US\$|\$)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)", "USD"),
        (r"¥\s*([0-9]{1,3}(?:,[0-9]{3})*)", "JPY"),
    ]
    for pat, cur in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return float(m.group(1).replace(",", "")), cur
    return 0.0, "USD"


def _year_from(text: str) -> int | None:
    m = re.search(r"\b(19[8-9]\d|20[0-2]\d)\b", text or "")
    return int(m.group(1)) if m else None


def parse_beforward(html: str, base_url: str, make: str, model: str) -> list[CarRecord]:
    soup = BeautifulSoup(html, "html.parser")
    cars: list[CarRecord] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/id/" not in href:
            continue
        url = _abs("https://www.beforward.jp", href).split("?")[0]
        if url in seen:
            continue
        seen.add(url)

        card = a.find_parent("div", class_=re.compile(r"stocklist-row($|\s)")) or a.find_parent(
            ["li", "div", "article", "tr"]
        ) or a
        text = card.get_text(" ", strip=True)[:800]

        # Prefer "2018 TOYOTA CAMRY ..." style title inside the row
        title_m = re.search(
            r"\b((?:19|20)\d{2})\s+([A-Z0-9][A-Z0-9 \-/]{2,60})",
            text,
        )
        if title_m:
            year = int(title_m.group(1))
            title = title_m.group(2).title().strip()
        else:
            title = a.get_text(" ", strip=True) or text[:100]
            year = _year_from(text)

        price, currency = _parse_price_text(text)
        mileage = None
        mm = re.search(r"Mileage\s+([0-9,]+)\s*km", text, re.I)
        if mm:
            mileage = int(mm.group(1).replace(",", ""))

        photos: list[str] = []
        img = card.find("img")
        if img and (img.get("src") or img.get("data-src") or img.get("data-original")):
            src = img.get("data-original") or img.get("data-src") or img.get("src")
            photos.append(_abs(base_url, src))

        m = re.search(r"/id/(\d+)", url)
        path_model = model
        parts = urlparse(url).path.strip("/").split("/")
        if len(parts) >= 2 and parts[0].lower() == make.lower():
            path_model = parts[1].replace("-", " ")

        # Skip rows without a usable vehicle title
        if title.lower().startswith("ref no"):
            continue

        cars.append(
            CarRecord(
                make=make.title(),
                model=(path_model or model or "").replace("-", " ").title(),
                year=year,
                mileage=mileage,
                mileage_unit="km",
                price=price,
                currency=currency if price else "USD",
                title=title[:500],
                source="beforward",
                source_url=url,
                source_id=m.group(1) if m else url.rstrip("/").split("/")[-1],
                country="JP",
                location="Japan",
                photos=photos[:3],
            )
        )
        if len(cars) >= 20:
            break
    return cars


def parse_opensooq(html: str, base_url: str, make: str, model: str) -> list[CarRecord]:
    """Parse OpenSooq from embedded Next.js __NEXT_DATA__ JSON (real listing URLs)."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        items = (
            data.get("props", {})
            .get("pageProps", {})
            .get("serpApiResponse", {})
            .get("listings", {})
            .get("items", [])
        )
    except Exception:
        return []

    cars: list[CarRecord] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        # Prefer Autos / cars
        cat = (it.get("cat1_uri") or it.get("cat1_code") or "").lower()
        if cat and cat not in {"cars", "autos", "vehicles"}:
            # still allow if title looks like a car and make matches
            title_l = (it.get("title") or "").lower()
            if make.lower() not in title_l:
                continue

        post_id = str(it.get("id") or "")
        post_url = it.get("post_url") or ""
        if post_id:
            url = f"https://om.opensooq.com/en/search/{post_id}"
        elif post_url.startswith("/"):
            url = "https://om.opensooq.com" + post_url
        elif post_url.startswith("http"):
            url = post_url
        else:
            continue

        title = it.get("title") or ""
        price_amount = it.get("price_amount") or ""
        price, currency = _parse_price_text(str(price_amount))
        if not currency or currency == "USD":
            currency = it.get("price_currency_iso") or currency
        year = _year_from(title) or _year_from(str(it.get("highlights") or ""))
        mileage = it.get("kilometers_Cars_value_i")
        try:
            mileage_i = int(str(mileage).replace(",", "")) if mileage not in (None, "") else None
        except ValueError:
            mileage_i = None

        photos: list[str] = []
        image_uri = it.get("image_uri") or ""
        if image_uri:
            if image_uri.startswith("http"):
                photos.append(image_uri)
            else:
                photos.append(OPENSOOQ_IMG + image_uri)

        # refine make/model from highlights "Toyota » Camry » 2018"
        make_out, model_out = make.title(), (model or "").title()
        highlights = str(it.get("highlights") or "")
        if "»" in highlights:
            parts = [p.strip() for p in highlights.split("»") if p.strip()]
            if parts:
                make_out = parts[0]
            if len(parts) > 1:
                model_out = re.sub(r"[^\w\s\-]", "", parts[1]).strip() or model_out

        cars.append(
            CarRecord(
                make=make_out,
                model=model_out,
                year=year,
                mileage=mileage_i,
                mileage_unit="km",
                price=price,
                currency=currency or "OMR",
                title=title[:500],
                source="opensooq",
                source_url=url,
                source_id=post_id or url.rstrip("/").split("/")[-1],
                country="OM",
                location=it.get("city_label") or "Oman",
                photos=photos[:3],
            )
        )
        if len(cars) >= 20:
            break
    return cars


def parse_dubizzle(html: str, base_url: str, make: str, model: str) -> list[CarRecord]:
    cars: list[CarRecord] = []
    seen: set[str] = set()
    html = html or ""

    # Listing URL shape (works on HTML and Jina markdown):
    # /motors/used-cars/{make}/{model}/{yyyy}/{m}/{d}/{slug}/
    listing_re = re.compile(
        r"https?://(?:uae|dubai)\.dubizzle\.com/motors/used-cars/"
        r"[a-z0-9\-]+/[a-z0-9\-]+/\d{4}/\d{1,2}/\d{1,2}/[a-z0-9\-]+/?",
        re.I,
    )

    # Collect AED amounts for nearest-prior price association (Jina markdown)
    aed_prices = [
        (m.start(), float(m.group(1).replace(",", "")))
        for m in re.finditer(r"(?:AED|Dhs\.?)\s*([0-9]{1,3}(?:,[0-9]{3})+)", html, re.I)
    ]
    # Keep full listing prices; drop tiny / monthly noise
    aed_prices = [(i, p) for i, p in aed_prices if p >= 3000]

    def _nearest_aed(pos: int) -> float:
        prior = [p for i, p in aed_prices if i <= pos]
        return prior[-1] if prior else 0.0

    def _title_from_slug(url: str) -> str:
        slug = url.rstrip("/").split("/")[-1]
        slug = re.sub(r"-\d+---[0-9a-f]{8,}$", "", slug, flags=re.I)
        slug = re.sub(r"-[0-9a-f]{16,}$", "", slug, flags=re.I)
        words = [w for w in slug.replace("-", " ").split() if w and w not in {"2", "3", "12"}]
        title = " ".join(words).strip()
        return title.title() if title else f"{make} {model}".strip()

    def _add(url: str, window: str = "", pos: int | None = None) -> None:
        url = url.split("?")[0].rstrip("/") + "/"
        if url in seen or "/s/trim/" in url:
            return
        seen.add(url)
        title = _title_from_slug(url)
        price, currency = _parse_price_text(window) if window else (0.0, "AED")
        if (not price or price < 3000) and pos is not None:
            near = _nearest_aed(pos)
            if near:
                price, currency = near, "AED"
        if not price or price < 3000:
            idx = html.find(url.rstrip("/"))
            if idx >= 0:
                near = _nearest_aed(idx)
                if near:
                    price, currency = near, "AED"
                else:
                    p2, c2 = _parse_price_text(html[max(0, idx - 500) : idx + 200])
                    if p2 >= 3000:
                        price, currency = p2, c2
        slug = url.rstrip("/").split("/")[-1]
        sid = slug[-40:]
        # Prefer year from title/slug — URL also contains posting date (yyyy/m/d)
        year = _year_from(title) or _year_from(slug) or _year_from(window)
        cars.append(
            CarRecord(
                make=make.title(),
                model=(model or "").title(),
                year=year,
                price=price if price and price >= 3000 else 0.0,
                currency=currency if price and price >= 3000 else "AED",
                title=title[:500],
                source="dubizzle_uae",
                source_url=url,
                source_id=sid,
                country="AE",
                location="UAE",
                photos=[],
            )
        )

    for m in listing_re.finditer(html):
        _add(m.group(0), pos=m.start())
        if len(cars) >= 20:
            return cars

    # Next.js embedded data
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            blob = json.dumps(data)
            for um in listing_re.finditer(blob):
                _add(um.group(0), blob[max(0, um.start() - 400) : um.end() + 400])
                if len(cars) >= 20:
                    return cars
            urls = list(
                dict.fromkeys(
                    re.findall(r"https://uae\.dubizzle\.com/motors/[^\"\\s]+/\d+/?", blob)
                    + ["https://uae.dubizzle.com" + u for u in re.findall(r"\"(/motors/[^\"\\s]+/\d+)/?\"", blob)]
                )
            )
            for url in urls:
                if listing_re.search(url):
                    _add(url)
                if len(cars) >= 20:
                    return cars
        except Exception as exc:
            logger.info("Dubizzle NEXT_DATA parse failed: %s", exc)

    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        url = _abs(base_url, href).split("?")[0]
        if not listing_re.search(url):
            continue
        if "dubizzle.com" not in urlparse(url).netloc:
            continue
        card = a.find_parent(["li", "div", "article"]) or a
        text = card.get_text(" ", strip=True)[:500]
        _add(url, text)
        if len(cars) >= 20:
            break
    return cars


def parse_iaai(html: str, base_url: str, make: str, model: str) -> list[CarRecord]:
    soup = BeautifulSoup(html, "html.parser")
    cars: list[CarRecord] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "vehicledetail" not in href.lower():
            continue
        url = _abs("https://www.iaai.com", href).split("?")[0].split("#")[0]
        if url in seen:
            continue
        seen.add(url)
        card = a.find_parent(["li", "div", "article", "tr", "section"]) or a
        text = card.get_text(" ", strip=True)[:800]
        title = a.get_text(" ", strip=True)
        if len(title) < 5:
            # IAAI often wraps image-only anchors; pull year/make/model from card text
            tm = re.search(
                r"\b((?:19|20)\d{2})\s+([A-Za-z0-9][A-Za-z0-9 \-/]{2,50})",
                text,
            )
            title = f"{tm.group(1)} {tm.group(2).title()}" if tm else f"{make} {model}".strip() or url
        price, currency = _parse_price_text(text)
        year = _year_from(title) or _year_from(text)
        sid_m = re.search(r"/VehicleDetail/(\d+)", url, re.I) or re.search(r"(\d{6,})", url)
        photos: list[str] = []
        img = card.find("img")
        if img and (img.get("src") or img.get("data-src")):
            photos.append(_abs(base_url, img.get("src") or img.get("data-src")))
        cars.append(
            CarRecord(
                make=make.title(),
                model=(model or "").title(),
                year=year,
                price=price,
                currency=currency if price else "USD",
                title=title[:500],
                source="iaai",
                source_url=url,
                source_id=sid_m.group(1) if sid_m else url[-40:],
                country="US",
                location="USA",
                photos=photos[:3],
            )
        )
        if len(cars) >= 20:
            break
    return cars


def parse_copart(html: str, base_url: str, make: str, model: str) -> list[CarRecord]:
    soup = BeautifulSoup(html or "", "html.parser")
    cars: list[CarRecord] = []
    seen: set[str] = set()

    def _title_from_lot_url(url: str, window: str = "") -> str:
        # e.g. /lot/99803885/2022-toyota-camry-se-pa-pittsburgh-north
        slug_m = re.search(r"/lot/\d+/([^/?#]+)", url, re.I)
        if slug_m:
            parts = [p for p in slug_m.group(1).split("-") if p and p.lower() not in {"salvage", "clean", "title"}]
            # drop trailing state/city noise after model-ish words when year present
            titled = " ".join(parts).strip()
            if titled:
                return titled.title()
        title_m = re.search(r"(?:lotDesc|title|yardName)\"?\s*[:=]\s*\"([^\"]{5,120})\"", window, re.I)
        if title_m:
            return title_m.group(1)
        return f"{make} {model}".strip()

    def _add(lot: str, url: str, window: str = "") -> None:
        canon = f"https://www.copart.com/lot/{lot}"
        if canon in seen:
            return
        seen.add(canon)
        title = _title_from_lot_url(url, window)
        price, currency = _parse_price_text(window)
        if not price:
            # Jina markdown often has "Current bid: $150.00 USD" near the lot link
            idx = (html or "").find(url) if url else -1
            if idx < 0:
                idx = (html or "").find(canon)
            if idx >= 0:
                chunk = (html or "")[idx : idx + 900]
                bid = re.search(
                    r"Current bid:\s*\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)",
                    chunk,
                    re.I,
                )
                if bid:
                    price, currency = float(bid.group(1).replace(",", "")), "USD"
                else:
                    price, currency = _parse_price_text(chunk)
        photos: list[str] = []
        img_m = re.search(r"https://cs\.copart\.com/[^\s\)\"']+", window or html or "")
        if img_m:
            photos.append(img_m.group(0))
        cars.append(
            CarRecord(
                make=make.title(),
                model=(model or "").title(),
                year=_year_from(title) or _year_from(url) or _year_from(window),
                price=price,
                currency=currency if price else "USD",
                title=title[:500],
                source="copart",
                source_url=url.split("?")[0] if "/lot/" in url else canon,
                source_id=lot,
                country="US",
                location="USA",
                photos=photos[:3],
            )
        )

    # Full lot URLs (HTML + Jina markdown)
    for m in re.finditer(r"https://www\.copart\.com/lot/(\d+)(/[^\s\)\]\"'<>]*)?", html or "", re.I):
        lot = m.group(1)
        path = m.group(2) or ""
        url = f"https://www.copart.com/lot/{lot}{path}".rstrip(".,;")
        window = (html or "")[max(0, m.start() - 120) : m.end() + 700]
        _add(lot, url, window)
        if len(cars) >= 20:
            return cars

    for pat in (r'"/lot/(\d+)[^"]*"', r'"lotNumber"\s*:\s*"?(\d+)"?'):
        for m in re.finditer(pat, html or "", re.I):
            lot = m.group(1)
            start = max(0, m.start() - 300)
            window = (html or "")[start : m.end() + 300]
            _add(lot, f"https://www.copart.com/lot/{lot}", window)
            if len(cars) >= 20:
                return cars

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/lot/" not in href.lower():
            continue
        url = _abs("https://www.copart.com", href).split("?")[0].split("#")[0]
        if "lotSearchResults" in url:
            continue
        lot_m = re.search(r"/lot/(\d+)", url)
        if not lot_m:
            continue
        card = a.find_parent(["li", "div", "tr", "article", "td"]) or a
        text = card.get_text(" ", strip=True)[:800]
        _add(lot_m.group(1), url, text)
        if len(cars) >= 20:
            break
    return cars


PARSERS = {
    "beforward": parse_beforward,
    "opensooq": parse_opensooq,
    "dubizzle_uae": parse_dubizzle,
    "copart": parse_copart,
    "iaai": parse_iaai,
}


async def enrich_missing_price(car: CarRecord) -> CarRecord:
    if car.price and car.year and car.title:
        return car
    try:
        html = await fetch_url(car.source_url)
        if _is_blocked(html):
            return car
        detailed = await extract_car(html, car.source_url)
        if detailed.price and not car.price:
            car.price = detailed.price
            car.currency = detailed.currency or car.currency
        if detailed.year and not car.year:
            car.year = detailed.year
        if detailed.mileage and not car.mileage:
            car.mileage = detailed.mileage
            car.mileage_unit = detailed.mileage_unit
        if detailed.vin and not car.vin:
            car.vin = detailed.vin
        if detailed.photos and not car.photos:
            car.photos = detailed.photos
        if detailed.title and (not car.title or len(car.title) < 8):
            car.title = detailed.title
        if detailed.make:
            car.make = detailed.make
        if detailed.model:
            car.model = detailed.model
    except Exception as exc:
        logger.info("Detail enrich failed for %s: %s", car.source_url, exc)
    return car


async def live_search(
    db: AsyncSession,
    *,
    make: str,
    model: str = "",
    year_min: int | None = None,
    year_max: int | None = None,
    source: str | None = None,
    max_per_source: int = 12,
    enrich: bool = False,
) -> dict:
    if not (make or "").strip():
        return {
            "items": [],
            "errors": {"query": "Make is required for live search"},
            "sources_ok": [],
            "sources_attempted": [],
            "saved_ids": [],
            "search_urls": {},
        }

    urls = build_search_urls(make, model, year_min)
    if source:
        urls = {k: v for k, v in urls.items() if k == source}

    errors: dict[str, str] = {}
    sources_ok: list[str] = []
    saved_ids: list[int] = []

    for src, search_url in urls.items():
        try:
            if src == "sooq_cars":
                cars = await search_sooq_cars(make, model, max_items=max_per_source)
            else:
                try:
                    html = await fetch_url(search_url)
                except FetchError as exc:
                    errors[src] = f"Fetch failed: {exc}"
                    continue
                except Exception as exc:
                    errors[src] = f"Fetch failed: {exc}"
                    continue

                if _is_blocked(html):
                    errors[src] = "Site blocked the request (captcha/bot protection)."
                    continue

                parser = PARSERS.get(src)
                if not parser:
                    errors[src] = "No parser for source"
                    continue

                cars = parser(html, search_url, make, model)
        except Exception as exc:
            errors[src] = f"Parse failed: {exc}"
            continue

        if not cars:
            errors[src] = "No listings found for this query on that site."
            continue

        sources_ok.append(src)
        count = 0
        for car in cars:
            if year_min and car.year and car.year < year_min:
                continue
            if year_max and car.year and car.year > year_max:
                continue
            # drop useless category shells
            if not car.source_url or car.source_url.rstrip("/").endswith(("cars-for-sale", "used-cars", "find")):
                continue
            car = apply_normalization(car)
            if enrich and count < 3 and not car.price:
                car = await enrich_missing_price(car)
            breakdown = await calculate_landed_cost(db, car)
            listing = await upsert_listing(db, car, landed_cost_omr=breakdown.total_landed_omr)
            saved_ids.append(listing.id)
            count += 1
            if count >= max_per_source:
                break

        if count == 0 and src not in errors:
            errors[src] = "Listings found but none matched year filters."

    await db.commit()
    return {
        "saved_ids": saved_ids,
        "errors": errors,
        "sources_ok": sources_ok,
        "sources_attempted": list(urls.keys()),
        "search_urls": urls,
    }
