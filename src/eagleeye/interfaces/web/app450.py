from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .app448 import COOKIE, render_workspace
from .app449 import _drop, create_workspace_app449


def create_workspace_app450(*, base_dir=None):
    app = create_workspace_app449(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    _ = ctx.build450
    app.title = "EagleEye Build 450.0 Investigation Workflow Hard Checkpoint"
    app.version = "450.0"

    old_health = next(
        (
            route.endpoint
            for route in app.router.routes
            if getattr(route, "path", None) == "/health"
            and "GET" in set(getattr(route, "methods", set()) or set())
        ),
        None,
    )
    _drop(app, "/", {"GET"})
    _drop(app, "/health", {"GET"})

    def fingerprint(request):
        material = "|".join(
            (
                request.headers.get("user-agent", ""),
                request.headers.get("accept-language", ""),
                request.client.host if request.client else "",
            )
        )
        return hashlib.sha256(material.encode()).hexdigest()

    def auth(request):
        identity = team.validate_session(
            request.cookies.get(COOKIE, ""),
            client_fingerprint=fingerprint(request),
            touch=True,
        )
        if not identity:
            raise HTTPException(401, "Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity

    def same_origin(request):
        site = str(request.headers.get("sec-fetch-site") or "").strip().lower()
        if site and site not in {"same-origin", "none"}:
            raise HTTPException(403, "Cross-origin mutation blocked")
        origin = str(request.headers.get("origin") or "").strip().rstrip("/")
        if origin:
            expected = (
                str(request.url.scheme) + "://" + str(request.headers.get("host") or "")
            ).rstrip("/")
            if origin != expected:
                raise HTTPException(403, "Cross-origin mutation blocked")

    def api_error(exc):
        if isinstance(exc, PermissionError):
            raise HTTPException(403, str(exc))
        if isinstance(exc, KeyError):
            raise HTTPException(404, str(exc))
        if isinstance(exc, RuntimeError):
            raise HTTPException(409, str(exc))
        if isinstance(exc, (ValueError, TypeError)):
            raise HTTPException(400, str(exc))
        raise exc

    def visible_cases(identity):
        return ctx.team_governance_359.visible_cases(identity)

    def choose_case(cases, requested):
        if requested:
            for item in cases:
                if str(item.get("case_id")) == str(requested):
                    return item
        return cases[0] if cases else None

    @app.get("/", response_class=HTMLResponse)
    def workspace450(request: Request, view: str = "overview", case_id: str = ""):
        try:
            identity = auth(request)
        except HTTPException:
            destination = "/security/bootstrap" if team.bootstrap_required() else "/security/login"
            return RedirectResponse(destination, status_code=303)
        cases = visible_cases(identity)
        selected = choose_case(cases, case_id)
        if not selected:
            return RedirectResponse("/legacy", status_code=303)
        snapshot = ctx.build449.team_review_snapshot_449(
            identity=identity,
            case_id=selected["case_id"],
        )
        status = ctx.build450.investigation_workflow_status_450()
        latest = ctx.build450.investigation_workflow_latest_450(selected["case_id"])
        snapshot["checkpoint450"] = {**status, "latest": latest}
        audits = ctx.build449.ui_audit_history_449(selected["case_id"], limit=15)
        return HTMLResponse(
            render_workspace(snapshot, view=view, cases=cases, audits=audits)
        )

    @app.get("/health")
    def health450():
        payload = dict(old_health() if callable(old_health) else {"ok": True})
        status = ctx.build450.investigation_workflow_status_450()
        payload.update(
            {
                "build": "450.0",
                "phase": 20,
                "phase20_builds_completed": 10,
                "hard_checkpoint": True,
                "checkpoint_name": "Investigation Workflow Hard Checkpoint",
                "investigation_workflow_checkpoint_pass": status["investigation_workflow_checkpoint_pass"],
                "external_nonfixture_acquisition_validated": status["external_nonfixture_acquisition_validated"],
                "release_gate_pass": False,
                "production_release_ready": False,
                "integrity_valid": status["integrity_valid"],
            }
        )
        return payload

    @app.get("/api/build450/status")
    def status450(request: Request):
        auth(request)
        return ctx.build450.investigation_workflow_status_450()

    @app.get("/api/build450/cases/{case_id}/latest")
    def latest450(case_id: str, request: Request):
        identity = auth(request)
        ctx.team_governance_359.authorize(
            identity,
            case_id=case_id,
            capability="case.read",
            object_type="qualification450",
            object_id=case_id,
        )
        return {"item": ctx.build450.investigation_workflow_latest_450(case_id)}

    @app.post("/api/build450/cases/{case_id}/qualify")
    async def qualify450(case_id: str, request: Request):
        same_origin(request)
        identity = auth(request)
        try:
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build450.qualify_investigation_workflow_450(
                identity=identity,
                case_id=case_id,
                reviewer_username=body.get("reviewer_username", ""),
            )
        except Exception as exc:
            api_error(exc)

    return app


create_app = create_workspace_app450
