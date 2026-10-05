from __future__ import annotations
from fastapi import HTTPException,Request
from .app379 import COOKIE
from .app436 import create_workspace_app436
def create_workspace_app437(*,base_dir=None):
 app=create_workspace_app436(base_dir=base_dir);ctx=app.state.context;team=ctx.team_identity_359;_=ctx.build437;app.title='EagleEye Build 437.0';app.version='437.0'
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
  h=dict(old() if callable(old) else {'ok':True});s=ctx.build437.entity_resolution_status_437();h.update({'build':'437.0','phase':19,'phase19_builds_completed':17,'cross_source_entity_resolution':True,'human_review_required':True,'entity_resolution_integrity':s['integrity_valid'],'production_release_ready':False});return h
 @app.get('/api/build437/entity-resolution/status')
 def status437(request:Request):auth(request);return ctx.build437.entity_resolution_status_437()
 @app.get('/api/build437/cases/{case_id}/entity-resolution/report')
 def report437(case_id:str,request:Request):case_auth(request,case_id,'case.read');return ctx.build437.entity_resolution_report(case_id)
 @app.get('/api/build437/cases/{case_id}/entity-resolution/bindings')
 def bindings437(case_id:str,request:Request):case_auth(request,case_id,'case.read');return {'items':ctx.build437.entity_resolution_bindings(case_id)}
 @app.get('/api/build437/cases/{case_id}/entity-resolution/review-queue')
 def queue437(case_id:str,request:Request):case_auth(request,case_id,'case.read');return {'items':ctx.build437.entity_resolution_review_queue(case_id)}
 @app.get('/api/build437/cases/{case_id}/entity-resolution/comparisons/{comparison_id}')
 def packet437(case_id:str,comparison_id:str,request:Request):
  case_auth(request,case_id,'case.read')
  try:return ctx.build437.entity_resolution_packet(case_id,comparison_id)
  except KeyError as e:raise HTTPException(404,str(e))
 @app.post('/api/build437/cases/{case_id}/entity-resolution/sync')
 async def sync437(case_id:str,request:Request):
  same_origin(request);identity=case_auth(request,case_id,'research.run')
  try:
   b=await request.json()
   if not isinstance(b,dict):b={}
   return ctx.build437.sync_cross_source_entities(identity=identity,case_id=case_id,include_fixtures=bool(b.get('include_fixtures',False)),min_news_confidence=b.get('min_news_confidence',.60),min_name_similarity=b.get('min_name_similarity',.84),max_entities=b.get('max_entities',500),max_pairs=b.get('max_pairs',2000))
  except PermissionError as e:raise HTTPException(403,str(e))
  except RuntimeError as e:raise HTTPException(409,'Entity-resolution provenance preflight failed: '+str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 @app.post('/api/build437/cases/{case_id}/entity-resolution/proposals')
 async def propose437(case_id:str,request:Request):
  same_origin(request);identity=case_auth(request,case_id,'research.run')
  try:
   b=await request.json();return ctx.build437.propose_same_entity_437(identity=identity,case_id=case_id,comparison_id=b['comparison_id'],canonical_entity_id=b['canonical_entity_id'])
  except PermissionError as e:raise HTTPException(403,str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 @app.post('/api/build437/cases/{case_id}/entity-resolution/proposals/{proposal_id}/review')
 async def review437(case_id:str,proposal_id:str,request:Request):
  same_origin(request);identity=case_auth(request,case_id,'dossier.review')
  try:
   b=await request.json();return ctx.build437.review_same_entity_437(identity=identity,case_id=case_id,proposal_id=proposal_id,approve=bool(b['approve']),reason=b['reason'])
  except PermissionError as e:raise HTTPException(403,str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 @app.post('/api/build437/cases/{case_id}/entity-resolution/selftest')
 def selftest437(case_id:str,request:Request):
  same_origin(request);identity=case_auth(request,case_id,'research.run')
  try:return ctx.build437.run_entity_resolution_case_selftest(identity=identity,case_id=case_id)
  except PermissionError as e:raise HTTPException(403,str(e))
  except RuntimeError as e:raise HTTPException(409,str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app437
