from src.reporting.report_generator import build_telegram_report

def test_build_report_empty():
    assert "без существенных изменений" in build_telegram_report([])
