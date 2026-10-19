from __future__ import annotations

from .app459 import create_workspace_app459
from .app449 import _drop


def create_workspace_app460(*, base_dir=None):
    app = create_workspace_app459(
        base_dir=base_dir,
        workspace_build="460.0",
        workspace_title="Full Regression Checkpoint",
    )
    app.title = "EagleEye Build 460.0 — Full Regression Checkpoint"
    app.version = "460.0"
    ctx = app.state.context
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

    return app


create_app = create_workspace_app460
