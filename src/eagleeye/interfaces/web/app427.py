from __future__ import annotations
from fastapi import HTTPException,Request
from .app379 import COOKIE
from .app426 import create_workspace_app426
def create_workspace_app427(*,base_dir=None):
 app=create_workspace_app426(base_dir=base_dir);ctx=app.state.context;team=ctx.team_identity_359;_=ctx.build427;app.title='EagleEye Build 427.0';app.version='427.0'
 old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None);app.router.routes[:]=[r for r in app.router.routes if not(getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
 def auth(req):
  import hashlib
  fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest();x=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
  if not x:raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
  return x
 @app.get('/health')
 def health():
  h=dict(old() if callable(old) else {'ok':True});s=ctx.build427.change_status();h.update({'build':'427.0','phase':19,'phase19_builds_completed':7,'incremental_change_detection':True,'change_integrity':s['integrity_valid'],'production_release_ready':False});return h
 @app.get('/api/build427/crawler/status')
 def status427(request:Request):auth(request);return ctx.build427.change_status()
 @app.get('/api/build427/cases/{case_id}/changes')
 def changes427(case_id:str,request:Request):auth(request);return ctx.build427.change_history(case_id)
 @app.post('/api/build427/acquisition-events/{event_id}/snapshot')
 async def snapshot427(event_id:str,request:Request):
  identity=auth(request)
  try:
   b=await request.json();return ctx.build427.capture_snapshot(identity=identity,event_id=event_id,content_id=b['content_id'],text=b.get('text',''))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app427
