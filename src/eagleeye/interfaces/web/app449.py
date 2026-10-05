from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .app448 import COOKIE, create_workspace_app448, render_workspace


def _drop(app, path, methods):
    methods = {x.upper() for x in methods}
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == path
            and methods.intersection(set(getattr(route, "methods", set()) or set()))
        )
    ]


def create_workspace_app449(*, base_dir=None):
    app = create_workspace_app448(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    _ = ctx.build449
    app.title = "EagleEye Build 449.0 Human Review & Team Workflow"
    app.version = "449.0"

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
    _drop(app, "/api/build448/cases/{case_id}/ui-audit", {"POST"})

    # Build 449 is the current review API surface. The lower-level Build-447
    # mutation routes remain available in app447/app448 compatibility apps, but
    # are deliberately removed from the current app so they cannot bypass the
    # formal review queue and four-eyes separation.
    for path in (
        "/api/build447/evidence/{evidence_id}/review",
        "/api/build447/claims/{claim_id}/review",
        "/api/build447/dossiers/{revision_id}/review",
        "/api/build447/dossiers/{revision_id}/export",
        "/api/build447/cases/{case_id}/selftest",
    ):
        _drop(app, path, {"POST"})

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

    def visible_cases(identity):
        return ctx.team_governance_359.visible_cases(identity)

    def choose_case(cases, requested):
        if requested:
            for item in cases:
                if str(item.get("case_id")) == str(requested):
                    return item
        return cases[0] if cases else None

    def route_inventory():
        rows = []
        for route in app.router.routes:
            path = getattr(route, "path", None)
            if not path:
                continue
            for method in getattr(route, "methods", set()) or set():
                rows.append((str(method).upper(), str(path)))
        return rows

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

    @app.get("/", response_class=HTMLResponse)
    def workspace449(request: Request, view: str = "overview", case_id: str = ""):
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
        audits = ctx.investigator_workspace_448.audit_history(
            selected["case_id"],
            limit=15,
        )
        return HTMLResponse(
            render_workspace(snapshot, view=view, cases=cases, audits=audits)
        )

    @app.get("/health")
    def health449():
        payload = dict(old_health() if callable(old_health) else {"ok": True})
        status = ctx.build449.human_review_status_449()
        payload.update(
            {
                "build": "449.0",
                "phase": 20,
                "phase20_builds_completed": 9,
                "human_review_team_workflow": True,
                "four_eyes_review": True,
                "direct_build447_review_mutations_current_app": False,
                "stale_object_detection": True,
                "production_release_ready": False,
                "next_hard_checkpoint": "450.0",
                "integrity_valid": status["integrity_valid"],
            }
        )
        return payload

    @app.get("/api/build449/status")
    def status449(request: Request):
        auth(request)
        return ctx.build449.human_review_status_449()

    @app.get("/api/build449/cases/{case_id}/snapshot")
    def snapshot449(case_id: str, request: Request):
        identity = auth(request)
        try:
            return ctx.build449.team_review_snapshot_449(
                identity=identity,
                case_id=case_id,
            )
        except Exception as exc:
            api_error(exc)

    @app.get("/api/build449/cases/{case_id}/reviews")
    def queue449(case_id: str, request: Request, include_closed: bool = True):
        identity = auth(request)
        try:
            return {
                "items": ctx.build449.review_queue_449(
                    identity=identity,
                    case_id=case_id,
                    include_closed=include_closed,
                )
            }
        except Exception as exc:
            api_error(exc)

    @app.get("/api/build449/cases/{case_id}/ui-audits")
    def ui_audits449(case_id: str, request: Request):
        identity = auth(request)
        try:
            ctx.team_governance_359.authorize(
                identity,
                case_id=case_id,
                capability="case.read",
                object_type="ui_audit_449",
                object_id=case_id,
            )
            return {"items": ctx.build449.ui_audit_history_449(case_id, limit=25)}
        except Exception as exc:
            api_error(exc)

    @app.post("/api/build449/cases/{case_id}/ui-audit")
    def ui_audit449(case_id: str, request: Request):
        same_origin(request)
        identity = auth(request)
        try:
            cases = visible_cases(identity)
            selected = choose_case(cases, case_id)
            if not selected or str(selected.get("case_id")) != str(case_id):
                raise PermissionError("case access denied")
            snapshot = ctx.build449.team_review_snapshot_449(
                identity=identity,
                case_id=case_id,
            )
            markup = render_workspace(
                snapshot,
                view="operations",
                cases=cases,
                audits=ctx.build449.ui_audit_history_449(case_id, limit=15),
            )
            result = ctx.build449.run_ui_audit_449(
                identity=identity,
                case_id=case_id,
                markup=markup,
                route_inventory=route_inventory(),
            )
            code = 200 if result["result"] == "PASS" else 409
            return JSONResponse(result, status_code=code)
        except Exception as exc:
            api_error(exc)

    @app.post("/api/build449/reviews")
    async def request_review449(request: Request):
        same_origin(request)
        identity = auth(request)
        try:
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build449.request_review_449(
                identity=identity,
                object_type=body.get("object_type", ""),
                object_id=body.get("object_id", ""),
                note=body.get("note", ""),
                assigned_to=body.get("assigned_to", ""),
            )
        except Exception as exc:
            api_error(exc)

    @app.post("/api/build449/reviews/{review_id}/claim")
    def claim_review449(review_id: str, request: Request):
        same_origin(request)
        identity = auth(request)
        try:
            return ctx.build449.claim_review_449(
                identity=identity,
                review_id=review_id,
            )
        except Exception as exc:
            api_error(exc)

    @app.post("/api/build449/reviews/{review_id}/complete")
    async def complete_review449(review_id: str, request: Request):
        same_origin(request)
        identity = auth(request)
        try:
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build449.complete_review_449(
                identity=identity,
                review_id=review_id,
                decision=body.get("decision", ""),
                note=body.get("note", ""),
                confirmation=body.get("confirmation", ""),
            )
        except Exception as exc:
            api_error(exc)

    @app.post("/api/build449/reviews/{review_id}/comments")
    async def comment_review449(review_id: str, request: Request):
        same_origin(request)
        identity = auth(request)
        try:
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build449.add_review_comment_449(
                identity=identity,
                review_id=review_id,
                kind=body.get("kind", "comment"),
                body=body.get("body", ""),
            )
        except Exception as exc:
            api_error(exc)

    @app.post("/api/build449/reviews/{review_id}/export")
    async def export_review449(review_id: str, request: Request):
        same_origin(request)
        identity = auth(request)
        try:
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build449.execute_approved_export_449(
                identity=identity,
                review_id=review_id,
                confirmation=body.get("confirmation", ""),
            )
        except Exception as exc:
            api_error(exc)

    return app


create_app = create_workspace_app449
