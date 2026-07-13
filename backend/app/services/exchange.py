"""Exchange rate helpers with in-memory cache and offline fallbacks."""

from datetime import datetime, timedelta, timezone

import httpx

from app.config import get_settings

_CACHE: dict[str, float] = {
    "USD": 1.0,
    "OMR": 0.3845,
    "AED": 3.6725,
    "JPY": 150.0,
    "EUR": 0.92,
    "GBP": 0.79,
}
_CACHE_AT: datetime | None = None
_CACHE_TTL = timedelta(hours=6)

OMR_PER_USD = 0.3845


async def get_rates() -> dict[str, float]:
    """Return rates as units of currency per 1 USD."""
    global _CACHE, _CACHE_AT
    now = datetime.now(timezone.utc)
    if _CACHE_AT and now - _CACHE_AT < _CACHE_TTL:
        return dict(_CACHE)

    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(settings.exchange_rate_api)
            resp.raise_for_status()
            data = resp.json()
            rates = data.get("rates") or {}
            if rates:
                _CACHE = {k: float(v) for k, v in rates.items()}
                _CACHE["USD"] = 1.0
                _CACHE_AT = now
    except Exception:
        pass
    return dict(_CACHE)


async def to_omr(amount: float, currency: str) -> float:
    rates = await get_rates()
    cur = (currency or "USD").upper()
    if cur == "OMR":
        return round(amount, 3)
    if cur not in rates or "OMR" not in rates:
        fallback = {"USD": 1.0, "AED": 3.6725, "JPY": 150.0, "EUR": 0.92, "GBP": 0.79}
        usd = amount / fallback.get(cur, 1.0)
        return round(usd * OMR_PER_USD, 3)
    usd = amount / rates[cur]
    omr = usd * rates["OMR"]
    return round(omr, 3)


async def usd_to_omr(amount_usd: float) -> float:
    return await to_omr(amount_usd, "USD")
