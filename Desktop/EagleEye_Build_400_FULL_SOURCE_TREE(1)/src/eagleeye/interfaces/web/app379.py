from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from .app378 import COOKIE, create_workspace_app378


def _drop(app: FastAPI, path: str, methods: set[str]) -> None:
    app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, "path", None) == path and methods.intersection(set(getattr(r, "methods", set()) or set())))]


def create_workspace_app379(*, base_dir: str | Path | None = None) -> FastAPI:
    app = create_workspace_app378(base_dir=base_dir)
    ctx = app.state.context
    team_identity = ctx.team_identity_359
    remote_enabled = bool(ctx.remote_team_364.config().get("enabled"))
    app.title = "EagleEye Intelligence Platform – Build 379.0 External Qualification"
    app.version = "379.0"
    base_health = next((r.endpoint for r in app.router.routes if getattr(r, "path", None) == "/health" and "GET" in set(getattr(r, "methods", set()) or set())), None)
    for path, methods in [
        ("/health", {"GET"}),
        ("/api/cases/{case_id}/phase16/autonomous-cycle", {"POST"}),
        ("/api/cases/{case_id}/phase16/opsec-protect", {"POST"}),
    ]:
        _drop(app, path, methods)

    def fp(request: Request) -> str:
        material = "|".join((request.headers.get("user-agent", ""), request.headers.get("accept-language", ""), (request.client.host if request.client else "")))
        return hashlib.sha256(material.encode()).hexdigest()

    def auth(request: Request) -> dict[str, Any]:
        token = request.cookies.get(COOKIE, "")
        fingerprint = fp(request)
        ident = team_identity.validate_session(token, client_fingerprint=fingerprint, touch=True)
        if not ident and token and remote_enabled:
            ctx.build379.protect_remote_session(token=token, observed_fingerprint=fingerprint, observed_ip=(request.client.host if request.client else ""))
        if not ident:
            raise HTTPException(401, "Anmeldung erforderlich oder Sitzung abgelaufen")
        return ident

    def caseauth(request: Request, case_id: str, capability: str = "case.read") -> dict[str, Any]:
        ident = auth(request)
        try:
            ctx.build379.authorize(ident, case_id=case_id, capability=capability, object_type="external_qualification_v379", object_id=case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        return ident

    @app.get("/health")
    def health379():
        p = dict(base_health() if callable(base_health) else {"ok": True})
        ext = ctx.build379.external_qualification_status()
        p.update({
            "build": "379.0",
            "phase16_builds_completed": 19,
            "external_qualification_framework": True,
            "local_prequalification_supported": True,
            "external_qualification_validated": bool(ext.get("externally_validated")),
            "production_fault_injection_api": False,
            "crawler_improvement_build": 379,
            "production_release_ready": False,
        })
        return p

    @app.get("/api/build379/phase16-status")
    def phase(request: Request):
        auth(request)
        return ctx.build379.phase16_status()

    @app.get("/api/build379/final-status")
    def final(request: Request):
        auth(request)
        return ctx.build379.dashboard()

    @app.get("/api/build379/qualification-contract")
    def contract(request: Request):
        auth(request)
        return ctx.build379.external_qualification_contract()

    @app.get("/api/build379/external-receipt-status")
    def receipt(request: Request):
        auth(request)
        return ctx.build379.external_qualification_status()

    @app.get("/api/cases/{case_id}/qualification379/snapshot")
    def snapshot(case_id: str, request: Request):
        caseauth(request, case_id, "case.read")
        return ctx.build379.qualification_snapshot(case_id=case_id)

    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def autonomous(case_id: str, request: Request):
        caseauth(request, case_id, "case.read")
        body = await request.json()
        return ctx.build379.run_autonomous_investigation(case_id=case_id, max_ticks=max(1, min(int(body.get("max_ticks", 8)), 20)))

    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def opsec(case_id: str, request: Request):
        caseauth(request, case_id, "case.manage")
        return ctx.build379.autonomous_opsec_protect(case_id=case_id)

    return app
