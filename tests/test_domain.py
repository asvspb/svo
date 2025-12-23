from src.domain import geo_changes


def test_compute_changes_returns_list():
    res = geo_changes.compute_changes('{"type":"FeatureCollection","features":[]}', '{"type":"FeatureCollection","features":[]}')
    assert isinstance(res, list)
