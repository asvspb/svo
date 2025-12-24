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

    # Top-3 by area (grouped by settlement if possible)
    top3_raw = sorted(items, key=lambda x: x["area_km2"], reverse=True)

    from collections import OrderedDict

    grouped: "OrderedDict[tuple[str, str], ChangeItem]" = OrderedDict()
    for it in top3_raw:
        key = (it.get("settlement") or "", it.get("direction") or "")
        if key not in grouped:
            grouped[key] = dict(it)
            continue
        # aggregate area within group
        grouped[key]["area_km2"] = float(grouped[key]["area_km2"]) + float(it["area_km2"])  # type: ignore[index]
        # keep the closest distance if present
        d0 = grouped[key].get("settlement_distance_km")
        d1 = it.get("settlement_distance_km")
        if d1 is not None:
            grouped[key]["settlement_distance_km"] = float(d1) if d0 is None else min(float(d0), float(d1))

    top3 = list(grouped.values())[:3]

    def fmt_item(it: ChangeItem) -> str:
        area = f"{it['area_km2']:.2f} км²"
        place = it.get("settlement") or "неизвестный н.п."
        dist = it.get("settlement_distance_km")
        if dist is not None:
            place = f"{place} (~{float(dist):.1f} км)"
        emoji = "🔴" if it["status"] == "gained" else "🟢" if it["status"] == "lost" else "⚪️"
        dir_txt = it.get("direction") or ""
        dir_pref = f" ({dir_txt})" if dir_txt else ""
        return f"{emoji} {place}{dir_pref}: {it['status']} (+{area} изменения)"

    lines = ["📊 Суточные изменения на карте:"]

    # Summary by direction
    from collections import defaultdict

    by_dir: dict[str, dict[str, float]] = defaultdict(lambda: {"gained": 0.0, "lost": 0.0})
    by_settlement: dict[str, dict[str, float]] = defaultdict(lambda: {"gained": 0.0, "lost": 0.0})

    for it in items:
        d = it.get("direction") or "misc"
        by_dir[d][it["status"]] = by_dir[d].get(it["status"], 0.0) + float(it["area_km2"])

        s = it.get("settlement") or ""
        if s:
            by_settlement[s][it["status"]] = by_settlement[s].get(it["status"], 0.0) + float(it["area_km2"])

    for d, agg in by_dir.items():
        lines.append(f"• {d}: +{agg.get('gained', 0.0):.2f} км², -{agg.get('lost', 0.0):.2f} км²")

    # Top settlements by total change
    if by_settlement:
        def _total(v: dict[str, float]) -> float:
            return float(v.get('gained', 0.0)) + float(v.get('lost', 0.0))

        top_places = sorted(by_settlement.items(), key=lambda kv: _total(kv[1]), reverse=True)[:5]
        lines.append("\nТоп населённых пунктов по суммарным изменениям:")
        for name, agg in top_places:
            lines.append(f"• {name}: +{agg.get('gained', 0.0):.2f} км², -{agg.get('lost', 0.0):.2f} км²")

    lines.append("")
    lines.append("ТОП-3 участков по площади:")
    for it in top3:
        lines.append(f"- {fmt_item(it)}")

    return "\n".join(lines)
