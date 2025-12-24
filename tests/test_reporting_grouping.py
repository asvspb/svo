from src.reporting.report_generator import build_telegram_report


def test_build_report_groups_by_settlement():
    items = [
        {"direction": "occupied", "settlement": "A", "settlement_distance_km": 1.2, "status": "gained", "area_km2": 1.0, "centroid": (0.0, 0.0)},
        {"direction": "occupied", "settlement": "A", "settlement_distance_km": 0.8, "status": "gained", "area_km2": 0.5, "centroid": (0.1, 0.0)},
        {"direction": "occupied", "settlement": "B", "status": "lost", "area_km2": 2.0, "centroid": (1.0, 1.0)},
    ]
    text = build_telegram_report(items)
    # should mention A once in top section due to grouping
    assert text.count("A") <= 2
    assert "Топ населённых пунктов" in text
