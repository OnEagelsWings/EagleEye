from __future__ import annotations

import hashlib
from html import escape
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .app458 import create_workspace_app458
from .app448 import COOKIE, render_workspace
from .app449 import _drop


def create_workspace_app459(*, base_dir=None, workspace_build="459.0", workspace_title="Investigator Navigation"):
    """Build 459: case-scoped documents in the primary investigator navigation."""
    app = create_workspace_app458(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    app.title = f"EagleEye Build {workspace_build} — {workspace_title}"
    app.version = workspace_build
    _drop(app, "/", {"GET"})
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health459():
        integrity = bool(ctx.build458.build458_status().get("integrity_valid", False))
        return {"ok": True, "build": workspace_build, "status": "ok" if integrity else "hold",
                "integrity_valid": integrity, "production_release_ready": False,
                "next_checkpoint": "460.0" if workspace_build == "459.0" else ("470.0" if workspace_build == "466.0" else "465.0")}


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
        snapshot = dict(snapshot, workspace_build=workspace_build)
        audits = ctx.investigator_workspace_448.audit_history(selected_id, limit=15)
        html = render_workspace(snapshot, view=view, cases=cases, audits=audits, ui_name_override=workspace_title)
        link = (
            '<a href="/documents458?'
            + escape(urlencode({"case_id": selected_id}), quote=True)
            + '">Dokumente &amp; Quellenprüfung</a>'
        )
        if workspace_build in {"461.0", "462.0", "463.0", "464.0", "465.0", "466.0", "467.0", "468.0", "469.0", "470.0", "471.0", "472.0"}:
            guide_url = "/workflow461?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(guide_url, quote=True) + '">Ermittlungsweg · Anleitung</a>'
        if workspace_build in {"462.0", "463.0", "464.0", "465.0", "466.0", "467.0", "468.0", "469.0", "470.0", "471.0", "472.0"}:
            graph_url = "/entities462?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(graph_url, quote=True) + '">Entitäten &amp; Beziehungen</a>'
        if workspace_build in {"463.0", "464.0", "465.0", "466.0", "467.0", "468.0", "469.0", "470.0", "471.0", "472.0"}:
            proof_url = "/source-links463?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(proof_url, quote=True) + '">Dokumentgebundene Beziehungen</a>'
        if workspace_build in {"464.0", "465.0", "466.0", "467.0", "468.0", "469.0", "470.0", "471.0", "472.0"}:
            graph_url = "/graph464?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(graph_url, quote=True) + '">Netzwerkanalyse</a>'
        if workspace_build in {"465.0","466.0","467.0", "468.0", "469.0", "470.0", "471.0", "472.0"}:
            review_url = "/review465?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(review_url,quote=True) + '">Integrierte Fallprüfung</a>'
        if workspace_build in {"466.0","467.0", "468.0", "469.0", "470.0", "471.0", "472.0"}:
            url = "/provenance466?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(url, quote=True) + '">Belegherkunft &amp; Integrität</a>'
        if workspace_build in {"468.0", "469.0", "470.0", "471.0", "472.0"}:
            link += '<a href="/benchmark468">Messprotokoll</a>'
        if workspace_build in {"469.0", "470.0", "471.0", "472.0"}:
            source_url = "/collect469?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(source_url, quote=True) + '">Öffentliche Quellen</a>'
        if workspace_build in {"470.0", "471.0", "472.0"}:
            readiness_url = "/readiness470?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(readiness_url, quote=True) + '">Qualitätsprüfung 470</a>'
        if int(workspace_build.split(".")[0]) >= 471:
            ai_url = "/assistant471?" + urlencode({"case_id": selected_id})
            link += '<a href="' + escape(ai_url, quote=True) + '">Lokaler KI-Ermittler</a>'
        html = html.replace("</nav>", link + "</nav>", 1)
        return HTMLResponse(html)

    return app


create_app = create_workspace_app459
