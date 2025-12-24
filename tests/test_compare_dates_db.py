from __future__ import annotations

import json
from datetime import date

from src.db import dao
from src.db.base import Base, clear_engine_cache, get_engine
from src.domain.pipeline import compare_dates_db


def _square(lon: float, lat: float, size: float = 1.0) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lon, lat],
                [lon + size, lat],
                [lon + size, lat + size],
                [lon, lat + size],
                [lon, lat],
            ]
        ],
    }


def _fc(geom: dict) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": geom, "properties": {}}],
    }


def test_compare_dates_db_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "t.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    clear_engine_cache()

    engine = get_engine()
    Base.metadata.create_all(engine)

    d1 = date(2024, 1, 1)
    d2 = date(2024, 1, 2)

    prev = json.dumps(_fc(_square(0, 0, 1.0)))
    curr = json.dumps(_fc(_square(0.5, 0, 1.0)))

    dao.upsert_layer(clazz="occupied", d=d1, geojson_text=prev)
    dao.upsert_layer(clazz="occupied", d=d2, geojson_text=curr)

    items = compare_dates_db("2024_01_01", "2024_01_02", clazzes=("occupied",), min_area_km2=0.0)
    assert items
    assert {it["status"] for it in items} == {"gained", "lost"}
    assert all(it["direction"] == "occupied" for it in items)
