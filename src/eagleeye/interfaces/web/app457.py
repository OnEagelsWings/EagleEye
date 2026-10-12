from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request

from .app456 import create_workspace_app456
from .app448 import COOKIE
from .app449 import _drop


def create_workspace_app457(*, base_dir=None):
    app = create_workspace_app456(base_dir=base_dir)
    ctx = app.state.context
    app.title = "EagleEye Build 457.0 Workspace Reliability + UI Functional Closure"
    app.version = "457.0"
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health():
        return {"ok": True, "status": "ok", "build": "457.0"}

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

    def authorize_case(identity, case_id, capability="case.read"):
        try:
            ctx.team_governance_359.authorize(
                identity,
                case_id=case_id,
                capability=capability,
                object_type="build457",
                object_id=case_id,
            )
        except PermissionError as exc:
            raise HTTPException(403, "Keine Berechtigung für diesen Fall") from exc

    @app.get("/api/build457/status")
    def status(request: Request):
        auth(request)
        return ctx.build457.build457_status()

    @app.get("/api/build457/cases/{case_id}/workspace")
    def workspace(case_id: str, request: Request):
        identity = auth(request)
        authorize_case(identity, case_id, "case.read")
        return ctx.build457.workspace_snapshot_457(identity=identity, case_id=case_id)

    return app
