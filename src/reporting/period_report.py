from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from src.domain.geo_changes import ChangeItem


@dataclass(frozen=True)
class PeriodReport:
    date_from: str
    date_to: str
    day_reports: list[tuple[str, str, str]]
    # summary_by_dir[direction][status] -> area
    summary_by_dir: dict[str, dict[str, float]]
    top_items: list[ChangeItem]


def build_period_report_text(rep: PeriodReport) -> str:
    """Build a text report for a period.

    - Includes daily summaries (from->to)
    - Includes total gained/lost per direction
    - Includes TOP changes for the whole period
    """
    lines: list[str] = []
    lines.append(f"📅 Отчёт за период: {rep.date_from} → {rep.date_to}")

    # Totals
    lines.append("\nИтого за период:")
    for d, agg in rep.summary_by_dir.items():
        lines.append(f"• {d}: +{agg.get('gained', 0.0):.2f} км², -{agg.get('lost', 0.0):.2f} км²")

    # Daily
    if rep.day_reports:
        lines.append("\nДень-за-днём:")
        for d1, d2, text in rep.day_reports:
            lines.append(f"\n---\n{d1} → {d2}\n{text}")

    # Top
    if rep.top_items:
        lines.append("\nТОП изменений за период:")
        for it in rep.top_items:
            place = it.get("settlement") or "н/п?"
            dir_txt = it.get("direction") or ""
            lines.append(
                f"- {place} ({dir_txt}): {it['status']} {it['area_km2']:.2f} км²"
            )

    return "\n".join(lines)


def aggregate_period(items_by_day: Iterable[list[ChangeItem]], *, top_n: int = 10) -> tuple[dict[str, dict[str, float]], list[ChangeItem]]:
    """Aggregate period totals and pick top-N items across all days."""
    summary: dict[str, dict[str, float]] = defaultdict(lambda: {"gained": 0.0, "lost": 0.0})
    all_items: list[ChangeItem] = []
    for items in items_by_day:
        for it in items:
            d = it.get("direction") or "misc"
            if it["status"] in ("gained", "lost"):
                summary[d][it["status"]] = summary[d].get(it["status"], 0.0) + float(it["area_km2"])
            all_items.append(it)

    top = sorted(all_items, key=lambda x: x["area_km2"], reverse=True)[:top_n]
    return dict(summary), top
