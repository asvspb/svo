"""Report generation from change items (skeleton)."""

from __future__ import annotations
from typing import Iterable
from src.domain.geo_changes import ChangeItem


def build_telegram_report(items: Iterable[ChangeItem]) -> str:
    """Format a short Telegram-friendly report from change items.

    Strategy:
    - Group small changes by direction
    - Select TOP-3 by area_km2
    - Render emojis and concise text
    """
    # TODO: implement
    return "На линии фронта без существенных изменений в конфигурации зон"
