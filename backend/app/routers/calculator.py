import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, get_current_user_optional
from app.database import get_db
from app.models import Calculation, Listing, User
from app.schemas import CalculationOut, CarRecord, CostBreakdown, FetchUrlRequest, ManualCarRequest
from app.services.cost_engine import calculate_landed_cost
from app.services.extract import extract_car
from app.services.fetcher import FetchError, fetch_url, fetch_url_or_demo
from app.services.live_search import _is_blocked, parse_opensooq
from app.services.normalize import apply_normalization, upsert_listing
from app.services.verdict import attach_local_verdict

router = APIRouter(prefix="/api/calculator", tags=["calculator"])


def _listing_to_car(listing: Listing) -> CarRecord:
    try:
        photos = json.loads(listing.photos_json or "[]")
    except json.JSONDecodeError:
        photos = []
    return CarRecord(
        make=listing.make,
        model=listing.model,
        year=listing.year,
        mileage=listing.mileage,
        mileage_unit=listing.mileage_unit or "km",
        vin=listing.vin or "",
        damage=listing.damage or "",
        price=float(listing.price or 0),
        currency=listing.currency or "USD",
        location=listing.location or "",
        country=listing.country or "",
        photos=photos,
        title=listing.title or "",
        source=listing.source or "",
        source_url=listing.source_url or "",
        source_id=listing.source_id or "",
    )


async def _extract_from_live_url(url: str) -> CarRecord | None:
    """Fetch a real listing URL with no demo fallback."""
    try:
        html = await fetch_url(url)
    except Exception:
        return None
    if _is_blocked(html):
        return None

    if "opensooq.com" in url.lower():
        m = re.search(r"/search/(\d+)", url)
        cars = parse_opensooq(html, url, make="", model="")
        if m and cars:
            for c in cars:
                if str(c.source_id) == m.group(1):
                    c.source_url = url
                    return apply_normalization(c)
        if cars:
            car = cars[0]
            car.source_url = url
            return apply_normalization(car)

    car = await extract_car(html, url)
    car = apply_normalization(car)
    car.source_url = url
    if not car.price and not car.make:
        return None
    return car


@router.post("/fetch", response_model=CostBreakdown)
async def fetch_and_calculate(
    payload: FetchUrlRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    url = payload.url.strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")

    # Prefer exact saved live listing for this URL
    existing = (
        await db.execute(select(Listing).where(Listing.source_url == url, Listing.is_active.is_(True)))
    ).scalar_one_or_none()
    if existing and existing.price:
        car = _listing_to_car(existing)
        breakdown = await calculate_landed_cost(db, car)
        breakdown = await attach_local_verdict(db, breakdown)
        if payload.save:
            listing = await upsert_listing(db, car, landed_cost_omr=breakdown.total_landed_omr)
            db.add(
                Calculation(
                    user_id=user.id if user else None,
                    source_url=url,
                    listing_id=listing.id,
                    car_json=json.dumps(breakdown.car.model_dump()),
                    breakdown_json=json.dumps(breakdown.model_dump()),
                    total_landed_omr=breakdown.total_landed_omr,
                    local_compare_omr=breakdown.local_compare_omr,
                    verdict=breakdown.verdict,
                    savings_omr=breakdown.savings_omr,
                )
            )
            await db.commit()
        return breakdown

    car = await _extract_from_live_url(url)
    if not car:
        try:
            html, used_demo = await fetch_url_or_demo(url)
            if used_demo:
                raise HTTPException(
                    status_code=502,
                    detail="Could not fetch that listing URL (site blocked). Use Recalculate from a live Search result.",
                )
            car = apply_normalization(await extract_car(html, url))
            car.source_url = url
        except HTTPException:
            raise
        except FetchError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not car.price and not car.make:
        raise HTTPException(status_code=502, detail="Could not extract car data from that URL")

    breakdown = await calculate_landed_cost(db, car)
    breakdown = await attach_local_verdict(db, breakdown)

    if payload.save:
        listing = await upsert_listing(db, car, landed_cost_omr=breakdown.total_landed_omr)
        db.add(
            Calculation(
                user_id=user.id if user else None,
                source_url=url,
                listing_id=listing.id,
                car_json=json.dumps(breakdown.car.model_dump()),
                breakdown_json=json.dumps(breakdown.model_dump()),
                total_landed_omr=breakdown.total_landed_omr,
                local_compare_omr=breakdown.local_compare_omr,
                verdict=breakdown.verdict,
                savings_omr=breakdown.savings_omr,
            )
        )
        await db.commit()
    return breakdown


@router.post("/listing/{listing_id}", response_model=CostBreakdown)
async def calculate_from_listing(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Recalculate using the exact saved listing link + price."""
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    car = _listing_to_car(listing)

    def _looks_like_year(value: float | None) -> bool:
        if value is None:
            return False
        return 1900 <= float(value) <= 2035 and float(value).is_integer()

    # Optional live refresh — only accept sensible prices
    if listing.source_url:
        refreshed = await _extract_from_live_url(listing.source_url)
        if (
            refreshed
            and refreshed.price
            and refreshed.price >= 100
            and not _looks_like_year(refreshed.price)
        ):
            same_id = bool(listing.source_id) and str(refreshed.source_id) == str(listing.source_id)
            same_make = (refreshed.make or "").lower() == (listing.make or "").lower() or not refreshed.make
            if same_id or same_make:
                car.price = refreshed.price
                car.currency = refreshed.currency or car.currency
                if refreshed.mileage:
                    car.mileage = refreshed.mileage
                if refreshed.year:
                    car.year = refreshed.year
                if refreshed.title:
                    car.title = refreshed.title
                if refreshed.photos:
                    car.photos = refreshed.photos

    # Repair corrupted rows where year was stored as price
    if _looks_like_year(car.price) and car.year and int(car.price) == int(car.year):
        raise HTTPException(
            status_code=409,
            detail="Listing price looks invalid (year stored as price). Run live Search again for this car, then recalculate.",
        )

    car.source_url = listing.source_url or car.source_url
    car.source = listing.source or car.source
    car.source_id = listing.source_id or car.source_id
    car = apply_normalization(car)

    breakdown = await calculate_landed_cost(db, car)
    breakdown = await attach_local_verdict(db, breakdown)
    breakdown.car.source_url = listing.source_url or breakdown.car.source_url
    breakdown.car.make = listing.make or breakdown.car.make
    breakdown.car.model = listing.model or breakdown.car.model
    if listing.price and not _looks_like_year(listing.price):
        # Keep displayed identity aligned with saved listing when refresh didn't improve price
        if _looks_like_year(breakdown.car.price) or not breakdown.car.price:
            breakdown.car.price = float(listing.price)
            breakdown.car.currency = listing.currency or breakdown.car.currency

    updated = await upsert_listing(db, car, landed_cost_omr=breakdown.total_landed_omr)
    db.add(
        Calculation(
            user_id=user.id if user else None,
            source_url=listing.source_url,
            listing_id=updated.id,
            car_json=json.dumps(breakdown.car.model_dump()),
            breakdown_json=json.dumps(breakdown.model_dump()),
            total_landed_omr=breakdown.total_landed_omr,
            local_compare_omr=breakdown.local_compare_omr,
            verdict=breakdown.verdict,
            savings_omr=breakdown.savings_omr,
        )
    )
    await db.commit()
    return breakdown


@router.post("/manual", response_model=CostBreakdown)
async def manual_calculate(
    payload: ManualCarRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    car = apply_normalization(payload.car)
    breakdown = await calculate_landed_cost(db, car, origin_country=payload.origin_country, mode=payload.mode)
    breakdown = await attach_local_verdict(db, breakdown)
    if payload.save:
        listing = await upsert_listing(db, car, landed_cost_omr=breakdown.total_landed_omr)
        db.add(
            Calculation(
                user_id=user.id if user else None,
                source_url=car.source_url,
                listing_id=listing.id,
                car_json=json.dumps(breakdown.car.model_dump()),
                breakdown_json=json.dumps(breakdown.model_dump()),
                total_landed_omr=breakdown.total_landed_omr,
                local_compare_omr=breakdown.local_compare_omr,
                verdict=breakdown.verdict,
                savings_omr=breakdown.savings_omr,
            )
        )
        await db.commit()
    return breakdown


@router.get("/history", response_model=list[CalculationOut])
async def history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Calculation).where(Calculation.user_id == user.id).order_by(Calculation.id.desc()).limit(50)
    )
    rows = result.scalars().all()
    out = []
    for r in rows:
        out.append(
            CalculationOut(
                id=r.id,
                source_url=r.source_url,
                car=json.loads(r.car_json or "{}"),
                breakdown=json.loads(r.breakdown_json or "{}"),
                total_landed_omr=r.total_landed_omr,
                local_compare_omr=r.local_compare_omr,
                verdict=r.verdict,
                savings_omr=r.savings_omr,
                created_at=r.created_at,
            )
        )
    return out
