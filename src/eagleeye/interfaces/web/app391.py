from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app390 import create_workspace_app390
from eagleeye_pro.phase17.investigation_synthesis391 import CONFIRM_CLAIM_REVIEW, CONFIRM_HYPOTHESIS_REVIEW, CONFIRM_KERNEL_ADMISSION, CONFIRM_SNAPSHOT


def create_workspace_app391(*, base_dir: str|Path|None=None) -> FastAPI:
    app=create_workspace_app390(base_dir=base_dir); ctx=app.state.context; team_identity=ctx.team_identity_359; _=ctx.build391
    app.title='EagleEye Intelligence Platform – Build 391.0 AI Investigation Synthesis'; app.version='391.0'
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
        try: ctx.build380.authorize(ident,case_id=case_id,capability=capability,object_type='phase17_v391',object_id=case_id)
        except PermissionError as exc: raise HTTPException(403,str(exc))
        return ident
    @app.get('/health')
    def health391():
        prev=dict(base_health() if callable(base_health) else {'ok':True}); prev.update({'build':'391.0','phase17_builds_completed':11,'phase17_integrated':True,'ai_investigation_synthesis':True,'automatic_truth_acceptance':False,'legacy_kernel_probability_path_used':False}); return prev
    @app.get('/api/build391/phase17-status')
    def status(request:Request): auth(request); return ctx.build391.phase17_status()
    @app.post('/api/cases/{case_id}/phase17/synthesis/claims/from-review/{review_id}')
    def synthesize(case_id:str,review_id:str,request:Request):
        ident=caseauth(request,case_id,'source.review')
        try: return ctx.build391.synthesize_corroboration_review(case_id=case_id,review_id=review_id,identity=ident)
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.post('/api/cases/{case_id}/phase17/synthesis/claims/{claim_id}/review')
    async def review_claim(case_id:str,claim_id:str,request:Request):
        ident=caseauth(request,case_id,'source.review'); body=await request.json()
        try: return ctx.build391.review_synthesis_claim(case_id=case_id,claim_id=claim_id,identity=ident,disposition=str(body.get('disposition') or ''),rationale=str(body.get('rationale') or ''),confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.post('/api/cases/{case_id}/phase17/synthesis/hypotheses')
    async def propose_hypothesis(case_id:str,request:Request):
        ident=caseauth(request,case_id,'dossier.write'); body=await request.json()
        try: return ctx.build391.propose_hypothesis(case_id=case_id,title=str(body.get('title') or ''),statement=str(body.get('statement') or ''),test_plan=str(body.get('test_plan') or ''),claim_relations=dict(body.get('claim_relations') or {}),identity=ident,origin=str(body.get('origin') or 'ai_proposed_for_review'))
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.post('/api/cases/{case_id}/phase17/synthesis/hypotheses/{hypothesis_id}/review')
    async def review_hypothesis(case_id:str,hypothesis_id:str,request:Request):
        ident=caseauth(request,case_id,'dossier.write'); body=await request.json()
        try: return ctx.build391.review_synthesis_hypothesis(case_id=case_id,hypothesis_id=hypothesis_id,identity=ident,disposition=str(body.get('disposition') or ''),rationale=str(body.get('rationale') or ''),confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.post('/api/cases/{case_id}/phase17/synthesis/{object_type}/{object_id}/kernel')
    async def kernel(case_id:str,object_type:str,object_id:str,request:Request):
        ident=caseauth(request,case_id,'dossier.write'); body=await request.json(); confirmation=str(body.get('confirmation') or '')
        try:
            if object_type=='claim': return ctx.build391.admit_claim_to_kernel(case_id=case_id,claim_id=object_id,identity=ident,confirmation=confirmation)
            if object_type=='hypothesis': return ctx.build391.admit_hypothesis_to_kernel(case_id=case_id,hypothesis_id=object_id,identity=ident,confirmation=confirmation)
            raise ValueError('object_type must be claim or hypothesis')
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.get('/api/cases/{case_id}/phase17/ai-synthesis-feed')
    def feed(case_id:str,request:Request): ident=caseauth(request,case_id,'case.read'); return ctx.build391.ai_investigation_synthesis_feed(case_id=case_id,identity=ident)
    @app.post('/api/cases/{case_id}/phase17/synthesis/snapshot')
    async def snapshot(case_id:str,request:Request):
        ident=caseauth(request,case_id,'dossier.write'); body=await request.json()
        try: return ctx.build391.create_synthesis_snapshot(case_id=case_id,identity=ident,confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403,str(exc))
    return app
