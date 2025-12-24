import json

from src.domain.geo_changes import compute_changes


def bowtie():
    # self-intersecting polygon (invalid)
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [0, 0],
                [1, 1],
                [1, 0],
                [0, 1],
                [0, 0],
            ]
        ],
    }


def fc(geom):
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": geom, "properties": {}}]}


def test_compute_changes_invalid_geom_does_not_crash():
    prev = json.dumps(fc(bowtie()))
    curr = json.dumps(fc({"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}))
    items = compute_changes(prev, curr, min_area_km2=0.0)
    assert isinstance(items, list)


def test_compute_changes_empty_featurecollection():
    prev = json.dumps({"type": "FeatureCollection", "features": []})
    curr = json.dumps({"type": "FeatureCollection", "features": []})
    items = compute_changes(prev, curr, min_area_km2=0.0)
    assert items == []
