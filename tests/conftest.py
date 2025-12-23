# Ensure the 'src' directory is importable as a top-level package for tests
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Ensure project root is on sys.path so 'src' package is importable
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
