from eagleeye.interfaces.web.app431 import create_workspace_app431
from eagleeye.interfaces.web.server import serve_workspace
app=create_workspace_app431()
if __name__=='__main__':
 raise SystemExit(serve_workspace())
