#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from src.db.dao import insert_report
from src.domain.pipeline import compare_dates_db
from src.reporting.report_generator import build_telegram_report

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
    ap = argparse.ArgumentParser(description="Generate report for two dates using DB-stored layers")
    ap.add_argument("--from", dest="date_from", type=_parse_date, required=True, help="Start date")
    ap.add_argument("--to", dest="date_to", type=_parse_date, required=True, help="End date")
    ap.add_argument(
        "--classes",
        default="occupied,gray",
        help="Comma-separated list (default: occupied,gray)",
    )
    ap.add_argument("--gazetteer-csv", default=None, help="Gazetteer CSV for settlement names")
    ap.add_argument("--min-area-km2", type=float, default=0.01, help="Filter small patches")
    ap.add_argument("--store", action="store_true", help="Store report in DB (reports table)")

    args = ap.parse_args(argv)

    clazzes = tuple([p.strip() for p in args.classes.split(",") if p.strip()])
    items = compare_dates_db(
        args.date_from,
        args.date_to,
        clazzes=clazzes,  # type: ignore[arg-type]
        gazetteer_csv=args.gazetteer_csv,
        min_area_km2=float(args.min_area_km2),
    )
    text = build_telegram_report(items)

    if args.store:
        # store as report for end date
        d_end = datetime.strptime(args.date_to, "%Y_%m_%d").date()
        insert_report(date_curr=d_end, text=text, top3=items[:3])

    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
