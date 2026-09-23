from eagleeye.interfaces.web.app435 import create_workspace_app435
from eagleeye.interfaces.web.server import serve_workspace
app=create_workspace_app435()
if __name__=='__main__':
 raise SystemExit(serve_workspace())
