from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
for path in (ROOT, SRC):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)
os.chdir(ROOT)


def _write_failure(message: str) -> Path:
    logs = ROOT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    target = logs / "startup_latest.log"
    target.write_text(message, encoding="utf-8")
    return target


def _runtime_preflight() -> None:
    required = {
        "fastapi": "fastapi", "starlette": "starlette", "uvicorn": "uvicorn", "pydantic": "pydantic",
        "sqlalchemy": "sqlalchemy", "alembic": "alembic", "cryptography": "cryptography", "PIL": "Pillow",
        "cv2": "opencv-python-headless", "reportlab": "reportlab", "argon2": "argon2-cffi", "multipart": "python-multipart", "fitz": "PyMuPDF", "pypdf": "pypdf", "pdfplumber": "pdfplumber", "pytesseract": "pytesseract",
    }
    missing=[]
    for module,package in required.items():
        try: __import__(module)
        except Exception as exc: missing.append(f"{package} ({type(exc).__name__}: {exc})")
    if missing: raise RuntimeError("Lokale EagleEye-Laufzeit unvollstaendig: " + "; ".join(missing) + ". Unter Windows bitte SETUP_EAGLEEYE_WINDOWS.bat starten und danach START_EAGLEEYE_PRO.bat verwenden.")


def run() -> int:
    try:
        if sys.version_info < (3,11):
            raise RuntimeError(f"Python 3.11 oder neuer erforderlich; gefunden: {sys.version.split()[0]}")
        _runtime_preflight()
        from eagleeye.interfaces.cli.main import main
        forwarded=list(sys.argv[1:])
        if forwarded:
            if "--base-dir" not in forwarded: forwarded.extend(["--base-dir",str(ROOT)])
            return int(main(forwarded))
        print("[EagleEye] Starte lokalen Workspace ...",flush=True)
        print("[EagleEye] Der robuste Windows-Startpfad aus 334.1 bleibt aktiv.",flush=True)
        return int(main(["--serve","--open-browser","--browser","firefox","--host","127.0.0.1","--port","8765","--base-dir",str(ROOT)]))
    except KeyboardInterrupt: return 0
    except Exception:
        path=_write_failure("EAGLEEYE BUILD 365.0 OPERATIONS START FAILED\n\n"+traceback.format_exc())
        print(f"EagleEye konnte nicht gestartet werden. Diagnose: {path}",file=sys.stderr,flush=True)
        return 1

if __name__ == "__main__":
    raise SystemExit(run())
