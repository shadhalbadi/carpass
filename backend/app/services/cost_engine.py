"""Landed cost engine for Oman imports."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import FeeTable, ShippingRoute
from app.schemas import CarRecord, CostBreakdown, CostLineItem
from app.services.exchange import get_rates, to_omr, usd_to_omr
from app.services.normalize import detect_country


DEFAULT_FEES = [
    ("auction_fee_usd", "Auction / broker fee", 350.0, "USD", "fees", "Typical auction + broker fee"),
    ("marine_insurance_pct", "Marine insurance", 1.5, "percent", "fees", "% of car + shipping CIF base"),
    ("port_handling_omr", "Port handling (Sohar)", 45.0, "OMR", "oman", "Port terminal handling"),
    ("clearing_agent_omr", "Clearing agent fee", 75.0, "OMR", "oman", "Bayan / clearance"),
    ("rop_registration_omr", "ROP inspection & registration", 55.0, "OMR", "oman", "Inspection + plates estimate"),
    ("bayan_fee_omr", "Bayan system fee", 5.0, "OMR", "oman", "Customs system charges"),
]

DEFAULT_ROUTES = [
    ("US", "Houston / US East", "Sohar", "roro", 1100, 1500, 250, 28, 40),
    ("US", "US West Coast", "Sohar", "roro", 1300, 1700, 300, 30, 45),
    ("JP", "Yokohama / Japan", "Sohar", "roro", 900, 1300, 150, 25, 35),
    ("KR", "Busan / Korea", "Sohar", "roro", 950, 1350, 150, 25, 35),
    ("AE", "Jebel Ali / Dubai", "Sohar", "roro", 80, 150, 50, 1, 3),
]


async def ensure_defaults(db: AsyncSession) -> None:
    for key, label, value, unit, category, notes in DEFAULT_FEES:
        result = await db.execute(select(FeeTable).where(FeeTable.key == key))
        if not result.scalar_one_or_none():
            db.add(
                FeeTable(key=key, label=label, value=value, unit=unit, category=category, notes=notes)
            )
    for row in DEFAULT_ROUTES:
        origin, port, dest, mode, mn, mx, inland, dmin, dmax = row
        result = await db.execute(
            select(ShippingRoute).where(
                ShippingRoute.origin_country == origin,
                ShippingRoute.origin_port == port,
                ShippingRoute.mode == mode,
            )
        )
        if not result.scalar_one_or_none():
            db.add(
                ShippingRoute(
                    origin_country=origin,
                    origin_port=port,
                    dest_port=dest,
                    mode=mode,
                    min_usd=mn,
                    max_usd=mx,
                    inland_usd=inland,
                    transit_days_min=dmin,
                    transit_days_max=dmax,
                )
            )
    await db.commit()


async def get_fee_map(db: AsyncSession) -> dict[str, FeeTable]:
    result = await db.execute(select(FeeTable))
    return {f.key: f for f in result.scalars().all()}


async def pick_route(
    db: AsyncSession, country: str, mode: str = "roro"
) -> ShippingRoute | None:
    country = (country or "").upper()
    result = await db.execute(
        select(ShippingRoute).where(
            ShippingRoute.origin_country == country,
            ShippingRoute.mode == mode,
            ShippingRoute.is_active.is_(True),
        )
    )
    routes = result.scalars().all()
    return routes[0] if routes else None


async def calculate_landed_cost(
    db: AsyncSession,
    car: CarRecord,
    origin_country: str | None = None,
    mode: str = "roro",
) -> CostBreakdown:
    settings = get_settings()
    fees = await get_fee_map(db)
    rates = await get_rates()

    country = (origin_country or car.country or detect_country(car.source, car.location) or "US").upper()
    # Local cars: landed = asking price
    if country == "OM":
        price_omr = await to_omr(car.price, car.currency)
        items = [
            CostLineItem(key="car_price", label="Local asking price", amount_omr=price_omr, amount_original=car.price, currency_original=car.currency)
        ]
        return CostBreakdown(
            car=car,
            line_items=items,
            cif_omr=price_omr,
            total_landed_omr=price_omr,
            exchange_rates={k: rates[k] for k in ("USD", "OMR", "AED", "JPY") if k in rates},
            route=None,
            verdict="local",
            verdict_message="This is a local Oman listing — no import costs apply.",
        )

    route = await pick_route(db, country, mode)
    car_omr = await to_omr(car.price, car.currency)

    auction_usd = fees.get("auction_fee_usd").value if fees.get("auction_fee_usd") else 350.0
    auction_omr = await usd_to_omr(auction_usd)

    if route:
        shipping_usd = (route.min_usd + route.max_usd) / 2
        inland_usd = route.inland_usd
        route_info: dict[str, Any] = {
            "origin_country": route.origin_country,
            "origin_port": route.origin_port,
            "dest_port": route.dest_port,
            "mode": route.mode,
            "shipping_usd_mid": shipping_usd,
            "inland_usd": inland_usd,
            "transit_days": f"{route.transit_days_min}-{route.transit_days_max}",
        }
    else:
        shipping_usd = 1200.0
        inland_usd = 200.0
        route_info = {
            "origin_country": country,
            "origin_port": "Unknown",
            "dest_port": "Sohar",
            "mode": mode,
            "shipping_usd_mid": shipping_usd,
            "inland_usd": inland_usd,
            "transit_days": "25-40",
        }

    shipping_omr = await usd_to_omr(shipping_usd)
    inland_omr = await usd_to_omr(inland_usd)

    # CIF ≈ car + auction + inland + ocean (insurance separate below)
    cif_base_omr = car_omr + auction_omr + inland_omr + shipping_omr
    insurance_pct = fees.get("marine_insurance_pct").value if fees.get("marine_insurance_pct") else 1.5
    insurance_omr = round(cif_base_omr * (insurance_pct / 100.0), 3)
    cif_omr = round(cif_base_omr + insurance_omr, 3)

    duty = round(cif_omr * settings.customs_duty_rate, 3)
    vat = round((cif_omr + duty) * settings.vat_rate, 3)

    port = fees.get("port_handling_omr").value if fees.get("port_handling_omr") else 45.0
    clearing = fees.get("clearing_agent_omr").value if fees.get("clearing_agent_omr") else 75.0
    rop = fees.get("rop_registration_omr").value if fees.get("rop_registration_omr") else 55.0
    bayan = fees.get("bayan_fee_omr").value if fees.get("bayan_fee_omr") else 5.0

    items = [
        CostLineItem(key="car_price", label="Car price", amount_omr=car_omr, amount_original=car.price, currency_original=car.currency),
        CostLineItem(key="auction_fee", label="Auction / broker fee", amount_omr=auction_omr, amount_original=auction_usd, currency_original="USD"),
        CostLineItem(key="inland", label="Inland transport to export port", amount_omr=inland_omr, amount_original=inland_usd, currency_original="USD"),
        CostLineItem(key="ocean", label="Ocean shipping (RoRo mid estimate)", amount_omr=shipping_omr, amount_original=shipping_usd, currency_original="USD", notes=route_info.get("transit_days", "")),
        CostLineItem(key="insurance", label=f"Marine insurance ({insurance_pct}%)", amount_omr=insurance_omr),
        CostLineItem(key="customs_duty", label=f"Customs duty ({int(settings.customs_duty_rate*100)}% of CIF)", amount_omr=duty),
        CostLineItem(key="vat", label=f"VAT ({int(settings.vat_rate*100)}% of CIF+duty)", amount_omr=vat),
        CostLineItem(key="port", label="Port handling", amount_omr=port),
        CostLineItem(key="clearing", label="Clearing agent", amount_omr=clearing),
        CostLineItem(key="bayan", label="Bayan fee", amount_omr=bayan),
        CostLineItem(key="rop", label="ROP inspection & registration", amount_omr=rop),
    ]

    total = round(sum(i.amount_omr for i in items), 3)
    return CostBreakdown(
        car=car,
        line_items=items,
        cif_omr=cif_omr,
        total_landed_omr=total,
        exchange_rates={k: rates[k] for k in ("USD", "OMR", "AED", "JPY") if k in rates},
        route=route_info,
    )
