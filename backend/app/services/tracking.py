"""AIS vessel tracking + shipment helpers."""

from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import MilestoneStatus, Notification, Shipment, ShipmentMilestone

logger = logging.getLogger(__name__)

MILESTONE_ORDER = [
    MilestoneStatus.PURCHASED.value,
    MilestoneStatus.EXPORT_YARD.value,
    MilestoneStatus.ON_VESSEL.value,
    MilestoneStatus.ARRIVED_PORT.value,
    MilestoneStatus.CUSTOMS.value,
    MilestoneStatus.RELEASED.value,
    MilestoneStatus.DELIVERED.value,
]

# Approximate Sohar port coordinates
SOHAR_LAT = 24.4920
SOHAR_LON = 56.6250


def generate_tracking_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "CP-" + "".join(secrets.choice(alphabet) for _ in range(8))


async def add_milestone(
    db: AsyncSession,
    shipment: Shipment,
    milestone: str,
    note: str = "",
    updated_by_id: int | None = None,
) -> ShipmentMilestone:
    if milestone not in MILESTONE_ORDER:
        raise ValueError(f"Invalid milestone: {milestone}")
    row = ShipmentMilestone(
        shipment_id=shipment.id,
        milestone=milestone,
        status_note=note,
        updated_by_id=updated_by_id,
    )
    shipment.current_milestone = milestone
    db.add(row)
    # notify owner
    db.add(
        Notification(
            user_id=shipment.user_id,
            shipment_id=shipment.id,
            title=f"Shipment {shipment.tracking_code} update",
            body=f"Status: {milestone.replace('_', ' ')}. {note}".strip(),
        )
    )
    await db.flush()
    return row


async def refresh_vessel_position(db: AsyncSession, shipment: Shipment) -> Shipment:
    """Update vessel lat/lon from AIS API when configured; else simulate progress toward Sohar."""
    settings = get_settings()
    now = datetime.now(timezone.utc)

    if settings.ais_api_key and shipment.vessel_name:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Generic placeholder — providers differ; store response if available
                params = {"api-key": settings.ais_api_key, "name": shipment.vessel_name}
                resp = await client.get(settings.ais_api_url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    # try common shapes
                    vessel = None
                    if isinstance(data, dict):
                        vessel = data.get("data") or data.get("vessel") or data
                        if isinstance(vessel, list) and vessel:
                            vessel = vessel[0]
                    if isinstance(vessel, dict):
                        lat = vessel.get("lat") or vessel.get("latitude")
                        lon = vessel.get("lon") or vessel.get("lng") or vessel.get("longitude")
                        if lat is not None and lon is not None:
                            shipment.vessel_lat = float(lat)
                            shipment.vessel_lon = float(lon)
                            shipment.vessel_updated_at = now
                            # naive ETA: 1 day per ~400km remaining (great-circle-ish approx)
                            rem_km = _approx_km(float(lat), float(lon), SOHAR_LAT, SOHAR_LON)
                            days = max(1, int(rem_km / 400))
                            shipment.eta = now + timedelta(days=days)
                            await db.flush()
                            return shipment
        except Exception as exc:
            logger.warning("AIS lookup failed: %s", exc)

    # Simulation fallback for demos
    if shipment.current_milestone == MilestoneStatus.ON_VESSEL.value:
        # interpolate toward Sohar
        start_lat = shipment.vessel_lat if shipment.vessel_lat is not None else 25.0
        start_lon = shipment.vessel_lon if shipment.vessel_lon is not None else -80.0
        # move 15% closer each refresh
        shipment.vessel_lat = start_lat + (SOHAR_LAT - start_lat) * 0.15
        shipment.vessel_lon = start_lon + (SOHAR_LON - start_lon) * 0.15
        rem_km = _approx_km(shipment.vessel_lat, shipment.vessel_lon, SOHAR_LAT, SOHAR_LON)
        shipment.eta = now + timedelta(days=max(1, int(rem_km / 400)))
        shipment.vessel_updated_at = now
    elif shipment.vessel_lat is None and shipment.origin_port:
        # seed a starting point based on origin keywords
        shipment.vessel_lat, shipment.vessel_lon = _origin_coords(shipment.origin_port)
        shipment.vessel_updated_at = now
        shipment.eta = now + timedelta(days=30)
    await db.flush()
    return shipment


def _approx_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Equirectangular approximation
    import math

    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6371 * math.sqrt(x * x + y * y)


def _origin_coords(port: str) -> tuple[float, float]:
    p = port.lower()
    if "houston" in p or "texas" in p:
        return 29.73, -95.0
    if "los angeles" in p or "long beach" in p:
        return 33.75, -118.2
    if "yokohama" in p or "japan" in p:
        return 35.44, 139.65
    if "busan" in p or "korea" in p:
        return 35.1, 129.04
    if "jebel" in p or "dubai" in p:
        return 25.0, 55.05
    return 30.0, -40.0
