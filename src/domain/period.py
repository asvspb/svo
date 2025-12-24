from __future__ import annotations

from datetime import date, datetime

from src.db.dao import list_layer_dates
from src.domain.pipeline import CLASSES, compare_dates_db
from src.reporting.period_report import PeriodReport, aggregate_period, build_period_report_text
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

    day_reports: list[tuple[str, str, str]] = []
    items_by_day: list[list] = []

    for a, b in zip(available, available[1:], strict=False):
        akey, bkey = _to_key(a), _to_key(b)
        items = compare_dates_db(
            akey,
            bkey,
            clazzes=clazzes,
            gazetteer_csv=gazetteer_csv,
            min_area_km2=min_area_km2,
        )
        items_by_day.append(items)
        day_reports.append((akey, bkey, build_telegram_report(items)))

    summary, top_items = aggregate_period(items_by_day, top_n=top_n)

    return PeriodReport(
        date_from=_to_key(df),
        date_to=_to_key(dt),
        day_reports=day_reports,
        summary_by_dir=summary,
        top_items=top_items,
    )


def render_period_report_text(rep: PeriodReport) -> str:
    return build_period_report_text(rep)
