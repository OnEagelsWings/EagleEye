from eagleeye.interfaces.web.app436 import create_workspace_app436
from eagleeye.interfaces.web.server import serve_workspace

# Multiprocessing "spawn" re-imports the launcher as __mp_main__.
# Do not construct the full workspace inside an isolated Tor worker child.
app = None
if __name__ not in {'__main__','__mp_main__'}:
    app = create_workspace_app436()

if __name__ == '__main__':
    raise SystemExit(serve_workspace())
