from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_roles
from app.crawlers import crawl_all
from app.database import get_db
from app.models import FeeTable, ShippingRoute, User
from app.schemas import FeeOut, FeeUpdate, ShippingRouteOut, ShippingRouteUpdate
from app.services.cost_engine import ensure_defaults

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/fees", response_model=list[FeeOut])
async def list_fees(db: AsyncSession = Depends(get_db), user: User = Depends(require_roles("admin"))):
    await ensure_defaults(db)
    rows = (await db.execute(select(FeeTable).order_by(FeeTable.category, FeeTable.key))).scalars().all()
    return [FeeOut.model_validate(r) for r in rows]


@router.patch("/fees/{fee_id}", response_model=FeeOut)
async def update_fee(
    fee_id: int,
    payload: FeeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    fee = await db.get(FeeTable, fee_id)
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
    fee.value = payload.value
    if payload.notes is not None:
        fee.notes = payload.notes
    await db.commit()
    await db.refresh(fee)
    return FeeOut.model_validate(fee)


@router.get("/routes", response_model=list[ShippingRouteOut])
async def list_routes(db: AsyncSession = Depends(get_db), user: User = Depends(require_roles("admin"))):
    await ensure_defaults(db)
    rows = (await db.execute(select(ShippingRoute).order_by(ShippingRoute.origin_country))).scalars().all()
    return [ShippingRouteOut.model_validate(r) for r in rows]


@router.patch("/routes/{route_id}", response_model=ShippingRouteOut)
async def update_route(
    route_id: int,
    payload: ShippingRouteUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    route = await db.get(ShippingRoute, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(route, field, value)
    await db.commit()
    await db.refresh(route)
    return ShippingRouteOut.model_validate(route)


@router.post("/crawl")
async def trigger_crawl(
    live: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    results = await crawl_all(db, use_live=live)
    return {"ok": True, "results": results}
