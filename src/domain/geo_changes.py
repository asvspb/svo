"""Geospatial change detection (skeleton).

Functions here are intentionally minimal and typed; implementation to be added.
"""

from __future__ import annotations
from typing import Iterable, TypedDict, Any
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely import force_2d

# Equal-area CRS suitable for large regions
EQUAL_AREA_EPSG = 6933  # NSIDC EASE-Grid 2.0 Global
WGS84_EPSG = 4326


class ChangeItem(TypedDict):
    direction: str
    settlement: str
    status: str  # e.g., "gained" | "lost" | "contested"
    area_km2: float
    centroid: tuple[float, float]  # lon, lat


def _to_gdf(obj: str) -> gpd.GeoDataFrame:
    """Load a GeoDataFrame from a path to file or a GeoJSON string."""
    if Path(obj).exists():
        gdf = gpd.read_file(obj)
    else:
        data = json.loads(obj)
        if isinstance(data, dict) and data.get("type") == "FeatureCollection":
            gdf = gpd.GeoDataFrame.from_features(data["features"], crs=f"EPSG:{WGS84_EPSG}")
        elif isinstance(data, dict) and data.get("type") in {"Polygon", "MultiPolygon"}:
            gdf = gpd.GeoDataFrame(geometry=[shape(data)], crs=f"EPSG:{WGS84_EPSG}")
        else:
            raise ValueError("Unsupported GeoJSON format: expected FeatureCollection or (Multi)Polygon")
    if gdf.crs is None:
        gdf.set_crs(epsg=WGS84_EPSG, inplace=True)
    return gdf


def _clean_unary(gdf: gpd.GeoDataFrame) -> gpd.GeoSeries:
    geoms = [force_2d(geom).buffer(0) for geom in gdf.geometry if geom and not geom.is_empty]
    if not geoms:
        return gpd.GeoSeries([], crs=gdf.crs)
    return gpd.GeoSeries([unary_union(geoms)], crs=gdf.crs)


def _project(g: gpd.GeoSeries | gpd.GeoDataFrame, epsg: int) -> gpd.GeoSeries | gpd.GeoDataFrame:
    return g.to_crs(epsg=epsg)


def _split_parts(geom) -> list:
    if geom is None or geom.is_empty:
        return []
    if getattr(geom, "geoms", None) is not None:
        return [g for g in geom.geoms if not g.is_empty]
    return [geom]


def compute_changes(prev_geojson: str, curr_geojson: str, *, min_area_km2: float = 0.01) -> list[ChangeItem]:
    """Compute area changes between two layers.

    Inputs represent the same category for two dates (e.g., occupied prev vs. occupied curr).
    Returns a list of change patches (gained and lost) with area (km^2) and centroid (lon, lat).
    Direction and settlement are left blank for now (to be enriched later).
    """
    prev_gdf = _to_gdf(prev_geojson)
    curr_gdf = _to_gdf(curr_geojson)

    # Clean and dissolve
    prev_u = _clean_unary(prev_gdf)
    curr_u = _clean_unary(curr_gdf)

    # Compute additions (curr - prev) and removals (prev - curr)
    added = (curr_u.iloc[0].difference(prev_u.iloc[0]) if len(curr_u) and len(prev_u) else None)
    removed = (prev_u.iloc[0].difference(curr_u.iloc[0]) if len(curr_u) and len(prev_u) else None)

    items: list[ChangeItem] = []

    def mk_items(geom, status: str) -> None:
        if geom is None or geom.is_empty:
            return
        # Project to equal-area for area calculation
        gseries = gpd.GeoSeries([geom], crs=prev_gdf.crs).to_crs(epsg=EQUAL_AREA_EPSG)
        parts = _split_parts(gseries.iloc[0])
        for part in parts:
            if part.is_empty:
                continue
            area_km2 = float(part.area) / 1_000_000.0  # m^2 -> km^2
            if area_km2 < min_area_km2:
                continue
            # centroid in WGS84
            c_wgs = gpd.GeoSeries([part], crs=f"EPSG:{EQUAL_AREA_EPSG}").to_crs(epsg=EQUAL_AREA_EPSG).iloc[0].centroid
            # Back-project centroid to WGS84
            c_lonlat = gpd.GeoSeries([part], crs=f"EPSG:{EQUAL_AREA_EPSG}").to_crs(epsg=WGS84_EPSG).iloc[0].centroid
            items.append(
                ChangeItem(
                    direction="",
                    settlement="",
                    status=status,
                    area_km2=round(area_km2, 4),
                    centroid=(float(c_lonlat.x), float(c_lonlat.y)),
                )
            )

    mk_items(added, "gained")
    mk_items(removed, "lost")

    # Sort by area desc
    items.sort(key=lambda x: x["area_km2"], reverse=True)
    return items
