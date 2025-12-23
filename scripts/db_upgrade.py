#!/usr/bin/env python3
from __future__ import annotations
import subprocess
import sys

if __name__ == "__main__":
    # Simple wrapper to run Alembic upgrade head
    sys.exit(subprocess.call([sys.executable, "-m", "alembic", "upgrade", "head"]))
