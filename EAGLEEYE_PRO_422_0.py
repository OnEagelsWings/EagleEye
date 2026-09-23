from eagleeye.interfaces.web.app422 import create_workspace_app422
app=create_workspace_app422()
if __name__=='__main__':
 import uvicorn
 uvicorn.run(app,host='127.0.0.1',port=8000)
