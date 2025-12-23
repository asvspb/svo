"""Report generation from change items (skeleton)."""

from __future__ import annotations
from typing import Iterable
from src.domain.geo_changes import ChangeItem


def build_telegram_report(items: Iterable[ChangeItem]) -> str:
    """Build a Telegram-friendly daily report from change items.

    Behavior:
    - If no items => neutral message
    - Group by direction (occupied/gray) and summarize counts/areas
    - Highlight TOP-3 changes by area with settlement names (if present)
    """
    items = list(items)
    if not items:
        return "⚪️ На линии фронта без существенных изменений в конфигурации зон"

    # Top-3 by area
    top3 = sorted(items, key=lambda x: x["area_km2"], reverse=True)[:3]

    def fmt_item(it: ChangeItem) -> str:
        area = f"{it['area_km2']:.2f} км²"
        place = it.get("settlement") or "неизвестный н.п."
        emoji = "🔴" if it["status"] == "gained" else "🟢" if it["status"] == "lost" else "⚪️"
        dir_txt = it.get("direction") or ""
        dir_pref = f" ({dir_txt})" if dir_txt else ""
        return f"{emoji} {place}{dir_pref}: {it['status']} (+{area} изменения)"

    lines = ["📊 Суточные изменения на карте:"]

    # Summary by direction
    from collections import defaultdict

    by_dir: dict[str, dict[str, float]] = defaultdict(lambda: {"gained": 0.0, "lost": 0.0})
    for it in items:
        d = it.get("direction") or "misc"
        by_dir[d][it["status"]] = by_dir[d].get(it["status"], 0.0) + float(it["area_km2"])

    for d, agg in by_dir.items():
        lines.append(f"• {d}: +{agg.get('gained', 0.0):.2f} км², -{agg.get('lost', 0.0):.2f} км²")

    lines.append("")
    lines.append("ТОП-3 участков по площади:")
    for it in top3:
        lines.append(f"- {fmt_item(it)}")

    return "\n".join(lines)
