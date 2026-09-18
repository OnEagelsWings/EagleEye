from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI,HTTPException,Request
from pydantic import BaseModel,Field
from .app379 import COOKIE
from .app413 import create_workspace_app413
class RunRequest(BaseModel): plan_id:str; max_waves:int=Field(default=5,ge=1,le=20); max_searches_per_wave:int=Field(default=8,ge=1,le=20)
class AuthRequest(BaseModel): confirmation:str

def create_workspace_app414(*,base_dir:str|Path|None=None)->FastAPI:
 app=create_workspace_app413(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build414; app.title='EagleEye Intelligence Platform – Build 414.0 Autonomous Research Waves'; app.version='414.0'
 old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None); app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
 def auth(req):
  import hashlib
  fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest(); x=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
  if not x: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
  return x
 @app.get('/health')
 def health():
  prev=dict(old() if callable(old) else {'ok':True}); s=ctx.build414.wave_status(); prev.update({'build':'414.0','phase':18,'phase18_builds_completed':14,'autonomous_research_waves':True,'autonomous_research_wave_gate_pass':s['autonomous_research_wave_gate_pass'],'network_execution_on_boot':False,'production_release_ready':False}); return prev
 @app.get('/api/build414/waves/status')
 def status(request:Request): auth(request); return ctx.build414.wave_status()
 @app.post('/api/build414/waves')
 def create(body:RunRequest,request:Request):
  try:return ctx.build414.create_research_wave_run(**body.model_dump(),identity=auth(request))
  except PermissionError as e: raise HTTPException(403,str(e))
  except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
 @app.post('/api/build414/waves/{run_id}/authorize')
 def authorize(run_id:str,body:AuthRequest,request:Request):
  try:return ctx.build414.authorize_research_wave_run(run_id=run_id,identity=auth(request),confirmation=body.confirmation)
  except PermissionError as e: raise HTTPException(403,str(e))
  except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
 @app.post('/api/build414/waves/{run_id}/advance')
 def advance(run_id:str,request:Request):
  try:return ctx.build414.advance_research_wave_run(run_id=run_id,identity=auth(request))
  except PermissionError as e: raise HTTPException(403,str(e))
  except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app414
