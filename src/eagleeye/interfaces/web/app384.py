from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app380 import create_workspace_app380


def create_workspace_app384(*, base_dir: str | Path | None = None) -> FastAPI:
    app=create_workspace_app380(base_dir=base_dir); ctx=app.state.context; team_identity=ctx.team_identity_359
    remote_enabled=bool(ctx.remote_team_364.config().get("enabled")); app.title="EagleEye Intelligence Platform – Build 384.0 Phase 17 Integrated Data Planning"; app.version="384.0"
    base_health=next((r.endpoint for r in app.router.routes if getattr(r,"path",None)=="/health" and "GET" in set(getattr(r,"methods",set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,"path",None)=="/health" and "GET" in set(getattr(r,"methods",set()) or set()))]
    def fp(request:Request)->str:
        material="|".join((request.headers.get("user-agent",""),request.headers.get("accept-language",""),(request.client.host if request.client else ""))); return hashlib.sha256(material.encode()).hexdigest()
    def auth(request:Request)->dict[str,Any]:
        token=request.cookies.get(COOKIE,""); ident=team_identity.validate_session(token,client_fingerprint=fp(request),touch=True)
        if not ident: raise HTTPException(401,"Anmeldung erforderlich oder Sitzung abgelaufen")
        return ident
    def caseauth(request:Request,case_id:str,capability:str="case.read")->dict[str,Any]:
        ident=auth(request)
        try: ctx.build380.authorize(ident,case_id=case_id,capability=capability,object_type="phase17_v384",object_id=case_id)
        except PermissionError as exc: raise HTTPException(403,str(exc))
        return ident
    @app.get('/health')
    def health384():
        p=dict(base_health() if callable(base_health) else {"ok":True}); p.update({"build":"384.0","phase17_builds_completed":4,"phase17_integrated":True,"network_execution_added":False}); return p
    @app.get('/api/build384/phase17-status')
    def phase17_status(request:Request): auth(request); return ctx.build384.phase17_status()
    @app.get('/api/cases/{case_id}/phase17/control-plane')
    def control(case_id:str,request:Request): caseauth(request,case_id); return ctx.build381.snapshot(case_id)
    @app.get('/api/cases/{case_id}/phase17/coverage')
    def coverage(case_id:str,request:Request): caseauth(request,case_id); return ctx.build382.coverage(case_id)
    @app.post('/api/cases/{case_id}/phase17/acquisition-plan')
    async def acquisition(case_id:str,request:Request):
        caseauth(request,case_id); body=await request.json(); return ctx.build383.plan_acquisition(case_id=case_id,mission=str(body.get('mission') or ''),jurisdictions=tuple(body.get('jurisdictions') or ()),entity_types=tuple(body.get('entity_types') or ()),source_classes=tuple(body.get('source_classes') or ()),confirmation=body.get('confirmation'))
    @app.post('/api/cases/{case_id}/phase17/research-waves')
    async def waves(case_id:str,request:Request):
        caseauth(request,case_id); body=await request.json(); return ctx.build384.plan_research_waves(case_id=case_id,mission=str(body.get('mission') or ''),jurisdictions=tuple(body.get('jurisdictions') or ()),entity_types=tuple(body.get('entity_types') or ()),source_classes=tuple(body.get('source_classes') or ()),selector_confirmation=body.get('selector_confirmation'),wave_confirmation=body.get('wave_confirmation'),max_steps_per_wave=max(1,min(int(body.get('max_steps_per_wave',6)),20)))
    return app
