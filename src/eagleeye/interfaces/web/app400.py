from __future__ import annotations
import hashlib
from pathlib import Path
from fastapi import FastAPI,HTTPException,Request
from .app379 import COOKIE
from .app399 import create_workspace_app399
from eagleeye_pro.phase17.final_acceptance400 import CONFIRM_RUN,CONFIRM_REVIEW

def create_workspace_app400(*,base_dir:str|Path|None=None)->FastAPI:
    app=create_workspace_app399(base_dir=base_dir);ctx=app.state.context;team=ctx.team_identity_359;_=ctx.build400
    app.title='EagleEye Intelligence Platform – Build 400.0 Phase 17 Final End-to-End Acceptance';app.version='400.0'
    base_health=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not(getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def fp(req):
        m='|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else ''));return hashlib.sha256(m.encode()).hexdigest()
    def auth(req):
        i=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp(req),touch=True)
        if not i:raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return i
    @app.get('/health')
    def health400():
        prev=dict(base_health() if callable(base_health) else {'ok':True});st=ctx.phase17_final_acceptance_400.status();prev.update({'build':'400.0','phase17_builds_completed':20,'phase17_final_acceptance_framework':True,'production_release_ready':False,'external_holdout_qualified':st['external_holdout_qualified'],'external_72h_soak_qualified':st['external_72h_soak_qualified']});return prev
    @app.get('/api/build400/phase17-status')
    def status(request:Request):auth(request);return ctx.build400.phase17_status()
    @app.post('/api/build400/final-acceptance')
    async def run(request:Request):
        i=auth(request);b=await request.json()
        try:return ctx.build400.run_phase17_acceptance(identity=i,case_id=str(b.get('case_id') or ''),confirmation=str(b.get('confirmation') or ''))
        except (KeyError,ValueError,PermissionError) as e:raise HTTPException(400,str(e))
    @app.post('/api/build400/final-acceptance/{run_id}/review')
    async def review(run_id:str,request:Request):
        i=auth(request);b=await request.json()
        try:return ctx.build400.review_phase17_acceptance(run_id=run_id,identity=i,disposition=str(b.get('disposition') or ''),rationale=str(b.get('rationale') or ''),confirmation=str(b.get('confirmation') or ''))
        except (KeyError,ValueError,PermissionError) as e:raise HTTPException(400,str(e))
    @app.get('/api/build400/final-acceptance/{run_id}')
    def get_run(run_id:str,request:Request):auth(request);return ctx.build400.phase17_acceptance(run_id)
    @app.get('/api/build400/final-acceptance/{run_id}/verify')
    def verify(run_id:str,request:Request):auth(request);return ctx.build400.verify_phase17_acceptance(run_id)
    @app.post('/api/build400/final-acceptance/{run_id}/export')
    def export(run_id:str,request:Request):auth(request);return ctx.build400.export_phase17_acceptance(run_id=run_id)
    return app
create_app=create_workspace_app400
