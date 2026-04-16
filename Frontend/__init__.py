"""Frontend package bootstrap for stable local imports."""

from pathlib import Path
import sys

_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_DIR.parent
_BACKEND_DIR = _PROJECT_ROOT / "BackEnd"

for _path in (_PROJECT_ROOT, _BACKEND_DIR, _PACKAGE_DIR):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)
