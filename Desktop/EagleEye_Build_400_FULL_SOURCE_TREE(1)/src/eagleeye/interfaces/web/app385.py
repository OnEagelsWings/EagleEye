from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from .app379 import COOKIE
from .app384 import create_workspace_app384


def create_workspace_app385(*, base_dir: str | Path | None = None) -> FastAPI:
    app = create_workspace_app384(base_dir=base_dir)
    ctx = app.state.context
    team_identity = ctx.team_identity_359
    _ = ctx.build385
    app.title = "EagleEye Intelligence Platform – Build 385.0 Acquisition Orchestration"
    app.version = "385.0"

    base_health = next(
        (r.endpoint for r in app.router.routes if getattr(r, "path", None) == "/health" and "GET" in set(getattr(r, "methods", set()) or set())),
        None,
    )
    app.router.routes[:] = [
        r for r in app.router.routes
        if not (getattr(r, "path", None) == "/health" and "GET" in set(getattr(r, "methods", set()) or set()))
    ]

    def fingerprint(request: Request) -> str:
        material = "|".join((request.headers.get("user-agent", ""), request.headers.get("accept-language", ""), (request.client.host if request.client else "")))
        return hashlib.sha256(material.encode()).hexdigest()

    def auth(request: Request) -> dict[str, Any]:
        token = request.cookies.get(COOKIE, "")
        identity = team_identity.validate_session(token, client_fingerprint=fingerprint(request), touch=True)
        if not identity:
            raise HTTPException(401, "Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity

    def caseauth(request: Request, case_id: str, capability: str = "case.read") -> dict[str, Any]:
        identity = auth(request)
        try:
            ctx.build380.authorize(identity, case_id=case_id, capability=capability, object_type="phase17_v385", object_id=case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        return identity

    @app.get("/health")
    def health385():
        previous = dict(base_health() if callable(base_health) else {"ok": True})
        previous.update({
            "build": "385.0",
            "phase17_builds_completed": 5,
            "phase17_integrated": True,
            "acquisition_orchestration": True,
            "network_execution_added": False,
        })
        return previous

    @app.get("/api/build385/phase17-status")
    def phase17_status(request: Request):
        auth(request)
        return ctx.build385.phase17_status()

    @app.get("/api/build385/acquisition-capabilities")
    def acquisition_capabilities(request: Request):
        auth(request)
        return {"build": "385.0", "capabilities": ctx.build385.acquisition_capabilities()}

    @app.post("/api/cases/{case_id}/phase17/acquisition-packets")
    async def compile_packet(case_id: str, request: Request):
        identity = caseauth(request, case_id, "research.run")
        body = await request.json()
        return ctx.build385.compile_acquisition_packet(
            case_id=case_id,
            wave_plan_id=str(body.get("wave_plan_id") or ""),
            identifiers=dict(body.get("identifiers") or {}),
            actor=str(identity.get("username") or "local-analyst"),
        )

    @app.get("/api/cases/{case_id}/phase17/acquisition-packets/{packet_id}")
    def packet(case_id: str, packet_id: str, request: Request):
        caseauth(request, case_id, "case.read")
        try:
            return ctx.build385.acquisition_packet(case_id=case_id, packet_id=packet_id)
        except KeyError:
            raise HTTPException(404, "Acquisition packet not found")

    @app.post("/api/cases/{case_id}/phase17/acquisition-packets/{packet_id}/prepare")
    async def prepare_packet(case_id: str, packet_id: str, request: Request):
        identity = caseauth(request, case_id, "research.run")
        body = await request.json()
        try:
            return ctx.build385.prepare_acquisition_packet(
                case_id=case_id,
                packet_id=packet_id,
                identity=identity,
                confirmation=str(body.get("confirmation") or ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc))

    @app.get("/api/cases/{case_id}/phase17/acquisition-packets/{packet_id}/execution-readiness")
    def execution_readiness(case_id: str, packet_id: str, request: Request):
        identity = caseauth(request, case_id, "case.read")
        try:
            return ctx.build385.acquisition_execution_readiness(case_id=case_id, packet_id=packet_id, identity=identity)
        except KeyError:
            raise HTTPException(404, "Acquisition packet not found")

    return app
