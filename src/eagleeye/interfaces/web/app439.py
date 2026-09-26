from __future__ import annotations

from fastapi import HTTPException, Request

from .app379 import COOKIE
from .app438 import create_workspace_app438


def create_workspace_app439(*, base_dir=None):
    app = create_workspace_app438(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    _ = ctx.build439
    app.title = "EagleEye Build 439.0"
    app.version = "439.0"

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
                object_type="phase19",
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
        status = ctx.build439.ai_investigation_status_439()
        payload.update(
            {
                "build": "439.0",
                "phase": 19,
                "phase19_builds_completed": 19,
                "ai_investigation_loop": True,
                "explicit_human_go_required": True,
                "direct_network_authority": False,
                "automatic_scope_expansion": False,
                "truth_determined": False,
                "next_hard_checkpoint": "440.0",
                "integrity_valid": status["integrity_valid"],
                "production_release_ready": False,
            }
        )
        return payload

    @app.get("/api/build439/investigation/status")
    def status439(request: Request):
        auth(request)
        return ctx.build439.ai_investigation_status_439()

    @app.get("/api/build439/cases/{case_id}/investigation/loops")
    def loops439(case_id: str, request: Request):
        case_auth(request, case_id, "case.read")
        return {"items": ctx.build439.ai_investigation_loops_439(case_id)}

    @app.get("/api/build439/cases/{case_id}/investigation/loops/{loop_id}")
    def loop439(case_id: str, loop_id: str, request: Request):
        identity = case_auth(request, case_id, "research.run")
        try:
            item = ctx.build439.ai_investigation_report_439(loop_id, identity=identity)
            if item["loop"]["case_id"] != str(case_id):
                raise HTTPException(404, "AI investigation loop not found in case")
            return item
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))

    @app.post("/api/build439/cases/{case_id}/investigation/loops")
    async def create439(case_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "research.run")
        try:
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
            return ctx.build439.create_ai_investigation_loop_439(
                identity=identity,
                case_id=case_id,
                objective=body["objective"],
                subquestions=body["subquestions"],
                allowed_source_ids=body.get("allowed_source_ids"),
                include_fixtures=bool(body.get("include_fixtures", False)),
                max_cycles=body.get("max_cycles", 4),
                max_collection_tasks_per_cycle=body.get(
                    "max_collection_tasks_per_cycle", 4
                ),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    @app.post(
        "/api/build439/cases/{case_id}/investigation/loops/{loop_id}/authorize"
    )
    async def authorize439(case_id: str, loop_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "research.run")
        try:
            body = await request.json()
            result = ctx.build439.authorize_ai_investigation_loop_439(
                identity=identity,
                loop_id=loop_id,
                confirmation=body["confirmation"],
            )
            if result["case_id"] != str(case_id):
                raise HTTPException(404, "AI investigation loop not found in case")
            return result
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    @app.post(
        "/api/build439/cases/{case_id}/investigation/loops/{loop_id}/advance"
    )
    def advance439(case_id: str, loop_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "research.run")
        try:
            current = ctx.build439.ai_investigation_loop_439(loop_id)
            if current["case_id"] != str(case_id):
                raise HTTPException(404, "AI investigation loop not found in case")
            return ctx.build439.advance_ai_investigation_loop_439(
                identity=identity, loop_id=loop_id
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/build439/cases/{case_id}/investigation/selftest")
    def selftest439(case_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "research.run")
        try:
            return ctx.build439.run_ai_investigation_case_selftest(
                identity=identity, case_id=case_id
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    return app


create_app = create_workspace_app439
