from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from .app459 import create_workspace_app459
from .app449 import _drop


def create_workspace_app460(*, base_dir=None):
    app = create_workspace_app459(base_dir=base_dir)
    app.title = "EagleEye Build 460.0 — Full Regression Checkpoint"
    app.version = "460.0"
    ctx = app.state.context

    # Preserve the previous authenticated/case-scoped handler rather than
    # mutating APIRoute.endpoint (FastAPI's dependant.call would stay stale).
    inherited_home = next(
        route.endpoint for route in app.router.routes
        if getattr(route, "path", None) == "/"
        and "GET" in (getattr(route, "methods", set()) or set())
    )
    _drop(app, "/", {"GET"})
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health460():
        integrity = bool(ctx.build458.build458_status().get("integrity_valid", False))
        return {
            "ok": True, "build": "460.0",
            "status": "ok" if integrity else "hold",
            "integrity_valid": integrity,
            "production_release_ready": False,
            "next_checkpoint": "465.0",
        }

    @app.get("/", response_class=HTMLResponse)
    def current_workspace(request: Request, view: str = "overview", case_id: str = ""):
        response = inherited_home(request=request, view=view, case_id=case_id)
        if not isinstance(response, HTMLResponse):
            return response
        content = response.body.decode("utf-8")
        content = content.replace("Build 459.0", "Build 460.0")
        content = content.replace("Investigator Navigation", "Full Regression Checkpoint")
        return HTMLResponse(content, status_code=response.status_code)

    return app


create_app = create_workspace_app460
