from eagleeye.interfaces.web.app423 import create_workspace_app423
app=create_workspace_app423()
if __name__=='__main__':
 import uvicorn
 uvicorn.run(app,host='127.0.0.1',port=8000)
