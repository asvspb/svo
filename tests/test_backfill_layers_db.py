from __future__ import annotations

import json
from datetime import date

from src.db.base import Base, clear_engine_cache, get_engine
from src.db import dao


def test_upsert_layer_and_exists_sqlite(tmp_path, monkeypatch):
    # Use a file-based sqlite DB to persist across engine creations
    db_path = tmp_path / "t.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    clear_engine_cache()

    engine = get_engine()
    Base.metadata.create_all(engine)

    d = date(2024, 1, 1)
    payload = {"type": "FeatureCollection", "features": []}
    lid1 = dao.upsert_layer(clazz="occupied", d=d, geojson_text=json.dumps(payload))
    assert isinstance(lid1, int)
    assert dao.layer_exists(clazz="occupied", d=d)

    # idempotent: same checksum => same row
    lid2 = dao.upsert_layer(clazz="occupied", d=d, geojson_text=json.dumps(payload))
    assert lid2 == lid1
