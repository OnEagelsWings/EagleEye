"""Standalone Windows entry point for the public-topic Research Bridge (RC).

Local-only initialization; no background network activity. --self-test runs
without reading private Git records or opening user data.
"""
import argparse
import os
from pathlib import Path
import sys

VERSION = "1.0.0-rc3"


def main(argv=None):
    parser = argparse.ArgumentParser(description="EagleEye public-topic Research Bridge")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if os.name != "nt":
        return 3
    # Checks using the same modules the GUI will import, but no network.
    from bridge import validate
    from desktop_workflow import DesktopWorkflow
    from desktop_ui import ResearchBridgeWindow
    if args.self_test:
        raw = (b'{"schema":1,"id":"00000000-0000-4000-8000-000000000001",'
               b'"kind":"research_request","classification":"public-topic",'
               b'"topic":"synthetic","summary":"synthetic",'
               b'"sources":[],"synthetic":true}')
        assert validate(raw)["synthetic"] is True
        import tkinter as tk
        app = tk.Tk()
        app.withdraw()
        app.update_idletasks()
        app.destroy()
        return 0
    from install_local import prepare_local
    root = Path(os.environ["LOCALAPPDATA"]) / "EagleEyeResearchBridge"
    prepare_local(root)
    ResearchBridgeWindow(root).mainloop()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Never print key contents or silently send diagnostics.
        import traceback
        traceback.print_exc()
        sys.exit(1)
