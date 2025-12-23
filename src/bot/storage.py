from __future__ import annotations
from pathlib import Path
import json
from typing import Set

DEFAULT_PATH = Path("data/subscribers.json")


def load_subscribers(path: Path = DEFAULT_PATH) -> Set[int]:
    try:
        if not path.exists():
            return set()
        data = json.loads(path.read_text(encoding="utf-8"))
        return {int(x) for x in data}
    except Exception:
        return set()


def save_subscribers(subs: Set[int], path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(list(subs))), encoding="utf-8")
