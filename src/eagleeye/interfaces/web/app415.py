from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI,HTTPException,Request
from pydantic import BaseModel
from .app379 import COOKIE
from .app414 import create_workspace_app414
class SessionRequest(BaseModel): plan_id:str; wave_run_id:str=''
def create_workspace_app415(*,base_dir:str|Path|None=None)->FastAPI:
 app=create_workspace_app414(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build415; app.title='EagleEye Intelligence Platform – Build 415.0 Multi-Agent Investigation'; app.version='415.0'
 old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None); app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
 def auth(req):
  import hashlib
  fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest(); x=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
  if not x: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
  return x
 @app.get('/health')
 def health():
  prev=dict(old() if callable(old) else {'ok':True}); s=ctx.build415.multi_agent_status(); prev.update({'build':'415.0','phase':18,'phase18_builds_completed':15,'multi_agent_investigation':True,'multi_agent_gate_pass':s['multi_agent_gate_pass'],'network_execution_on_boot':False,'production_release_ready':False}); return prev
 @app.get('/api/build415/multi-agent/status')
 def status(request:Request): auth(request); return ctx.build415.multi_agent_status()
 @app.post('/api/build415/multi-agent/sessions')
 def create(body:SessionRequest,request:Request):
  try:return ctx.build415.create_multi_agent_session(**body.model_dump(),identity=auth(request))
  except PermissionError as e: raise HTTPException(403,str(e))
  except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
 @app.post('/api/build415/multi-agent/sessions/{session_id}/round')
 def round(session_id:str,request:Request):
  try:return ctx.build415.run_multi_agent_round(session_id=session_id,identity=auth(request))
  except PermissionError as e: raise HTTPException(403,str(e))
  except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app415
