from __future__ import annotations
from typing import Optional, Tuple, Any
try:
    import geopandas as gpd  # type: ignore
    from shapely.geometry import Point  # type: ignore
    _GEOS = True
except Exception:  # pragma: no cover
    gpd = None  # type: ignore
    Point = None  # type: ignore
    _GEOS = False

try:
    from geopy.geocoders import Nominatim  # optional external geocoder
except Exception:  # pragma: no cover
    Nominatim = None  # type: ignore


def load_gazetteer_csv(path: str, name_col: str = "name", lon_col: str = "lon", lat_col: str = "lat"):
    """Load a simple gazetteer CSV with columns: name, lon, lat -> GeoDataFrame in WGS84.

    If geopandas is unavailable, returns a list of tuples (name, lon, lat).
    """
    import pandas as pd  # lightweight dependency
    df = pd.read_csv(path)
    if _GEOS and gpd is not None:
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
            crs="EPSG:4326",
        )
        return gdf[[name_col, "geometry"]].rename(columns={name_col: "name"})
    # fallback: return simple list
    return list(zip(df[name_col].astype(str), df[lon_col].astype(float), df[lat_col].astype(float)))


def nearest_from_gazetteer(lon: float, lat: float, gazetteer) -> Optional[Tuple[str, float]]:
    """Find nearest settlement in a provided gazetteer. Returns (name, distance_km).

    Supports both GeoDataFrame and list[(name, lon, lat)] fallback.
    """
    if gazetteer is None:
        return None
    if _GEOS and gpd is not None and hasattr(gazetteer, "empty"):
        if gazetteer.empty:
            return None
        pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")
        pt_m = pt.to_crs(epsg=6933).iloc[0]
        gaz_m = gazetteer.to_crs(epsg=6933)
        sidx = gaz_m.sindex
        cand_idx = list(sidx.nearest(pt_m.bounds, num_results=1))
        if not cand_idx:
            return None
        cand = gaz_m.iloc[cand_idx[0]]
        dist_km = float(cand.geometry.distance(pt_m)) / 1000.0
        return str(cand["name"]), dist_km
    # fallback: brute-force in lat/lon using haversine approx
    import math
    best = None
    for name, lo, la in gazetteer:
        dlon = math.radians(lon - float(lo))
        dlat = math.radians(lat - float(la))
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat))*math.cos(math.radians(float(la))) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        R = 6371.0
        dist = R * c
        if best is None or dist < best[1]:
            best = (str(name), float(dist))
    return best


def reverse_geocode_geopy(lon: float, lat: float, user_agent: str = "deepstate-reports") -> Optional[str]:
    """Fallback reverse geocoding via geopy/Nominatim (if installed)."""
    if Nominatim is None:
        return None
    try:
        geolocator = Nominatim(user_agent=user_agent, timeout=10)
        location = geolocator.reverse((lat, lon), language="en")
        if not location:
            return None
        # try to extract settlement-like fields
        addr = location.raw.get("address", {})
        for key in ("town", "village", "city", "hamlet", "municipality"):
            if addr.get(key):
                return addr[key]
        return location.address
    except Exception:
        return None
