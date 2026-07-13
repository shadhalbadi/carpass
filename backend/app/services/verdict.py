"""Import vs buy-local verdict using local listing comparisons."""

from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Listing
from app.schemas import CostBreakdown
from app.services.normalize import normalize_make, normalize_model


async def attach_local_verdict(db: AsyncSession, breakdown: CostBreakdown) -> CostBreakdown:
    car = breakdown.car
    n_make = normalize_make(car.make)
    n_model = normalize_model(car.model)

    clauses = [Listing.is_local.is_(True), Listing.is_active.is_(True), Listing.duplicate_of_id.is_(None)]
    if n_make:
        clauses.append(Listing.normalized_make == n_make)
    if n_model:
        clauses.append(Listing.normalized_model == n_model)
    if car.year:
        clauses.append(Listing.year.between(car.year - 1, car.year + 1))

    result = await db.execute(select(Listing).where(and_(*clauses)).limit(30))
    locals_ = result.scalars().all()

    if not locals_:
        # broaden: same make/year band
        broad = [Listing.is_local.is_(True), Listing.is_active.is_(True)]
        if n_make:
            broad.append(Listing.normalized_make == n_make)
        if car.year:
            broad.append(Listing.year.between(car.year - 2, car.year + 2))
        result = await db.execute(select(Listing).where(and_(*broad)).limit(30))
        locals_ = result.scalars().all()

    if not locals_:
        breakdown.verdict = "no_local_data"
        breakdown.verdict_message = (
            f"Landed import cost estimate: {breakdown.total_landed_omr:.3f} OMR. "
            "Not enough local comparable listings yet to judge savings."
        )
        return breakdown

    prices = [float(l.price_omr or l.price) for l in locals_ if (l.price_omr or l.price)]
    if not prices:
        breakdown.verdict = "no_local_data"
        breakdown.verdict_message = "Local listings found but prices missing."
        return breakdown

    prices.sort()
    # median
    mid = len(prices) // 2
    median = prices[mid] if len(prices) % 2 else (prices[mid - 1] + prices[mid]) / 2
    breakdown.local_compare_omr = round(median, 3)
    breakdown.local_sample_count = len(prices)
    savings = round(median - breakdown.total_landed_omr, 3)
    breakdown.savings_omr = savings

    if savings > 100:
        breakdown.verdict = "import_saves"
        breakdown.verdict_message = (
            f"Importing looks cheaper. Landed ≈ {breakdown.total_landed_omr:.3f} OMR vs "
            f"local median ≈ {median:.3f} OMR — save about {savings:.3f} OMR "
            f"(based on {len(prices)} local listings)."
        )
    elif savings < -100:
        breakdown.verdict = "buy_local"
        breakdown.verdict_message = (
            f"Buying local looks better. Landed import ≈ {breakdown.total_landed_omr:.3f} OMR vs "
            f"local median ≈ {median:.3f} OMR — local is about {abs(savings):.3f} OMR cheaper."
        )
    else:
        breakdown.verdict = "similar"
        breakdown.verdict_message = (
            f"Import and local prices are similar (landed {breakdown.total_landed_omr:.3f} OMR vs "
            f"local median {median:.3f} OMR)."
        )
    return breakdown
