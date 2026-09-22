from eagleeye.interfaces.web.app428 import create_workspace_app428
app=create_workspace_app428()
if __name__=='__main__':
 import uvicorn
 uvicorn.run(app,host='127.0.0.1',port=8000)
