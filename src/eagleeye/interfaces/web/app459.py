from __future__ import annotations

import hashlib
from fastapi import HTTPException,Request
from starlette.concurrency import run_in_threadpool

from .app458 import create_workspace_app458
from .app448 import COOKIE
from .app449 import _drop


def create_workspace_app459(*,base_dir=None):
    app=create_workspace_app458(base_dir=base_dir)
    ctx=app.state.context
    service=ctx.field_readiness_459
    app.title="EagleEye Build 459.0 — Field Workflow Readiness"
    app.version="459.0"
    _drop(app,"/health",{"GET"})

    def auth(request:Request):
        material="|".join((
            request.headers.get("user-agent",""),
            request.headers.get("accept-language",""),
            request.client.host if request.client else "",
        ))
        ident=ctx.team_identity_359.validate_session(
            request.cookies.get(COOKIE,""),
            client_fingerprint=hashlib.sha256(material.encode()).hexdigest(),touch=True)
        if not ident:
            raise HTTPException(401,"Anmeldung erforderlich")
        return ident

    def failed(error):
        if isinstance(error,PermissionError):
            raise HTTPException(403,str(error)) from error
        if isinstance(error,KeyError):
            raise HTTPException(404,str(error)) from error
        if isinstance(error,ValueError):
            raise HTTPException(422,str(error)) from error
        raise error

    @app.get("/health")
    def health():
        status=ctx.build459.build459_status()
        return {"ok":True,"status":"ok" if status["integrity_valid"] else "hold",
                "build":"459.0","integrity_valid":status["integrity_valid"],
                "next_checkpoint":"460.0","field_resume":True}

    @app.get("/api/build459/status")
    def status(request:Request):
        auth(request)
        return ctx.build459.build459_status()

    @app.get("/api/build459/cases/{case_id}/readiness")
    def case_readiness(case_id:str,request:Request):
        ident=auth(request)
        try:
            return service.snapshot(identity=ident,case_id=case_id)
        except (PermissionError,KeyError,ValueError) as exc:
            failed(exc)

    @app.post("/api/build459/cases/{case_id}/checkpoint")
    async def case_checkpoint(case_id:str,request:Request):
        ident=auth(request)
        try:
            def work():
                with ctx.audit.actor_scope(ident["username"]):
                    return service.checkpoint(identity=ident,case_id=case_id)
            return await run_in_threadpool(work)
        except (PermissionError,KeyError,ValueError) as exc:
            failed(exc)

    @app.get("/api/build459/checkpoints/{run_id}/verify-reopened")
    def verify_reopened(run_id:str,request:Request):
        ident=auth(request)
        try:
            return service.verify_reopened(identity=ident,run_id=run_id)
        except (PermissionError,KeyError,ValueError) as exc:
            failed(exc)

    return app


create_app=create_workspace_app459
