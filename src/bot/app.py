"""Telegram bot skeleton (aiogram) — minimal example.

This module is a placeholder; real implementation will:
- Register /start and subscription handlers
- Schedule daily scraping and reporting
- Send messages to subscribers
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from src.core.config import settings
from src.pipeline.daily import generate_and_send_report
from src.bot.storage import load_subscribers, save_subscribers

try:
    from aiogram import Bot, Dispatcher, F
    from aiogram.filters import Command
    from aiogram.types import Message
except Exception:  # pragma: no cover - optional dependency
    Bot = None  # type: ignore
    Dispatcher = None  # type: ignore
    F = None  # type: ignore
    Command = None  # type: ignore
    Message = None  # type: ignore

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
except Exception:  # pragma: no cover - optional dependency
    AsyncIOScheduler = None  # type: ignore
    CronTrigger = None  # type: ignore


def create_bot() -> Bot:  # type: ignore[valid-type]
    if Bot is None:
        raise RuntimeError("aiogram is not installed")
    token = settings.TELEGRAM_BOT_TOKEN or ""
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    return Bot(token=token)  # type: ignore[call-arg]


def create_dispatcher() -> Dispatcher:  # type: ignore[valid-type]
    if Dispatcher is None:
        raise RuntimeError("aiogram is not installed")
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def cmd_start(msg: Message):  # type: ignore[valid-type]
        subs = load_subscribers()
        subs.add(msg.chat.id)
        save_subscribers(subs)
        await msg.answer("Вы подписаны на ежедневный отчёт. Отписаться: /stop. Запросить сейчас: /report")

    @dp.message(Command("stop"))
    async def cmd_stop(msg: Message):  # type: ignore[valid-type]
        subs = load_subscribers()
        subs.discard(msg.chat.id)
        save_subscribers(subs)
        await msg.answer("Вы отписаны от ежедневной рассылки")

    @dp.message(Command("report"))
    async def cmd_report(msg: Message):  # type: ignore[valid-type]
        # Try DB latest report first
        from src.db.dao import get_latest_report
        text = get_latest_report()
        if not text:
            # Fallback on-the-fly generation
            text = await generate_and_send_report(
                data_root=settings.DATA_ROOT,
                recipients_from_env=False,
                extra_chat_ids=[msg.chat.id],
            )
        await msg.answer(text)

    return dp


async def _scheduled_broadcast() -> None:
    subs = list(load_subscribers())
    if not subs:
        logging.info("No subscribers to broadcast")
        return
    logging.info("Scheduled broadcast to %d subscribers", len(subs))
    await generate_and_send_report(
        data_root=settings.DATA_ROOT,
        recipients_from_env=False,
        extra_chat_ids=subs,
    )


async def run_bot_polling() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    bot = create_bot()
    dp = create_dispatcher()

    # Setup scheduler if available and cron is set
    scheduler = None
    if AsyncIOScheduler is not None and CronTrigger is not None and settings.REPORT_SCHEDULE_CRON:
        try:
            scheduler = AsyncIOScheduler(timezone="UTC")
            trigger = CronTrigger.from_crontab(settings.REPORT_SCHEDULE_CRON)
            scheduler.add_job(_scheduled_broadcast, trigger=trigger, id="daily_report", replace_existing=True)
            scheduler.start()
            logging.info("Scheduler started with cron: %s", settings.REPORT_SCHEDULE_CRON)
        except Exception as e:
            logging.warning("Failed to start scheduler: %s", e)

    try:
        await dp.start_polling(bot)
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
