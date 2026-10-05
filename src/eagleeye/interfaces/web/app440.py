from __future__ import annotations

from fastapi import HTTPException, Request

from .app379 import COOKIE
from .app439 import create_workspace_app439


def create_workspace_app440(*, base_dir=None):
    app = create_workspace_app439(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    _ = ctx.build440
    app.title = "EagleEye Build 440.0"
    app.version = "440.0"

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
                object_type="phase19_checkpoint",
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
        status = ctx.build440.phase19_qualification_status_440()
        payload.update(
            {
                "build": "440.0",
                "phase": 19,
                "phase19_builds_completed": 20,
                "hard_checkpoint": True,
                "phase19_gate_pass": status["phase19_gate_pass"],
                "live_collection_complete": False,
                "real_world_general_research_ready": False,
                "production_release_ready": False,
            }
        )
        return payload

    @app.get("/api/build440/qualification/status")
    def status440(request: Request):
        auth(request)
        return ctx.build440.phase19_qualification_status_440()

    @app.get("/api/build440/qualification/capabilities")
    def capabilities440(request: Request):
        auth(request)
        return ctx.build440.phase19_capability_matrix_440()

    @app.get("/api/build440/cases/{case_id}/qualification/latest")
    def latest440(case_id: str, request: Request):
        case_auth(request, case_id, "case.read")
        result = ctx.build440.phase19_qualification_latest_440(case_id)
        if result is None:
            raise HTTPException(404, "No Build-440 qualification exists for this case")
        return result

    @app.post("/api/build440/cases/{case_id}/qualification/run")
    def qualify440(case_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "research.run")
        try:
            return ctx.build440.qualify_phase19(identity=identity, case_id=case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    return app


create_app = create_workspace_app440
