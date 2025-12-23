"""Scraper interface and Playwright-based implementation (skeleton).

Note: current working prototype lives in project root `scraper.py`.
This module provides a structured place for future refactor.
"""

from __future__ import annotations
from typing import Any, Callable


class ScrapeResult(dict[str, Any]):
    """Container for captured datasets keyed by endpoint name."""


import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.config import settings


class Scraper:
    """Abstract scraper protocol (simplified)."""

    async def run(self) -> ScrapeResult:  # pragma: no cover - interface only
        raise NotImplementedError


# Example hook signature for filtering responses
ResponsePredicate = Callable[[str, int, dict[str, str] | None], bool]


async def run_deepstate_scraper(
    *,
    headless: Optional[bool] = None,
    wait_after_load_ms: Optional[int] = None,
    output_dir: str = "data",
    url: str = "https://deepstatemap.live/",
    response_filter: Optional[ResponsePredicate] = None,
) -> Path:
    """Run a Playwright-based scraper that captures JSON API responses and saves them.

    Returns path to the saved file.
    """
    try:
        from playwright.async_api import async_playwright
    except Exception as e:  # pragma: no cover - optional at runtime
        raise RuntimeError("Playwright is required to run the scraper") from e

    headless = settings.HEADLESS if headless is None else headless
    wait_after_load_ms = (
        settings.WAIT_NETWORK_IDLE_MS if wait_after_load_ms is None else wait_after_load_ms
    )

    logging.getLogger(__name__).info("Starting scraper", extra={"url": url, "headless": headless})

    out_base = Path(output_dir) / datetime.now().strftime("%Y/%m")
    out_base.mkdir(parents=True, exist_ok=True)
    filename = f"deepstate_data_{datetime.now().strftime('%Y_%m_%d')}.json"
    out_path = out_base / filename

    captured: ScrapeResult = ScrapeResult()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=settings.USER_AGENT or None,
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        async def handle_response(response):
            try:
                url_l = response.url.lower()
                ctype = response.headers.get("content-type") if hasattr(response, "headers") else None
                if response.status != 200:
                    return
                if response_filter and not response_filter(response.url, response.status, response.headers):
                    return
                if ("api" in url_l or "json" in url_l) and ctype and "application/json" in ctype:
                    data = await response.json()
                    key = response.url.split("/")[-1].split("?")[0]
                    captured[key] = data
                    logging.getLogger(__name__).debug("Captured", extra={"key": key, "url": response.url})
            except Exception as e:
                logging.getLogger(__name__).warning("Response parse failed", extra={"error": str(e)})

        page.on("response", handle_response)

        await page.goto(url, timeout=settings.NAV_TIMEOUT_MS)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(wait_after_load_ms)

        out_path.write_text(json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")

        await context.close()
        await browser.close()

    logging.getLogger(__name__).info("Saved captured data", extra={"path": str(out_path)})
    return out_path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run_deepstate_scraper())


if __name__ == "__main__":  # pragma: no cover
    main()
