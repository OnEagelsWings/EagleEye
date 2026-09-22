from __future__ import annotations
from fastapi import HTTPException,Request
from .app379 import COOKIE
from .app420 import create_workspace_app420
def create_workspace_app421(*,base_dir=None):
 app=create_workspace_app420(base_dir=base_dir);ctx=app.state.context;team=ctx.team_identity_359;_=ctx.build421;app.title='EagleEye Build 421.0';app.version='421.0'
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
  h=dict(old() if callable(old) else {'ok':True});s=ctx.build421.acquisition_status();h.update({'build':'421.0','phase':19,'phase19_builds_completed':1,'acquisition_registry':True,'acquisition_integrity':s['integrity_valid'],'production_release_ready':False});return h
 @app.get('/api/build421/acquisition/sources')
 def sources421(request:Request,source_type:str='',capability:str=''):auth(request);return {'items':ctx.build421.sources(source_type=source_type,capability=capability)}
 @app.get('/api/build421/acquisition/status')
 def status421(request:Request):auth(request);return ctx.build421.acquisition_status()
 @app.post('/api/build421/acquisition/sources')
 async def register421(request:Request):
  identity=auth(request)
  try:
   ctx.team_identity_359.require_global(identity,'source.manage')
   b=await request.json()
   if not isinstance(b,dict):raise ValueError('JSON object required')
   return ctx.build421.register_source(identity=identity,name=b.get('name',''),source_type=b.get('source_type',''),access_mode=b.get('access_mode','public'),base_url=b.get('base_url',''),capabilities=b.get('capabilities') or (),coverage=b.get('coverage') or {},terms_url=b.get('terms_url',''),license_note=b.get('license_note',''))
  except PermissionError as e:raise HTTPException(403,str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app421
