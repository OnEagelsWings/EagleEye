from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app389 import create_workspace_app389


def create_workspace_app390(*, base_dir: str|Path|None=None) -> FastAPI:
    app=create_workspace_app389(base_dir=base_dir); ctx=app.state.context; team_identity=ctx.team_identity_359; _=ctx.build390
    app.title='EagleEye Intelligence Platform – Build 390.0 Evidence Review & Corroboration'; app.version='390.0'
    base_health=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def fp(request:Request)->str:
        material='|'.join((request.headers.get('user-agent',''),request.headers.get('accept-language',''),(request.client.host if request.client else ''))); return hashlib.sha256(material.encode()).hexdigest()
    def auth(request:Request)->dict[str,Any]:
        ident=team_identity.validate_session(request.cookies.get(COOKIE,''),client_fingerprint=fp(request),touch=True)
        if not ident: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return ident
    def caseauth(request:Request,case_id:str,capability:str='case.read')->dict[str,Any]:
        ident=auth(request)
        try: ctx.build380.authorize(ident,case_id=case_id,capability=capability,object_type='phase17_v390',object_id=case_id)
        except PermissionError as exc: raise HTTPException(403,str(exc))
        return ident
    @app.get('/health')
    def health390():
        prev=dict(base_health() if callable(base_health) else {'ok':True}); prev.update({'build':'390.0','phase17_builds_completed':10,'phase17_integrated':True,'evidence_review_corroboration':True,'automatic_truth_acceptance':False}); return prev
    @app.get('/api/build390/phase17-status')
    def status(request:Request): auth(request); return ctx.build390.phase17_status()
    @app.get('/api/build390/source-independence-profiles')
    def profiles(request:Request): auth(request); return {'profiles':ctx.build390.source_independence_profiles()}
    @app.post('/api/cases/{case_id}/phase17/evidence-candidates/{candidate_id}/independence-review')
    async def independence(case_id:str,candidate_id:str,request:Request):
        ident=caseauth(request,case_id,'source.review'); body=await request.json()
        try:
            return ctx.build390.review_source_independence(case_id=case_id,candidate_id=candidate_id,identity=ident,source_family=str(body.get('source_family') or ''),independence_group=str(body.get('independence_group') or ''),origin_key=str(body.get('origin_key') or ''),countable=bool(body.get('countable')),rationale=str(body.get('rationale') or ''),confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.post('/api/cases/{case_id}/phase17/corroboration-reviews')
    async def create_review(case_id:str,request:Request):
        ident=caseauth(request,case_id,'source.review'); body=await request.json()
        try: return ctx.build390.create_corroboration_review(case_id=case_id,proposition=str(body.get('proposition') or ''),candidate_stances=dict(body.get('candidate_stances') or {}),identity=ident)
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.post('/api/cases/{case_id}/phase17/corroboration-reviews/{review_id}/assess')
    async def assess(case_id:str,review_id:str,request:Request):
        ident=caseauth(request,case_id,'source.review'); body=await request.json()
        try: return ctx.build390.assess_corroboration_review(case_id=case_id,review_id=review_id,identity=ident,confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.post('/api/cases/{case_id}/phase17/corroboration-reviews/{review_id}/finalize')
    async def finalize(case_id:str,review_id:str,request:Request):
        ident=caseauth(request,case_id,'source.review'); body=await request.json()
        try: return ctx.build390.finalize_corroboration_review(case_id=case_id,review_id=review_id,identity=ident,disposition=str(body.get('disposition') or ''),confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.get('/api/cases/{case_id}/phase17/corroboration-reviews/{review_id}')
    def review(case_id:str,review_id:str,request:Request):
        ident=caseauth(request,case_id,'case.read')
        try: return ctx.build390.corroboration_review(case_id=case_id,review_id=review_id,identity=ident)
        except KeyError: raise HTTPException(404,'Corroboration review not found')
    @app.get('/api/cases/{case_id}/phase17/ai-corroboration-feed')
    def feed(case_id:str,request:Request,limit:int=100):
        ident=caseauth(request,case_id,'case.read'); return ctx.build390.ai_corroboration_feed(case_id=case_id,identity=ident,limit=limit)
    return app
