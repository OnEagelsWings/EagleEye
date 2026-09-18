from eagleeye.interfaces.web.app416 import create_workspace_app416
app=create_workspace_app416()
if __name__=='__main__':
 import uvicorn
 uvicorn.run(app,host='127.0.0.1',port=8000)
