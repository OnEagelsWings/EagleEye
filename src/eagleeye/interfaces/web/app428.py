from __future__ import annotations
from fastapi import HTTPException,Request
from .app379 import COOKIE
from .app427 import create_workspace_app427
def create_workspace_app428(*,base_dir=None):
 app=create_workspace_app427(base_dir=base_dir);ctx=app.state.context;team=ctx.team_identity_359;_=ctx.build428;app.title='EagleEye Build 428.0';app.version='428.0'
 old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None);app.router.routes[:]=[r for r in app.router.routes if not(getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
 def auth(req):
  import hashlib
  fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest();x=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
  if not x:raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
  return x
 @app.get('/health')
 def health():
  h=dict(old() if callable(old) else {'ok':True});s=ctx.build428.archive_status();h.update({'build':'428.0','phase':19,'phase19_builds_completed':8,'historical_web':True,'archive_integrity':s['integrity_valid'],'production_release_ready':False});return h
 @app.get('/api/build428/archive/status')
 def status428(request:Request):auth(request);return ctx.build428.archive_status()
 @app.get('/api/build428/cases/{case_id}/archive')
 def timeline428(case_id:str,original_url:str,request:Request):auth(request);return ctx.build428.archive_timeline(case_id,original_url)
 @app.post('/api/build428/archive/captures')
 async def capture428(request:Request):
  identity=auth(request)
  try:
   b=await request.json();return ctx.build428.register_archive_capture(identity=identity,case_id=b['case_id'],source_id=b['source_id'],original_url=b['original_url'],archive_url=b['archive_url'],captured_at=b['captured_at'],retrieved_event_id=b['retrieved_event_id'],content_id=b['content_id'],archive_provider=b.get('archive_provider',''),metadata=b.get('metadata'))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app428
