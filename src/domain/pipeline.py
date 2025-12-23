from __future__ import annotations
from typing import Iterable, Optional
from pathlib import Path
import re
import json

from src.domain.geo_changes import compute_changes, ChangeItem
from src.domain.nearest import load_gazetteer_csv, nearest_from_gazetteer, reverse_geocode_geopy
from src.reporting.report_generator import build_telegram_report
from src.db.dao import insert_changes, insert_report

CLASSES = ("occupied", "gray")


def _find_layer_files(root: str, clazz: str) -> list[Path]:
    root_p = Path(root)
    pattern = re.compile(rf"layer_{re.escape(clazz)}_\d{{4}}_\d{{2}}_\d{{2}}\.geojson$")
    files = [p for p in root_p.rglob("*.geojson") if pattern.search(p.name)]
    return sorted(files)


def compare_latest(data_root: str, *, gazetteer_csv: Optional[str] = None) -> list[ChangeItem]:
    """Compare the two latest dates per class (occupied/gray) and return merged changes.

    - Looks for files named layer_<class>_YYYY_MM_DD.geojson under data_root/ (any subfolders)
    - For each class, takes the two most recent files and computes changes
    - Optionally enriches with nearest settlement from a CSV gazetteer; otherwise tries reverse geocoding
    """
    all_items: list[ChangeItem] = []
    gaz_gdf = load_gazetteer_csv(gazetteer_csv) if gazetteer_csv else None

    selected: dict[str, tuple[Path, Path]] = {}
    for clazz in CLASSES:
        files = _find_layer_files(data_root, clazz)
        if len(files) < 2:
            continue
        prev, curr = files[-2], files[-1]
        selected[clazz] = (prev, curr)
        items = compute_changes(str(prev), str(curr))
        # enrich items: set status already contains gained/lost; fill settlement via gazetteer or reverse geocoding
        for it in items:
            lon, lat = it["centroid"]
            name = None
            if gaz_gdf is not None:
                res = nearest_from_gazetteer(lon, lat, gaz_gdf)
                if res:
                    name = res[0]
            if not name:
                name = reverse_geocode_geopy(lon, lat) or ""
            it["settlement"] = name
            it["direction"] = clazz
        all_items.extend(items)

    # sort aggregated by area desc
    all_items.sort(key=lambda x: x["area_km2"], reverse=True)
    return all_items
