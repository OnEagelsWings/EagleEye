"""Build 483 – operational public-search leads without unauthorized crawler actions."""
from .app482 import create_workspace_app482
from .research483 import attach_research483

def create_workspace_app483(*, base_dir=None, workspace_build="483.0"):
    app = create_workspace_app482(base_dir=base_dir, workspace_build=workspace_build)
    app.version = workspace_build
    app.title = "EagleEye – Recherchen und fallbezogene Quellenhinweise 483"
    attach_research483(app, workspace_build)
    return app

create_app = create_workspace_app483
