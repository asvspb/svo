import json
from pathlib import Path

from src.data_io.history_index import parse_history_entries, save_index, load_index


def test_parse_history_entries_variants():
    raw_list = [{"id": 123, "timestamp": 1000}, {"id": 124, "timestamp": 2000}]
    entries = parse_history_entries(raw_list)
    assert [e.id for e in entries] == [123, 124]

    raw_dict_items = {"items": [{"timestamp": 10}, {"timestamp": 20}]}
    entries2 = parse_history_entries(raw_dict_items)
    assert [e.timestamp for e in entries2] == [10, 20]


def test_save_and_load_index(tmp_path: Path):
    entries = parse_history_entries([{"id": 7, "timestamp": 1700000000}])
    out = save_index(entries, data_root=str(tmp_path))
    assert out.exists()
    loaded = load_index(data_root=str(tmp_path))
    assert len(loaded) == 1
    assert loaded[0].id == 7
