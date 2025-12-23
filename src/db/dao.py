from __future__ import annotations
import gzip
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import select, insert
from sqlalchemy.orm import Session

from .base import get_session_maker
from .models import DateRef, Layer, Change, Report
from src.domain.geo_changes import ChangeItem


def _ensure_date(sess: Session, d: date) -> int:
    row = sess.execute(select(DateRef).where(DateRef.date == d)).scalar_one_or_none()
    if row:
        return row.id  # type: ignore[attr-defined]
    obj = DateRef(date=d)
    sess.add(obj)
    sess.flush()
    return obj.id  # type: ignore[attr-defined]


def upsert_layer(
    *,
    clazz: str,
    d: date,
    geojson_text: str,
    source_url: Optional[str] = None,
    features_count: Optional[int] = None,
) -> int:
    """Store layer GeoJSON (gzipped) with idempotency via checksum."""
    SessionLocal = get_session_maker()
    checksum = hashlib.sha256(geojson_text.encode("utf-8")).hexdigest()
    gz = gzip.compress(geojson_text.encode("utf-8"))
    with SessionLocal() as sess:
        did = _ensure_date(sess, d)
        # check existing
        existing = sess.execute(
            select(Layer).where(Layer.date_id == did, Layer.clazz == clazz)
        ).scalar_one_or_none()
        if existing and existing.checksum == checksum:
            return existing.id  # type: ignore[attr-defined]
        if existing:
            # update existing
            existing.geojson = gz  # type: ignore[assignment]
            existing.features_count = features_count
            existing.source_url = source_url
            existing.checksum = checksum
            sess.commit()
            return existing.id  # type: ignore[attr-defined]
        obj = Layer(
            clazz=clazz,
            date_id=did,
            source_url=source_url,
            geojson=gz,
            features_count=features_count,
            checksum=checksum,
        )
        sess.add(obj)
        sess.commit()
        return obj.id  # type: ignore[attr-defined]


def insert_changes(
    *,
    clazz: str,
    date_prev: date,
    date_curr: date,
    items: Iterable[ChangeItem],
) -> int:
    """Insert change patches idempotently using a content hash."""
    SessionLocal = get_session_maker()
    count = 0
    with SessionLocal() as sess:
        dprev_id = _ensure_date(sess, date_prev)
        dcurr_id = _ensure_date(sess, date_curr)
        for it in items:
            hsrc = f"{clazz}|{it['status']}|{it['centroid'][0]:.6f}|{it['centroid'][1]:.6f}|{it['area_km2']:.4f}|{date_curr.isoformat()}"
            hkey = hashlib.sha256(hsrc.encode("utf-8")).hexdigest()
            exists = sess.execute(
                select(Change).where(Change.hash_key == hkey)
            ).scalar_one_or_none()
            if exists:
                continue
            obj = Change(
                date_prev_id=dprev_id,
                date_curr_id=dcurr_id,
                clazz=clazz,
                status=it["status"],
                area_km2=float(it["area_km2"]),
                centroid_lon=float(it["centroid"][0]),
                centroid_lat=float(it["centroid"][1]),
                settlement=it.get("settlement"),
                settlement_distance_km=None,
                hash_key=hkey,
            )
            sess.add(obj)
            count += 1
        sess.commit()
    return count


def insert_report(*, date_curr: date, text: str, top3: list[ChangeItem] | None = None) -> int:
    SessionLocal = get_session_maker()
    with SessionLocal() as sess:
        did = _ensure_date(sess, date_curr)
        obj = Report(date_curr_id=did, text=text, top3_json=json.dumps(top3 or []))
        sess.add(obj)
        sess.commit()
        return obj.id  # type: ignore[attr-defined]


def get_latest_report() -> Optional[str]:
    SessionLocal = get_session_maker()
    with SessionLocal() as sess:
        row = sess.execute(
            select(Report.text).order_by(Report.id.desc()).limit(1)
        ).scalar_one_or_none()
        return row
