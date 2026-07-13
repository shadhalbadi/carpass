import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Notification, User, WatchAlert
from app.schemas import NotificationOut, WatchCreate, WatchOut

router = APIRouter(prefix="/api/watches", tags=["watches"])


def _watch_out(w: WatchAlert) -> WatchOut:
    try:
        sources = json.loads(w.sources_json or "[]")
    except json.JSONDecodeError:
        sources = []
    return WatchOut(
        id=w.id,
        name=w.name,
        make=w.make,
        model=w.model,
        year_min=w.year_min,
        year_max=w.year_max,
        max_landed_omr=w.max_landed_omr,
        sources=sources,
        is_active=w.is_active,
        created_at=w.created_at,
    )


@router.get("", response_model=list[WatchOut])
async def list_watches(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(WatchAlert).where(WatchAlert.user_id == user.id).order_by(WatchAlert.id.desc()))).scalars().all()
    return [_watch_out(w) for w in rows]


@router.post("", response_model=WatchOut)
async def create_watch(payload: WatchCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    w = WatchAlert(
        user_id=user.id,
        name=payload.name or f"{payload.make} {payload.model}".strip(),
        make=payload.make.lower(),
        model=payload.model.lower(),
        year_min=payload.year_min,
        year_max=payload.year_max,
        max_landed_omr=payload.max_landed_omr,
        sources_json=json.dumps(payload.sources or []),
    )
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return _watch_out(w)


@router.delete("/{watch_id}")
async def delete_watch(watch_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    w = await db.get(WatchAlert, watch_id)
    if not w or w.user_id != user.id:
        raise HTTPException(status_code=404, detail="Watch not found")
    await db.delete(w)
    await db.commit()
    return {"ok": True}


@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(50)
        )
    ).scalars().all()
    return [NotificationOut.model_validate(r) for r in rows]


@router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    n = await db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    n.is_read = True
    await db.commit()
    return {"ok": True}
