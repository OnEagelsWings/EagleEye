from __future__ import annotations
from fastapi import HTTPException,Request
from .app379 import COOKIE
from .app435 import create_workspace_app435
def create_workspace_app436(*,base_dir=None):
 app=create_workspace_app435(base_dir=base_dir);ctx=app.state.context;team=ctx.team_identity_359;_=ctx.build436;app.title='EagleEye Build 436.0';app.version='436.0'
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
 def same_origin(req):
  site=str(req.headers.get('sec-fetch-site') or '').strip().lower()
  if site and site not in {'same-origin','none'}:raise HTTPException(403,'Cross-origin mutation blocked')
  origin=str(req.headers.get('origin') or '').strip().rstrip('/')
  if origin:
   expected=(str(req.url.scheme)+'://'+str(req.headers.get('host') or '')).rstrip('/')
   if origin!=expected:raise HTTPException(403,'Cross-origin mutation blocked')
 @app.get('/health')
 def health():
  h=dict(old() if callable(old) else {'ok':True});s=ctx.build436.surface_onion_status();h.update({'build':'436.0','phase':19,'phase19_builds_completed':16,'surface_onion_correlation':True,'opsec_gate':True,'correlation_integrity':s['integrity_valid'],'production_release_ready':False});return h
 @app.get('/api/build436/surface-onion/status')
 def status436(request:Request):auth(request);return ctx.build436.surface_onion_status()
 @app.get('/api/build436/cases/{case_id}/surface-onion/latest')
 def latest436(case_id:str,request:Request):case_auth(request,case_id,'case.read');return ctx.build436.latest_surface_onion(case_id)
 @app.get('/api/build436/cases/{case_id}/surface-onion/report')
 def report436(case_id:str,request:Request):case_auth(request,case_id,'case.read');return ctx.build436.case_surface_onion_report(case_id)
 @app.post('/api/build436/cases/{case_id}/surface-onion/analyze')
 async def analyze436(case_id:str,request:Request):
  same_origin(request);identity=case_auth(request,case_id,'research.run')
  try:
   b=await request.json()
   if not isinstance(b,dict):b={}
   return ctx.build436.analyze_surface_onion(identity=identity,case_id=case_id,min_jaccard=b.get('min_jaccard',.75))
  except PermissionError as e:raise HTTPException(403,str(e))
  except RuntimeError as e:raise HTTPException(409,'Correlation integrity preflight failed: '+str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 @app.post('/api/build436/cases/{case_id}/surface-onion/selftest')
 def selftest436(case_id:str,request:Request):
  same_origin(request);identity=case_auth(request,case_id,'research.run')
  try:return ctx.build436.run_surface_onion_case_selftest(identity=identity,case_id=case_id)
  except PermissionError as e:raise HTTPException(403,str(e))
  except RuntimeError as e:raise HTTPException(409,'Correlation integrity preflight failed: '+str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app436
