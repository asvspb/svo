"""Geospatial change detection.

This module computes patch-level differences (gained/lost) between two daily layers.

Quality improvements over the initial skeleton:
- Robust loading of GeoJSON (FeatureCollection / (Multi)Polygon)
- Geometry validation/repair (make_valid / buffer(0) fallback)
- Area computation in km^2 using a local UTM projection (pyproj) when available

Note: direction/settlement enrichment is done by the pipeline layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from shapely.geometry import shape
from shapely.ops import transform, unary_union

try:
    from shapely.validation import make_valid  # Shapely >= 2
except Exception:  # pragma: no cover
    make_valid = None  # type: ignore[assignment]

try:
    import pyproj
except Exception:  # pragma: no cover
    pyproj = None  # type: ignore[assignment]

WGS84_EPSG = 4326


class ChangeItem(TypedDict, total=False):
    direction: str
    settlement: str
    settlement_distance_km: float
    status: str  # "gained" | "lost"
    area_km2: float
    centroid: tuple[float, float]  # lon, lat


def _load_geom(obj: str):
    """Load a unified geometry (dissolved) from a file path or GeoJSON string."""

    # `obj` can be either a filesystem path or a GeoJSON string.
    # Avoid calling Path(...).exists() on a long JSON string (can raise OSError on some OSes).
    is_probably_path = (
        "{" not in obj
        and "\n" not in obj
        and len(obj) < 300
    )
    if is_probably_path:
        try:
            p = Path(obj)
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = json.loads(obj)
        except OSError:
            data = json.loads(obj)
    else:
        data = json.loads(obj)

    if not isinstance(data, dict):
        raise ValueError("Unsupported GeoJSON format: expected dict")

    geoms = []
    t = data.get("type")

    if t == "FeatureCollection":
        for feat in data.get("features", []):
            geom = feat.get("geometry") if isinstance(feat, dict) else None
            if isinstance(geom, dict):
                geoms.append(shape(geom))
    elif t in {"Polygon", "MultiPolygon"}:
        geoms.append(shape(data))
    else:
        # ignore empty/unsupported collections
        if t not in {"GeometryCollection"}:
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


def _fix_validity(geom):
    """Make geometry valid for overlay operations when possible."""

    if geom is None:
        return None
    if geom.is_empty:
        return geom

    # Shapely 2: make_valid can return a GeometryCollection
    try:
        if make_valid is not None:
            geom = make_valid(geom)
    except Exception:
        pass

    # Fallback: buffer(0) fixes many self-intersections
    try:
        if hasattr(geom, "is_valid") and not geom.is_valid:
            geom = geom.buffer(0)
    except Exception:
        pass

    return geom


def _local_utm_epsg(lon: float, lat: float) -> int:
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def _area_km2(geom) -> float:
    """Compute area in km^2.

    Prefer local UTM meters-based area if pyproj is available.
    Fallback to a rough lon/lat conversion otherwise.
    """

    if geom is None or geom.is_empty:
        return 0.0

    geom = _fix_validity(geom)
    if geom is None or geom.is_empty:
        return 0.0

    if pyproj is not None:
        c = geom.representative_point()
        epsg = _local_utm_epsg(float(c.x), float(c.y))
        try:
            transformer = pyproj.Transformer.from_crs(
                f"EPSG:{WGS84_EPSG}", f"EPSG:{epsg}", always_xy=True
            ).transform
            g_m = transform(transformer, geom)
            return float(g_m.area) / 1_000_000.0
        except Exception:
            pass

    # Fallback: approximate using km per degree at mid-lat
    minx, miny, maxx, maxy = geom.bounds
    import math

    lat_mid = (miny + maxy) / 2.0
    km_per_deg_lat = 110.574
    km_per_deg_lon = 111.320 * abs(math.cos(math.radians(lat_mid)))
    width_km = max(0.0, (maxx - minx)) * km_per_deg_lon
    height_km = max(0.0, (maxy - miny)) * km_per_deg_lat
    return width_km * height_km


def compute_changes(
    prev_geojson: str,
    curr_geojson: str,
    *,
    min_area_km2: float = 0.01,
    cluster_distance_km: float | None = None,
) -> list[ChangeItem]:
    """Compute patch-level changes between two same-category layers.

    Returns gained and lost patches with centroid (lon,lat) and area_km2.
    """

    prev_geom = _fix_validity(_load_geom(prev_geojson))
    curr_geom = _fix_validity(_load_geom(curr_geojson))

    # Compute differences (handle missing geometries)
    if prev_geom is None and curr_geom is None:
        return []

    if prev_geom is None:
        added = curr_geom
        removed = None
    elif curr_geom is None:
        added = None
        removed = prev_geom
    else:
        added = curr_geom.difference(prev_geom)
        removed = prev_geom.difference(curr_geom)

    items: list[ChangeItem] = []

    def _cluster_parts(parts: list, *, dist_km: float) -> list:
        if not parts:
            return []
        # If pyproj is unavailable, fall back to centroid-distance clustering in lon/lat.
        if pyproj is None:
            import math

            cent = [p.representative_point() for p in parts]
            n = len(cent)
            parent = list(range(n))

            def find(i: int) -> int:
                while parent[i] != i:
                    parent[i] = parent[parent[i]]
                    i = parent[i]
                return i

            def union(i: int, j: int) -> None:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri

            def hav_km(a, b) -> float:
                # haversine
                lon1, lat1 = float(a.x), float(a.y)
                lon2, lat2 = float(b.x), float(b.y)
                dlon = math.radians(lon2 - lon1)
                dlat = math.radians(lat2 - lat1)
                x = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
                c = 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x))
                return 6371.0 * c

            for i in range(n):
                for j in range(i + 1, n):
                    if hav_km(cent[i], cent[j]) <= float(dist_km):
                        union(i, j)

            groups: dict[int, list] = {}
            for i in range(n):
                groups.setdefault(find(i), []).append(parts[i])

            return [unary_union(mems) for mems in groups.values()]
        all_union = unary_union(parts)
        c0 = all_union.representative_point()
        epsg = _local_utm_epsg(float(c0.x), float(c0.y))
        try:
            to_m = pyproj.Transformer.from_crs(f"EPSG:{WGS84_EPSG}", f"EPSG:{epsg}", always_xy=True).transform
            to_ll = pyproj.Transformer.from_crs(f"EPSG:{epsg}", f"EPSG:{WGS84_EPSG}", always_xy=True).transform
            buf_m = float(dist_km) * 1000.0
            parts_m = [transform(to_m, p) for p in parts]

            # Cluster by centroid distance (connected components in a proximity graph).
            centroids = [p.representative_point() for p in parts_m]
            n = len(parts_m)
            parent = list(range(n))

            def find(i: int) -> int:
                while parent[i] != i:
                    parent[i] = parent[parent[i]]
                    i = parent[i]
                return i

            def union(i: int, j: int) -> None:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri

            for i in range(n):
                for j in range(i + 1, n):
                    if centroids[i].distance(centroids[j]) <= buf_m:
                        union(i, j)

            groups: dict[int, list] = {}
            for i in range(n):
                groups.setdefault(find(i), []).append(parts_m[i])

            clustered_ll = [transform(to_ll, unary_union(mems)) for mems in groups.values()]
            return clustered_ll
        except Exception:
            return parts

    def mk_items(geom, status: str) -> None:
        if geom is None or geom.is_empty:
            return
        parts = _split_parts(geom)
        if cluster_distance_km is not None and cluster_distance_km > 0:
            parts = _cluster_parts(parts, dist_km=float(cluster_distance_km))
        for part in parts:
            if part.is_empty:
                continue
            area_km2 = _area_km2(part)
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

    items.sort(key=lambda x: x["area_km2"], reverse=True)
    return items
