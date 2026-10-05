from __future__ import annotations

from fastapi import HTTPException, Request

from .app379 import COOKIE
from .app443 import create_workspace_app443


def create_workspace_app444(*, base_dir=None):
    app = create_workspace_app443(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    _ = ctx.build444
    app.title = "EagleEye Build 444.0"
    app.version = "444.0"

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
                object_type="social_acquisition_444",
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
        status = ctx.build444.public_social_status_444()
        payload.update(
            {
                "build": "444.0",
                "phase": 20,
                "phase20_builds_completed": 4,
                "controlled_surface_network_executor": True,
                "surface_hardening": True,
                "live_news_acquisition": True,
                "controlled_public_social_acquisition": True,
                "core_public_acquisition_paths_implemented": True,
                "general_live_collection_complete": False,
                "production_release_ready": False,
                "integrity_valid": status["integrity_valid"],
            }
        )
        return payload

    @app.get("/api/build444/social/status")
    def status444(request: Request):
        auth(request)
        return ctx.build444.public_social_status_444()

    @app.get("/api/build444/cases/{case_id}/social/runs")
    def runs444(case_id: str, request: Request):
        case_auth(request, case_id, "case.read")
        return {"items": ctx.build444.public_social_runs_444(case_id)}

    @app.post("/api/build444/cases/{case_id}/sources/{source_id}/tasks")
    async def create_task444(case_id: str, source_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "crawler.run")
        try:
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build444.create_public_social_task_444(
                identity=identity,
                case_id=case_id,
                source_id=source_id,
                endpoint_url=body.get("endpoint_url", ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/build444/cases/{case_id}/tasks/{task_id}/execute")
    async def execute444(case_id: str, task_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "crawler.run")
        try:
            task = ctx.crawler_core_425.get(task_id)
            if task["case_id"] != str(case_id):
                raise HTTPException(404, "social task not found in case")
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build444.execute_public_social_task_444(
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

    @app.post("/api/build444/cases/{case_id}/social/selftest")
    def selftest444(case_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "crawler.run")
        try:
            return ctx.build444.run_public_social_case_selftest(
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


create_app = create_workspace_app444
