from __future__ import annotations
from fastapi import HTTPException,Request
from .app379 import COOKIE
from .app433 import create_workspace_app433
def create_workspace_app434(*,base_dir=None):
 app=create_workspace_app433(base_dir=base_dir);ctx=app.state.context;team=ctx.team_identity_359;_=ctx.build434;app.title='EagleEye Build 434.0';app.version='434.0'
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
  h=dict(old() if callable(old) else {'ok':True});s=ctx.build434.registry_organization_status();h.update({'build':'434.0','phase':19,'phase19_builds_completed':14,'registry_organization_integration':True,'case_specific_selftest':True,'registry_integration_integrity':s['integrity_valid'],'production_release_ready':False});return h
 @app.get('/api/build434/registry-organizations/status')
 def status434(request:Request):auth(request);return ctx.build434.registry_organization_status()
 @app.get('/api/build434/cases/{case_id}/registry-organizations')
 def records434(case_id:str,request:Request):case_auth(request,case_id,'case.read');return {'items':ctx.build434.case_registry_records(case_id)}
 @app.get('/api/build434/cases/{case_id}/registry-organizations/report')
 def report434(case_id:str,request:Request):case_auth(request,case_id,'case.read');return ctx.build434.case_registry_report(case_id)
 @app.get('/api/build434/cases/{case_id}/registry-organizations/identifier-candidates')
 def candidates434(case_id:str,request:Request,identifier_type:str,value:str):case_auth(request,case_id,'case.read');return ctx.build434.registry_identifier_candidates(case_id,identifier_type,value)
 @app.post('/api/build434/cases/{case_id}/registry-organizations/import')
 async def import434(case_id:str,request:Request):
  identity=case_auth(request,case_id,'research.run')
  try:
   b=await request.json()
   if not isinstance(b,dict):raise ValueError('JSON object required')
   return ctx.build434.import_registry_organization(identity=identity,case_id=case_id,source_id=b['source_id'],event_id=b['event_id'],content_id=b['content_id'],registry_kind=b['registry_kind'],registry_name=b['registry_name'],record_key=b['record_key'],record=b['record'],subject_id=b.get('subject_id',''),relations=b.get('relations') or [],test_fixture=False)
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 @app.post('/api/build434/cases/{case_id}/registry-organizations/selftest')
 def selftest434(case_id:str,request:Request):
  identity=case_auth(request,case_id,'research.run')
  try:return ctx.build434.run_registry_case_selftest(identity=identity,case_id=case_id)
  except PermissionError as e:raise HTTPException(403,str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app434
