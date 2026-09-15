from __future__ import annotations
import hashlib
from pathlib import Path
from fastapi import FastAPI,HTTPException,Request
from .app379 import COOKIE
from .app397 import create_workspace_app397
from eagleeye_pro.phase17.model_holdout398 import CONFIRM_FREEZE_SUITE,CONFIRM_EXTERNAL_RUN,CONFIRM_HUMAN_REVIEW,CONFIRM_FREEZE_BASELINE

def create_workspace_app398(*,base_dir:str|Path|None=None)->FastAPI:
    app=create_workspace_app397(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build398
    app.title='EagleEye Intelligence Platform – Build 398.0 Model Holdout & Human Evaluation Framework'; app.version='398.0'
    base_health=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not(getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def fp(req):
        m='|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')); return hashlib.sha256(m.encode()).hexdigest()
    def auth(req):
        i=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp(req),touch=True)
        if not i: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return i
    @app.get('/health')
    def health398():
        prev=dict(base_health() if callable(base_health) else {'ok':True}); q=ctx.model_holdout_398.qualification_status(); prev.update({'build':'398.0','phase17_builds_completed':18,'model_holdout_framework':True,'bundled_holdout_cases':60,'real_model_runs':q.get('real_model_runs',0),'human_reviewed_cases':q.get('human_reviewed_cases',0),'external_holdout_qualified':False,'production_release_ready':False}); return prev
    @app.get('/api/build398/phase17-status')
    def status(request:Request): auth(request); return ctx.build398.phase17_status()
    @app.post('/api/build398/holdout/reference-suite')
    async def reference(request:Request):
        i=auth(request); b=await request.json(); s=ctx.model_holdout_398.create_reference_suite();
        if b.get('freeze'): s=ctx.model_holdout_398.freeze_suite(suite_id=s['suite_id'],identity=i,confirmation=str(b.get('confirmation') or ''))
        return s
    @app.get('/api/build398/holdout/status')
    def hstatus(request:Request): auth(request); return ctx.model_holdout_398.qualification_status()
    @app.post('/api/build398/holdout/runs/external')
    async def external(request:Request):
        i=auth(request); b=await request.json()
        try:return ctx.model_holdout_398.record_external_model_run(suite_id=str(b.get('suite_id')),case_id=str(b.get('case_id')),adapter_id=str(b.get('adapter_id') or ''),model_id=str(b.get('model_id') or ''),output=dict(b.get('output') or {}),execution_receipt=str(b.get('execution_receipt') or ''),identity=i,confirmation=str(b.get('confirmation') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.post('/api/build398/holdout/runs/{run_id}/reviews')
    async def review(run_id:str,request:Request):
        i=auth(request); b=await request.json()
        try:return ctx.model_holdout_398.submit_human_review(run_id=run_id,identity=i,blind_review=bool(b.get('blind_review')),scores=dict(b.get('scores') or {}),harmful_overreach=bool(b.get('harmful_overreach')),notes=str(b.get('notes') or ''),confirmation=str(b.get('confirmation') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    return app
create_app=create_workspace_app398
