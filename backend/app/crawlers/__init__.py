"""Scheduled crawlers for Gulf-relevant car listings (demo + live parse)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import CarRecord
from app.services.cost_engine import calculate_landed_cost
from app.services.extract import extract_car, heuristic_extract
from app.services.fetcher import DEMO_FIXTURES, fetch_url_or_demo
from app.services.normalize import upsert_listing

logger = logging.getLogger(__name__)

# Gulf-relevant makes/models to keep crawl volume small
GULF_QUERIES = [
    ("toyota", "camry"),
    ("toyota", "land cruiser"),
    ("toyota", "prado"),
    ("toyota", "hilux"),
    ("lexus", "lx"),
    ("lexus", "gx"),
    ("nissan", "patrol"),
    ("nissan", "altima"),
    ("honda", "accord"),
    ("hyundai", "tucson"),
]


SOURCE_SEED_URLS: dict[str, list[str]] = {
    "copart": [
        "https://www.copart.com/lot/51234891/2019-toyota-camry",
        "https://www.copart.com/lot/51234892/2018-toyota-land-cruiser",
    ],
    "iaai": [
        "https://www.iaai.com/VehicleDetail/38001234~US",
    ],
    "dubizzle_uae": [
        "https://uae.dubizzle.com/motors/used-cars/toyota/camry/2020/1/",
    ],
    "beforward": [
        "https://www.beforward.jp/toyota/land-cruiser-prado/id/123456/",
        "https://www.beforward.jp/toyota/camry/id/123457/",
    ],
    "sbt": [
        "https://www.sbtjapan.com/vehicle/toyota-camry-2019",
    ],
    "opensooq": [
        "https://om.opensooq.com/ar/سيارات/تويوتا-كامري",
    ],
}


DEMO_CARS: list[CarRecord] = [
    # source_url points to live marketplace SEARCH pages (not fake lot IDs that 404)
    CarRecord(make="Toyota", model="Camry", year=2019, mileage=48230, mileage_unit="mi", vin="4T1B11HK5KU123456", damage="Front End", price=9250, currency="USD", location="Houston, TX", country="US", photos=["https://images.unsplash.com/photo-1621007947382-bb3c3994e3fb?w=800"], title="2019 Toyota Camry SE", source="copart", source_url="https://www.copart.com/lotSearchResults/?free=true&query=2019%20toyota%20camry", source_id="51234891"),
    CarRecord(make="Toyota", model="Land Cruiser", year=2018, mileage=72000, mileage_unit="mi", vin="JTMHY05J5J4123456", damage="Normal Wear", price=28500, currency="USD", location="Savannah, GA", country="US", photos=["https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=800"], title="2018 Toyota Land Cruiser", source="copart", source_url="https://www.copart.com/lotSearchResults/?free=true&query=toyota%20land%20cruiser", source_id="51234892"),
    CarRecord(make="Toyota", model="Prado", year=2018, mileage=75400, mileage_unit="km", price=18890, currency="USD", location="Yokohama, Japan", country="JP", photos=["https://images.unsplash.com/photo-1533473359331-0135ef1bdf37?w=800"], title="2018 Toyota Land Cruiser Prado TX", source="beforward", source_url="https://www.beforward.jp/toyota/land-cruiser-prado/", source_id="123456"),
    CarRecord(make="Toyota", model="Camry", year=2020, mileage=41000, mileage_unit="km", price=16500, currency="USD", location="Nagoya, Japan", country="JP", photos=["https://images.unsplash.com/photo-1621007947382-bb3c3994e3fb?w=800"], title="2020 Toyota Camry G", source="beforward", source_url="https://www.beforward.jp/toyota/camry/", source_id="123457"),
    CarRecord(make="Lexus", model="LX 570", year=2017, mileage=89000, mileage_unit="km", price=145000, currency="AED", location="Dubai", country="AE", photos=["https://images.unsplash.com/photo-1617814076367-b759c7d7e738?w=800"], title="2017 Lexus LX 570", source="dubizzle_uae", source_url="https://uae.dubizzle.com/motors/used-cars/lexus/", source_id="lx570-1"),
    CarRecord(make="Nissan", model="Patrol", year=2019, mileage=67000, mileage_unit="km", price=98000, currency="AED", location="Abu Dhabi", country="AE", photos=["https://images.unsplash.com/photo-1606664515524-ed2f786a0bd6?w=800"], title="2019 Nissan Patrol SE", source="dubizzle_uae", source_url="https://uae.dubizzle.com/motors/used-cars/nissan/", source_id="patrol-1"),
    CarRecord(make="Toyota", model="Camry", year=2020, mileage=62000, mileage_unit="km", price=7900, currency="OMR", location="Muscat", country="OM", photos=["https://images.unsplash.com/photo-1621007947382-bb3c3994e3fb?w=800"], title="تويوتا كامري 2020", source="opensooq", source_url="https://om.opensooq.com/en/cars/toyota", source_id="om-camry-2020"),
    CarRecord(make="Toyota", model="Land Cruiser", year=2018, mileage=95000, mileage_unit="km", price=14500, currency="OMR", location="Muscat", country="OM", photos=["https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=800"], title="تويوتا لاند كروزر 2018", source="opensooq", source_url="https://om.opensooq.com/en/cars/toyota", source_id="om-lc-2018"),
    CarRecord(make="Toyota", model="Prado", year=2019, mileage=80000, mileage_unit="km", price=11800, currency="OMR", location="Salalah", country="OM", photos=["https://images.unsplash.com/photo-1533473359331-0135ef1bdf37?w=800"], title="تويوتا برادو 2019", source="opensooq", source_url="https://om.opensooq.com/en/cars/toyota", source_id="om-prado-2019"),
    CarRecord(make="Honda", model="Accord", year=2019, mileage=55000, mileage_unit="mi", price=11200, currency="USD", location="Florida", country="US", photos=["https://images.unsplash.com/photo-1590362891991-f8809c76df8f?w=800"], title="2019 Honda Accord Sport", source="iaai", source_url="https://www.iaai.com/Search?Keyword=honda%20accord", source_id="38001234"),
    CarRecord(make="Hyundai", model="Tucson", year=2021, mileage=34000, mileage_unit="km", price=7200, currency="OMR", location="Sohar", country="OM", photos=["https://images.unsplash.com/photo-1619767886558-efdc259cde1a?w=800"], title="هيونداي توسان 2021", source="dubizzle_om", source_url="https://oman.dubizzle.com/motors/used-cars/", source_id="om-tucson-2021"),
    CarRecord(make="Lexus", model="GX 460", year=2018, mileage=62000, mileage_unit="mi", price=24900, currency="USD", location="Texas", country="US", photos=["https://images.unsplash.com/photo-1617814076367-b759c7d7e738?w=800"], title="2018 Lexus GX 460", source="copart", source_url="https://www.copart.com/lotSearchResults/?free=true&query=lexus%20gx%20460", source_id="61234001"),
]


async def crawl_source(db: AsyncSession, source: str, use_live: bool = False) -> int:
    """Crawl one source. Returns number of listings upserted."""
    count = 0
    if not use_live:
        for car in DEMO_CARS:
            if car.source == source or (source == "opensooq" and car.source in ("opensooq", "dubizzle_om")):
                breakdown = await calculate_landed_cost(db, car)
                await upsert_listing(db, car, landed_cost_omr=breakdown.total_landed_omr)
                count += 1
        await db.commit()
        return count

    urls = SOURCE_SEED_URLS.get(source, [])
    for url in urls:
        try:
            html, _demo = await fetch_url_or_demo(url)
            car = await extract_car(html, url)
            if not car.make:
                car = heuristic_extract(html if not _demo else DEMO_FIXTURES.get(source, html), url)
            car.source = source
            breakdown = await calculate_landed_cost(db, car)
            await upsert_listing(db, car, landed_cost_omr=breakdown.total_landed_omr)
            count += 1
        except Exception as exc:
            logger.warning("Crawl failed %s: %s", url, exc)
    await db.commit()
    return count


async def crawl_all(db: AsyncSession, use_live: bool = False) -> dict[str, int]:
    results = {}
    for source in ("copart", "iaai", "dubizzle_uae", "beforward", "sbt", "opensooq"):
        results[source] = await crawl_source(db, source, use_live=use_live)
    return results


def matches_gulf_scope(make: str, model: str) -> bool:
    m = (make or "").lower()
    mod = (model or "").lower()
    for gm, gmod in GULF_QUERIES:
        if gm in m and (not gmod or gmod in mod):
            return True
    return m in {g[0] for g in GULF_QUERIES}
