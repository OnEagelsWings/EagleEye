from __future__ import annotations

from fastapi import HTTPException, Request

from .app379 import COOKIE
from .app444 import create_workspace_app444


def create_workspace_app445(*, base_dir=None):
    app = create_workspace_app444(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    _ = ctx.build445
    app.title = "EagleEye Build 445.0"
    app.version = "445.0"

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
                object_type="data_acquisition_checkpoint_445",
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
        status = ctx.build445.data_acquisition_status_445()
        payload.update(
            {
                "build": "445.0",
                "phase": 20,
                "phase20_builds_completed": 5,
                "hard_checkpoint": True,
                "checkpoint_name": "Data Acquisition Hard Checkpoint",
                "engineering_acquisition_stack_qualified": status["engineering_acquisition_stack_qualified"],
                "all_three_paths_externally_validated": status["all_three_paths_externally_validated"],
                "data_acquisition_gate_pass": status["data_acquisition_gate_pass"],
                "real_world_general_research_ready": False,
                "production_release_ready": False,
            }
        )
        return payload

    @app.get("/api/build445/qualification/status")
    def status445(request: Request):
        auth(request)
        return ctx.build445.data_acquisition_status_445()

    @app.get("/api/build445/cases/{case_id}/qualification/latest")
    def latest445(case_id: str, request: Request):
        case_auth(request, case_id, "case.read")
        result = ctx.build445.data_acquisition_latest_445(case_id)
        if result is None:
            raise HTTPException(404, "No Build-445 qualification exists for this case")
        return result

    @app.post("/api/build445/cases/{case_id}/qualification/run")
    def qualify445(case_id: str, request: Request):
        same_origin(request)
        identity = case_auth(request, case_id, "research.run")
        try:
            return ctx.build445.qualify_data_acquisition_445(
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


create_app = create_workspace_app445
