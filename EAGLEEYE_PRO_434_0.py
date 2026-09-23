from eagleeye.interfaces.web.app434 import create_workspace_app434
from eagleeye.interfaces.web.server import serve_workspace
app=create_workspace_app434()
if __name__=='__main__':
 raise SystemExit(serve_workspace())
