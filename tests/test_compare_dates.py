from pathlib import Path
import json
from src.domain.pipeline import compare_dates


def test_compare_dates_no_files(tmp_path: Path):
    items = compare_dates(str(tmp_path), "2024_01_01", "2024_01_02")
    assert items == []
