from __future__ import annotations
from fastapi import HTTPException,Request
from .app379 import COOKIE
from .app419 import create_workspace_app419
def create_workspace_app420(*,base_dir=None):
 app=create_workspace_app419(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build420; app.title='EagleEye Build 420.0'; app.version='420.0'
 old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None); app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
 def auth(req):
  import hashlib
  fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest(); x=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
  if not x: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
  return x
 @app.get('/health')
 def health():
  h=dict(old() if callable(old) else {'ok':True}); s=ctx.build420.qualification_status(); h.update({'build':'420.0','phase':18,'phase18_builds_completed':20,'phase18_complete':True,'qualification_framework':True,'phase18_gate_pass':s['phase18_gate_pass'],'production_release_ready':False}); return h
 @app.get('/api/build420/qualification/status')
 def status420(request:Request): auth(request); return ctx.build420.qualification_status()
 @app.post('/api/build420/qualification/run')
 async def qualify420(request:Request):
  try:
   b=await request.json(); return ctx.build420.qualify_phase18(identity=auth(request),case_id=b.get('case_id',''))
  except PermissionError as e: raise HTTPException(403,str(e))
  except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app420
