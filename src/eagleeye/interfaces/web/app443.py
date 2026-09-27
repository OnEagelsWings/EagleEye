from __future__ import annotations

from fastapi import HTTPException, Request

from .app379 import COOKIE
from .app442 import create_workspace_app442


def create_workspace_app443(*, base_dir=None):
    app = create_workspace_app442(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    _ = ctx.build443
    app.title = "EagleEye Build 443.0"
    app.version = "443.0"

    old = next(
        (
            r.endpoint
            for r in app.router.routes
            if getattr(r, "path", None) == "/health"
            and "GET" in set(getattr(r, "methods", set()) or set())
        ),
        None,
    )
    app.router.routes[:] = [
        r
        for r in app.router.routes
        if not (
            getattr(r, "path", None) == "/health"
            and "GET" in set(getattr(r, "methods", set()) or set())
        )
    ]

    def auth(req):
        import hashlib

        fingerprint = hashlib.sha256(
            "|".join(
                (
                    req.headers.get("user-agent", ""),
                    req.headers.get("accept-language", ""),
                    req.client.host if req.client else "",
                )
            ).encode()
        ).hexdigest()
        identity = team.validate_session(
            req.cookies.get(COOKIE, ""),
            client_fingerprint=fingerprint,
            touch=True,
        )
        if not identity:
            raise HTTPException(401, "Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity

    def case_auth(req, case_id, capability="case.read"):
        identity = auth(req)
        try:
            ctx.team_governance_359.authorize(
                identity,
                case_id=str(case_id),
                capability=capability,
                object_type="news_acquisition_443",
                object_id=str(case_id),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        return identity

    def same_origin(req):
        site = str(req.headers.get("sec-fetch-site") or "").strip().lower()
        if site and site not in {"same-origin", "none"}:
            raise HTTPException(403, "Cross-origin mutation blocked")
        origin = str(req.headers.get("origin") or "").strip().rstrip("/")
        if origin:
            expected = (
                str(req.url.scheme) + "://" + str(req.headers.get("host") or "")
            ).rstrip("/")
            if origin != expected:
                raise HTTPException(403, "Cross-origin mutation blocked")

    @app.get("/health")
    def health():
        payload = dict(old() if callable(old) else {"ok": True})
        status = ctx.build443.live_news_status_443()
        payload.update(
            {
                "build": "443.0",
                "phase": 20,
                "phase20_builds_completed": 3,
                "controlled_surface_network_executor": True,
                "surface_hardening": True,
                "live_news_acquisition": True,
                "public_social_retrieval_adapter_complete": False,
                "general_live_collection_complete": False,
                "production_release_ready": False,
                "integrity_valid": status["integrity_valid"],
            }
        )
        return payload

    @app.get("/api/build443/news/status")
    def status443(request: Request):
        auth(request)
        return ctx.build443.live_news_status_443()

    @app.get("/api/build443/cases/{case_id}/news/runs")
    def runs443(case_id: str, request: Request):
        case_auth(request, case_id, "case.read")
        return {"items": ctx.build443.live_news_runs_443(case_id)}

    @app.post("/api/build443/cases/{case_id}/sources/{source_id}/tasks")
    async def create_task443(case_id: str, source_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "crawler.run")
        try:
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build443.create_news_feed_task_443(
                identity=identity,
                case_id=case_id,
                source_id=source_id,
                feed_url=body.get("feed_url", ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/build443/cases/{case_id}/tasks/{task_id}/execute")
    async def execute443(case_id: str, task_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "crawler.run")
        try:
            task = ctx.crawler_core_425.get(task_id)
            if task["case_id"] != str(case_id):
                raise HTTPException(404, "news task not found in case")
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build443.execute_live_news_feed_443(
                identity=identity,
                case_id=case_id,
                task_id=task_id,
                confirmation=body.get("confirmation", ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/build443/cases/{case_id}/news/selftest")
    def selftest443(case_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "crawler.run")
        try:
            return ctx.build443.run_live_news_case_selftest(
                identity=identity,
                case_id=case_id,
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    return app


create_app = create_workspace_app443
