from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from .app379 import COOKIE
from .app385 import create_workspace_app385


def create_workspace_app386(*, base_dir: str | Path | None = None) -> FastAPI:
    app = create_workspace_app385(base_dir=base_dir)
    ctx = app.state.context
    team_identity = ctx.team_identity_359
    _ = ctx.build386
    app.title = "EagleEye Intelligence Platform – Build 386.0 Capability-Scoped GO"
    app.version = "386.0"

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
            ctx.build380.authorize(identity, case_id=case_id, capability=capability, object_type="phase17_v386", object_id=case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        return identity

    @app.get("/health")
    def health386():
        previous = dict(base_health() if callable(base_health) else {"ok": True})
        previous.update({"build": "386.0", "phase17_builds_completed": 6, "phase17_integrated": True, "capability_scoped_go": True, "network_execution_added": False})
        return previous

    @app.get("/api/build386/phase17-status")
    def phase17_status(request: Request):
        auth(request)
        return ctx.build386.phase17_status()

    @app.post("/api/cases/{case_id}/phase17/acquisition-packets/{packet_id}/go-preflight")
    async def go_preflight(case_id: str, packet_id: str, request: Request):
        identity = caseauth(request, case_id, "crawler.run")
        body = await request.json()
        try:
            return ctx.build386.execution_preflight(case_id=case_id, packet_id=packet_id, identity=identity, source_ids=body.get("source_ids"))
        except (PermissionError, KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/cases/{case_id}/phase17/acquisition-packets/{packet_id}/go")
    async def issue_go(case_id: str, packet_id: str, request: Request):
        identity = caseauth(request, case_id, "crawler.run")
        body = await request.json()
        try:
            return ctx.build386.issue_execution_grant(case_id=case_id, packet_id=packet_id, identity=identity, confirmation=str(body.get("confirmation") or ""), source_ids=body.get("source_ids"), ttl_minutes=int(body.get("ttl_minutes") or 10))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc))

    @app.get("/api/cases/{case_id}/phase17/go-grants/{grant_id}")
    def grant(case_id: str, grant_id: str, request: Request):
        caseauth(request, case_id, "case.read")
        try:
            return ctx.build386.execution_grant(case_id=case_id, grant_id=grant_id)
        except KeyError:
            raise HTTPException(404, "Execution grant not found")

    @app.post("/api/cases/{case_id}/phase17/go-grants/{grant_id}/verify")
    async def verify_grant(case_id: str, grant_id: str, request: Request):
        identity = caseauth(request, case_id, "crawler.run")
        body = await request.json()
        try:
            return ctx.build386.verify_execution_grant(case_id=case_id, grant_id=grant_id, grant_token=str(body.get("grant_token") or ""), identity=identity)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except KeyError:
            raise HTTPException(404, "Execution grant not found")

    @app.post("/api/cases/{case_id}/phase17/go-grants/{grant_id}/revoke")
    async def revoke_grant(case_id: str, grant_id: str, request: Request):
        identity = caseauth(request, case_id, "crawler.run")
        body = await request.json()
        try:
            return ctx.build386.revoke_execution_grant(case_id=case_id, grant_id=grant_id, identity=identity, confirmation=str(body.get("confirmation") or ""))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except KeyError:
            raise HTTPException(404, "Execution grant not found")

    return app
