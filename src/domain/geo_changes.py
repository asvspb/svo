"""Geospatial change detection (skeleton).

Functions here are intentionally minimal and typed; implementation to be added.
"""

from __future__ import annotations
from typing import Iterable, TypedDict


class ChangeItem(TypedDict):
    direction: str
    settlement: str
    status: str  # e.g., "advancement_rf" | "contested"
    area_km2: float
    centroid: tuple[float, float]  # lon, lat


def compute_changes(prev_geojson: str, curr_geojson: str) -> list[ChangeItem]:
    """Compute polygon diffs between two GeoJSON strings.

    TODO:
    - Parse GeoJSON into GeoDataFrames (geopandas)
    - Ensure CRS is set and project to equal-area CRS for area calculations
    - Compute differences per class (occupied/gray)
    - Calculate centroids and nearest settlements
    - Map to ChangeItem list
    """
    raise NotImplementedError
