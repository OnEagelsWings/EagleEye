from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app388 import create_workspace_app388


def create_workspace_app389(*, base_dir: str|Path|None=None) -> FastAPI:
    app=create_workspace_app388(base_dir=base_dir); ctx=app.state.context; team_identity=ctx.team_identity_359; _=ctx.build389
    app.title='EagleEye Intelligence Platform – Build 389.0 Result Intake & Evidence Normalization'; app.version='389.0'
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
        try: ctx.build380.authorize(ident,case_id=case_id,capability=capability,object_type='phase17_v388',object_id=case_id)
        except PermissionError as exc: raise HTTPException(403,str(exc))
        return ident
    @app.get('/health')
    def health389():
        prev=dict(base_health() if callable(base_health) else {'ok':True}); prev.update({'build':'389.0','phase17_builds_completed':9,'phase17_integrated':True,'result_intake_normalization':True,'automatic_evidence_promotion':False}); return prev
    @app.get('/api/build389/phase17-status')
    def status(request:Request): auth(request); return ctx.build389.phase17_status()
    @app.post('/api/cases/{case_id}/phase17/wave-sessions/{session_id}/normalize-results')
    def normalize(case_id:str,session_id:str,request:Request):
        ident=caseauth(request,case_id,'case.read')
        try: return ctx.build389.normalize_wave_results(case_id=case_id,session_id=session_id,identity=ident)
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except KeyError as exc: raise HTTPException(404,str(exc))
    @app.get('/api/cases/{case_id}/phase17/evidence-candidates')
    def candidates(case_id:str,request:Request,limit:int=200):
        ident=caseauth(request,case_id,'case.read'); return {'case_id':case_id,'candidates':ctx.build389.evidence_candidates(case_id=case_id,identity=ident,limit=limit)}
    @app.get('/api/cases/{case_id}/phase17/ai-candidate-feed')
    def ai_feed(case_id:str,request:Request,limit:int=100):
        ident=caseauth(request,case_id,'case.read'); return ctx.build389.ai_evidence_candidates(case_id=case_id,identity=ident,limit=limit)
    @app.post('/api/cases/{case_id}/phase17/evidence-candidates/{candidate_id}/promote')
    async def promote(case_id:str,candidate_id:str,request:Request):
        ident=caseauth(request,case_id,'source.review'); body=await request.json()
        try: return ctx.build389.promote_evidence_candidate(case_id=case_id,candidate_id=candidate_id,identity=ident,confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except KeyError as exc: raise HTTPException(404,str(exc))
    @app.get('/api/cases/{case_id}/phase17/evidence-candidates/{candidate_id}/verify')
    def verify_candidate(case_id:str,candidate_id:str,request:Request):
        caseauth(request,case_id,'case.read')
        try: return ctx.build389.verify_evidence_candidate(case_id=case_id,candidate_id=candidate_id)
        except KeyError: raise HTTPException(404,'Evidence candidate not found')
    return app
