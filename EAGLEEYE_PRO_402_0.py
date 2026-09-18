from __future__ import annotations
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
for entry in (ROOT/'src',ROOT):
    v=str(entry)
    if v not in sys.path: sys.path.insert(0,v)
from eagleeye.interfaces.web.server import serve_workspace
if __name__ == '__main__': raise SystemExit(serve_workspace(base_dir=ROOT, open_browser=True))
