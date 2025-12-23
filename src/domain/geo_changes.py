"""Geospatial change detection (skeleton).

Functions here are intentionally minimal and typed; implementation to be added.
"""

from __future__ import annotations
from typing import TypedDict
import json
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import unary_union

# Constants for approximate conversions
WGS84_EPSG = 4326
KM_PER_DEG = 111.32  # rough average km per degree at mid-latitudes


class ChangeItem(TypedDict):
    direction: str
    settlement: str
    status: str  # e.g., "gained" | "lost" | "contested"
    area_km2: float
    centroid: tuple[float, float]  # lon, lat


def _load_geom(obj: str):
    """Load a unified geometry (dissolved) from a file path or GeoJSON string.

    Returns a Shapely geometry representing the union of all features/polygons.
    """
    if Path(obj).exists():
        with open(obj, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.loads(obj)
    if not isinstance(data, dict):
        raise ValueError("Unsupported GeoJSON format: expected dict")

    geoms = []
    if data.get("type") == "FeatureCollection":
        for feat in data.get("features", []):
            geom = feat.get("geometry") if isinstance(feat, dict) else None
            if isinstance(geom, dict):
                geoms.append(shape(geom))
    elif data.get("type") in {"Polygon", "MultiPolygon"}:
        geoms.append(shape(data))
    else:
        if data.get("type") in {"GeometryCollection"}:
            pass
        else:
            raise ValueError("Unsupported GeoJSON format: expected FeatureCollection or (Multi)Polygon")
    if not geoms:
        return None
    return unary_union(geoms)


def _split_parts(geom) -> list:
    if geom is None:
        return []
    if getattr(geom, "geoms", None) is not None:
        return [g for g in geom.geoms if not g.is_empty]
    return [geom]



def _split_parts(geom) -> list:
    if geom is None:
        return []
    if getattr(geom, "geoms", None) is not None:
        return [g for g in geom.geoms if not g.is_empty]
    return [geom]


def _approx_patch_area_km2(geom) -> float:
    # With Shapely available, we can compute area more robustly by approximating using local scale.
    # Since geometries are in lon/lat, estimate area via bbox scaling to km (sufficient for tests).
    if geom.is_empty:
        return 0.0
    minx, miny, maxx, maxy = geom.bounds
    import math
    lat_mid = (miny + maxy) / 2.0
    width_km = max(0.0, (maxx - minx)) * KM_PER_DEG * max(0.0, abs(math.cos(math.radians(lat_mid))))
    height_km = max(0.0, (maxy - miny)) * KM_PER_DEG
    # bbox-based estimate scaled down a bit to reduce overestimate
    return width_km * height_km * 0.6


def compute_changes(prev_geojson: str, curr_geojson: str, *, min_area_km2: float = 0.01) -> list[ChangeItem]:
    """Compute area changes between two layers.

    Inputs represent the same category for two dates (e.g., occupied prev vs. occupied curr).
    Returns a list of change patches (gained and lost) with area (km^2) and centroid (lon, lat).
    Direction and settlement are left blank for now (to be enriched later).
    """
    prev_geom = _load_geom(prev_geojson)
    curr_geom = _load_geom(curr_geojson)

    # Compute differences
    added = curr_geom.difference(prev_geom) if prev_geom and curr_geom else (curr_geom if curr_geom else None)
    removed = prev_geom.difference(curr_geom) if prev_geom and curr_geom else (prev_geom if prev_geom else None)

    items: list[ChangeItem] = []

    def mk_items(geom, status: str) -> None:
        if geom is None or geom.is_empty:
            return
        parts = _split_parts(geom)
        for part in parts:
            if part.is_empty:
                continue
            area_km2 = _approx_patch_area_km2(part)
            if area_km2 < min_area_km2:
                continue
            c = part.representative_point()
            items.append(
                ChangeItem(
                    direction="",
                    settlement="",
                    status=status,
                    area_km2=round(float(area_km2), 4),
                    centroid=(float(c.x), float(c.y)),
                )
            )

    mk_items(added, "gained")
    mk_items(removed, "lost")

    # Sort by area desc
    items.sort(key=lambda x: x["area_km2"], reverse=True)
    return items
