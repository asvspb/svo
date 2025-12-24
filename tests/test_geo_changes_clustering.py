import json

from src.domain.geo_changes import compute_changes


def fc(features):
    return {"type": "FeatureCollection", "features": features}


def feat(poly):
    return {"type": "Feature", "geometry": poly, "properties": {}}


def square(x, y, s=0.01):
    return {
        "type": "Polygon",
        "coordinates": [[[x, y], [x + s, y], [x + s, y + s], [x, y + s], [x, y]]],
    }


def test_clustering_merges_close_patches():
    # prev empty, curr has two tiny squares close to each other
    prev = json.dumps(fc([]))
    curr = json.dumps(fc([feat(square(30.0, 50.0)), feat(square(30.015, 50.0))]))

    # without clustering: likely 2 gained patches
    items_no = compute_changes(prev, curr, min_area_km2=0.0, cluster_distance_km=None)
    assert len([i for i in items_no if i["status"] == "gained"]) >= 2

    # with clustering distance should merge them into 1 (distance depends on projection)
    items_cl = compute_changes(prev, curr, min_area_km2=0.0, cluster_distance_km=5.0)
    gained = [i for i in items_cl if i["status"] == "gained"]
    assert len(gained) == 1
