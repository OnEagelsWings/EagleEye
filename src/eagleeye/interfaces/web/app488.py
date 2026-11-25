"""Build 488: integrate audited entity candidate review into existing workspace."""
from .app487 import create_workspace_app487
from .entities488 import attach_entities488


def create_workspace_app488(*, base_dir=None, workspace_build="488.0"):
    app = create_workspace_app487(base_dir=base_dir, workspace_build=workspace_build)
    app.version = workspace_build
    app.title = "EagleEye – Entity-Prüfung 488"
    attach_entities488(app, workspace_build, base_dir)
    return app


create_app = create_workspace_app488
