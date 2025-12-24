from __future__ import annotations

from datetime import date, datetime

from src.db.dao import get_change_summary, list_cached_pairs, list_layer_dates, upsert_change_summary
from src.domain.pipeline import CLASSES, compare_dates_db
from collections import defaultdict

from src.reporting.period_report import PeriodReport, build_period_report_text
from src.reporting.report_generator import build_telegram_report


def _to_key(d: date) -> str:
    return d.strftime("%Y_%m_%d")


def generate_period_report_db(
    date_from: str,
    date_to: str,
    *,
    clazzes: tuple[str, ...] = CLASSES,
    gazetteer_csv: str | None = None,
    min_area_km2: float = 0.01,
    top_n: int = 10,
    cluster_distance_km: float | None = 1.0,
    use_cache: bool = True,
    force_recompute: bool = False,
) -> PeriodReport:
    """Generate period report based on layers stored in DB.

    Strategy:
    - Determine available dates in DB within [date_from, date_to]
    - For each adjacent pair (d[i], d[i+1]) compute changes and build daily summary
    - Aggregate totals across days and collect top-N changes
    """

    df = datetime.strptime(date_from, "%Y_%m_%d").date()
    dt = datetime.strptime(date_to, "%Y_%m_%d").date()
    if dt < df:
        df, dt = dt, df

    available = [d for d in list_layer_dates() if df <= d <= dt]
    available.sort()

    # Determine which day-pairs to report on.
    # If cache-only mode: use cached pairs.
    # Else: prefer layers-based adjacency, fallback to cached pairs.
    if not use_cache:
        day_pairs = list(zip(available, available[1:], strict=False))
    else:
        if len(available) >= 2:
            day_pairs = list(zip(available, available[1:], strict=False))
        else:
            day_pairs = list_cached_pairs(date_from=df, date_to=dt)

    day_reports: list[tuple[str, str, str]] = []

    summary_by_dir: dict[str, dict[str, float]] = defaultdict(lambda: {"gained": 0.0, "lost": 0.0})
    top_candidates: list = []

    for a, b in day_pairs:
        akey, bkey = _to_key(a), _to_key(b)

        # Try to use cached summaries per class; if any class is missing, recompute.
        cached_per_class: dict[str, tuple[float, float, list]] = {}
        if use_cache and not force_recompute:
            for clazz in clazzes:
                cached = get_change_summary(clazz=clazz, date_prev=a, date_curr=b)
                if cached is None:
                    cached_per_class = {}
                    break
                cached_per_class[clazz] = cached

        if cached_per_class:
            # Build daily top list from cached top patches; totals from cached gained/lost.
            day_top: list = []
            for clazz, (gained, lost, top_items) in cached_per_class.items():
                summary_by_dir[clazz]["gained"] += float(gained)
                summary_by_dir[clazz]["lost"] += float(lost)
                day_top.extend(top_items)
            day_items = sorted(day_top, key=lambda x: x["area_km2"], reverse=True)[:top_n]
            top_candidates.extend(day_items)
        else:
            # Compute full diff from layers.
            day_items = compare_dates_db(
                akey,
                bkey,
                clazzes=clazzes,
                gazetteer_csv=gazetteer_csv,
                min_area_km2=min_area_km2,
                cluster_distance_km=cluster_distance_km,
            )
            # Aggregate totals and cache per class.
            for clazz in clazzes:
                sub = [it for it in day_items if it.get("direction") == clazz]
                gained = sum(it["area_km2"] for it in sub if it["status"] == "gained")
                lost = sum(it["area_km2"] for it in sub if it["status"] == "lost")
                summary_by_dir[clazz]["gained"] += float(gained)
                summary_by_dir[clazz]["lost"] += float(lost)
                top_sub = sorted(sub, key=lambda x: x["area_km2"], reverse=True)[:top_n]
                upsert_change_summary(
                    clazz=clazz,
                    date_prev=a,
                    date_curr=b,
                    gained_km2=float(gained),
                    lost_km2=float(lost),
                    top_items=top_sub,
                )
            top_candidates.extend(sorted(day_items, key=lambda x: x["area_km2"], reverse=True)[:top_n])

        day_reports.append((akey, bkey, build_telegram_report(day_items)))

    top_items = sorted(top_candidates, key=lambda x: x["area_km2"], reverse=True)[:top_n]

    return PeriodReport(
        date_from=_to_key(df),
        date_to=_to_key(dt),
        day_reports=day_reports,
        summary_by_dir=dict(summary_by_dir),
        top_items=top_items,
    )


def render_period_report_text(rep: PeriodReport) -> str:
    return build_period_report_text(rep)
