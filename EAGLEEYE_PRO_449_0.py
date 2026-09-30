from eagleeye.interfaces.web.app449 import create_workspace_app449
from eagleeye.interfaces.web.server import serve_workspace

app = None
if __name__ not in {"__main__", "__mp_main__"}:
    app = create_workspace_app449()
if __name__ == "__main__":
    raise SystemExit(serve_workspace())
