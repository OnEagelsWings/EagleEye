from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request

from .app454 import create_workspace_app454
from .app448 import COOKIE
from .app449 import _drop


def create_workspace_app455(*, base_dir=None):
    app = create_workspace_app454(base_dir=base_dir)
    ctx = app.state.context
    app.title = "EagleEye Build 455.0 Full Operations / Real-Source Research Gate"
    app.version = "455.0"
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health():
        return {"ok": True, "status": "ok", "build": "455.0"}

    def auth(request: Request):
        material = "|".join((
            request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""),
            request.client.host if request.client else "",
        ))
        identity = ctx.team_identity_359.validate_session(
            request.cookies.get(COOKIE, ""),
            client_fingerprint=hashlib.sha256(material.encode()).hexdigest(),
            touch=True,
        )
        if not identity:
            raise HTTPException(401, "Anmeldung erforderlich")
        return identity

    @app.get("/api/build455/status")
    def status(request: Request):
        auth(request)
        return ctx.build455.build455_status()

    @app.get("/api/build455/cases/{case_id}/qualification")
    def case_qualification(case_id: str, request: Request):
        auth(request)
        item = ctx.build455.operational_research_latest_455(case_id)
        return {"case_id": case_id, "qualification": item}

    return app
