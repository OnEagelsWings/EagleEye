from __future__ import annotations

from pathlib import Path
import sys

# Allow EagleEye to run directly from a fresh source checkout without requiring
# an editable install first. The canonical Python package lives under src/.
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
for entry in (SRC, ROOT):
    value = str(entry)
    if value not in sys.path:
        sys.path.insert(0, value)

try:
    from eagleeye.interfaces.web.server import serve_workspace
except ModuleNotFoundError as exc:
    missing = exc.name or "a required dependency"
    raise SystemExit(
        f"EagleEye cannot start because {missing!r} is not installed.\n"
        "Install the runtime first with:  python -m pip install -e .\n"
        "Python 3.11 or newer is required."
    ) from exc


if __name__ == "__main__":
    raise SystemExit(serve_workspace(base_dir=ROOT, open_browser=True))
