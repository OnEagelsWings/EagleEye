from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from .app379 import COOKIE, create_workspace_app379


def _drop(app: FastAPI, path: str, methods: set[str]) -> None:
    app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, "path", None) == path and methods.intersection(set(getattr(r, "methods", set()) or set())))]


def create_workspace_app380(*, base_dir: str | Path | None = None) -> FastAPI:
    app = create_workspace_app379(base_dir=base_dir)
    ctx = app.state.context
    team_identity = ctx.team_identity_359
    remote_enabled = bool(ctx.remote_team_364.config().get("enabled"))
    app.title = "EagleEye Intelligence Platform – Build 380.0 Professional Pilot / Production Decision"
    app.version = "380.0"
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
            ctx.build380.protect_remote_session(token=token, observed_fingerprint=fingerprint, observed_ip=(request.client.host if request.client else ""))
        if not ident:
            raise HTTPException(401, "Anmeldung erforderlich oder Sitzung abgelaufen")
        return ident

    def caseauth(request: Request, case_id: str, capability: str = "case.read") -> dict[str, Any]:
        ident = auth(request)
        try:
            ctx.build380.authorize(ident, case_id=case_id, capability=capability, object_type="professional_pilot_v380", object_id=case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        return ident

    @app.get("/health")
    def health380():
        p = dict(base_health() if callable(base_health) else {"ok": True})
        decision = ctx.build380.final_decision()
        gate = ctx.build380.qualified_gate()
        p.update({
            "build": "380.0",
            "phase16_builds_completed": 20,
            "phase16_complete": True,
            "final_decision": decision["decision"],
            "professional_pilot_ready": bool(decision["professional_pilot_ready"]),
            "production_candidate": bool(decision["production_candidate"]),
            "production_release_ready": bool(gate["production_release_ready"]),
            "external_qualification_validated": bool(decision["external_qualification_validated"]),
            "crawler_improvement_build": 380,
        })
        return p

    @app.get("/api/build380/phase16-status")
    def phase(request: Request):
        auth(request)
        return ctx.build380.phase16_status()

    @app.get("/api/build380/final-status")
    def final(request: Request):
        auth(request)
        return ctx.build380.dashboard()

    @app.get("/api/build380/final-decision")
    def decision(request: Request):
        auth(request)
        return ctx.build380.final_decision()

    @app.get("/api/build380/crawler-slo-gate")
    def crawler_slo(request: Request):
        auth(request)
        return ctx.build380.final_crawler_slo_gate()

    @app.get("/api/build380/external-validation-matrix")
    def ext_matrix(request: Request):
        auth(request)
        return ctx.build380.external_validation_matrix()

    @app.get("/api/cases/{case_id}/pilot380/telemetry")
    def telemetry(case_id: str, request: Request):
        caseauth(request, case_id, "case.read")
        return ctx.build380.pilot_telemetry(case_id=case_id)

    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def autonomous(case_id: str, request: Request):
        caseauth(request, case_id, "case.read")
        body = await request.json()
        return ctx.build380.run_autonomous_investigation(case_id=case_id, max_ticks=max(1, min(int(body.get("max_ticks", 8)), 20)))

    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def opsec(case_id: str, request: Request):
        caseauth(request, case_id, "case.manage")
        return ctx.build380.autonomous_opsec_protect(case_id=case_id)

    return app
