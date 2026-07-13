import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Listing
from app.schemas import ListingOut, ListingSearchResult
from app.services.live_search import live_search
from app.services.normalize import normalize_make, normalize_model

router = APIRouter(prefix="/api/listings", tags=["listings"])


def _freshness(fetched_at: datetime | None) -> str:
    if not fetched_at:
        return "unknown"
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - fetched_at
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return "fetched <1h ago"
    if hours < 24:
        return f"fetched {int(hours)}h ago"
    return f"fetched {int(hours / 24)}d ago"


def listing_to_out(row: Listing) -> ListingOut:
    try:
        photos = json.loads(row.photos_json or "[]")
    except json.JSONDecodeError:
        photos = []
    return ListingOut(
        id=row.id,
        source=row.source,
        source_url=row.source_url,
        make=row.make,
        model=row.model,
        year=row.year,
        mileage=row.mileage,
        mileage_unit=row.mileage_unit,
        vin=row.vin,
        damage=row.damage,
        price=row.price,
        currency=row.currency,
        location=row.location,
        country=row.country,
        photos=photos,
        title=row.title,
        normalized_make=row.normalized_make,
        normalized_model=row.normalized_model,
        price_omr=row.price_omr,
        landed_cost_omr=row.landed_cost_omr,
        is_local=row.is_local,
        fetched_at=row.fetched_at,
        freshness=_freshness(row.fetched_at),
    )


@router.get("/search", response_model=ListingSearchResult)
async def search_listings(
    q: str | None = None,
    make: str | None = None,
    model: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    max_landed_omr: float | None = None,
    source: str | None = None,
    is_local: bool | None = None,
    live: bool = Query(True, description="Fetch live marketplace results for this query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    make_value = (make or "").strip()
    model_value = (model or "").strip()
    if q and not make_value:
        # allow free-text "toyota camry" in q
        parts = q.strip().split()
        if parts:
            make_value = parts[0]
            model_value = " ".join(parts[1:]) if len(parts) > 1 else model_value

    live_meta: dict = {
        "live": False,
        "sources_ok": [],
        "sources_attempted": [],
        "errors": {},
        "search_urls": {},
        "message": "",
    }

    if live:
        if not make_value:
            raise HTTPException(status_code=400, detail="Enter a make (e.g. Toyota) to search live listings")
        live_meta = await live_search(
            db,
            make=make_value,
            model=model_value,
            year_min=year_min,
            year_max=year_max,
            source=source,
        )
        live_meta["live"] = True
        if live_meta.get("sources_ok"):
            live_meta["message"] = (
                f"Fetched live results from: {', '.join(live_meta['sources_ok'])}."
            )
        else:
            live_meta["message"] = (
                "No live listings could be fetched. Marketplaces may be blocking bots — "
                "set SCRAPING_PROXY_URL or try BE FORWARD / OpenSooq."
            )

    clauses = [Listing.is_active.is_(True), Listing.duplicate_of_id.is_(None)]
    if make_value:
        clauses.append(Listing.normalized_make == normalize_make(make_value))
    if model_value:
        clauses.append(Listing.normalized_model.contains(normalize_model(model_value)))
    if year_min:
        clauses.append(Listing.year >= year_min)
    if year_max:
        clauses.append(Listing.year <= year_max)
    if max_landed_omr is not None:
        clauses.append(Listing.landed_cost_omr <= max_landed_omr)
    if source:
        clauses.append(Listing.source == source)
    if is_local is not None:
        clauses.append(Listing.is_local.is_(is_local))
    if q and not make:
        like = f"%{q}%"
        clauses.append((Listing.title.ilike(like)) | (Listing.make.ilike(like)) | (Listing.model.ilike(like)))

    # For live searches, prefer freshly saved IDs from this request
    saved_ids = live_meta.get("saved_ids") or []
    if live and saved_ids:
        result = await db.execute(select(Listing).where(Listing.id.in_(saved_ids)))
        rows = list(result.scalars().all())
        # keep order of saved_ids
        by_id = {r.id: r for r in rows}
        rows = [by_id[i] for i in saved_ids if i in by_id]
        if max_landed_omr is not None:
            rows = [r for r in rows if r.landed_cost_omr is not None and r.landed_cost_omr <= max_landed_omr]
        total = len(rows)
        start = (page - 1) * page_size
        rows = rows[start : start + page_size]
    else:
        total = (await db.execute(select(func.count()).select_from(Listing).where(and_(*clauses)))).scalar() or 0
        result = await db.execute(
            select(Listing)
            .where(and_(*clauses))
            .order_by(Listing.fetched_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list(result.scalars().all())
        rows = sorted(rows, key=lambda r: (r.landed_cost_omr is None, r.landed_cost_omr or 0))

    return ListingSearchResult(
        total=total,
        page=page,
        page_size=page_size,
        items=[listing_to_out(r) for r in rows],
        live=bool(live_meta.get("live")),
        sources_ok=list(live_meta.get("sources_ok") or []),
        sources_attempted=list(live_meta.get("sources_attempted") or []),
        errors=dict(live_meta.get("errors") or {}),
        search_urls=dict(live_meta.get("search_urls") or {}),
        message=str(live_meta.get("message") or ""),
    )


@router.delete("/seed")
async def clear_seed_listings(db: AsyncSession = Depends(get_db)):
    """Remove previously seeded / stale demo listings so search is live-only."""
    demo_ids = {
        "51234891",
        "51234892",
        "123456",
        "123457",
        "lx570-1",
        "patrol-1",
        "om-camry-2020",
        "om-lc-2018",
        "om-prado-2019",
        "38001234",
        "om-tucson-2021",
        "61234001",
    }
    result = await db.execute(delete(Listing).where(Listing.source_id.in_(demo_ids)))
    await db.commit()
    return {"deleted": result.rowcount or 0}


@router.get("/{listing_id}", response_model=ListingOut)
async def get_listing(listing_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(Listing, listing_id)
    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing_to_out(row)
