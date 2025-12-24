from __future__ import annotations
import os
from functools import lru_cache

from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine

class Base(DeclarativeBase):
    pass


def make_sync_url() -> str:
    """Build SQLAlchemy sync URL.

    Priority:
    1) DATABASE_URL env var (allows sqlite for local dev/tests)
    2) MySQL env vars (MYSQL_*)
    """
    direct = os.getenv("DATABASE_URL")
    if direct:
        return direct
    user = os.getenv("MYSQL_USER", "app")
    password = os.getenv("MYSQL_PASSWORD", "app_pass")
    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    db = os.getenv("MYSQL_DATABASE", "deepstate")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset=utf8mb4"


@lru_cache(maxsize=4)
def _cached_engine(url: str, echo: bool) -> object:
    # Note: return type is Engine, but keep it broad to avoid importing typing-only
    return create_engine(url, echo=echo, pool_pre_ping=True, pool_recycle=3600)


def get_engine(echo: bool | None = None):
    if echo is None:
        echo = os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true"
    url = make_sync_url()
    return _cached_engine(url, echo)  # type: ignore[return-value]


def clear_engine_cache() -> None:
    """Clear cached SQLAlchemy engines (useful in tests when env changes)."""
    _cached_engine.cache_clear()


def get_session_maker() -> sessionmaker:
    engine = get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)
