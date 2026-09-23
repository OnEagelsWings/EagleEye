from eagleeye.interfaces.web.app436 import create_workspace_app436
from eagleeye.interfaces.web.server import serve_workspace
app=create_workspace_app436()
if __name__=='__main__':
 raise SystemExit(serve_workspace())
