from eagleeye.interfaces.web.app435 import create_workspace_app435
from eagleeye.interfaces.web.server import serve_workspace

# Windows/macOS multiprocessing "spawn" re-imports the launcher as __mp_main__.
# Never construct the full EagleEye application in that child bootstrap path.
app = None
if __name__ not in {'__main__','__mp_main__'}:
    app = create_workspace_app435()

if __name__ == '__main__':
    raise SystemExit(serve_workspace())
