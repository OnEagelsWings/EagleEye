from __future__ import annotations

import hashlib
import inspect
import json

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Match

from .app448 import COOKIE, render_workspace
from .app449 import _drop, create_workspace_app449

JSON_PAYLOAD_GUARD_MAX_BYTES = 1024 * 1024
MANUAL_JSON_GUARD_PATHS = {"/api/build449/reviews"}
_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_FORM_MEDIA_TYPES = {"multipart/form-data", "application/x-www-form-urlencoded"}


def _route_body_requires_payload_guard(route):
    body_field = getattr(route, "body_field", None)
    if body_field is not None:
        field_info = getattr(body_field, "field_info", None)
        media_type = str(getattr(field_info, "media_type", "") or "").split(";", 1)[0].strip().lower()
        return media_type not in _FORM_MEDIA_TYPES

    # Several inherited endpoints intentionally accept Request directly and
    # call await request.json(), so FastAPI does not expose a body_field.
    # Detect those handlers by their actual implementation instead of assuming
    # that "no body_field" means "no JSON body".
    endpoint = getattr(route, "endpoint", None)
    if endpoint is None:
        return False
    try:
        source = inspect.getsource(endpoint)
    except (OSError, TypeError):
        source = ""
    compact = "".join(source.split())
    if ".json()" in compact:
        return True
    code = getattr(endpoint, "__code__", None)
    return bool(code and "json" in set(getattr(code, "co_names", ()) or ()))


def _route_requires_payload_guard(app, scope):
    method = str(scope.get("method") or "").upper()
    path = str(scope.get("path") or "")
    if method not in _MUTATION_METHODS:
        return False
    if not path.startswith("/api/") or path.startswith("/api/build450/"):
        return False
    if path in MANUAL_JSON_GUARD_PATHS:
        return True
    for route in app.router.routes:
        try:
            match, _child_scope = route.matches(scope)
        except Exception:
            continue
        if match is not Match.FULL:
            continue
        return _route_body_requires_payload_guard(route)
    return False


async def _guarded_json_payload(request):
    declared = str(request.headers.get("content-length") or "").strip()
    if declared:
        try:
            if int(declared) > JSON_PAYLOAD_GUARD_MAX_BYTES:
                raise HTTPException(413, "JSON mutation body exceeds Build-450 guard limit")
        except ValueError:
            pass

    chunks = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > JSON_PAYLOAD_GUARD_MAX_BYTES:
            raise HTTPException(413, "JSON mutation body exceeds Build-450 guard limit")
        chunks.append(chunk)
    raw = b"".join(chunks)
    # Preserve the exact bytes for the inherited route. Starlette Request.json()
    # also feeds bytes directly to json.loads(), which supports UTF-8/16/32.
    request._body = raw
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


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

    def qualification_case_for_tokens(tokens, marked):
        tokens = {str(x) for x in tokens if str(x)}
        for case_id in marked:
            if case_id in tokens:
                return case_id
        # Resolve current and inherited case-bound identifier classes.
        # Static lookups cover the core investigation chain; the schema-driven
        # primary-key fallback additionally covers older ID-only routes (for
        # example media assets and legacy export/task resources) without relying
        # on the literal case_id being present in the URL or JSON payload.
        lookups = {
            ("acquisition_event_422", "event_id"),
            ("content_observation_423", "observation_id"),
            ("crawl_task_425", "task_id"),
            ("news_item_429", "news_item_id"),
            ("social_observation_432", "observation_id"),
            ("phase19_ai_loop_439", "loop_id"),
            ("live_ai_dispatch_446", "dispatch_id"),
            ("live_ai_execution_446", "execution_id"),
            ("evidence_item_447", "evidence_id"),
            ("claim_447", "claim_id"),
            ("dossier_revision_447", "revision_id"),
            ("review_request_449", "review_id"),
            ("review_export_execution_449", "execution_id"),
        }
        for table_row in ctx.db.all(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        ):
            table = str(table_row.get("name") or "")
            if not table or not table.replace("_", "").isalnum():
                continue
            columns = ctx.db.all(f'PRAGMA table_info("{table}")')
            names = {str(col.get("name") or "") for col in columns}
            if "case_id" not in names:
                continue
            for col in columns:
                key = str(col.get("name") or "")
                if int(col.get("pk") or 0) > 0 and key and key != "case_id":
                    lookups.add((table, key))

        for table, key in sorted(lookups):
            for token in tokens:
                row = ctx.db.one(
                    f'SELECT case_id FROM "{table}" WHERE "{key}"=? LIMIT 1',
                    (token,),
                )
                if row and str(row.get("case_id") or "") in marked:
                    return str(row.get("case_id") or "")
        return ""

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
        return qualification_case_for_tokens(
            {x for x in path.split("/") if x},
            marked,
        )

    def payload_tokens(value):
        out = set()
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).lower() in {
                    "case_id", "object_id", "review_id", "evidence_id", "claim_id",
                    "revision_id", "loop_id", "dispatch_id", "execution_id",
                    "event_id", "observation_id", "task_id", "news_item_id",
                } and isinstance(item, (str, int)):
                    out.add(str(item))
                out.update(payload_tokens(item))
        elif isinstance(value, list):
            for item in value:
                out.update(payload_tokens(item))
        return out

    @app.middleware("http")
    async def isolate_qualification_cases450(request: Request, call_next):
        case_id = qualification_case_for_path(request)
        if not case_id and _route_requires_payload_guard(app, request.scope):
            try:
                payload = await _guarded_json_payload(request)
            except HTTPException as exc:
                return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
            case_id = qualification_case_for_tokens(
                payload_tokens(payload),
                qualification_case_ids(),
            )
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
