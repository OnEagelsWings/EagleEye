from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from .app379 import COOKIE
from .app386 import create_workspace_app386


def create_workspace_app387(*, base_dir: str | Path | None = None) -> FastAPI:
    app = create_workspace_app386(base_dir=base_dir)
    ctx = app.state.context
    team_identity = ctx.team_identity_359
    _ = ctx.build387
    app.title = "EagleEye Intelligence Platform – Build 387.0 Controlled Executor"
    app.version = "387.0"

    base_health = next((r.endpoint for r in app.router.routes if getattr(r, "path", None) == "/health" and "GET" in set(getattr(r, "methods", set()) or set())), None)
    app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, "path", None) == "/health" and "GET" in set(getattr(r, "methods", set()) or set()))]

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
            ctx.build380.authorize(identity, case_id=case_id, capability=capability, object_type="phase17_v387", object_id=case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        return identity

    @app.get("/health")
    def health387():
        previous = dict(base_health() if callable(base_health) else {"ok": True})
        previous.update({
            "build": "387.0",
            "phase17_builds_completed": 7,
            "phase17_integrated": True,
            "controlled_executor": True,
            "direct_network_fetch_by_executor": False,
        })
        return previous

    @app.get("/api/build387/phase17-status")
    def phase17_status(request: Request):
        auth(request)
        return ctx.build387.phase17_status()

    @app.post("/api/cases/{case_id}/phase17/go-grants/{grant_id}/execute")
    async def execute_grant(case_id: str, grant_id: str, request: Request):
        identity = caseauth(request, case_id, "crawler.run")
        body = await request.json()
        try:
            return ctx.build387.execute_grant(
                case_id=case_id,
                grant_id=grant_id,
                grant_token=str(body.get("grant_token") or ""),
                identity=identity,
                confirmation=str(body.get("confirmation") or ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(400, str(exc))

    @app.get("/api/cases/{case_id}/phase17/execution-dispatches/{dispatch_id}")
    def dispatch(case_id: str, dispatch_id: str, request: Request):
        caseauth(request, case_id, "case.read")
        try:
            return ctx.build387.execution_dispatch(case_id=case_id, dispatch_id=dispatch_id)
        except KeyError:
            raise HTTPException(404, "Execution dispatch not found")

    @app.get("/api/cases/{case_id}/phase17/execution-dispatches/{dispatch_id}/verify")
    def verify_dispatch(case_id: str, dispatch_id: str, request: Request):
        caseauth(request, case_id, "case.read")
        try:
            return ctx.build387.verify_execution_dispatch(case_id=case_id, dispatch_id=dispatch_id)
        except KeyError:
            raise HTTPException(404, "Execution dispatch not found")

    return app
