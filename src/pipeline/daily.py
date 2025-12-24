from __future__ import annotations
import asyncio
from typing import Iterable, Optional, Sequence

from src.core.config import settings
from src.domain.pipeline import compare_latest
from src.reporting.report_generator import build_telegram_report

try:
    from aiogram import Bot
except Exception:  # pragma: no cover - optional at runtime
    Bot = None  # type: ignore


def _parse_admin_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    out: list[int] = []
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            continue
    return out


async def send_report_via_bot(text: str, chat_ids: Sequence[int]) -> None:
    if not text or not chat_ids:
        return
    # Telegram integration disabled: no bot token is configured in settings.
    if Bot is None:
        return
    return
    try:
        for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id=chat_id, text=text)
            except Exception:
                # continue sending to others even if one fails
                continue
    finally:
        await bot.session.close()  # type: ignore[func-returns-value]


async def generate_and_send_report(
    data_root: str = "data",
    *,
    gazetteer_csv: Optional[str] = None,
    recipients_from_env: bool = True,
    extra_chat_ids: Optional[Sequence[int]] = None,
) -> str:
    """Generate report from latest changes and optionally send it via Telegram bot.

    Returns the report text.
    """
    items = compare_latest(data_root, gazetteer_csv=gazetteer_csv)
    text = build_telegram_report(items)

    chat_ids: list[int] = []
    if recipients_from_env:
        chat_ids.extend(_parse_admin_ids(settings.TELEGRAM_ADMIN_IDS))
    if extra_chat_ids:
        chat_ids.extend(int(x) for x in extra_chat_ids)

    await send_report_via_bot(text, chat_ids)
    return text
