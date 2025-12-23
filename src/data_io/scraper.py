"""Scraper interface and Playwright-based implementation (skeleton).

Note: current working prototype lives in project root `scraper.py`.
This module provides a structured place for future refactor.
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

import asyncio
import json
import logging
import re

from src.core.config import settings


class ScrapeResult(dict[str, Any]):
    """Container for captured datasets keyed by endpoint name."""


class Scraper:
    """Abstract scraper protocol (simplified)."""

    async def run(self) -> ScrapeResult:  # pragma: no cover - interface only
        raise NotImplementedError


# Example hook signature for filtering responses
ResponsePredicate = Callable[[str, int, dict[str, str] | None], bool]

# Whitelist helpers

def parse_whitelist(raw: str | None) -> list[re.Pattern[str]]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    patterns: list[re.Pattern[str]] = []
    for p in parts:
        try:
            patterns.append(re.compile(p, re.IGNORECASE))
        except re.error:
            # treat as literal substring by escaping
            patterns.append(re.compile(re.escape(p), re.IGNORECASE))
    return patterns


def url_allowed(url: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    if not patterns:
        return True
    return any(pt.search(url) for pt in patterns)


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
    manifest: list[dict[str, object]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=settings.USER_AGENT or None,
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        # Build combined allow predicate using whitelist and optional external filter
        wl_patterns = parse_whitelist(settings.ENDPOINT_WHITELIST)

        def allow(u: str, s: int, h: dict[str, str] | None) -> bool:
            if response_filter and not response_filter(u, s, h):
                return False
            return url_allowed(u, wl_patterns)

        async def handle_response(response):
            try:
                url = response.url
                url_l = url.lower()
                ctype = response.headers.get("content-type") if hasattr(response, "headers") else None
                status = response.status
                allowed = allow(url, status, response.headers)
                is_json_like = ("api" in url_l or "json" in url_l) and ctype and "application/json" in ctype

                # record manifest entry
                manifest.append({
                    "url": url,
                    "status": status,
                    "content_type": ctype,
                    "allowed": allowed,
                    "json_like": bool(is_json_like),
                })

                if status != 200:
                    return
                if not allowed:
                    return
                if is_json_like:
                    data = await response.json()
                    key = url.split("/")[-1].split("?")[0]
                    captured[key] = data
                    logging.getLogger(__name__).debug("Captured", extra={"key": key, "url": url})
            except Exception as e:
                logging.getLogger(__name__).warning("Response parse failed", extra={"error": str(e)})

        page.on("response", handle_response)

        await page.goto(url, timeout=settings.NAV_TIMEOUT_MS)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(wait_after_load_ms)

        # Save combined capture
        out_path.write_text(json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")

        # Save manifest with URLs and metadata to help tune whitelist
        manifest_path = out_base / f"capture_manifest_{datetime.now().strftime('%Y_%m_%d')}.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        # Additionally, try to save per-layer GeoJSON files if detected
        def classify_layer(url: str, data: dict) -> str:
            url_l = url.lower()
            name = "unknown"
            # URL-based heuristics
            if any(k in url_l for k in ["frontline", "/front", "/line", "front_line"]):
                name = "frontline"
            elif any(k in url_l for k in ["gray", "grey", "contested", "sgray", "greyzone"]):
                name = "gray"
            elif any(k in url_l for k in ["occup", "occupied", "control", "ru", "russia_control"]):
                name = "occupied"
            # Data-based hints
            try:
                dtype = str(data.get("type", "")).lower()
                if dtype in {"featurecollection", "geometrycollection", "feature"}:
                    # look into properties of first feature if present
                    feats = data.get("features") or []
                    if feats and isinstance(feats, list):
                        props = feats[0].get("properties") if isinstance(feats[0], dict) else None
                        if isinstance(props, dict):
                            ptxt = json.dumps(props).lower()
                            if any(k in ptxt for k in ["frontline", "front_line"]):
                                name = "frontline"
                            elif any(k in ptxt for k in ["gray", "grey", "contested"]):
                                name = "gray"
                            elif any(k in ptxt for k in ["occupied", "control", "ru", "russian"]):
                                name = "occupied"
            except Exception:
                pass
            return name

        saved_layers: set[str] = set()
        for key, data in captured.items():
            if isinstance(data, dict) and data.get("type"):
                try:
                    std_name = classify_layer(key, data)
                    # ensure unique filenames if multiple from same class
                    stamp = datetime.now().strftime('%Y_%m_%d')
                    base_name = std_name if std_name != "unknown" else (key or "layer")
                    # de-duplicate
                    suffix = ""
                    idx = 1
                    while True:
                        fname = f"layer_{base_name}{suffix}_{stamp}.geojson"
                        if fname not in saved_layers:
                            saved_layers.add(fname)
                            break
                        idx += 1
                        suffix = f"_{idx}"
                    layer_file = out_base / fname
                    Path(layer_file).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception as e:
                    logging.getLogger(__name__).warning("Layer save failed", extra={"key": key, "error": str(e)})

        await context.close()
        await browser.close()

    logging.getLogger(__name__).info("Saved captured data", extra={"path": str(out_path)})
    return out_path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run_deepstate_scraper())


if __name__ == "__main__":  # pragma: no cover
    main()
