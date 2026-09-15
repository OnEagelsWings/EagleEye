from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app391 import create_workspace_app391
from eagleeye_pro.phase17.case_reasoning392 import CONFIRM_PLAN_REVIEW, CONFIRM_KERNEL_ADMISSION


def create_workspace_app392(*, base_dir: str|Path|None=None) -> FastAPI:
    app=create_workspace_app391(base_dir=base_dir); ctx=app.state.context; team_identity=ctx.team_identity_359; _=ctx.build392
    app.title='EagleEye Intelligence Platform – Build 392.0 Case Reasoning Workspace'; app.version='392.0'
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
        try: ctx.build380.authorize(ident,case_id=case_id,capability=capability,object_type='phase17_v392',object_id=case_id)
        except PermissionError as exc: raise HTTPException(403,str(exc))
        return ident
    @app.get('/health')
    def health392():
        prev=dict(base_health() if callable(base_health) else {'ok':True}); prev.update({'build':'392.0','phase17_builds_completed':12,'phase17_integrated':True,'case_reasoning_workspace':True,'automatic_go_issuance':False,'execution_authority':False,'truth_probability':False}); return prev
    @app.get('/api/build392/phase17-status')
    def status(request:Request): auth(request); return ctx.build392.phase17_status()
    @app.post('/api/cases/{case_id}/phase17/reasoning/workspaces')
    def create_workspace(case_id:str,request:Request):
        ident=caseauth(request,case_id,'dossier.write')
        try: return ctx.build392.create_case_reasoning_workspace(case_id=case_id,identity=ident)
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.get('/api/cases/{case_id}/phase17/reasoning/workspaces/{workspace_id}')
    def workspace(case_id:str,workspace_id:str,request:Request):
        ident=caseauth(request,case_id,'case.read')
        try: return ctx.build392.case_reasoning_workspace(case_id=case_id,workspace_id=workspace_id,identity=ident)
        except KeyError: raise HTTPException(404,'Reasoning workspace not found')
    @app.post('/api/cases/{case_id}/phase17/reasoning/workspaces/{workspace_id}/plan')
    def propose_plan(case_id:str,workspace_id:str,request:Request):
        ident=caseauth(request,case_id,'dossier.write')
        try: return ctx.build392.propose_next_investigation_plan(case_id=case_id,workspace_id=workspace_id,identity=ident)
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.post('/api/cases/{case_id}/phase17/reasoning/plans/{plan_id}/review')
    async def review_plan(case_id:str,plan_id:str,request:Request):
        ident=caseauth(request,case_id,'dossier.write'); body=await request.json()
        try: return ctx.build392.review_reasoning_plan(case_id=case_id,plan_id=plan_id,identity=ident,disposition=str(body.get('disposition') or ''),rationale=str(body.get('rationale') or ''),confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.post('/api/cases/{case_id}/phase17/reasoning/plans/{plan_id}/kernel')
    async def kernel(case_id:str,plan_id:str,request:Request):
        ident=caseauth(request,case_id,'dossier.write'); body=await request.json()
        try: return ctx.build392.admit_reasoning_plan_to_kernel(case_id=case_id,plan_id=plan_id,identity=ident,confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.get('/api/cases/{case_id}/phase17/ai-reasoning-feed')
    def feed(case_id:str,request:Request): ident=caseauth(request,case_id,'case.read'); return ctx.build392.ai_case_reasoning_feed(case_id=case_id,identity=ident)
    return app
