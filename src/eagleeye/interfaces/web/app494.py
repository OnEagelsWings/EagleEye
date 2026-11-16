"""Build 494: unified PersonOSINT lead and entity reviewer workbench."""
from .app493 import create_workspace_app493
from .personosint494 import attach_personosint494


def create_workspace_app494(*, base_dir=None, workspace_build="494.0"):
    app = create_workspace_app493(base_dir=base_dir, workspace_build=workspace_build)
    app.version = workspace_build
    app.title = f"EagleEye – Build {workspace_build}"
    attach_personosint494(app, workspace_build)
    return app


create_app = create_workspace_app494
