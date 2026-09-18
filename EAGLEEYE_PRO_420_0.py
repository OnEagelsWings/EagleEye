from eagleeye.interfaces.web.app420 import create_workspace_app420
app=create_workspace_app420()
if __name__=='__main__':
 import uvicorn
 uvicorn.run(app,host='127.0.0.1',port=8000)
