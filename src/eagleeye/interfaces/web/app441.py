from __future__ import annotations

from fastapi import HTTPException, Request

from .app379 import COOKIE
from .app440 import create_workspace_app440


def create_workspace_app441(*, base_dir=None):
    app = create_workspace_app440(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    _ = ctx.build441
    app.title = "EagleEye Build 441.0"
    app.version = "441.0"

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
                object_type="surface_retrieval_441",
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
        status = ctx.build441.surface_retrieval_status_441()
        payload.update(
            {
                "build": "441.0",
                "phase": 20,
                "phase20_builds_completed": 1,
                "controlled_surface_network_executor": True,
                "ordinary_surface_retrieval_available": True,
                "general_live_collection_complete": False,
                "real_world_general_research_ready": False,
                "production_release_ready": False,
                "integrity_valid": status["integrity_valid"],
            }
        )
        return payload

    @app.get("/api/build441/retrieval/status")
    def status441(request: Request):
        auth(request)
        return ctx.build441.surface_retrieval_status_441()

    @app.get("/api/build441/cases/{case_id}/retrieval/runs")
    def runs441(case_id: str, request: Request):
        case_auth(request, case_id, "case.read")
        return {"items": ctx.build441.surface_retrieval_runs_441(case_id)}

    @app.post("/api/build441/cases/{case_id}/tasks/{task_id}/execute")
    async def execute441(case_id: str, task_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "crawler.run")
        try:
            task = ctx.crawler_core_425.get(task_id)
            if task["case_id"] != str(case_id):
                raise HTTPException(404, "crawl task not found in case")
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build441.execute_surface_task_441(
                identity=identity,
                task_id=task_id,
                confirmation=body.get("confirmation", ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/build441/cases/{case_id}/tasks/{task_id}/execute-loop-authorized")
    def execute_loop441(case_id: str, task_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "crawler.run")
        try:
            task = ctx.crawler_core_425.get(task_id)
            if task["case_id"] != str(case_id):
                raise HTTPException(404, "crawl task not found in case")
            return ctx.build441.execute_authorized_loop_surface_task_441(
                identity=identity,
                task_id=task_id,
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/build441/cases/{case_id}/retrieval/selftest")
    def selftest441(case_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "crawler.run")
        try:
            return ctx.build441.run_surface_retrieval_case_selftest(
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


create_app = create_workspace_app441
