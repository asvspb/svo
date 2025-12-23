import json
from src.domain.geo_changes import compute_changes

# Simple square test: prev is 1x1 at origin, curr is 1x1 shifted by +0.5 lon (overlaps half)

def square(lon, lat, size=1.0):
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon, lat],
            [lon + size, lat],
            [lon + size, lat + size],
            [lon, lat + size],
            [lon, lat],
        ]]
    }


def featurecollection(geom):
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": geom, "properties": {}}]}


def test_compute_changes_basic():
    prev = json.dumps(featurecollection(square(0, 0, 1.0)))
    curr = json.dumps(featurecollection(square(0.5, 0, 1.0)))
    items = compute_changes(prev, curr, min_area_km2=0.0)
    # We expect both gained and lost patches (two patches total)
    assert any(it["status"] == "gained" for it in items)
    assert any(it["status"] == "lost" for it in items)
    # Areas should be positive
    assert all(it["area_km2"] > 0 for it in items)
