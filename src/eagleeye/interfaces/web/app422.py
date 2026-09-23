from __future__ import annotations
from fastapi import HTTPException,Request
from .app379 import COOKIE
from .app421 import create_workspace_app421
def create_workspace_app422(*,base_dir=None):
 app=create_workspace_app421(base_dir=base_dir);ctx=app.state.context;team=ctx.team_identity_359;_=ctx.build422;app.title='EagleEye Build 422.0';app.version='422.0'
 old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None);app.router.routes[:]=[r for r in app.router.routes if not(getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
 def auth(req):
  import hashlib
  fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest();x=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
  if not x:raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
  return x
 def case_auth(req,case_id,capability='case.read'):
  identity=auth(req)
  try:ctx.team_governance_359.authorize(identity,case_id=str(case_id),capability=capability,object_type='phase19',object_id=str(case_id))
  except PermissionError as e:raise HTTPException(403,str(e))
  return identity
 @app.get('/health')
 def health():
  h=dict(old() if callable(old) else {'ok':True});s=ctx.build422.acquisition_event_status();h.update({'build':'422.0','phase':19,'phase19_builds_completed':2,'acquisition_events':True,'acquisition_event_integrity':s['integrity_valid'],'production_release_ready':False});return h
 @app.get('/api/build422/acquisition/status')
 def status422(request:Request):auth(request);return ctx.build422.acquisition_event_status()
 @app.get('/api/build422/cases/{case_id}/acquisition-events')
 def events422(case_id:str,request:Request):case_auth(request,case_id,'case.read');return {'items':ctx.build422.case_events(case_id)}
 @app.post('/api/build422/cases/{case_id}/acquisition-events')
 async def record422(case_id:str,request:Request):
  identity=case_auth(request,case_id,'research.run')
  try:
   b=await request.json()
   if not isinstance(b,dict):raise ValueError('JSON object required')
   return ctx.build422.record_event(identity=identity,case_id=case_id,source_id=b.get('source_id',''),target=b.get('target',''),method=b.get('method',''),status=b.get('status','retrieved'),content_sha256=b.get('content_sha256',''),media_type=b.get('media_type',''),bytes_count=b.get('bytes_count',0),provenance=b.get('provenance') or {},usage=b.get('usage') or {},retrieved_at=b.get('retrieved_at',''))
  except PermissionError as e:raise HTTPException(403,str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app422
