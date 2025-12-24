from __future__ import annotations

import json
from datetime import date

from src.db import dao
from src.db.base import Base, clear_engine_cache, get_engine
from src.domain.period import generate_period_report_db


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
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": geom, "properties": {}}]}


def test_period_report_db_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "t.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    clear_engine_cache()

    engine = get_engine()
    Base.metadata.create_all(engine)

    # Three consecutive days, with shifting polygon each day
    d1 = date(2024, 1, 1)
    d2 = date(2024, 1, 2)
    d3 = date(2024, 1, 3)

    dao.upsert_layer(clazz="occupied", d=d1, geojson_text=json.dumps(_fc(_square(0.0, 0.0, 1.0))))
    dao.upsert_layer(clazz="occupied", d=d2, geojson_text=json.dumps(_fc(_square(0.5, 0.0, 1.0))))
    dao.upsert_layer(clazz="occupied", d=d3, geojson_text=json.dumps(_fc(_square(1.0, 0.0, 1.0))))

    rep = generate_period_report_db("2024_01_01", "2024_01_03", clazzes=("occupied",), min_area_km2=0.0, top_n=5)

    assert rep.day_reports  # should have at least one day pair
    assert len(rep.day_reports) == 2  # 01->02 and 02->03
    assert "occupied" in rep.summary_by_dir
    assert rep.summary_by_dir["occupied"]["gained"] > 0
    assert rep.summary_by_dir["occupied"]["lost"] > 0

    # Second run should use cached summaries even if layers are removed.
    # Remove all layers (keep dates + summaries).
    from sqlalchemy import delete
    from src.db.models import Layer

    # Directly delete layers using SQLAlchemy Core.
    with engine.begin() as conn:
        conn.execute(delete(Layer))

    rep2 = generate_period_report_db("2024_01_01", "2024_01_03", clazzes=("occupied",), min_area_km2=0.0, top_n=5)
    assert rep2.day_reports
    assert rep2.summary_by_dir["occupied"]["gained"] > 0
