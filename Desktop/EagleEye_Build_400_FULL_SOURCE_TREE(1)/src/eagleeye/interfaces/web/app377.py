from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from .app376 import COOKIE, create_workspace_app376


def _drop(app: FastAPI, path: str, methods: set[str]) -> None:
    app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, "path", None) == path and methods.intersection(set(getattr(r, "methods", set()) or set())))]


def create_workspace_app377(*, base_dir: str | Path | None = None) -> FastAPI:
    app = create_workspace_app376(base_dir=base_dir)
    ctx = app.state.context
    team_identity = ctx.team_identity_359
    remote_enabled = bool(ctx.remote_team_364.config().get("enabled"))
    app.title = "EagleEye Intelligence Platform – Build 377.0 Image Live Validation"
    app.version = "377.0"
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
            ctx.build377.protect_remote_session(token=token, observed_fingerprint=fingerprint, observed_ip=(request.client.host if request.client else ""))
        if not ident:
            raise HTTPException(401, "Anmeldung erforderlich oder Sitzung abgelaufen")
        return ident

    def caseauth(request: Request, case_id: str, capability: str = "case.read") -> dict[str, Any]:
        ident = auth(request)
        try:
            ctx.build377.authorize(ident, case_id=case_id, capability=capability, object_type="image_validation_v377", object_id=case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        return ident

    @app.get("/health")
    def health377():
        p = dict(base_health() if callable(base_health) else {"ok": True})
        p.update({
            "build": "377.0",
            "phase16_builds_completed": 17,
            "image_live_validation": True,
            "image_media_provenance": True,
            "exact_image_dedup": True,
            "object_store_pressure_control": True,
            "crawler_improvement_build": 377,
            "external_image_validation": "not_run",
            "production_release_ready": False,
        })
        return p

    @app.get("/api/build377/phase16-status")
    def phase(request: Request):
        auth(request); return ctx.build377.phase16_status()

    @app.get("/api/build377/final-status")
    def final(request: Request):
        auth(request); return ctx.build377.dashboard()

    @app.get("/api/cases/{case_id}/image377/summary")
    def image_summary(case_id: str, request: Request):
        caseauth(request, case_id, "crawler.monitor"); return ctx.build377.image_case_summary(case_id=case_id)

    @app.get("/api/cases/{case_id}/image377/provenance")
    def image_provenance(case_id: str, request: Request):
        caseauth(request, case_id, "crawler.monitor"); return ctx.build377.image_provenance(case_id=case_id)

    @app.get("/api/cases/{case_id}/image377/storage-pressure")
    def storage_pressure(case_id: str, request: Request):
        caseauth(request, case_id, "crawler.monitor"); return ctx.build377.image_storage_pressure(case_id=case_id)

    @app.post("/api/cases/{case_id}/image377/{media_id}/visual-geolocation")
    async def visual_geo(case_id: str, media_id: str, request: Request):
        caseauth(request, case_id, "case.manage")
        body = await request.json()
        asset = ctx.build377.image_asset(media_id)
        if asset["case_id"] != case_id:
            raise HTTPException(404, "media not in case")
        try:
            return ctx.build377.visual_geolocation(media_id=media_id, confirmation=str(body.get("confirmation") or ""))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))

    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def autonomous(case_id: str, request: Request):
        caseauth(request, case_id, "case.read")
        body = await request.json()
        return ctx.build377.run_autonomous_investigation(case_id=case_id, max_ticks=max(1, min(int(body.get("max_ticks", 8)), 20)))

    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def opsec(case_id: str, request: Request):
        caseauth(request, case_id, "case.manage")
        return ctx.build377.autonomous_opsec_protect(case_id=case_id)

    return app
