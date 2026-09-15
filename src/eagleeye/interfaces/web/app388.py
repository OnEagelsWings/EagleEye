from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app387 import create_workspace_app387


def create_workspace_app388(*, base_dir: str|Path|None=None) -> FastAPI:
    app=create_workspace_app387(base_dir=base_dir); ctx=app.state.context; team_identity=ctx.team_identity_359; _=ctx.build388
    app.title='EagleEye Intelligence Platform – Build 388.0 Governed Research Waves'; app.version='388.0'
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
    def health388():
        prev=dict(base_health() if callable(base_health) else {'ok':True}); prev.update({'build':'388.0','phase17_builds_completed':8,'phase17_integrated':True,'governed_research_waves':True,'automatic_go_issuance':False}); return prev
    @app.get('/api/build388/phase17-status')
    def status(request:Request): auth(request); return ctx.build388.phase17_status()
    @app.post('/api/cases/{case_id}/phase17/wave-sessions')
    async def start(case_id:str,request:Request):
        ident=caseauth(request,case_id,'crawler.run'); body=await request.json()
        try: return ctx.build388.start_wave_session(case_id=case_id,wave_plan_id=str(body.get('wave_plan_id') or ''),packet_id=str(body.get('packet_id') or ''),identity=ident,confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc))
    @app.post('/api/cases/{case_id}/phase17/wave-sessions/{session_id}/dispatches/{dispatch_id}')
    async def attach(case_id:str,session_id:str,dispatch_id:str,request:Request):
        ident=caseauth(request,case_id,'crawler.run'); body=await request.json()
        try: return ctx.build388.attach_wave_dispatch(case_id=case_id,session_id=session_id,dispatch_id=dispatch_id,identity=ident,confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except KeyError as exc: raise HTTPException(404,str(exc))
    @app.post('/api/cases/{case_id}/phase17/wave-sessions/{session_id}/reconcile')
    def reconcile(case_id:str,session_id:str,request:Request):
        ident=caseauth(request,case_id,'case.read')
        try: return ctx.build388.reconcile_wave_session(case_id=case_id,session_id=session_id,identity=ident)
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except KeyError as exc: raise HTTPException(404,str(exc))
    @app.post('/api/cases/{case_id}/phase17/wave-sessions/{session_id}/advance')
    async def advance(case_id:str,session_id:str,request:Request):
        ident=caseauth(request,case_id,'crawler.run'); body=await request.json()
        try: return ctx.build388.advance_wave_session(case_id=case_id,session_id=session_id,identity=ident,confirmation=str(body.get('confirmation') or ''))
        except PermissionError as exc: raise HTTPException(403,str(exc))
        except KeyError as exc: raise HTTPException(404,str(exc))
    @app.get('/api/cases/{case_id}/phase17/wave-sessions/{session_id}')
    def session(case_id:str,session_id:str,request:Request):
        caseauth(request,case_id,'case.read')
        try: return ctx.build388.wave_session(case_id=case_id,session_id=session_id)
        except KeyError: raise HTTPException(404,'Wave session not found')
    @app.get('/api/cases/{case_id}/phase17/wave-sessions/{session_id}/verify')
    def verify(case_id:str,session_id:str,request:Request):
        caseauth(request,case_id,'case.read')
        try: return ctx.build388.verify_wave_session(case_id=case_id,session_id=session_id)
        except KeyError: raise HTTPException(404,'Wave session not found')
    return app
