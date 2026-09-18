from __future__ import annotations
from pathlib import Path
from eagleeye.interfaces.web.server import serve_workspace

if __name__ == "__main__":
    raise SystemExit(serve_workspace(base_dir=Path(__file__).resolve().parent))
