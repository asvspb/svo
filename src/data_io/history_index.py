from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib import request

from src.core.config import settings

DEFAULT_BASE_URL = "https://deepstatemap.live"
INDEX_RELATIVE_PATH = "history/index.json"


@dataclass(frozen=True)
class HistoryEntry:
    id: int
    timestamp: int  # unix seconds

    @property
    def date(self) -> str:
        dt = datetime.fromtimestamp(self.timestamp, tz=timezone.utc)
        return dt.strftime("%Y_%m_%d")


def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def save_index(entries: Iterable[HistoryEntry], data_root: Optional[str] = None) -> Path:
    root = Path(data_root or settings.DATA_ROOT)
    out_path = root / INDEX_RELATIVE_PATH
    _ensure_dir(out_path)
    serial = [{"id": e.id, "timestamp": e.timestamp, "date": e.date} for e in entries]
    out_path.write_text(json.dumps(serial, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def load_index(data_root: Optional[str] = None) -> list[HistoryEntry]:
    root = Path(data_root or settings.DATA_ROOT)
    in_path = root / INDEX_RELATIVE_PATH
    if not in_path.exists():
        return []
    data = json.loads(in_path.read_text(encoding="utf-8"))
    out: list[HistoryEntry] = []
    for row in data:
        try:
            out.append(HistoryEntry(id=int(row["id"]), timestamp=int(row["timestamp"])) )
        except Exception:
            continue
    return out


def fetch_history_json(base_url: str = DEFAULT_BASE_URL, endpoint: Optional[str] = None, timeout: int = 30) -> Any:
    """
    Fetch raw history JSON from DeepStateMap.

    The exact endpoint may vary; allow caller to override via `endpoint`.
    Common possibilities include '/api/history' or '/api/history/index'.
    """
    url = endpoint or (base_url.rstrip("/") + "/api/history")
    with request.urlopen(url, timeout=timeout) as resp:  # nosec - controlled URL
        charset = resp.headers.get_content_charset() or "utf-8"
        txt = resp.read().decode(charset)
        return json.loads(txt)


def parse_history_entries(raw: Any) -> list[HistoryEntry]:
    """
    Parse history listing payloads.
    Expected shapes (examples):
      - [ {"id": 1705524300, ...}, ... ]
      - [ {"timestamp": 1705524300, ...}, ... ]
      - { "items": [ ... ] }
    We'll pick the first field that looks like an integer timestamp/id.
    """
    items: list[Any]
    if isinstance(raw, dict):
        # pick first list in dict, or 'items'
        if isinstance(raw.get("items"), list):
            items = raw["items"]
        else:
            # fallback: find first list value
            items = next((v for v in raw.values() if isinstance(v, list)), [])
    elif isinstance(raw, list):
        items = raw
    else:
        return []

    out: list[HistoryEntry] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        ts = it.get("timestamp") or it.get("id") or it.get("time")
        try:
            ts_i = int(ts)
        except Exception:
            continue
        # if there is a separate numeric id, prefer that for id, else use ts
        id_val = it.get("id")
        try:
            id_i = int(id_val) if id_val is not None else ts_i
        except Exception:
            id_i = ts_i
        out.append(HistoryEntry(id=id_i, timestamp=ts_i))
    # sort ascending by timestamp
    out.sort(key=lambda e: e.timestamp)
    return out


def refresh_index(base_url: str = DEFAULT_BASE_URL, endpoint: Optional[str] = None, data_root: Optional[str] = None) -> Path:
    raw = fetch_history_json(base_url=base_url, endpoint=endpoint)
    entries = parse_history_entries(raw)
    return save_index(entries, data_root=data_root)
