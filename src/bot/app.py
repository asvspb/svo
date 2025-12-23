"""Telegram bot skeleton (aiogram) — minimal example.

This module is a placeholder; real implementation will:
- Register /start and subscription handlers
- Schedule daily scraping and reporting
- Send messages to subscribers
"""

from __future__ import annotations

try:
    from aiogram import Bot, Dispatcher
except Exception:  # pragma: no cover - optional dependency
    Bot = object  # type: ignore
    Dispatcher = object  # type: ignore

from src.core.config import settings


def create_bot() -> Bot:  # type: ignore[valid-type]
    token = settings.TELEGRAM_BOT_TOKEN or ""
    return Bot(token=token)  # type: ignore[call-arg]


def create_dispatcher() -> Dispatcher:  # type: ignore[valid-type]
    return Dispatcher()  # type: ignore[call-arg]
