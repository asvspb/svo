from __future__ import annotations
from typing import Optional, Tuple
import geopandas as gpd
from shapely.geometry import Point

try:
    from geopy.geocoders import Nominatim  # optional external geocoder
except Exception:  # pragma: no cover
    Nominatim = None  # type: ignore


def load_gazetteer_csv(path: str, name_col: str = "name", lon_col: str = "lon", lat_col: str = "lat") -> gpd.GeoDataFrame:
    """Load a simple gazetteer CSV with columns: name, lon, lat -> GeoDataFrame in WGS84."""
    df = gpd.pd.read_csv(path)
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
        crs="EPSG:4326",
    )
    return gdf[[name_col, "geometry"]].rename(columns={name_col: "name"})


def nearest_from_gazetteer(lon: float, lat: float, gazetteer: gpd.GeoDataFrame) -> Optional[Tuple[str, float]]:
    """Find nearest settlement in a provided gazetteer. Returns (name, distance_km)."""
    if gazetteer is None or gazetteer.empty:
        return None
    pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")
    # project to metric CRS for distance (approx)
    pt_m = pt.to_crs(epsg=6933).iloc[0]
    gaz_m = gazetteer.to_crs(epsg=6933)
    # use spatial index for speed
    sidx = gaz_m.sindex
    cand_idx = list(sidx.nearest(pt_m.bounds, num_results=1))
    if not cand_idx:
        return None
    cand = gaz_m.iloc[cand_idx[0]]
    dist_km = float(cand.geometry.distance(pt_m)) / 1000.0
    return str(cand["name"]), dist_km


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
