from __future__ import annotations
import json
import gzip
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib import request

from src.core.config import settings

DEFAULT_BASE_URL = "https://deepstatemap.live"


@dataclass(frozen=True)
class LayerSavePaths:
    root: Path
    date_dir: Path
    file_path: Path


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _build_save_paths(date_str: str, clazz: str, data_root: Optional[str] = None) -> LayerSavePaths:
    root = Path(data_root or settings.DATA_ROOT)
    date_dir = root / "history" / date_str[:4] / date_str[5:7]
    _ensure_dir(date_dir)
    file_name = f"layer_{clazz}_{date_str}.geojson"
    return LayerSavePaths(root=root, date_dir=date_dir, file_path=date_dir / file_name)


def fetch_history_layer(history_id: int, base_url: str = DEFAULT_BASE_URL, timeout: int = 60) -> dict:
    """Fetch GeoJSON for a given history id.

    Endpoint pattern: /api/history/{ID}
    """
    url = base_url.rstrip("/") + f"/api/history/{history_id}"
    with request.urlopen(url, timeout=timeout) as resp:  # nosec - controlled URL
        charset = resp.headers.get_content_charset() or "utf-8"
        txt = resp.read().decode(charset)
        data = json.loads(txt)
        if not isinstance(data, dict) or data.get("type") not in {"FeatureCollection", "Feature"}:
            # Some payloads may be dictionaries with layers; accept them as-is.
            return data
        return data


def save_layer_geojson(data: dict, date_str: str, clazz: str, data_root: Optional[str] = None, *, gzip_copy: bool = True) -> Path:
    paths = _build_save_paths(date_str, clazz, data_root=data_root)
    txt = json.dumps(data, ensure_ascii=False)
    paths.file_path.write_text(txt, encoding="utf-8")
    if gzip_copy:
        gz = str(paths.file_path) + ".gz"
        with gzip.open(gz, "wt", encoding="utf-8") as f:
            f.write(txt)
    return paths.file_path
