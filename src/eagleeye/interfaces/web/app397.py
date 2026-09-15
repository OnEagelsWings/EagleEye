from __future__ import annotations
import hashlib
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app396 import create_workspace_app396
from eagleeye_pro.phase17.argumentative_analyst397 import CONFIRM_REVIEW


def create_workspace_app397(*, base_dir: str|Path|None=None) -> FastAPI:
    app=create_workspace_app396(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build397
    app.title='EagleEye Intelligence Platform – Build 397.0 Argumentative AI Analyst & Crawler Readiness Hardening'; app.version='397.0'
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
        try: ctx.build380.authorize(i,case_id=case_id,capability=cap,object_type='phase17_v397',object_id=case_id)
        except PermissionError as e: raise HTTPException(403,str(e))
        return i
    @app.get('/health')
    def health397():
        prev=dict(base_health() if callable(base_health) else {'ok':True}); prev.update({'build':'397.0','phase17_builds_completed':17,'argumentative_ai_analyst':True,'robots_parser_hardened':True,'robots_fail_closed':True,'execution_authority':False,'truth_probability':False}); return prev
    @app.get('/api/build397/phase17-status')
    def status(request:Request): auth(request); return ctx.build397.phase17_status()
    @app.post('/api/cases/{case_id}/phase17/analyst/assessments')
    async def assess(case_id:str,request:Request):
        i=caseauth(request,case_id,'case.read'); b=await request.json()
        try:return ctx.build397.assess_argumentation(case_id=case_id,target_type=str(b.get('target_type') or ''),target_id=str(b.get('target_id') or ''),identity=i)
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.get('/api/cases/{case_id}/phase17/analyst/assessments/{assessment_id}')
    def get_assessment(case_id:str,assessment_id:str,request:Request): return ctx.build397.analyst_assessment(case_id=case_id,assessment_id=assessment_id,identity=caseauth(request,case_id))
    @app.post('/api/cases/{case_id}/phase17/analyst/assessments/{assessment_id}/recommendations')
    async def recommend(case_id:str,assessment_id:str,request:Request):
        i=caseauth(request,case_id,'dossier.write'); b=await request.json()
        try:return ctx.build397.propose_analyst_recommendation(case_id=case_id,assessment_id=assessment_id,identity=i,recommendation_type=str(b.get('recommendation_type') or ''),proposal=dict(b.get('proposal') or {}),rationale=str(b.get('rationale') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.post('/api/cases/{case_id}/phase17/analyst/recommendations/{recommendation_id}/review')
    async def review(case_id:str,recommendation_id:str,request:Request):
        i=caseauth(request,case_id,'dossier.write'); b=await request.json()
        try:return ctx.build397.review_analyst_recommendation(case_id=case_id,recommendation_id=recommendation_id,identity=i,disposition=str(b.get('disposition') or ''),rationale=str(b.get('rationale') or ''),confirmation=str(b.get('confirmation') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    return app

create_app=create_workspace_app397
