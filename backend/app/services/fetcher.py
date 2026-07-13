"""Fetch listing pages via httpx / Playwright, with Jina reader fallback for bot walls."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}

# Hosts that usually need a real browser (still often blocked → Jina fallback)
PLAYWRIGHT_FIRST_HOSTS = (
    "dubizzle.com",
    "copart.com",
    "iaai.com",
)

# Bot walls where a markdown reader proxy recovers listing links/text
JINA_FALLBACK_HOSTS = (
    "dubizzle.com",
    "copart.com",
)


class FetchError(Exception):
    pass


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _needs_playwright_first(url: str) -> bool:
    host = _host(url)
    return any(host.endswith(h) for h in PLAYWRIGHT_FIRST_HOSTS)


def _needs_jina_fallback(url: str) -> bool:
    host = _host(url)
    return any(host.endswith(h) for h in JINA_FALLBACK_HOSTS)


def _has_useful_listing_signals(html: str) -> bool:
    lowered = (html or "").lower()
    return any(
        sig in lowered
        for sig in (
            "/id/",
            "vehicledetail",
            "/lot/",
            "__next_data__",
            "serpapiresponse",
            "/motors/used-cars/",
            "stocklist-row",
            "current bid",
            "markdown content",
        )
    )


def _looks_blocked_or_empty(html: str) -> bool:
    if not html:
        return True
    lowered = html.lower()
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    # Jina / markdown payloads may have sparse tags but rich listing text
    if _has_useful_listing_signals(html) and (len(text) > 400 or len(html) > 4000):
        if "pardon our interruption" in lowered and "/motors/used-cars/" not in lowered and "/lot/" not in lowered:
            return True
        return False
    if len(text) < 250:
        return True
    strong = (
        "request unsuccessful",
        "cf-browser-verification",
        "attention required",
        "pardon our interruption",
        "verify you are human",
        "robot or human",
        "access denied",
    )
    if any(s in lowered for s in strong):
        return True
    if "just a moment" in lowered and len(text) < 2000:
        return True
    return False


async def fetch_url(url: str) -> str:
    settings = get_settings()
    proxy = settings.scraping_proxy_url or None
    errors: list[str] = []

    order: list[str] = (
        ["playwright", "httpx"] if _needs_playwright_first(url) else ["httpx", "playwright"]
    )
    if _needs_jina_fallback(url):
        order.append("jina")

    for method in order:
        try:
            if method == "httpx":
                html = await _http_fetch(url, proxy)
            elif method == "playwright":
                html = await _playwright_fetch(url, proxy)
            else:
                html = await _jina_fetch(url)
            if _looks_blocked_or_empty(html):
                errors.append(f"{method}: blocked/empty page")
                continue
            return html
        except Exception as exc:
            logger.warning("%s fetch failed for %s: %s", method, url, exc)
            errors.append(f"{method}: {exc}")

    raise FetchError("; ".join(errors) if errors else "Could not fetch URL")


async def _http_fetch(url: str, proxy: str | None) -> str:
    kwargs: dict = {
        "headers": DEFAULT_HEADERS,
        "follow_redirects": True,
        "timeout": httpx.Timeout(45.0, connect=20.0),
    }
    if proxy:
        kwargs["proxy"] = proxy
    async with httpx.AsyncClient(**kwargs) as client:
        resp = await client.get(url)
        if resp.status_code >= 500:
            resp.raise_for_status()
        return resp.text


async def _jina_fetch(url: str) -> str:
    """Fetch via r.jina.ai markdown reader — bypasses many Imperva/Akamai HTML walls."""
    target = url.strip()
    if not target.startswith("http"):
        target = "https://" + target
    # https:// scheme is required; http:// often returns only the interstitial
    jina_url = f"https://r.jina.ai/{target}"
    headers = {
        **DEFAULT_HEADERS,
        "Accept": "text/plain, text/markdown, text/html, */*",
        "X-Return-Format": "markdown",
    }
    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        timeout=httpx.Timeout(90.0, connect=20.0),
    ) as client:
        resp = await client.get(jina_url)
        resp.raise_for_status()
        text = resp.text or ""
        if "pardon our interruption" in text.lower() and "/lot/" not in text.lower():
            raise FetchError("jina returned bot interstitial")
        return text


async def _playwright_fetch(url: str, proxy: str | None) -> str:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise FetchError("playwright not installed") from exc

    launch_kwargs: dict = {
        "headless": True,
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    context_kwargs: dict = {
        "user_agent": DEFAULT_HEADERS["User-Agent"],
        "locale": "en-US",
        "viewport": {"width": 1365, "height": 900},
    }
    if proxy:
        context_kwargs["proxy"] = {"server": proxy}

    async with async_playwright() as p:
        browser = None
        # Prefer installed Google Chrome when available (better anti-bot), else bundled Chromium
        for channel in ("chrome", None):
            try:
                kwargs = dict(launch_kwargs)
                if channel:
                    kwargs["channel"] = channel
                browser = await p.chromium.launch(**kwargs)
                break
            except Exception as exc:
                logger.info("Playwright launch channel=%s failed: %s", channel, exc)
                browser = None
        if browser is None:
            raise FetchError("could not launch chromium/chrome")

        context = await browser.new_context(**context_kwargs)
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = await context.new_page()
        await page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            await page.wait_for_timeout(2500)
        except Exception:
            pass
        for selector in (
            "a[href*='/id/']",
            "a[href*='VehicleDetail']",
            "a[href*='/lot/']",
            "a[href*='/motors/']",
            "script#__NEXT_DATA__",
        ):
            try:
                await page.wait_for_selector(selector, timeout=4000)
                break
            except Exception:
                continue
        html = await page.content()
        await browser.close()
        return html


# Demo HTML fixtures for offline / blocked environments
DEMO_FIXTURES: dict[str, str] = {
    "copart": """
    <html><head><title>2019 Toyota Camry SE - Lot 51234891 - Copart</title></head>
    <body>
    <h1>2019 Toyota Camry SE</h1>
    <div>Location: Houston, TX</div>
    <div>Odometer: 48,230 mi Actual</div>
    <div>VIN: 4T1B11HK5KU123456</div>
    <div>Primary Damage: Front End</div>
    <div>Current Bid: USD 9,250</div>
    </body></html>
    """,
    "beforward": """
    <html><head><title>2018 Toyota Land Cruiser Prado TX - BE FORWARD</title></head>
    <body>
    <h1>2018 Toyota Land Cruiser Prado TX</h1>
    <div>Price: USD 18,890</div>
    <div>Mileage: 75,400 km</div>
    <div>Location: Yokohama, Japan</div>
    </body></html>
    """,
    "opensooq": """
    <html><head><title>Toyota Camry 2020 - OpenSooq</title></head>
    <body>
    <h1>Toyota Camry 2020</h1>
    <div>Price: 7,900 OMR</div>
    <div>Mileage: 62000 km</div>
    <div>Location: Muscat, Oman</div>
    </body></html>
    """,
}


async def fetch_url_or_demo(url: str) -> tuple[str, bool]:
    """Returns (html, used_demo). Falls back to demo fixture when live fetch fails or is blocked."""
    from app.services.normalize import detect_source

    source = detect_source(url)
    fixture = DEMO_FIXTURES.get(source) or DEMO_FIXTURES.get("copart")

    try:
        html = await fetch_url(url)
        if _looks_blocked_or_empty(html):
            logger.info("Treating fetch as blocked/empty for %s — using demo fixture", url)
            return fixture, True
        return html, False
    except Exception as exc:
        logger.warning("Fetch failed for %s (%s) — using demo fixture", url, exc)
        return fixture, True
