from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from fastapi import FastAPI,HTTPException,Request
from .app379 import COOKIE
from .app394 import create_workspace_app394
from eagleeye_pro.phase17.case_state_graph395 import CONFIRM_REVIEW,CONFIRM_ADOPT,CONFIRM_ROLLBACK,CONFIRM_BRANCH,CONFIRM_STAGE

def create_workspace_app395(*,base_dir:str|Path|None=None)->FastAPI:
    app=create_workspace_app394(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build395
    app.title='EagleEye Intelligence Platform – Build 395.0 Case State Version Graph & Controlled Adoption'; app.version='395.0'
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
        try: ctx.build380.authorize(i,case_id=case_id,capability=cap,object_type='phase17_v395',object_id=case_id)
        except PermissionError as e: raise HTTPException(403,str(e))
        return i
    @app.get('/health')
    def health395():
        prev=dict(base_health() if callable(base_health) else {'ok':True}); prev.update({'build':'395.0','phase17_builds_completed':15,'phase17_integrated':True,'case_state_version_graph':True,'controlled_adoption':True,'execution_authority':False,'truth_probability':False}); return prev
    @app.get('/api/build395/phase17-status')
    def status(request:Request): auth(request); return ctx.build395.phase17_status()
    @app.get('/api/cases/{case_id}/phase17/state/{target_type}/{target_id}')
    def active(case_id:str,target_type:str,target_id:str,request:Request): return ctx.build395.active_case_state(case_id=case_id,target_type=target_type,target_id=target_id,identity=caseauth(request,case_id))
    @app.post('/api/cases/{case_id}/phase17/state/{target_type}/{target_id}/branches')
    async def branch(case_id:str,target_type:str,target_id:str,request:Request):
        i=caseauth(request,case_id,'dossier.write'); b=await request.json()
        try:return ctx.build395.create_case_state_branch(case_id=case_id,target_type=target_type,target_id=target_id,branch_name=str(b.get('branch_name') or ''),identity=i,confirmation=str(b.get('confirmation') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.post('/api/cases/{case_id}/phase17/state/branches/{branch_id}/stage')
    async def stage(case_id:str,branch_id:str,request:Request):
        i=caseauth(request,case_id,'dossier.write'); b=await request.json()
        try:return ctx.build395.stage_case_state_branch(case_id=case_id,branch_id=branch_id,version_id=str(b.get('version_id') or ''),identity=i,confirmation=str(b.get('confirmation') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.post('/api/cases/{case_id}/phase17/state/{target_type}/{target_id}/adoption-proposals')
    async def propose(case_id:str,target_type:str,target_id:str,request:Request):
        i=caseauth(request,case_id,'dossier.write'); b=await request.json()
        try:return ctx.build395.propose_case_state_adoption(case_id=case_id,target_type=target_type,target_id=target_id,candidate_version_id=str(b.get('candidate_version_id') or ''),source_branch_id=str(b.get('source_branch_id') or ''),proposal_kind=str(b.get('proposal_kind') or 'adopt'),rationale=str(b.get('rationale') or ''),identity=i)
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.post('/api/cases/{case_id}/phase17/state/adoption-proposals/{proposal_id}/review')
    async def review(case_id:str,proposal_id:str,request:Request):
        i=caseauth(request,case_id,'dossier.write'); b=await request.json()
        try:return ctx.build395.review_case_state_adoption(case_id=case_id,proposal_id=proposal_id,identity=i,disposition=str(b.get('disposition') or ''),rationale=str(b.get('rationale') or ''),confirmation=str(b.get('confirmation') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.post('/api/cases/{case_id}/phase17/state/adoption-proposals/{proposal_id}/apply')
    async def apply(case_id:str,proposal_id:str,request:Request):
        i=caseauth(request,case_id,'dossier.write'); b=await request.json()
        try:return ctx.build395.apply_case_state_adoption(case_id=case_id,proposal_id=proposal_id,identity=i,confirmation=str(b.get('confirmation') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    return app
