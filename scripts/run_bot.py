#!/usr/bin/env python3
from __future__ import annotations
import asyncio
import socket
import random

from src.bot.app import run_bot_polling

def find_free_port():
    for _ in range(100):
        port = random.randint(8001, 65535)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('localhost', port))
                return port
            except OSError:
                continue
    return None

if __name__ == "__main__":
    port = find_free_port()
    if port:
        print(f"Using port: {port}")
        asyncio.run(run_bot_polling())
    else:
        print("No free port found, using default")
        asyncio.run(run_bot_polling())
