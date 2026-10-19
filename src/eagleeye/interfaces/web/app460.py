from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from .app459 import create_workspace_app459
from .app449 import _drop


def create_workspace_app460(*, base_dir=None):
    app = create_workspace_app459(base_dir=base_dir)
    app.title = "EagleEye Build 460.0 — Full Regression Checkpoint"
    app.version = "460.0"
    _drop(app, "/health", {"GET"})
    ctx = app.state.context

    @app.get("/health")
    def health460():
        integrity = ctx.build458.build458_status().get("integrity_valid", False)
        return {"ok": True, "build": "460.0",
                "status": "ok" if integrity else "hold",
                "integrity_valid": bool(integrity),
                "production_release_ready": False, "next_checkpoint": "465.0"}

    # Preserve authentication and case authorization from Build 459.
    for route in app.router.routes:
        if getattr(route, "path", None) == "/" and "GET" in (getattr(route, "methods", set()) or set()):
            original = route.endpoint

            def current_workspace(request: Request, view: str = "overview", case_id: str = ""):
                response = original(request=request, view=view, case_id=case_id)
                if isinstance(response, HTMLResponse):
                    body = response.body.decode("utf-8")
                    body = body.replace("Build 459.0", "Build 460.0")
                    body = body.replace("Investigator Navigation", "Full Regression Checkpoint")
                    return HTMLResponse(body, status_code=response.status_code, headers=dict(response.headers))
                return response

            route.endpoint = current_workspace
            break
    return app


create_app = create_workspace_app460
