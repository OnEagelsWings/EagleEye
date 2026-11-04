"""Build 489 workspace: consolidate existing review and source provenance views."""
from .app488 import create_workspace_app488
from .checkpoint489 import attach_checkpoint489


def create_workspace_app489(*, base_dir=None, workspace_build="489.0"):
    app = create_workspace_app488(base_dir=base_dir, workspace_build=workspace_build)
    app.version = workspace_build
    app.title = "EagleEye – Prüfcheckpoint 489"
    attach_checkpoint489(app, workspace_build)
    return app


create_app = create_workspace_app489
