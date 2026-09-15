from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app392 import create_workspace_app392
from eagleeye_pro.phase17.investigator_dialogue393 import CONFIRM_PROPOSAL_REVIEW, CONFIRM_KERNEL_ADMISSION


def create_workspace_app393(*, base_dir: str|Path|None=None) -> FastAPI:
    app=create_workspace_app392(base_dir=base_dir); ctx=app.state.context; team_identity=ctx.team_identity_359; _=ctx.build393
    app.title='EagleEye Intelligence Platform – Build 393.0 Investigator Dialogue & Challenge'; app.version='393.0'
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
        try: ctx.build380.authorize(ident,case_id=case_id,capability=capability,object_type='phase17_v393',object_id=case_id)
        except PermissionError as exc: raise HTTPException(403,str(exc))
        return ident
    @app.get('/health')
    def health393():
        prev=dict(base_health() if callable(base_health) else {'ok':True}); prev.update({'build':'393.0','phase17_builds_completed':13,'phase17_integrated':True,'investigator_dialogue':True,'challenge_engine':True,'automatic_upstream_mutation':False,'automatic_go_issuance':False,'execution_authority':False,'truth_probability':False}); return prev
    @app.get('/api/build393/phase17-status')
    def status(request:Request): auth(request); return ctx.build393.phase17_status()
    @app.post('/api/cases/{case_id}/phase17/dialogue/sessions')
    async def create_session(case_id:str,request:Request):
        ident=caseauth(request,case_id,'dossier.write'); body=await request.json()
        try: return ctx.build393.create_investigator_dialogue(case_id=case_id,workspace_id=str(body.get('workspace_id') or ''),identity=ident)
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.get('/api/cases/{case_id}/phase17/dialogue/sessions/{session_id}')
    def get_session(case_id:str,session_id:str,request:Request):
        ident=caseauth(request,case_id,'case.read')
        try: return ctx.build393.investigator_dialogue(case_id=case_id,session_id=session_id,identity=ident)
        except KeyError: raise HTTPException(404,'Dialogue session not found')
    @app.post('/api/cases/{case_id}/phase17/dialogue/sessions/{session_id}/challenge')
    async def challenge(case_id:str,session_id:str,request:Request):
        ident=caseauth(request,case_id,'dossier.write'); body=await request.json()
        try: return ctx.build393.challenge_reasoning(case_id=case_id,session_id=session_id,prompt=str(body.get('prompt') or ''),mode=str(body.get('mode') or ''),target_type=str(body.get('target_type') or ''),target_id=str(body.get('target_id') or ''),identity=ident)
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.post('/api/cases/{case_id}/phase17/dialogue/proposals/{proposal_id}/review')
    async def review_proposal(case_id:str,proposal_id:str,request:Request):
        ident=caseauth(request,case_id,'dossier.write'); body=await request.json()
        try: return ctx.build393.review_challenge_proposal(case_id=case_id,proposal_id=proposal_id,identity=ident,disposition=str(body.get('disposition') or ''),rationale=str(body.get('rationale') or ''),confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.post('/api/cases/{case_id}/phase17/dialogue/turns/{turn_id}/kernel')
    async def kernel(case_id:str,turn_id:str,request:Request):
        ident=caseauth(request,case_id,'dossier.write'); body=await request.json()
        try: return ctx.build393.admit_challenge_to_kernel(case_id=case_id,turn_id=turn_id,identity=ident,confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.get('/api/cases/{case_id}/phase17/ai-dialogue-feed')
    def feed(case_id:str,request:Request): ident=caseauth(request,case_id,'case.read'); return ctx.build393.ai_investigator_dialogue_feed(case_id=case_id,identity=ident)
    return app
