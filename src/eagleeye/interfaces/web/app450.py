from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

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
    old_legacy = next(
        (
            route.endpoint
            for route in app.router.routes
            if getattr(route, "path", None) == "/legacy"
            and "GET" in set(getattr(route, "methods", set()) or set())
        ),
        None,
    )
    _drop(app, "/", {"GET"})
    _drop(app, "/health", {"GET"})
    _drop(app, "/legacy", {"GET"})

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

    def qualification_case_ids():
        return {
            str(row["case_id"])
            for row in ctx.db.all("SELECT case_id FROM phase20_qualification_case_450")
        }

    def qualification_case_for_path(request):
        # Build-450 checkpoint read endpoints are allowed to report qualification
        # status. Every inherited operational/legacy route is denied when its
        # path or referenced object resolves to a marked qualification case.
        path = str(request.url.path or "")
        if path.startswith("/api/build450/"):
            return ""
        marked = qualification_case_ids()
        requested = str(request.query_params.get("case_id") or "")
        if requested in marked:
            return requested
        tokens = {x for x in path.split("/") if x}
        for case_id in marked:
            if case_id in tokens:
                return case_id
        lookups = (
            ("evidence_item_447", "evidence_id"),
            ("claim_447", "claim_id"),
            ("dossier_revision_447", "revision_id"),
            ("review_request_449", "review_id"),
            ("review_export_execution_449", "execution_id"),
            ("phase19_ai_loop_439", "loop_id"),
            ("live_ai_dispatch_446", "dispatch_id"),
            ("live_ai_execution_446", "execution_id"),
        )
        for table, key in lookups:
            for token in tokens:
                row = ctx.db.one(
                    f"SELECT case_id FROM {table} WHERE {key}=?",
                    (token,),
                )
                if row and str(row.get("case_id") or "") in marked:
                    return str(row.get("case_id") or "")
        return ""

    @app.middleware("http")
    async def isolate_qualification_cases450(request: Request, call_next):
        case_id = qualification_case_for_path(request)
        if case_id:
            message = "Build-450 qualification cases are isolated from operational and legacy routes"
            if str(request.url.path).startswith("/api/"):
                return JSONResponse({"detail": message}, status_code=403)
            return HTMLResponse(
                "<!doctype html><html lang=\"de\"><body><main>"
                "<h1>Qualifikationsfall isoliert</h1>"
                "<p>Dieser Build-450-Qualifikationsfall ist nicht über operative oder Legacy-Routen zugänglich.</p>"
                "</main></body></html>",
                status_code=403,
            )
        return await call_next(request)

    def visible_cases(identity):
        marked = qualification_case_ids()
        return [
            item
            for item in ctx.team_governance_359.visible_cases(identity)
            if str(item.get("case_id") or "") not in marked
        ]

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
            return HTMLResponse(
                """<!doctype html><html lang="de"><head><meta charset="utf-8">"""
                """<meta name="viewport" content="width=device-width,initial-scale=1">"""
                """<title>EagleEye Build 450</title></head><body>"""
                """<main><h1>Kein operativer Fall verfügbar</h1>"""
                """<p>Build-450-Qualifikationsfälle sind absichtlich aus dem operativen """
                """Workspace und den Legacy-Werkzeugen ausgeschlossen.</p>"""
                """<p>Lege einen normalen Ermittlungsfall an, um den Investigator Workspace zu nutzen.</p>"""
                """</main></body></html>""",
                status_code=200,
            )
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

    @app.get("/legacy", response_class=HTMLResponse)
    def legacy450(request: Request, case_id: str = ""):
        try:
            identity = auth(request)
        except HTTPException:
            destination = "/security/bootstrap" if team.bootstrap_required() else "/security/login"
            return RedirectResponse(destination, status_code=303)
        cases = visible_cases(identity)
        selected = choose_case(cases, case_id)
        if not selected:
            return HTMLResponse(
                """<!doctype html><html lang="de"><head><meta charset="utf-8">"""
                """<meta name="viewport" content="width=device-width,initial-scale=1">"""
                """<title>EagleEye Build 450</title></head><body><main>"""
                """<h1>Legacy Workspace nicht verfügbar</h1>"""
                """<p>Es existiert kein operativer Fall. Qualifikationsfälle bleiben isoliert.</p>"""
                """</main></body></html>""",
                status_code=200,
            )
        if not callable(old_legacy):
            raise HTTPException(404, "Legacy workspace unavailable")
        return old_legacy(request, case_id=selected["case_id"])

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


    return app


create_app = create_workspace_app450
