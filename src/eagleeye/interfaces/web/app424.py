from __future__ import annotations
from fastapi import HTTPException,Request
from .app379 import COOKIE
from .app423 import create_workspace_app423
def create_workspace_app424(*,base_dir=None):
 app=create_workspace_app423(base_dir=base_dir);ctx=app.state.context;team=ctx.team_identity_359;_=ctx.build424;app.title='EagleEye Build 424.0';app.version='424.0'
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
  h=dict(old() if callable(old) else {'ok':True});s=ctx.build424.source_health_status();h.update({'build':'424.0','phase':19,'phase19_builds_completed':4,'source_health':True,'source_health_integrity':s['integrity_valid'],'production_release_ready':False});return h
 @app.get('/api/build424/acquisition/status')
 def status424(request:Request):auth(request);return ctx.build424.source_health_status()
 @app.get('/api/build424/acquisition/sources/{source_id}/health')
 def health_source424(source_id:str,request:Request):auth(request);return {'latest':ctx.build424.source_health(source_id),'advice':ctx.build424.acquisition_advice(source_id)}
 @app.post('/api/build424/acquisition/sources/{source_id}/health')
 async def record424(source_id:str,request:Request):
  identity=auth(request)
  try:
   ctx.team_identity_359.require_global(identity,'source.manage')
   b=await request.json()
   if not isinstance(b,dict):raise ValueError('JSON object required')
   return ctx.build424.record_source_health(identity=identity,source_id=source_id,state=b.get('state','unknown'),http_status=b.get('http_status'),latency_ms=b.get('latency_ms'),quota_remaining=b.get('quota_remaining'),quota_limit=b.get('quota_limit'),retry_after_seconds=b.get('retry_after_seconds'),freshness_at=b.get('freshness_at'),error_class=b.get('error_class',''),metadata=b.get('metadata') or {},observed_at=b.get('observed_at'))
  except PermissionError as e:raise HTTPException(403,str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app424
