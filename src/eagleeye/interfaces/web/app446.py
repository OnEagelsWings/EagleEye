from __future__ import annotations

from fastapi import HTTPException, Request

from .app379 import COOKIE
from .app445 import create_workspace_app445


def create_workspace_app446(*, base_dir=None):
    app = create_workspace_app445(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    _ = ctx.build446
    app.title = "EagleEye Build 446.0"
    app.version = "446.0"

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
                object_type="live_ai_dispatch_446",
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
        status = ctx.build446.live_loop_status_446()
        payload.update(
            {
                "build": "446.0",
                "phase": 20,
                "phase20_builds_completed": 6,
                "live_ai_investigation_dispatch": True,
                "specialized_surface_dispatch": True,
                "specialized_news_dispatch": True,
                "specialized_social_dispatch": True,
                "per_path_confirmation_required": True,
                "generic_network_authority": False,
                "real_world_general_research_ready": False,
                "production_release_ready": False,
                "integrity_valid": status["integrity_valid"],
            }
        )
        return payload

    @app.get("/api/build446/status")
    def status446(request: Request):
        auth(request)
        return ctx.build446.live_loop_status_446()

    @app.get("/api/build446/loops/{loop_id}/dispatches")
    def dispatches446(loop_id: str, request: Request):
        identity = auth(request)
        try:
            loop = ctx.ai_investigation_loop_439.loop(loop_id)
            case_auth(request, loop["case_id"], "case.read")
            return {"items": ctx.build446.live_loop_dispatches_446(loop_id)}
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @app.get("/api/build446/loops/{loop_id}/executions")
    def executions446(loop_id: str, request: Request):
        identity = auth(request)
        try:
            loop = ctx.ai_investigation_loop_439.loop(loop_id)
            case_auth(request, loop["case_id"], "case.read")
            return {"items": ctx.build446.live_loop_executions_446(loop_id)}
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @app.post("/api/build446/loops/{loop_id}/dispatches/prepare")
    async def prepare446(loop_id: str, request: Request):
        same_origin(request)
        identity = auth(request)
        try:
            loop = ctx.ai_investigation_loop_439.loop(loop_id)
            case_auth(request, loop["case_id"], "research.run")
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build446.prepare_live_loop_dispatches_446(
                identity=identity,
                loop_id=loop_id,
                source_ids=body.get("source_ids"),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/build446/dispatches/{dispatch_id}/execute")
    async def execute446(dispatch_id: str, request: Request):
        same_origin(request)
        identity = auth(request)
        try:
            dispatch = ctx.live_investigation_dispatcher_446.dispatch(dispatch_id)
            case_auth(request, dispatch["case_id"], "crawler.run")
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build446.execute_live_loop_dispatch_446(
                identity=identity,
                dispatch_id=dispatch_id,
                confirmation=body.get("confirmation", ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/build446/cases/{case_id}/selftest")
    def selftest446(case_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "research.run")
        try:
            return ctx.build446.run_live_loop_case_selftest(
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


create_app = create_workspace_app446
