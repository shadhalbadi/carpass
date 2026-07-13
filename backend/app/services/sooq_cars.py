"""Sooq Cars (sooq-cars.com) — Oman ready-car listings via public API."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.schemas import CarRecord

logger = logging.getLogger(__name__)

API_BASE = "https://app.sooq-cars.com/api/v2"
SITE = "https://sooq-cars.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Origin": SITE,
    "Referer": f"{SITE}/om/en/ready/cars",
}


def _year_from(text: str) -> int | None:
    m = re.search(r"\b(19[8-9]\d|20[0-2]\d)\b", text or "")
    return int(m.group(1)) if m else None


async def _get_json(client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> Any:
    resp = await client.get(f"{API_BASE}{path}", params=params)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "success":
        raise RuntimeError(data.get("message") or f"Sooq Cars API error on {path}")
    return data.get("data")


async def _resolve_make_id(client: httpx.AsyncClient, make: str) -> int | None:
    rows = await _get_json(client, "/cars/makes", {"country": "om", "section": "ready"})
    want = (make or "").strip().lower()
    if not want or not isinstance(rows, list):
        return None
    for row in rows:
        name = (row.get("make_en") or row.get("name_en") or "").strip().lower()
        if name == want or want in name or name in want:
            return int(row["id"])
    return None


async def _resolve_model_id(client: httpx.AsyncClient, make_id: int, model: str) -> int | None:
    rows = await _get_json(
        client,
        "/cars/models",
        {"country": "om", "section": "ready", "make_id": make_id},
    )
    want = (model or "").strip().lower()
    if not want or not isinstance(rows, list):
        return None
    for row in rows:
        name = (row.get("model_en") or row.get("name_en") or "").strip().lower()
        if name == want or want in name or name in want:
            return int(row["id"])
    return None


def _record_from_item(item: dict, make: str, model: str) -> CarRecord:
    title = (item.get("title_en") or item.get("title_ar") or "").strip() or f"{make} {model}".strip()
    price_raw = item.get("price")
    try:
        price = float(price_raw) if price_raw not in (None, "", "null") else 0.0
    except (TypeError, ValueError):
        price = 0.0
    currency = (item.get("currency") or "OMR").upper()
    sid = str(item.get("id") or "")
    photo = item.get("main_image") or item.get("image") or ""
    return CarRecord(
        make=(make or "").title() or "Unknown",
        model=(model or "").title(),
        year=_year_from(title),
        price=price,
        currency=currency if price else "OMR",
        title=title[:500],
        source="sooq_cars",
        source_url=f"{SITE}/om/en/ready/cars/{sid}" if sid else f"{SITE}/om/en/ready/cars",
        source_id=sid,
        country="OM",
        location="Oman",
        photos=[photo] if photo else [],
    )


async def search_sooq_cars(
    make: str,
    model: str = "",
    *,
    max_items: int = 20,
    page: int = 1,
) -> list[CarRecord]:
    """Search Sooq Cars Oman ready listings for make/model."""
    make = (make or "").strip()
    model = (model or "").strip()
    if not make:
        return []

    params: dict[str, Any] = {"country": "om", "page": page}
    async with httpx.AsyncClient(headers=HEADERS, timeout=httpx.Timeout(45.0, connect=20.0)) as client:
        make_id = await _resolve_make_id(client, make)
        if make_id is None:
            logger.info("Sooq Cars: make not found for %r", make)
            return []
        params["make_id"] = f"[{make_id}]"

        if model:
            model_id = await _resolve_model_id(client, make_id, model)
            if model_id is None:
                logger.info("Sooq Cars: model not found for %r %r — searching make only", make, model)
            else:
                params["model_id"] = f"[{model_id}]"

        rows = await _get_json(client, "/ready-car/filters", params)

    if not isinstance(rows, list):
        return []

    cars: list[CarRecord] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        car = _record_from_item(item, make, model)
        # If model was requested but API returned make-only, keep title matches
        if model and model.lower() not in (car.title or "").lower() and model.lower() not in (car.model or "").lower():
            # API already filtered by model_id when resolved; skip only soft make-only misses
            if "model_id" in params:
                pass
            else:
                continue
        cars.append(car)
        if len(cars) >= max_items:
            break
    return cars
