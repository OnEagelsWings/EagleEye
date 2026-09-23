from eagleeye.interfaces.web.app433 import create_workspace_app433
from eagleeye.interfaces.web.server import serve_workspace
app=create_workspace_app433()
if __name__=='__main__':
 raise SystemExit(serve_workspace())
