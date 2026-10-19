from __future__ import annotations

from .app459 import create_workspace_app459
from .app449 import _drop


def create_workspace_app460(*, base_dir=None):
    app = create_workspace_app459(base_dir=base_dir)
    app.title = "EagleEye Build 460.0 — Full Regression Checkpoint"
    app.version = "460.0"
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health460():
        return {"ok": True, "build": "460.0", "status": "ok", "production_release_ready": False,
                "next_checkpoint": "465.0"}

    return app


create_app = create_workspace_app460
