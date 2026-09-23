from __future__ import annotations
from fastapi import HTTPException,Request
from .app379 import COOKIE
from .app430 import create_workspace_app430
def create_workspace_app431(*,base_dir=None):
 app=create_workspace_app430(base_dir=base_dir);ctx=app.state.context;team=ctx.team_identity_359;_=ctx.build431;app.title='EagleEye Build 431.0';app.version='431.0'
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
  h=dict(old() if callable(old) else {'ok':True});s=ctx.build431.provenance_status();h.update({'build':'431.0','phase':19,'phase19_builds_completed':11,'news_provenance_syndication':True,'provenance_integrity':s['integrity_valid'],'production_release_ready':False});return h
 @app.get('/api/build431/news-provenance/status')
 def status431(request:Request):auth(request);return ctx.build431.provenance_status()
 @app.get('/api/build431/cases/{case_id}/news-provenance/latest')
 def latest431(case_id:str,request:Request):case_auth(request,case_id,'case.read');return ctx.build431.latest_news_provenance(case_id)
 @app.post('/api/build431/cases/{case_id}/news-provenance/analyze')
 def analyze431(case_id:str,request:Request):
  identity=case_auth(request,case_id,'research.run')
  try:return ctx.build431.analyze_news_provenance(identity=identity,case_id=case_id)
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app431
