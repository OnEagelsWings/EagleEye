from __future__ import annotations
from fastapi import HTTPException,Request
from starlette.concurrency import run_in_threadpool
from .app379 import COOKIE
from .app434 import create_workspace_app434
def create_workspace_app435(*,base_dir=None):
 app=create_workspace_app434(base_dir=base_dir);ctx=app.state.context;team=ctx.team_identity_359;_=ctx.build435;app.title='EagleEye Build 435.0';app.version='435.0'
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
  h=dict(old() if callable(old) else {'ok':True});s=ctx.build435.tor_worker_status();h.update({'build':'435.0','phase':19,'phase19_builds_completed':15,'isolated_tor_research_worker':True,'hard_checkpoint_435':True,'checkpoint_ready':s['checkpoint_ready'],'tor_integrity':s['integrity_valid'],'production_release_ready':False});return h
 @app.get('/api/build435/tor/status')
 def status435(request:Request):auth(request);return ctx.build435.tor_worker_status()
 @app.get('/api/build435/checkpoint')
 def checkpoint435(request:Request):auth(request);return ctx.build435.checkpoint_435()
 @app.get('/api/build435/cases/{case_id}/tor/tasks')
 def tasks435(case_id:str,request:Request):case_auth(request,case_id,'case.read');return {'items':ctx.build435.case_tor_research(case_id)}
 @app.get('/api/build435/cases/{case_id}/tor/report')
 def report435(case_id:str,request:Request):case_auth(request,case_id,'case.read');return ctx.build435.case_tor_report(case_id)
 @app.post('/api/build435/cases/{case_id}/tor/tasks')
 async def create435(case_id:str,request:Request):
  same_origin(request);identity=case_auth(request,case_id,'research.run')
  try:
   b=await request.json()
   if not isinstance(b,dict):raise ValueError('JSON object required')
   return ctx.build435.create_tor_research_task(identity=identity,case_id=case_id,source_id=b['source_id'],target=b['target'],objective=b['objective'],approval_ref=b['approval_ref'],max_bytes=b.get('max_bytes',500000),timeout_seconds=b.get('timeout_seconds',20))
  except PermissionError as e:raise HTTPException(403,str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 @app.post('/api/build435/cases/{case_id}/tor/tasks/{task_id}/execute-live')
 async def execute435(case_id:str,task_id:str,request:Request):
  same_origin(request);identity=case_auth(request,case_id,'research.run')
  try:
   task=ctx.tor_research_435.get(task_id)
   if task['case_id']!=case_id:raise KeyError('Tor task not found in case')
   b=await request.json()
   if not isinstance(b,dict):raise ValueError('JSON object required')
   return await run_in_threadpool(ctx.build435.execute_tor_research_live,identity=identity,task_id=task_id,approval_ref=b['approval_ref'],confirmation=b['confirmation'])
  except KeyError as e:raise HTTPException(404,str(e))
  except PermissionError as e:raise HTTPException(403,str(e))
  except RuntimeError as e:raise HTTPException(502,str(e))
  except (ValueError,TypeError) as e:raise HTTPException(400,str(e))
 @app.post('/api/build435/cases/{case_id}/tor/tasks/{task_id}/review')
 async def review435(case_id:str,task_id:str,request:Request):
  same_origin(request);identity=case_auth(request,case_id,'research.run')
  try:
   task=ctx.tor_research_435.get(task_id)
   if task['case_id']!=case_id:raise KeyError('Tor task not found in case')
   b=await request.json()
   if not isinstance(b,dict):raise ValueError('JSON object required')
   return ctx.build435.review_tor_research(identity=identity,task_id=task_id,decision=b['decision'],note=b.get('note',''))
  except KeyError as e:raise HTTPException(404,str(e))
  except PermissionError as e:raise HTTPException(403,str(e))
  except (ValueError,TypeError) as e:raise HTTPException(400,str(e))
 @app.post('/api/build435/cases/{case_id}/tor/selftest')
 def selftest435(case_id:str,request:Request):
  same_origin(request);identity=case_auth(request,case_id,'research.run')
  try:return ctx.build435.run_tor_case_selftest(identity=identity,case_id=case_id)
  except PermissionError as e:raise HTTPException(403,str(e))
  except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
 return app
create_app=create_workspace_app435
