#!/usr/bin/env python3
from __future__ import annotations
import asyncio
import argparse

from src.pipeline.daily import generate_and_send_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily report and send via Telegram (optional)")
    parser.add_argument("--data-root", default="data", help="Root folder with layer_*.geojson")
    parser.add_argument("--gazetteer-csv", default=None, help="Path to local gazetteer CSV")
    parser.add_argument("--no-send", action="store_true", help="Do not send via Telegram, only print")
    args = parser.parse_args()

    async def _run():
        text = await generate_and_send_report(
            data_root=args.data_root,
            gazetteer_csv=args.gazetteer_csv,
            recipients_from_env=not args.no_send,
        )
        print(text)

    asyncio.run(_run())


if __name__ == "__main__":
    main()
