from pathlib import Path
import json

from src.data_io.history_fetcher import save_layer_geojson


def test_save_layer_geojson(tmp_path: Path):
    data = {"type": "FeatureCollection", "features": []}
    out = save_layer_geojson(data, date_str="2024_01_01", clazz="occupied", data_root=str(tmp_path), gzip_copy=True)
    assert out.exists()
    gz = Path(str(out) + ".gz")
    assert gz.exists()
    txt = Path(out).read_text(encoding="utf-8")
    assert json.loads(txt)["type"] == "FeatureCollection"
