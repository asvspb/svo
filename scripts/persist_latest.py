#!/usr/bin/env python3
from __future__ import annotations
import argparse

from src.domain.persist import compute_and_store_latest


def main() -> None:
    ap = argparse.ArgumentParser(description="Compute latest changes and persist to DB")
    ap.add_argument("--data-root", default="data")
    ap.add_argument("--gazetteer-csv", default=None)
    args = ap.parse_args()

    text = compute_and_store_latest(args.data_root, gazetteer_csv=args.gazetteer_csv)
    print(text)


if __name__ == "__main__":
    main()
