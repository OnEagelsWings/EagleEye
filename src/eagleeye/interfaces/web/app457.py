from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .app456 import create_workspace_app456
from .app448 import COOKIE, render_workspace
from .app449 import _drop


def create_workspace_app457(*, base_dir=None):
    app = create_workspace_app456(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    _ = ctx.build457
    app.title = "EagleEye Build 457.0 Workspace Reliability"
    app.version = "457.0"

    _drop(app, "/", {"GET"})
    _drop(app, "/health", {"GET"})

    def auth(request: Request):
        fingerprint = hashlib.sha256(
            "|".join(
                (
                    request.headers.get("user-agent", ""),
                    request.headers.get("accept-language", ""),
                    request.client.host if request.client else "",
                )
            ).encode()
        ).hexdigest()
        identity = team.validate_session(
            request.cookies.get(COOKIE, ""),
            client_fingerprint=fingerprint,
            touch=True,
        )
        if not identity:
            raise HTTPException(401, "Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity

    def visible_cases(identity):
        return ctx.team_governance_359.visible_cases(identity)

    def choose_case(cases, requested):
        if requested:
            for item in cases:
                if str(item.get("case_id")) == str(requested):
                    return item
        return cases[0] if cases else None

    @app.get("/", response_class=HTMLResponse)
    def workspace457(request: Request, view: str = "overview", case_id: str = ""):
        try:
            identity = auth(request)
        except HTTPException:
            destination = "/security/bootstrap" if team.bootstrap_required() else "/security/login"
            return RedirectResponse(destination, status_code=303)
        cases = visible_cases(identity)
        selected = choose_case(cases, case_id)
        if not selected:
            return RedirectResponse("/legacy", status_code=303)
        snap = ctx.workspace_reliability_457.snapshot(
            identity=identity,
            case_id=selected["case_id"],
        )
        audits = ctx.investigator_workspace_448.audit_history(selected["case_id"], limit=15)
        return HTMLResponse(render_workspace(snap, view=view, cases=cases, audits=audits))

    @app.get("/health")
    def health457():
        status = ctx.build457.build457_status()
        return {
            "ok": True,
            "status": "ok",
            "build": "457.0",
            "workspace_reliability": True,
            "active_loop_selected_independently": True,
            "remaining_dispatch_budget_enforced": True,
            "full_research_gate_this_build": False,
            "next_checkpoint": "460.0",
            "production_release_ready": False,
            "integrity_valid": bool(status.get("integrity_valid")),
        }

    @app.get("/api/build457/status")
    def status457(request: Request):
        auth(request)
        return ctx.build457.build457_status()

    @app.get("/api/build457/cases/{case_id}/snapshot")
    def snapshot457(case_id: str, request: Request):
        identity = auth(request)
        return ctx.build457.workspace_snapshot_457(identity=identity, case_id=case_id)

    return app


create_app = create_workspace_app457
