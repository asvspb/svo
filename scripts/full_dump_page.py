"""Full page dump via Playwright.

Captures:
- final DOM (HTML after JS)
- screenshot
- HAR (embedded bodies)
- response bodies (JSON/GeoJSON + text; optional binaries)
- manifest with request/response metadata and saved file paths

Usage example:
    python scripts/full_dump_page.py \
      --url "https://deepstatemap.live/#6/48.6836777/34.7718844" \
      --headless false \
      --wait-after-load-ms 8000

Notes:
- Some sites may block headless browsers; try --headless false.
- If you need to capture specific endpoints, use ENDPOINT_WHITELIST/BLACKLIST in .env
  (see docs/configuration.md). This script is more general and captures broadly.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import request

ROOT = Path(__file__).resolve().parents[1]


def _ensure_project_root_on_syspath() -> None:
    """Ensure repo root is importable when running this file as a script."""

    root_str = str(ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def _get_settings():
    """Lazy-import settings after ensuring project root is on sys.path."""

    _ensure_project_root_on_syspath()
    from src.core.config import settings  # local import by design

    return settings


def _now_stamp() -> str:
    return datetime.now().strftime("%Y_%m_%d__%H%M%S")


def _safe_name(s: str, max_len: int = 120) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:max_len] if len(s) > max_len else s


DEFAULT_BASE_URL = "https://deepstatemap.live"
INDEX_RELATIVE_PATH = "history/index.json"


def _fetch_json(url: str, timeout: int = 60) -> Any:
    with request.urlopen(url, timeout=timeout) as resp:  # nosec - controlled URL
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset))


def _parse_select_date_to_ymd(select_date: str) -> str:
    """Convert 'DD.MM.YYYY' to 'YYYY_MM_DD'."""
    # Accept also 'DD.MM.YY'
    date_parts = select_date.split(".")
    if len(date_parts) == 3 and len(date_parts[-1]) == 4:
        dt = datetime.strptime(select_date, "%d.%m.%Y")
    else:
        dt = datetime.strptime(select_date, "%d.%m.%y")
    return dt.strftime("%Y_%m_%d")


def _extract_history_items(index_payload: Any) -> list[dict[str, Any]]:
    """Return normalized list of dict entries from history/index.json payload."""

    items: Any = index_payload
    if isinstance(index_payload, dict):
        items = next((v for v in index_payload.values() if isinstance(v, list)), [])
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _try_int(value: Any) -> int | None:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _ymd_from_unix_seconds(ts: int) -> str | None:
    try:
        dt = datetime.utcfromtimestamp(ts)
    except (ValueError, OSError):
        return None
    return dt.strftime("%Y_%m_%d")


def _find_history_id_for_date(index_payload: Any, ymd: str) -> int | None:
    """Find history id for given date (YYYY_MM_DD) from history/index.json payload."""

    items = _extract_history_items(index_payload)
    if not items:
        return None

    # Strategy:
    # 1) Prefer explicit 'date' field if present.
    for item in items:
        d = item.get("date")
        if isinstance(d, str) and d == ymd:
            return _try_int(item.get("id") or item.get("timestamp") or item.get("time"))

    # 2) Otherwise, infer date from timestamp/id if it looks like unix seconds.
    for item in items:
        ts_i = _try_int(item.get("timestamp") or item.get("time") or item.get("id"))
        if ts_i is None:
            continue
        if _ymd_from_unix_seconds(ts_i) == ymd:
            return _try_int(item.get("id")) or ts_i

    return None


def _guess_ext(content_type: str | None) -> str:
    if not content_type:
        return "bin"
    ct = content_type.lower().split(";")[0].strip()
    return {
        "application/json": "json",
        "application/geo+json": "geojson",
        "text/html": "html",
        "text/plain": "txt",
        "text/css": "css",
        "application/javascript": "js",
        "text/javascript": "js",
        "application/xml": "xml",
        "text/xml": "xml",
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/svg+xml": "svg",
        "application/octet-stream": "bin",
    }.get(ct, "bin")


def _is_text_like(content_type: str | None) -> bool:
    if not content_type:
        return False
    ct = content_type.lower()
    return any(
        k in ct
        for k in [
            "application/json",
            "application/geo+json",
            "text/",
            "application/javascript",
            "text/javascript",
            "application/xml",
        ]
    )


def _make_response_handler(
    *,
    paths: DumpPaths,
    manifest: list[dict[str, Any]],
    max_body_bytes: int,
    save_binaries: bool,
) -> tuple[Callable[[Any], Awaitable[None]], Callable[[], int]]:
    """Create a Playwright response handler.

    Returns (handler, get_saved_count).
    """

    resp_counter = 0

    async def handle_response(response: Any) -> None:
        nonlocal resp_counter
        try:
            req = response.request
            url_r = response.url
            status = response.status
            headers = dict(response.headers) if hasattr(response, "headers") else {}
            ctype = headers.get("content-type")

            entry: dict[str, Any] = {
                "url": url_r,
                "status": status,
                "content_type": ctype,
                "request": {
                    "method": req.method,
                    "resource_type": getattr(req, "resource_type", None),
                },
            }

            if status != 200:
                manifest.append(entry)
                return

            ext = _guess_ext(ctype)
            should_save_text = _is_text_like(ctype)

            if should_save_text:
                body_text = await response.text()
                body_len = len(body_text.encode("utf-8", errors="ignore"))
                entry["body_bytes"] = body_len
                if body_len <= max_body_bytes:
                    resp_counter += 1
                    fname = f"{resp_counter:05d}_{_safe_name(url_r)}.{ext}"
                    out = paths.responses_dir / fname
                    out.write_text(body_text, encoding="utf-8")
                    entry["saved_path"] = str(out.relative_to(paths.base_dir))
                else:
                    entry["skipped"] = f"body_too_large>{max_body_bytes}"
            else:
                if save_binaries:
                    body = await response.body()
                    entry["body_bytes"] = len(body)
                    if len(body) <= max_body_bytes:
                        resp_counter += 1
                        fname = f"{resp_counter:05d}_{_safe_name(url_r)}.{ext}"
                        out = paths.responses_dir / fname
                        out.write_bytes(body)
                        entry["saved_path"] = str(out.relative_to(paths.base_dir))
                    else:
                        entry["skipped"] = f"binary_too_large>{max_body_bytes}"
                else:
                    entry["skipped"] = "binary_not_saved"

            manifest.append(entry)
        except Exception as e:  # keep dump running
            url_val = getattr(response, "url", None)
            manifest.append({"url": url_val, "error": str(e)})

    def get_saved_count() -> int:
        return resp_counter

    return handle_response, get_saved_count


async def _select_date_in_ui(
    page: Any,
    *,
    select_date: str,
    calendar_button_text: str,
    date_text_timeout_ms: int,
) -> None:
    """Try selecting a date via calendar UI. Best-effort, no exceptions."""

    try:
        await page.get_by_text(calendar_button_text, exact=True).first.click(timeout=5000)
    except Exception:
        try:
            await page.locator(f"text={calendar_button_text}").first.click(timeout=5000)
        except Exception:
            return

    await page.wait_for_timeout(700)

    try:
        await page.get_by_text(select_date, exact=True).first.click(timeout=date_text_timeout_ms)
    except Exception:
        calendar_selectors = ".mat-calendar, .calendar, .datepicker, .cdk-overlay-container"
        try:
            await page.locator(calendar_selectors).get_by_text(
                select_date,
                exact=True,
            ).first.click(timeout=date_text_timeout_ms)
        except Exception:
            return


def _fetch_history_payload_for_date(
    *,
    paths: DumpPaths,
    ymd: str,
    base_url: str,
    extra_downloads: list[dict[str, Any]],
) -> None:
    """Download history/index.json and /api/history/{id} for a given YMD, best-effort."""

    index_url = base_url.rstrip("/") + "/" + INDEX_RELATIVE_PATH
    idx = _fetch_json(index_url)

    idx_path = paths.responses_dir / f"extra_history_index_{ymd}.json"
    idx_content = json.dumps(idx, ensure_ascii=False, indent=2)
    idx_path.write_text(idx_content, encoding="utf-8")
    extra_downloads.append(
        {
            "kind": "history_index",
            "url": index_url,
            "saved_path": str(idx_path.relative_to(paths.base_dir)),
        }
    )

    hist_id = _find_history_id_for_date(idx, ymd)
    if hist_id is None:
        return

    hist_url = base_url.rstrip("/") + f"/api/history/{hist_id}"
    hist = _fetch_json(hist_url, timeout=120)

    hist_filename = f"extra_api_history_{hist_id}_{ymd}.json"
    hist_path = paths.responses_dir / hist_filename
    hist_content = json.dumps(hist, ensure_ascii=False, indent=2)
    hist_path.write_text(hist_content, encoding="utf-8")

    extra_downloads.append(
        {
            "kind": "api_history",
            "history_id": hist_id,
            "ymd": ymd,
            "url": hist_url,
            "saved_path": str(hist_path.relative_to(paths.base_dir)),
        }
    )


async def _save_step_screenshot(page: Any, out_dir: Path, name: str) -> None:
    try:
        screenshot_path = str(out_dir / f"step_{_safe_name(name, max_len=80)}.png")
        await page.screenshot(path=screenshot_path, full_page=True)
    except Exception:
        return


async def _stimulate_page_activity(
    page: Any,
    *,
    zoom_steps: int,
    pan_steps: int,
    pan_px: int,
    settle_ms: int,
) -> None:
    """Try to provoke additional network activity.

    Many map apps lazily load layers/tiles after user interaction.
    This function performs a few zooms and pans to trigger extra requests.
    """

    if zoom_steps <= 0 and pan_steps <= 0:
        return

    # Ensure the page is focused.
    try:
        await page.bring_to_front()
    except Exception:
        pass  # noqa

    # Center point for interactions.
    viewport = page.viewport_size or {"width": 1280, "height": 800}
    cx = int(viewport.get("width", 1280) / 2)
    cy = int(viewport.get("height", 800) / 2)

    # Zoom in/out a bit.
    for _ in range(max(0, zoom_steps)):
        try:
            await page.mouse.wheel(0, -800)
        except Exception:
            break  # noqa
        await page.wait_for_timeout(settle_ms)

    for _ in range(max(0, zoom_steps)):
        try:
            await page.mouse.wheel(0, 800)
        except Exception:
            break # noqa
        await page.wait_for_timeout(settle_ms)

    # Pan around in a simple square pattern.
    directions = [(pan_px, 0), (0, pan_px), (-pan_px, 0), (0, -pan_px)]
    try:
        await page.mouse.move(cx, cy)
    except Exception:
        return  # noqa

    for i in range(max(0, pan_steps)):
        dx, dy = directions[i % len(directions)]
        try:
            await page.mouse.down()
            await page.mouse.move(cx + dx, cy + dy, steps=20)
            await page.mouse.up()
        except Exception:
            break # noqa
        await page.wait_for_timeout(settle_ms)


@dataclass
class DumpPaths:
    base_dir: Path
    responses_dir: Path
    html_path: Path
    screenshot_path: Path
    har_path: Path
    manifest_path: Path


def _build_output_paths(
    output_root: str,
    url: str,
    date: str | None = None,
    *,
    prefix: str = "full_dump",
) -> DumpPaths:
    root = Path(output_root)
    if date:
        # Parse date from DD.MM.YYYY or DD.MM.YY format to YYYY/MM
        try:
            if len(date) == 10:
                parsed_date = datetime.strptime(date, "%d.%m.%Y")
            else:
                parsed_date = datetime.strptime(date, "%d.%m.%y")
            y_m = parsed_date.strftime("%Y/%m")
            date_part = parsed_date.strftime("%Y_%m_%d")
        except ValueError:
            # If date parsing fails, fall back to current date
            y_m = datetime.now().strftime("%Y/%m")
            date_part = _now_stamp()
    else:
        y_m = datetime.now().strftime("%Y/%m")
        date_part = _now_stamp()
    
    base = root / y_m / f"{prefix}_{_safe_name(url)}_{date_part}"
    responses = base / "responses"
    base.mkdir(parents=True, exist_ok=True)
    responses.mkdir(parents=True, exist_ok=True)
    return DumpPaths(
        base_dir=base,
        responses_dir=responses,
        html_path=base / "page.html",
        screenshot_path=base / "screenshot.png",
        har_path=base / "network.har",
        manifest_path=base / "manifest.json",
    )


async def _finalize_dump(
    *,
    page: Any,
    paths: DumpPaths,
    url: str,
    headless: bool,
    wait_after_load_ms: int,
    max_body_bytes: int,
    save_binaries: bool,
    extra_downloads: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
    responses_saved: int,
) -> None:
    # Save final DOM
    html = await page.content()
    paths.html_path.write_text(html, encoding="utf-8")

    # Screenshot
    await page.screenshot(path=str(paths.screenshot_path), full_page=True)

    # Store manifest
    manifest_data = {
        "url": url,
        "captured_at": datetime.now().isoformat(),
        "headless": headless,
        "wait_after_load_ms": wait_after_load_ms,
        "max_body_bytes": max_body_bytes,
        "save_binaries": save_binaries,
        "responses_saved": responses_saved,
        "extra_downloads": extra_downloads,
        "entries": manifest,
    }
    manifest_content = json.dumps(manifest_data, ensure_ascii=False, indent=2)
    paths.manifest_path.write_text(manifest_content, encoding="utf-8")


async def _setup_browser_and_context(
    p: Any,
    settings: Any,
    paths: DumpPaths,
    headless: bool,
    max_body_bytes: int,
    save_binaries: bool,
) -> tuple[Any, Any, list[dict[str, Any]], Callable[[], int]]:
    """Set up browser, context, page, and response handler."""
    browser = await p.chromium.launch(headless=headless)

    # HAR with embedded bodies so the dump is self-contained.
    context = await browser.new_context(
        user_agent=settings.USER_AGENT or None,
        viewport={"width": 1280, "height": 800},
        record_har_path=str(paths.har_path),
        record_har_content="embed",
    )

    page = await context.new_page()

    manifest: list[dict[str, Any]] = []
    handler, get_saved_count = _make_response_handler(
        paths=paths,
        manifest=manifest,
        max_body_bytes=max_body_bytes,
        save_binaries=save_binaries,
    )
    page.on("response", handler)

    return browser, context, manifest, get_saved_count


async def _handle_date_selection(
    page: Any,
    select_date: str | None,
    calendar_button_text: str,
    date_text_timeout_ms: int,
    steps_screenshots: bool,
    paths: DumpPaths,
    fetch_history_for_selected_date: bool | None,
    base_url: str,
    extra_downloads: list[dict[str, Any]],
) -> None:
    """Handle date selection and related operations."""
    if not select_date:
        return

    if fetch_history_for_selected_date is None:
        fetch_history_for_selected_date = True

    if steps_screenshots:
        await _save_step_screenshot(page, paths.base_dir, "before_calendar")

    await _select_date_in_ui(
        page,
        select_date=select_date,
        calendar_button_text=calendar_button_text,
        date_text_timeout_ms=date_text_timeout_ms,
    )

    if steps_screenshots:
        await _save_step_screenshot(page, paths.base_dir, "calendar_open")

    # wait for any data to load after date selection
    try:
        await page.wait_for_load_state("networkidle", timeout=60000)
    except Exception:
        pass  # noqa
    await page.wait_for_timeout(1500)
    if steps_screenshots:
        await _save_step_screenshot(page, paths.base_dir, "after_date_select")

    if fetch_history_for_selected_date:
        try:
            ymd = _parse_select_date_to_ymd(select_date)
            try:
                await asyncio.to_thread(
                    _fetch_history_payload_for_date,
                    paths=paths,
                    ymd=ymd,
                    base_url=base_url,
                    extra_downloads=extra_downloads,
                )
            except Exception:
                # If index.json doesn't exist or the API is unavailable,
                # it might still be captured by the response handler.
                pass
        except Exception as e:
            extra_downloads.append(
                {
                    "kind": "error",
                    "where": "fetch_history_for_selected_date",
                    "error": str(e),
                }
            )


async def _perform_page_interactions(
    page: Any,
    interact: bool,
    zoom_steps: int,
    pan_steps: int,
    pan_px: int,
    settle_ms: int,
) -> None:
    """Perform page interactions to trigger additional network activity."""
    if interact:
        await _stimulate_page_activity(
            page,
            zoom_steps=int(zoom_steps),
            pan_steps=int(pan_steps),
            pan_px=int(pan_px),
            settle_ms=int(settle_ms),
        )


async def run_full_dump(
    *,
    url: str,
    output_root: str,
    headless: bool | None = None,
    nav_timeout_ms: int | None = None,
    wait_after_load_ms: int = 8000,
    max_body_bytes: int = 10_000_000,
    save_binaries: bool = False,
    interact: bool = False,
    zoom_steps: int = 2,
    pan_steps: int = 8,
    pan_px: int = 250,
    settle_ms: int = 1200,
    select_date: str | None = None,
    calendar_button_text: str = "calendar_month",
    date_text_timeout_ms: int = 15000,
    steps_screenshots: bool = True,
    fetch_history_for_selected_date: bool | None = None,
    base_url: str = DEFAULT_BASE_URL,
) -> DumpPaths:
    """Run the full page dump and return paths to the dump directory and files."""

    try:
        from playwright.async_api import async_playwright
    except Exception as e:  # pragma: no cover
        msg = "Playwright is required. Install deps and run 'playwright install'."
        raise RuntimeError(msg) from e

    settings = _get_settings()

    headless = settings.HEADLESS if headless is None else headless
    nav_timeout_ms = settings.NAV_TIMEOUT_MS if nav_timeout_ms is None else nav_timeout_ms

    paths = _build_output_paths(output_root, url, date=select_date)

    extra_downloads: list[dict[str, Any]] = []

    async with async_playwright() as p:
        browser, context, manifest, get_saved_count = await _setup_browser_and_context(
            p,
            settings,
            paths,
            headless,
            max_body_bytes,
            save_binaries,
        )

        page = context.pages[0] # Get the page that was created

        # Navigate and wait for initial load
        await page.goto(url, timeout=nav_timeout_ms)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(wait_after_load_ms)

        # Handle date selection if needed
        await _handle_date_selection(
            page,
            select_date,
            calendar_button_text,
            date_text_timeout_ms,
            steps_screenshots,
            paths,
            fetch_history_for_selected_date,
            base_url,
            extra_downloads,
        )

        # Perform interactions if needed
        await _perform_page_interactions(
            page,
            interact,
            zoom_steps,
            pan_steps,
            pan_px,
            settle_ms,
        )

        # Finalize the dump with all collected data
        await _finalize_dump(
            page=page,
            paths=paths,
            url=url,
            headless=headless,
            wait_after_load_ms=wait_after_load_ms,
            max_body_bytes=max_body_bytes,
            save_binaries=save_binaries,
            extra_downloads=extra_downloads,
            manifest=manifest,
            responses_saved=get_saved_count(),
        )

        await context.close()
        await browser.close()

    return paths


def _parse_bool(v: str) -> bool:
    if v.lower() in {"1", "true", "yes", "y", "on"}:
        return True
    if v.lower() in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid bool: {v}")


def main() -> None:
    settings = _get_settings()

    ap = argparse.ArgumentParser(description="Full dump of a page via Playwright")
    ap.add_argument(
        "--url",
        required=True,
        help="Target URL (include hash/zoom/lat/lon as needed)",
    )
    ap.add_argument(
        "--output-root",
        default=settings.DATA_ROOT,
        help="Where to store dump folders (default: settings.DATA_ROOT)",
    )
    ap.add_argument(
        "--headless",
        type=_parse_bool,
        default=None,
        help="Override headless mode (true/false). Default: settings.HEADLESS",
    )
    ap.add_argument(
        "--nav-timeout-ms",
        type=int,
        default=None,
        help="Navigation timeout in ms. Default: settings.NAV_TIMEOUT_MS",
    )
    ap.add_argument(
        "--wait-after-load-ms",
        type=int,
        default=8000,
        help="Extra wait after networkidle to let the app load layers.",
    )
    ap.add_argument(
        "--max-body-bytes",
        type=int,
        default=10_000_000,
        help="Max bytes per saved response body (default 10MB).",
    )
    ap.add_argument(
        "--save-binaries",
        type=_parse_bool,
        default=False,
        help="Save binary responses too (images, wasm, etc.).",
    )
    ap.add_argument(
        "--select-date",
        default=None,
        help="Select date via in-page calendar (visible text, e.g. '23.12.2025').",
    )
    ap.add_argument(
        "--fetch-history-for-selected-date",
        type=_parse_bool,
        default=None,
        help=(
            "If --select-date is set, also download history/index.json and "
            "/api/history/{id} for that date (default: true)."
        ),
    )
    ap.add_argument(
        "--calendar-button-text",
        default="calendar_month",
        help="Text/icon of the calendar button to click (default: calendar_month).",
    )
    ap.add_argument(
        "--date-text-timeout-ms",
        type=int,
        default=15000,
        help="Timeout for finding date text in calendar UI.",
    )
    ap.add_argument(
        "--steps-screenshots",
        type=_parse_bool,
        default=True,
        help="Save step screenshots (before/after opening calendar and selecting date).",
    )
    ap.add_argument(
        "--interact",
        type=_parse_bool,
        default=False,
        help="Perform simple zoom/pan interactions to trigger lazy-loaded tiles/layers.",
    )
    ap.add_argument(
        "--zoom-steps",
        type=int,
        default=2,
        help="How many zoom-in steps to perform (and the same amount zoom-out).",
    )
    ap.add_argument(
        "--pan-steps",
        type=int,
        default=8,
        help="How many pan drags to perform.",
    )
    ap.add_argument(
        "--pan-px",
        type=int,
        default=250,
        help="Pan distance in pixels per drag.",
    )
    ap.add_argument(
        "--settle-ms",
        type=int,
        default=1200,
        help="Wait after each interaction (ms).",
    )
    ap.add_argument(
        "--max",
        dest="max_mode",
        action="store_true",
        help=(
            "Maximal dump mode: enables --save-binaries and --interact "
            "and increases limits/timeouts."
        ),
    )

    args = ap.parse_args()

    # Max mode overrides (unless user explicitly provided non-default values).
    if getattr(args, "max_mode", False):
        # Always enable these in max mode.
        args.save_binaries = True
        args.interact = True
        # Increase defaults if left untouched.
        if args.wait_after_load_ms == 8000:
            args.wait_after_load_ms = 60000
        if args.max_body_bytes == 10_000_000:
            args.max_body_bytes = 200_000_000
        if args.nav_timeout_ms is None:
            args.nav_timeout_ms = max(settings.NAV_TIMEOUT_MS, 120000)

    paths = asyncio.run(
        run_full_dump(
            url=args.url,
            output_root=args.output_root,
            headless=args.headless,
            nav_timeout_ms=args.nav_timeout_ms,
            wait_after_load_ms=args.wait_after_load_ms,
            max_body_bytes=args.max_body_bytes,
            save_binaries=args.save_binaries,
            interact=args.interact,
            zoom_steps=args.zoom_steps,
            pan_steps=args.pan_steps,
            pan_px=args.pan_px,
            settle_ms=args.settle_ms,
            select_date=args.select_date,
            calendar_button_text=args.calendar_button_text,
            date_text_timeout_ms=args.date_text_timeout_ms,
            steps_screenshots=args.steps_screenshots,
            fetch_history_for_selected_date=args.fetch_history_for_selected_date,
        )
    )

    print(str(paths.base_dir))


if __name__ == "__main__":  # pragma: no cover
    main()
