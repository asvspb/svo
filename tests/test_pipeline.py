import json
from pathlib import Path

from src.domain.pipeline import compare_latest


def test_compare_latest_no_files(tmp_path: Path):
    items = compare_latest(str(tmp_path))
    assert items == []
