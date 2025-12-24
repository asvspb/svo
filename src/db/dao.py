from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Iterable
from datetime import date

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.geo_changes import ChangeItem

from .base import get_session_maker
from .models import Change, ChangeSummary, DateRef, Layer, Report


def _get_date_id(sess: Session, d: date) -> int | None:
    row = sess.execute(select(DateRef.id).where(DateRef.date == d)).scalar_one_or_none()
    return int(row) if row is not None else None


def layer_exists(*, clazz: str, d: date) -> bool:
    """Return True if layer(clazz, d) exists in DB."""
    SessionLocal = get_session_maker()
    with SessionLocal() as sess:
        did = _get_date_id(sess, d)
        if did is None:
            return False
        row = sess.execute(select(Layer.id).where(Layer.date_id == did, Layer.clazz == clazz)).scalar_one_or_none()
        return row is not None


def get_layer_geojson_text(*, clazz: str, d: date) -> str | None:
    """Load gzipped GeoJSON from DB and return as text."""
    SessionLocal = get_session_maker()
    with SessionLocal() as sess:
        did = _get_date_id(sess, d)
        if did is None:
            return None
        row = sess.execute(select(Layer.geojson).where(Layer.date_id == did, Layer.clazz == clazz)).scalar_one_or_none()
        if row is None:
            return None
        try:
            return gzip.decompress(row).decode("utf-8")
        except Exception:
            return None


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
    source_url: str | None = None,
    features_count: int | None = None,
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


def get_latest_report() -> str | None:
    SessionLocal = get_session_maker()
    with SessionLocal() as sess:
        row = sess.execute(
            select(Report.text).order_by(Report.id.desc()).limit(1)
        ).scalar_one_or_none()
        return row


def upsert_change_summary(
    *,
    clazz: str,
    date_prev: date,
    date_curr: date,
    gained_km2: float,
    lost_km2: float,
    top_items: list[ChangeItem],
) -> int:
    """Upsert cached summary for a (prev,curr,clazz) pair."""
    SessionLocal = get_session_maker()
    with SessionLocal() as sess:
        dprev_id = _ensure_date(sess, date_prev)
        dcurr_id = _ensure_date(sess, date_curr)
        existing = sess.execute(
            select(ChangeSummary).where(
                ChangeSummary.date_prev_id == dprev_id,
                ChangeSummary.date_curr_id == dcurr_id,
                ChangeSummary.clazz == clazz,
            )
        ).scalar_one_or_none()
        payload = json.dumps(top_items, ensure_ascii=False)
        if existing:
            existing.gained_km2 = float(gained_km2)  # type: ignore[assignment]
            existing.lost_km2 = float(lost_km2)  # type: ignore[assignment]
            existing.top_json = payload  # type: ignore[assignment]
            sess.commit()
            return existing.id  # type: ignore[attr-defined]
        obj = ChangeSummary(
            date_prev_id=dprev_id,
            date_curr_id=dcurr_id,
            clazz=clazz,
            gained_km2=float(gained_km2),
            lost_km2=float(lost_km2),
            top_json=payload,
        )
        sess.add(obj)
        sess.commit()
        return obj.id  # type: ignore[attr-defined]


def get_change_summary(
    *, clazz: str, date_prev: date, date_curr: date
) -> tuple[float, float, list[ChangeItem]] | None:
    """Get cached summary (gained, lost, top_items)."""
    SessionLocal = get_session_maker()
    with SessionLocal() as sess:
        dprev_id = _get_date_id(sess, date_prev)
        dcurr_id = _get_date_id(sess, date_curr)
        if dprev_id is None or dcurr_id is None:
            return None
        row = sess.execute(
            select(ChangeSummary.gained_km2, ChangeSummary.lost_km2, ChangeSummary.top_json).where(
                ChangeSummary.date_prev_id == dprev_id,
                ChangeSummary.date_curr_id == dcurr_id,
                ChangeSummary.clazz == clazz,
            )
        ).one_or_none()
        if row is None:
            return None
        gained, lost, top_json = row
        top_items: list[ChangeItem] = []
        if top_json:
            try:
                top_items = json.loads(top_json)
            except Exception:
                top_items = []
        return float(gained), float(lost), top_items


def list_cached_pairs(*, date_from: date, date_to: date) -> list[tuple[date, date]]:
    """List distinct (prev_date, curr_date) pairs available in change_summaries within range."""
    SessionLocal = get_session_maker()
    with SessionLocal() as sess:
        # Join twice to dates
        prev = sa.orm.aliased(DateRef)
        curr = sa.orm.aliased(DateRef)
        stmt = (
            select(prev.date, curr.date)
            .select_from(ChangeSummary)
            .join(prev, prev.id == ChangeSummary.date_prev_id)
            .join(curr, curr.id == ChangeSummary.date_curr_id)
            .where(curr.date >= date_from, curr.date <= date_to)
            .distinct()
            .order_by(prev.date.asc(), curr.date.asc())
        )
        return list(sess.execute(stmt).all())


def list_layer_dates(*, clazz: str | None = None) -> list[date]:
    """List distinct dates that have layers in DB.

    If `clazz` is provided, only dates that have that layer class are returned.
    """
    SessionLocal = get_session_maker()
    with SessionLocal() as sess:
        stmt = select(DateRef.date).join(Layer, Layer.date_id == DateRef.id)
        if clazz is not None:
            stmt = stmt.where(Layer.clazz == clazz)
        stmt = stmt.distinct().order_by(DateRef.date.asc())
        rows = sess.execute(stmt).scalars().all()
        return list(rows)
