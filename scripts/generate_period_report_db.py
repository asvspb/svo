#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.domain.period import generate_period_report_db, render_period_report_text


def _parse_date(s: str) -> str:
    try:
        if "_" in s:
            datetime.strptime(s, "%Y_%m_%d")
            return s
        d = datetime.strptime(s, "%Y-%m-%d")
        return d.strftime("%Y_%m_%d")
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date: {s}") from e


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate period report using DB-stored layers")
    ap.add_argument("--from", dest="date_from", type=_parse_date, required=True)
    ap.add_argument("--to", dest="date_to", type=_parse_date, required=True)
    ap.add_argument("--classes", default="occupied,gray", help="Comma-separated classes")
    ap.add_argument("--gazetteer-csv", default=None)
    ap.add_argument("--min-area-km2", type=float, default=0.01)
    ap.add_argument("--top-n", type=int, default=10)
    ap.add_argument("--cluster-distance-km", type=float, default=1.0, help="Cluster nearby patches (km); set 0 to disable")

    cache = ap.add_mutually_exclusive_group()
    cache.add_argument("--no-cache", action="store_true", help="Do not read/write cached summaries")
    cache.add_argument("--recompute", action="store_true", help="Ignore cache and recompute from layers (will overwrite cache)")

    args = ap.parse_args(argv)
    clazzes = tuple([p.strip() for p in args.classes.split(",") if p.strip()])

    rep = generate_period_report_db(
        args.date_from,
        args.date_to,
        clazzes=clazzes,  # type: ignore[arg-type]
        gazetteer_csv=args.gazetteer_csv,
        min_area_km2=args.min_area_km2,
        top_n=args.top_n,
        cluster_distance_km=None if float(args.cluster_distance_km) <= 0 else float(args.cluster_distance_km),
        use_cache=not bool(args.no_cache),
        force_recompute=bool(args.recompute),
    )
    print(render_period_report_text(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
