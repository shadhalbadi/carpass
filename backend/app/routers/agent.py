from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_roles
from app.database import get_db
from app.models import Shipment, User
from app.routers.shipments import _shipment_out
from app.schemas import MilestoneUpdate, ShipmentOut
from app.services.tracking import add_milestone, refresh_vessel_position

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/shipments", response_model=list[ShipmentOut])
async def agent_shipments(user: User = Depends(require_roles("agent", "admin")), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import or_

    q = (
        select(Shipment)
        .options(selectinload(Shipment.milestones), selectinload(Shipment.documents))
        .order_by(Shipment.id.desc())
    )
    if user.role == "agent":
        # Assigned to this agent OR still unclaimed (so agents can claim work)
        q = q.where(or_(Shipment.agent_id == user.id, Shipment.agent_id.is_(None)))
    rows = (await db.execute(q)).scalars().all()
    return [_shipment_out(s) for s in rows]


@router.post("/shipments/{shipment_id}/claim", response_model=ShipmentOut)
async def claim_shipment(
    shipment_id: int,
    user: User = Depends(require_roles("agent", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(selectinload(Shipment.milestones), selectinload(Shipment.documents))
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    s.agent_id = user.id
    await add_milestone(db, s, s.current_milestone, f"Assigned to clearing agent {user.company_name or user.email}", user.id)
    await db.commit()
    result = await db.execute(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(selectinload(Shipment.milestones), selectinload(Shipment.documents))
    )
    return _shipment_out(result.scalar_one())


@router.post("/shipments/{shipment_id}/status", response_model=ShipmentOut)
async def agent_update_status(
    shipment_id: int,
    payload: MilestoneUpdate,
    user: User = Depends(require_roles("agent", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(selectinload(Shipment.milestones), selectinload(Shipment.documents))
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    if user.role == "agent" and s.agent_id not in (None, user.id):
        raise HTTPException(status_code=403, detail="Not your shipment")
    if s.agent_id is None:
        s.agent_id = user.id
    try:
        await add_milestone(db, s, payload.milestone, payload.status_note, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await refresh_vessel_position(db, s)
    await db.commit()
    result = await db.execute(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(selectinload(Shipment.milestones), selectinload(Shipment.documents))
    )
    return _shipment_out(result.scalar_one())


@router.get("/track-link/{tracking_code}")
async def white_label_link(tracking_code: str, user: User = Depends(require_roles("agent", "admin"))):
    """Return a shareable tracking URL for agent clients."""
    return {
        "tracking_code": tracking_code.upper(),
        "public_path": f"/track/{tracking_code.upper()}",
        "message": "Share this link with your client for live shipment status.",
    }
