from __future__ import annotations
from datetime import date
from pathlib import Path
from typing import Optional
import json

from src.domain.pipeline import compare_latest, CLASSES
from src.domain.utils_dates import date_from_filename
from src.reporting.report_generator import build_telegram_report
from src.db.dao import insert_changes, insert_report


def compute_and_store_latest(data_root: str, *, gazetteer_csv: Optional[str] = None) -> str:
    """Compute changes for latest two dates per class, store in DB, and store report.

    Returns report text.
    """
    # First, compute items and track picked files
    from src.domain.pipeline import _find_layer_files  # reuse internal helper

    picked: dict[str, tuple[Path, Path]] = {}
    for clazz in CLASSES:
        files = _find_layer_files(data_root, clazz)
        if len(files) >= 2:
            picked[clazz] = (files[-2], files[-1])

    # compute combined items using pipeline.compare_latest
    items = compare_latest(data_root, gazetteer_csv=gazetteer_csv)

    # persist changes per class with parsed dates
    if picked:
        # assume same latest dates across classes; take max curr
        curr_dates = [date_from_filename(pp[1]) for pp in picked.values()]
        prev_dates = [date_from_filename(pp[0]) for pp in picked.values()]
        d_curr = max(curr_dates)
        d_prev = max(prev_dates)
        # insert changes per class
        for clazz, (prev_p, curr_p) in picked.items():
            # filter items by direction
            sub = [it for it in items if it.get("direction") == clazz]
            if sub:
                insert_changes(clazz=clazz, date_prev=d_prev, date_curr=d_curr, items=sub)
        # store report
        text = build_telegram_report(items)
        insert_report(date_curr=d_curr, text=text, top3=items[:3])
        return text

    # fallback: just return text without DB if not enough files
    return build_telegram_report(items)
