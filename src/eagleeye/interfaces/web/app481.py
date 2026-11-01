"""Build 481 – real, case-bound sources to governed Evidence and investigative navigation."""
from .app480 import create_workspace_app480
from .bridge481 import attach_bridge

def create_workspace_app481(*, base_dir=None):
    app = create_workspace_app480(base_dir=base_dir, workspace_build="481.0")
    app.version = "481.0"
    app.title = "EagleEye – Operativer Ermittlungsarbeitsplatz 481"
    attach_bridge(app, "481.0")
    return app

create_app = create_workspace_app481
