from __future__ import annotations

import hashlib
from html import escape
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .app458 import create_workspace_app458
from .app448 import COOKIE, render_workspace
from .app449 import _drop


def create_workspace_app459(*, base_dir=None):
    """Build 459: case-scoped documents in the primary investigator navigation."""
    app = create_workspace_app458(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    app.title = "EagleEye Build 460.0 — Full Regression Checkpoint"
    app.version = "460.0"
    _drop(app, "/", {"GET"})
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health459():
        return {"ok": True, "build": "460.0", "status": "ok", "production_release_ready": False, "next_checkpoint": "465.0"}


    @app.get("/", response_class=HTMLResponse)
    def investigator_home(request: Request, view: str = "overview", case_id: str = ""):
        fingerprint = hashlib.sha256("|".join((
            request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""),
            request.client.host if request.client else "",
        )).encode()).hexdigest()
        identity = team.validate_session(
            request.cookies.get(COOKIE, ""),
            client_fingerprint=fingerprint,
            touch=True,
        )
        if not identity:
            destination = "/security/bootstrap" if team.bootstrap_required() else "/security/login"
            return RedirectResponse(destination, status_code=303)
        cases = ctx.team_governance_359.visible_cases(identity)
        selected = next((item for item in cases if str(item.get("case_id")) == str(case_id)), None)
        if selected is None:
            selected = cases[0] if cases else None
        if selected is None:
            return RedirectResponse("/legacy", status_code=303)
        selected_id = str(selected["case_id"])
        snapshot = ctx.workspace_reliability_457.snapshot(identity=identity, case_id=selected_id)
        snapshot = dict(snapshot, workspace_build="460.0")
        audits = ctx.investigator_workspace_448.audit_history(selected_id, limit=15)
        html = render_workspace(snapshot, view=view, cases=cases, audits=audits)
        link = (
            '<a href="/documents458?'
            + escape(urlencode({"case_id": selected_id}), quote=True)
            + '">Dokumente &amp; Quellenprüfung</a>'
        )
        html = html.replace("</nav>", link + "</nav>", 1)
        html = html.replace("Build 460.0 · Investigation Workflow Hard Checkpoint",
                            "Build 459.0 · Investigator Navigation")
        html = html.replace("Build 460.0 · Investigator Workspace",
                            "Build 459.0 · Investigator Navigation")
        return HTMLResponse(html)

    return app


create_app = create_workspace_app459
