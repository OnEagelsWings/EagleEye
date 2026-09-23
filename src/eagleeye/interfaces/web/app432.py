from __future__ import annotations
from fastapi import HTTPException,Request
from .app379 import COOKIE
from .app431 import create_workspace_app431
def create_workspace_app432(*,base_dir=None):
 app=create_workspace_app431(base_dir=base_dir);ctx=app.state.context;team=ctx.team_identity_359;_=ctx.build432;app.title='EagleEye Build 432.0';app.version='432.0'
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
  h=dict(old() if callable(old) else {'ok':True});s=ctx.build432.social_status();h.update({'build':'432.0','phase':19,'phase19_builds_completed':12,'social_public_adapters':True,'case_specific_selftest':True,'social_integrity':s['integrity_valid'],'production_release_ready':False});return h
 @app.get('/api/build432/social/status')
 def status432(request:Request):auth(request);return ctx.build432.social_status()
 @app.get('/api/build432/cases/{case_id}/social')
 def items432(case_id:str,request:Request,platform:str='',adapter:str='',include_fixtures:bool=True):case_auth(request,case_id,'case.read');return {'items':ctx.build432.case_social(case_id,platform=platform,adapter=adapter,include_fixtures=include_fixtures)}
 @app.get('/api/build432/cases/{case_id}/social/report')
 def report432(case_id:str,request:Request):case_auth(request,case_id,'case.read');return ctx.build432.case_social_report(case_id)
 @app.post('/api/build432/cases/{case_id}/social/observation')
 async def observation432(case_id:str,request:Request):
  identity=case_auth(request,case_id,'research.run')
  try:
   b=await request.json()
   if not isinstance(b,dict):raise ValueError('JSON object required')
   return ctx.build432.record_social_observation(identity=identity,case_id=case_id,source_id=b['source_id'],event_id=b['event_id'],content_id=b['content_id'],adapter=b['adapter'],canonical_url=b['canonical_url'],external_object_id=b['external_object_id'],platform=b.get('platform',''),object_type=b.get('object_type','post'),account_id=b.get('account_id',''),account_handle=b.get('account_handle',''),published_at=b.get('published_at',''),visibility=b.get('visibility','public'),language=b.get('language',''),reply_to_external_id=b.get('reply_to_external_id',''),reshare_of_external_id=b.get('reshare_of_external_id',''),metrics=b.get('metrics') or {},metadata=b.get('metadata') or {},test_fixture=False)
  except PermissionError as e:raise HTTPException(403,str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 @app.post('/api/build432/cases/{case_id}/social/fixture')
 async def fixture432(case_id:str,request:Request):
  identity=case_auth(request,case_id,'research.run')
  try:
   b=await request.json()
   if not isinstance(b,dict):raise ValueError('JSON object required')
   return ctx.build432.ingest_social_fixture(identity=identity,case_id=case_id,source_id=b['source_id'],adapter=b.get('adapter','generic_public'),canonical_url=b['canonical_url'],text=b['text'],external_object_id=b['external_object_id'],platform=b.get('platform',''),object_type=b.get('object_type','post'),account_id=b.get('account_id',''),account_handle=b.get('account_handle',''),published_at=b.get('published_at',''),language=b.get('language',''),metrics=b.get('metrics') or {},metadata=b.get('metadata') or {})
  except PermissionError as e:raise HTTPException(403,str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 @app.post('/api/build432/cases/{case_id}/social/selftest')
 def selftest432(case_id:str,request:Request):
  identity=case_auth(request,case_id,'research.run')
  try:return ctx.build432.run_case_selftest(identity=identity,case_id=case_id)
  except PermissionError as e:raise HTTPException(403,str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app432
