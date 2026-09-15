from __future__ import annotations
import hashlib
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app395 import create_workspace_app395
from eagleeye_pro.phase17.case_reconciliation396 import CONFIRM_BASELINE, CONFIRM_REVIEW, CONFIRM_BRANCH, CONFIRM_ADVANCE


def create_workspace_app396(*, base_dir: str|Path|None=None) -> FastAPI:
    app=create_workspace_app395(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build396
    app.title='EagleEye Intelligence Platform – Build 396.0 Case State Reconciliation & Incremental Re-analysis'; app.version='396.0'
    base_health=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not(getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def fp(req):
        m='|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')); return hashlib.sha256(m.encode()).hexdigest()
    def auth(req):
        i=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp(req),touch=True)
        if not i: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return i
    def caseauth(req,case_id,cap='case.read'):
        i=auth(req)
        try: ctx.build380.authorize(i,case_id=case_id,capability=cap,object_type='phase17_v396',object_id=case_id)
        except PermissionError as e: raise HTTPException(403,str(e))
        return i
    @app.get('/health')
    def health396():
        prev=dict(base_health() if callable(base_health) else {'ok':True}); prev.update({'build':'396.0','phase17_builds_completed':16,'phase17_integrated':True,'incremental_reconciliation':True,'automatic_active_state_mutation':False,'execution_authority':False,'truth_probability':False}); return prev
    @app.get('/api/build396/phase17-status')
    def status(request:Request): auth(request); return ctx.build396.phase17_status()
    @app.post('/api/cases/{case_id}/phase17/reconciliation/baselines')
    async def baseline(case_id:str,request:Request):
        i=caseauth(request,case_id,'dossier.write'); b=await request.json()
        try:return ctx.build396.create_reconciliation_baseline(case_id=case_id,identity=i,confirmation=str(b.get('confirmation') or ''),previous_baseline_id=str(b.get('previous_baseline_id') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.get('/api/cases/{case_id}/phase17/reconciliation/baselines/latest')
    def latest(case_id:str,request:Request): return ctx.build396.latest_reconciliation_baseline(case_id=case_id,identity=caseauth(request,case_id))
    @app.post('/api/cases/{case_id}/phase17/reconciliation/scans')
    async def scan(case_id:str,request:Request):
        i=caseauth(request,case_id,'case.read'); b=await request.json()
        try:return ctx.build396.reconcile_case_state(case_id=case_id,baseline_id=str(b.get('baseline_id') or ''),identity=i)
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.get('/api/cases/{case_id}/phase17/reconciliation/scans/{scan_id}')
    def scan_get(case_id:str,scan_id:str,request:Request): return ctx.build396.reconciliation_scan(case_id=case_id,scan_id=scan_id,identity=caseauth(request,case_id))
    @app.post('/api/cases/{case_id}/phase17/reconciliation/scans/{scan_id}/reanalysis-proposals')
    async def proposal(case_id:str,scan_id:str,request:Request):
        i=caseauth(request,case_id,'dossier.write'); b=await request.json()
        try:return ctx.build396.propose_reanalysis(case_id=case_id,scan_id=scan_id,target_type=str(b.get('target_type') or ''),target_id=str(b.get('target_id') or ''),identity=i,rationale=str(b.get('rationale') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.post('/api/cases/{case_id}/phase17/reanalysis/{proposal_id}/review')
    async def review(case_id:str,proposal_id:str,request:Request):
        i=caseauth(request,case_id,'dossier.write'); b=await request.json()
        try:return ctx.build396.review_reanalysis(case_id=case_id,proposal_id=proposal_id,identity=i,disposition=str(b.get('disposition') or ''),rationale=str(b.get('rationale') or ''),confirmation=str(b.get('confirmation') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.post('/api/cases/{case_id}/phase17/reanalysis/{proposal_id}/branch')
    async def branch(case_id:str,proposal_id:str,request:Request):
        i=caseauth(request,case_id,'dossier.write'); b=await request.json()
        try:return ctx.build396.create_reanalysis_branch(case_id=case_id,proposal_id=proposal_id,identity=i,confirmation=str(b.get('confirmation') or ''),branch_name=str(b.get('branch_name') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.post('/api/cases/{case_id}/phase17/reconciliation/scans/{scan_id}/advance-baseline')
    async def advance(case_id:str,scan_id:str,request:Request):
        i=caseauth(request,case_id,'dossier.write'); b=await request.json()
        try:return ctx.build396.advance_reconciliation_baseline(case_id=case_id,scan_id=scan_id,identity=i,confirmation=str(b.get('confirmation') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    return app

create_app=create_workspace_app396
