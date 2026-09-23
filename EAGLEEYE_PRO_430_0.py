from eagleeye.interfaces.web.app430 import create_workspace_app430
from eagleeye.interfaces.web.server import serve_workspace
app=create_workspace_app430()
if __name__=='__main__':
 raise SystemExit(serve_workspace())
