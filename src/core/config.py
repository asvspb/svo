"""Configuration management using pydantic-settings (optional).

Usage:
    from src.core.config import settings
    print(settings.HEADLESS)
"""

from __future__ import annotations
from pydantic import Field
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except Exception:  # fallback if not installed
    from pydantic import BaseModel as BaseSettings  # type: ignore
    SettingsConfigDict = dict  # type: ignore


class Settings(BaseSettings):
    ENV: str = Field(default="dev")
    HEADLESS: bool = Field(default=False)
    USER_AGENT: str | None = None
    NAV_TIMEOUT_MS: int = 60000
    WAIT_NETWORK_IDLE_MS: int = 5000

    # Comma-separated substrings or regex patterns to whitelist endpoints
    ENDPOINT_WHITELIST: str | None = None
    ENDPOINT_BLACKLIST: str | None = None
    MIN_JSON_BYTES: int = 200  # ignore tiny payloads
    SAVE_RAW_JSON: bool = False

    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_ADMIN_IDS: str | None = None  # comma-separated
    REPORT_SCHEDULE_CRON: str | None = "0 21 * * *"  # daily at 21:00
    DATA_ROOT: str = "data"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
