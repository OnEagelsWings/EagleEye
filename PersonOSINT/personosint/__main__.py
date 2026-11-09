"""Start: ``python -m personosint`` – öffnet die Oberfläche im Browser."""
from __future__ import annotations

import argparse
import threading
import webbrowser


def main() -> None:
    parser = argparse.ArgumentParser(description="EagleEye PersonOSINT starten")
    parser.add_argument("--host", default="127.0.0.1", help="Adresse (Standard: nur lokal erreichbar)")
    parser.add_argument("--port", type=int, default=8380)
    parser.add_argument("--data", default=None, help="Datenordner (Standard: Benutzerprofil)")
    parser.add_argument("--no-browser", action="store_true", help="Browser nicht automatisch öffnen")
    args = parser.parse_args()

    import uvicorn

    from .api import create_app

    app = create_app(args.data)
    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '::') else args.host}:{args.port}/"
    print(f"EagleEye PersonOSINT läuft unter {url}  (Daten: {app.state.platform.data_dir})  – Beenden mit Strg+C")
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
