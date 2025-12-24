from __future__ import annotations
from sqlalchemy import BigInteger, Column, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, LargeBinary, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

# SQLite does not auto-increment BIGINT primary keys the same way as MySQL.
# Use per-dialect type variants so tests/dev can run on sqlite.
ID_BIGINT = BigInteger().with_variant(Integer, "sqlite")


class DateRef(Base):
    __tablename__ = "dates"
    id: Mapped[int] = mapped_column(ID_BIGINT, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(Date, unique=True, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class Layer(Base):
    __tablename__ = "layers"
    id: Mapped[int] = mapped_column(ID_BIGINT, primary_key=True, autoincrement=True)
    clazz: Mapped[str] = mapped_column(Enum("occupied", "gray", "frontline", name="layer_class"), nullable=False)
    date_id: Mapped[int] = mapped_column(ID_BIGINT, ForeignKey("dates.id"), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(512))
    geojson: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    features_count: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("clazz", "date_id", name="uk_layer_class_date"),
    )


class Change(Base):
    __tablename__ = "changes"
    id: Mapped[int] = mapped_column(ID_BIGINT, primary_key=True, autoincrement=True)
    date_prev_id: Mapped[int] = mapped_column(ID_BIGINT, ForeignKey("dates.id"), nullable=False)
    date_curr_id: Mapped[int] = mapped_column(ID_BIGINT, ForeignKey("dates.id"), nullable=False)
    clazz: Mapped[str] = mapped_column(Enum("occupied", "gray", name="change_class"), nullable=False)
    status: Mapped[str] = mapped_column(Enum("gained", "lost", name="change_status"), nullable=False)
    area_km2: Mapped[float] = mapped_column(Float, nullable=False)
    centroid_lon: Mapped[float] = mapped_column(Float, nullable=False)
    centroid_lat: Mapped[float] = mapped_column(Float, nullable=False)
    settlement: Mapped[str | None] = mapped_column(String(128))
    settlement_distance_km: Mapped[float | None] = mapped_column(Float)
    hash_key: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_changes_date_class", "date_curr_id", "clazz", "status"),
    )


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(ID_BIGINT, primary_key=True, autoincrement=True)
    date_curr_id: Mapped[int] = mapped_column(ID_BIGINT, ForeignKey("dates.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    top3_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class Subscriber(Base):
    __tablename__ = "subscribers"
    id: Mapped[int] = mapped_column(ID_BIGINT, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(ID_BIGINT, unique=True, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
