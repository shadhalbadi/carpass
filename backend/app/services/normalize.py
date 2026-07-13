"""Normalize makes/models (EN/AR) and deduplicate listings."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Listing
from app.schemas import CarRecord
from app.services.exchange import to_omr

MAKE_ALIASES: dict[str, str] = {
    "toyota": "toyota",
    "تويوتا": "toyota",
    "lexus": "lexus",
    "لكزس": "lexus",
    "nissan": "nissan",
    "نيسان": "nissan",
    "honda": "honda",
    "هوندا": "honda",
    "hyundai": "hyundai",
    "هيونداي": "hyundai",
    "هيونداى": "hyundai",
    "kia": "kia",
    "كيا": "kia",
    "mitsubishi": "mitsubishi",
    "ميتسوبيشي": "mitsubishi",
    "ford": "ford",
    "فورد": "ford",
    "chevrolet": "chevrolet",
    "شيفروليه": "chevrolet",
    "gmc": "gmc",
    "جي ام سي": "gmc",
    "mercedes": "mercedes-benz",
    "mercedes-benz": "mercedes-benz",
    "مرسيدس": "mercedes-benz",
    "bmw": "bmw",
    "بي ام دبليو": "bmw",
    "land rover": "land rover",
    "لاند روفر": "land rover",
    "range rover": "land rover",
}

MODEL_ALIASES: dict[str, str] = {
    "camry": "camry",
    "كامري": "camry",
    "كامرى": "camry",
    "land cruiser": "land cruiser",
    "لاند كروزر": "land cruiser",
    "اف جي": "fj cruiser",
    "prado": "prado",
    "برادو": "prado",
    "corolla": "corolla",
    "كورولا": "corolla",
    "hilux": "hilux",
    "هايلوكس": "hilux",
    "patrol": "patrol",
    "باترول": "patrol",
    "altima": "altima",
    "التيما": "altima",
    "accord": "accord",
    "اكورد": "accord",
    "civic": "civic",
    "سيفيك": "civic",
    "sonata": "sonata",
    "سوناتا": "sonata",
    "elantra": "elantra",
    "النترا": "elantra",
    "tucson": "tucson",
    "تucson": "tucson",
    "توسان": "tucson",
    "sportage": "sportage",
    "سبورتاج": "sportage",
    "lx570": "lx 570",
    "lx 570": "lx 570",
    "gx460": "gx 460",
    "gx 460": "gx 460",
    "es350": "es 350",
    "es 350": "es 350",
}


def _clean(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_make(make: str) -> str:
    cleaned = _clean(make)
    return MAKE_ALIASES.get(cleaned, cleaned)


def normalize_model(model: str) -> str:
    cleaned = _clean(model)
    if cleaned in MODEL_ALIASES:
        return MODEL_ALIASES[cleaned]
    # try partial contains
    for alias, canon in MODEL_ALIASES.items():
        if alias in cleaned:
            return canon
    return cleaned


def detect_source(url: str) -> str:
    u = (url or "").lower()
    if "copart.com" in u:
        return "copart"
    if "iaai.com" in u:
        return "iaai"
    if "beforward.jp" in u or "be-forward" in u:
        return "beforward"
    if "sbtjapan" in u:
        return "sbt"
    if "dubizzle.com" in u and ("/uae/" in u or "dubai" in u or "uae." in u):
        return "dubizzle_uae"
    if "dubizzle.com" in u or "dubizzle.om" in u:
        return "dubizzle_om"
    if "opensooq.com" in u:
        return "opensooq"
    if "sooq-cars.com" in u:
        return "sooq_cars"
    if "encar.com" in u:
        return "encar"
    return "unknown"


def detect_country(source: str, location: str = "") -> str:
    mapping = {
        "copart": "US",
        "iaai": "US",
        "beforward": "JP",
        "sbt": "JP",
        "encar": "KR",
        "dubizzle_uae": "AE",
        "dubizzle_om": "OM",
        "opensooq": "OM",
        "sooq_cars": "OM",
    }
    if source in mapping:
        return mapping[source]
    loc = (location or "").lower()
    if any(x in loc for x in ("oman", "muscat", "salalah", "sohar", "مسقط")):
        return "OM"
    if any(x in loc for x in ("dubai", "abu dhabi", "uae", "الامارات")):
        return "AE"
    if any(x in loc for x in ("japan", "tokyo", "osaka")):
        return "JP"
    if any(x in loc for x in ("usa", "texas", "california", "florida", "georgia")):
        return "US"
    return ""


def apply_normalization(car: CarRecord) -> CarRecord:
    data = car.model_dump()
    data["make"] = car.make or ""
    data["model"] = car.model or ""
    if not data.get("source") and data.get("source_url"):
        data["source"] = detect_source(data["source_url"])
    if not data.get("country"):
        data["country"] = detect_country(data.get("source", ""), data.get("location", ""))
    return CarRecord(**data)


async def upsert_listing(db: AsyncSession, car: CarRecord, landed_cost_omr: float | None = None) -> Listing:
    car = apply_normalization(car)
    source = car.source or detect_source(car.source_url)
    source_id = car.source_id or _source_id_from_url(car.source_url)
    price_omr = await to_omr(car.price, car.currency)
    n_make = normalize_make(car.make)
    n_model = normalize_model(car.model)
    is_local = (car.country or "").upper() == "OM" or source in ("opensooq", "dubizzle_om", "sooq_cars")

    existing = None
    if source_id:
        result = await db.execute(
            select(Listing).where(Listing.source == source, Listing.source_id == source_id)
        )
        existing = result.scalar_one_or_none()

    photos_json = json.dumps(car.photos or [])
    if existing:
        existing.make = car.make
        existing.model = car.model
        existing.year = car.year
        existing.mileage = car.mileage
        existing.mileage_unit = car.mileage_unit
        existing.vin = car.vin or existing.vin
        existing.damage = car.damage
        existing.price = car.price
        existing.currency = car.currency
        existing.location = car.location
        existing.country = car.country
        existing.photos_json = photos_json
        existing.title = car.title
        existing.normalized_make = n_make
        existing.normalized_model = n_model
        existing.price_omr = price_omr
        if landed_cost_omr is not None:
            existing.landed_cost_omr = landed_cost_omr
        existing.is_local = is_local
        existing.source_url = car.source_url or existing.source_url
        existing.is_active = True
        listing = existing
    else:
        listing = Listing(
            source=source,
            source_id=source_id or f"gen-{abs(hash(car.source_url or car.title)) % 10**10}",
            source_url=car.source_url,
            make=car.make,
            model=car.model,
            year=car.year,
            mileage=car.mileage,
            mileage_unit=car.mileage_unit,
            vin=car.vin,
            damage=car.damage,
            price=car.price,
            currency=car.currency,
            location=car.location,
            country=car.country,
            photos_json=photos_json,
            title=car.title,
            normalized_make=n_make,
            normalized_model=n_model,
            price_omr=price_omr,
            landed_cost_omr=landed_cost_omr,
            is_local=is_local,
        )
        db.add(listing)

    await db.flush()
    await _maybe_mark_duplicate(db, listing)
    return listing


def _source_id_from_url(url: str) -> str:
    if not url:
        return ""
    # common patterns
    m = re.search(r"/lot/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"[?&](?:id|lot|stock)=([A-Za-z0-9_-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"/(\d{5,})(?:/|$|\?)", url)
    if m:
        return m.group(1)
    return ""


async def _maybe_mark_duplicate(db: AsyncSession, listing: Listing) -> None:
    """Mark duplicates by VIN or strong make/model/year/price similarity."""
    if listing.vin and len(listing.vin) >= 11:
        result = await db.execute(
            select(Listing).where(
                Listing.vin == listing.vin,
                Listing.id != listing.id,
                Listing.is_active.is_(True),
            )
        )
        other = result.scalars().first()
        if other:
            listing.duplicate_of_id = other.id
            return

    result = await db.execute(
        select(Listing).where(
            Listing.normalized_make == listing.normalized_make,
            Listing.normalized_model == listing.normalized_model,
            Listing.year == listing.year,
            Listing.id != listing.id,
            Listing.is_active.is_(True),
        )
    )
    candidates = result.scalars().all()
    for other in candidates:
        if not listing.title or not other.title:
            continue
        ratio = SequenceMatcher(None, listing.title.lower(), other.title.lower()).ratio()
        price_close = abs((listing.price_omr or 0) - (other.price_omr or 0)) < 50
        if ratio > 0.85 and price_close:
            listing.duplicate_of_id = other.id
            return


def photo_similarity_score(urls_a: list[str], urls_b: list[str]) -> float:
    """Lightweight URL-set overlap as a proxy until vision compare is available."""
    if not urls_a or not urls_b:
        return 0.0
    set_a = {u.split("?")[0].rstrip("/").lower() for u in urls_a}
    set_b = {u.split("?")[0].rstrip("/").lower() for u in urls_b}
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / max(len(set_a | set_b), 1)
