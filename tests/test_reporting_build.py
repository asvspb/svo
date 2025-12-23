from src.reporting.report_generator import build_telegram_report


def test_report_empty():
    assert "без существенных" in build_telegram_report([])


def test_report_top3():
    items = [
        {"direction": "occupied", "settlement": "TownA", "status": "gained", "area_km2": 1.2, "centroid": (0, 0)},
        {"direction": "gray", "settlement": "TownB", "status": "lost", "area_km2": 0.7, "centroid": (0, 0)},
        {"direction": "occupied", "settlement": "TownC", "status": "gained", "area_km2": 2.1, "centroid": (0, 0)},
        {"direction": "gray", "settlement": "TownD", "status": "lost", "area_km2": 0.2, "centroid": (0, 0)},
    ]
    text = build_telegram_report(items)
    assert "ТОП-3" in text
    assert "TownC" in text  # largest
    assert "TownA" in text  # second largest
