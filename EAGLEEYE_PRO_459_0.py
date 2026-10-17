from eagleeye.interfaces.web.app459 import create_workspace_app459
from eagleeye.interfaces.web.server import serve_workspace

app=None
if __name__ not in {"__main__","__mp_main__"}:
    app=create_workspace_app459()
if __name__=="__main__":
    raise SystemExit(serve_workspace())
