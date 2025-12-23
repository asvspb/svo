from __future__ import annotations
import os
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine

class Base(DeclarativeBase):
    pass


def make_sync_url() -> str:
    user = os.getenv("MYSQL_USER", "app")
    password = os.getenv("MYSQL_PASSWORD", "app_pass")
    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    db = os.getenv("MYSQL_DATABASE", "deepstate")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset=utf8mb4"


def get_engine(echo: bool | None = None):
    if echo is None:
        echo = os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true"
    url = make_sync_url()
    engine = create_engine(url, echo=echo, pool_pre_ping=True, pool_recycle=3600)
    return engine


def get_session_maker() -> sessionmaker:
    engine = get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)
