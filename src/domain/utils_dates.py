from __future__ import annotations
import re
from datetime import date
from pathlib import Path

_DATE_RE = re.compile(r"(\d{4})_(\d{2})_(\d{2})")

def date_from_filename(p: Path) -> date:
    m = _DATE_RE.search(p.name)
    if not m:
        raise ValueError(f"Cannot parse date from {p}")
    y, mth, d = map(int, m.groups())
    return date(y, mth, d)
