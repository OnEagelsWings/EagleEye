from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI,HTTPException,Request
from .app379 import COOKIE
from .app415 import create_workspace_app415
def create_workspace_app416(*,base_dir:str|Path|None=None)->FastAPI:
 app=create_workspace_app415(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build416; app.title='EagleEye Intelligence Platform – Build 416.0 Multi-Agent Integrity & Case Continuity'; app.version='416.0'
 old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None); app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
 def auth(req):
  import hashlib
  fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest(); x=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
  if not x: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
  return x
 @app.get('/health')
 def health():
  prev=dict(old() if callable(old) else {'ok':True}); s=ctx.build416.continuity_status(); prev.update({'build':'416.0','phase':18,'phase18_builds_completed':16,'multi_agent_integrity_case_continuity':True,'continuity_gate_pass':s['continuity_gate_pass'],'network_execution_on_boot':False,'production_release_ready':False}); return prev
 @app.get('/api/build416/continuity/status')
 def status(request:Request): auth(request); return ctx.build416.continuity_status()
 @app.post('/api/build416/multi-agent/sessions/{session_id}/validate')
 def validate(session_id:str,request:Request):
  try:return ctx.build416.validate_multi_agent_session(session_id=session_id,identity=auth(request))
  except PermissionError as e: raise HTTPException(403,str(e))
  except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
 @app.post('/api/build416/multi-agent/sessions/{session_id}/round')
 def round416(session_id:str,request:Request):
  try:return ctx.build416.run_multi_agent_round(session_id=session_id,identity=auth(request))
  except PermissionError as e: raise HTTPException(403,str(e))
  except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app416
