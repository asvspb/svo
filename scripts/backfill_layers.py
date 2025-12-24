#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

# Ensure project root is on sys.path when running as a script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_io.history_fetcher import DEFAULT_BASE_URL, fetch_history_layer
from src.data_io.history_index import DEFAULT_BASE_URL as DEFAULT_INDEX_BASE_URL
from src.data_io.history_index import load_index, refresh_index
from src.db import dao
from src.db.base import Base, get_engine


def _parse_date(s: str) -> date:
    # accept YYYY_MM_DD (project standard) or ISO YYYY-MM-DD
    try:
        if "_" in s:
            return datetime.strptime(s, "%Y_%m_%d").date()
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date: {s}") from e


def _date_to_key(d: date) -> str:
    return d.strftime("%Y_%m_%d")


def _parse_classes(raw: str) -> tuple[str, ...]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise argparse.ArgumentTypeError("classes list is empty")
    allowed = {"occupied", "gray", "frontline"}
    bad = [p for p in parts if p not in allowed]
    if bad:
        raise argparse.ArgumentTypeError(f"Unsupported classes: {bad}. Allowed: {sorted(allowed)}")
    return tuple(parts)


def _iter_days(d1: date, d2: date) -> Iterable[date]:
    if d2 < d1:
        d1, d2 = d2, d1
    cur = d1
    while cur <= d2:
        yield cur
        cur = cur.fromordinal(cur.toordinal() + 1)


def _extract_layers(payload: dict, clazzes: tuple[str, ...]) -> dict[str, dict]:
    """Extract per-class GeoJSON dicts from history payload.

    We support two shapes:
    - payload is a GeoJSON FeatureCollection (single layer) => will map to key 'occupied' ONLY if requested
      and no per-class keys exist.
    - payload is a dict with keys like 'occupied'/'gray'/'frontline' each containing GeoJSON.
    """
    # Shape 1: already a GeoJSON object
    if isinstance(payload, dict) and payload.get("type") in {"FeatureCollection", "Feature", "GeometryCollection"}:
        # Ambiguous: assign to first requested class only.
        # This keeps behavior deterministic, and caller can restrict classes accordingly.
        first = clazzes[0]
        return {first: payload}

    out: dict[str, dict] = {}
    for c in clazzes:
        v = payload.get(c) if isinstance(payload, dict) else None
        if isinstance(v, dict) and v.get("type") in {"FeatureCollection", "Feature", "GeometryCollection"}:
            out[c] = v
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Backfill DeepStateMap history layers into DB (layers table)")

    ap.add_argument("--from", dest="date_from", type=_parse_date, help="Start date (YYYY_MM_DD or YYYY-MM-DD)")
    ap.add_argument("--to", dest="date_to", type=_parse_date, help="End date (YYYY_MM_DD or YYYY-MM-DD)")
    ap.add_argument("--days", type=int, help="Alternative to --from/--to: last N days (inclusive)")

    ap.add_argument(
        "--classes",
        type=_parse_classes,
        default=("occupied", "gray", "frontline"),
        help="Comma-separated list: occupied,gray,frontline",
    )

    ap.add_argument("--data-root", default=os.getenv("DATA_ROOT", "data"), help="Local data root")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL, help="DeepState base URL")
    ap.add_argument(
        "--history-endpoint",
        default=None,
        help="Override history index endpoint (default: {base}/api/history)",
    )

    ap.add_argument("--no-refresh-index", action="store_true", help="Do not refresh history index")
    ap.add_argument("--create-tables", action="store_true", help="Create DB tables (Base.metadata.create_all)")

    ap.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip download+write when layer(date,class) already exists in DB",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing to DB",
    )

    args = ap.parse_args(argv)

    if args.days is not None and (args.date_from or args.date_to):
        ap.error("Use either --days or --from/--to")

    if args.days is not None:
        if args.days <= 0:
            ap.error("--days must be positive")
        today = datetime.utcnow().date()
        d1 = today.fromordinal(today.toordinal() - (args.days - 1))
        d2 = today
    else:
        if not args.date_from or not args.date_to:
            ap.error("Either provide --days or both --from and --to")
        d1, d2 = args.date_from, args.date_to

    # DB init
    if args.create_tables and not args.dry_run:
        engine = get_engine()
        Base.metadata.create_all(engine)

    # Refresh/load index
    if not args.no_refresh_index:
        refresh_index(base_url=args.base_url or DEFAULT_INDEX_BASE_URL, endpoint=args.history_endpoint, data_root=args.data_root)

    entries = load_index(data_root=args.data_root)
    by_date: dict[str, int] = {}
    # choose the latest entry per day
    for e in entries:
        dkey = e.date
        # our index is sorted asc by timestamp, so overwrite gives latest
        by_date[dkey] = e.id

    wanted_dates = [_date_to_key(d) for d in _iter_days(d1, d2)]

    total_written = 0
    total_skipped = 0
    total_missing = 0

    for dkey in wanted_dates:
        hid = by_date.get(dkey)
        if hid is None:
            total_missing += 1
            print(f"[missing] {dkey}: no history id in index")
            continue

        # fast skip: all requested classes exist
        if args.skip_existing:
            all_exist = True
            for c in args.classes:
                if not dao.layer_exists(clazz=c, d=_parse_date(dkey)):
                    all_exist = False
                    break
            if all_exist:
                total_skipped += 1
                print(f"[skip] {dkey}: all classes already in DB")
                continue

        payload = fetch_history_layer(hid, base_url=args.base_url)
        layers = _extract_layers(payload, args.classes)
        if not layers:
            total_missing += 1
            print(f"[missing] {dkey}: no layers found in payload (id={hid})")
            continue

        for clazz, layer_geo in layers.items():
            dd = _parse_date(dkey)
            if args.skip_existing and dao.layer_exists(clazz=clazz, d=dd):
                total_skipped += 1
                print(f"[skip] {dkey} {clazz}: exists")
                continue

            geojson_text = json.dumps(layer_geo, ensure_ascii=False)
            if args.dry_run:
                print(f"[dry-run] would upsert layer {dkey} {clazz} bytes={len(geojson_text)}")
                continue

            lid = dao.upsert_layer(
                clazz=clazz,
                d=dd,
                geojson_text=geojson_text,
                source_url=f"{args.base_url.rstrip('/')}/api/history/{hid}#{clazz}",
                features_count=len(layer_geo.get("features") or []) if isinstance(layer_geo.get("features"), list) else None,
            )
            total_written += 1
            print(f"[ok] {dkey} {clazz}: layer_id={lid}")

    print(
        f"Done. written={total_written} skipped={total_skipped} missing={total_missing} dates={len(wanted_dates)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
