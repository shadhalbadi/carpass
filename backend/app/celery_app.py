"""Celery app for scheduled crawls and watch-alert processing."""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "carpass",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.timezone = "Asia/Muscat"
celery_app.conf.beat_schedule = {
    "crawl-copart-iaai-every-6h": {
        "task": "app.celery_app.task_crawl_auctions",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "crawl-daily-markets": {
        "task": "app.celery_app.task_crawl_daily",
        "schedule": crontab(minute=30, hour=6),
    },
    "process-watch-alerts": {
        "task": "app.celery_app.task_process_watches",
        "schedule": crontab(minute="*/30"),
    },
}


def _run_async(coro):
    import asyncio

    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(name="app.celery_app.task_crawl_auctions")
def task_crawl_auctions():
    return _run_async(_crawl(["copart", "iaai"]))


@celery_app.task(name="app.celery_app.task_crawl_daily")
def task_crawl_daily():
    return _run_async(_crawl(["dubizzle_uae", "beforward", "sbt", "opensooq"]))


@celery_app.task(name="app.celery_app.task_process_watches")
def task_process_watches():
    return _run_async(_process_watches())


async def _crawl(sources: list[str]):
    from app.crawlers import crawl_source
    from app.database import AsyncSessionLocal

    out = {}
    async with AsyncSessionLocal() as db:
        for s in sources:
            out[s] = await crawl_source(db, s, use_live=False)
    return out


async def _process_watches():
    import json

    from sqlalchemy import and_, select

    from app.database import AsyncSessionLocal
    from app.models import Listing, Notification, WatchAlert

    created = 0
    async with AsyncSessionLocal() as db:
        watches = (await db.execute(select(WatchAlert).where(WatchAlert.is_active.is_(True)))).scalars().all()
        for w in watches:
            clauses = [Listing.is_active.is_(True), Listing.duplicate_of_id.is_(None)]
            if w.make:
                clauses.append(Listing.normalized_make == w.make.lower())
            if w.model:
                clauses.append(Listing.normalized_model.contains(w.model.lower()))
            if w.year_min:
                clauses.append(Listing.year >= w.year_min)
            if w.year_max:
                clauses.append(Listing.year <= w.year_max)
            if w.max_landed_omr is not None:
                clauses.append(Listing.landed_cost_omr <= w.max_landed_omr)
            sources = json.loads(w.sources_json or "[]")
            if sources:
                clauses.append(Listing.source.in_(sources))
            rows = (await db.execute(select(Listing).where(and_(*clauses)).limit(5))).scalars().all()
            if not rows:
                continue
            titles = ", ".join(f"{r.year} {r.make} {r.model} ({r.landed_cost_omr} OMR)" for r in rows[:3])
            db.add(
                Notification(
                    user_id=w.user_id,
                    watch_id=w.id,
                    title=f"Watch match: {w.name or w.make}",
                    body=f"Found {len(rows)} matching cars. Examples: {titles}",
                )
            )
            from datetime import datetime, timezone

            w.last_notified_at = datetime.now(timezone.utc)
            created += 1
        await db.commit()
    return {"notifications": created}
