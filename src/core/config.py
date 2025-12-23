"""Configuration management using pydantic-settings (optional).

Usage:
    from src.core.config import settings
    print(settings.HEADLESS)
"""

from __future__ import annotations
from pydantic import Field
try:
    from pydantic_settings import BaseSettings
except Exception:  # fallback if not installed
    from pydantic import BaseModel as BaseSettings  # type: ignore


class Settings(BaseSettings):
    ENV: str = Field(default="dev")
    HEADLESS: bool = Field(default=False)
    USER_AGENT: str | None = None
    NAV_TIMEOUT_MS: int = 60000
    WAIT_NETWORK_IDLE_MS: int = 5000

    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_ADMIN_IDS: str | None = None  # comma-separated

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
