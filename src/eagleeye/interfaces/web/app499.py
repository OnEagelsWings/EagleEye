"""Build 499: source-backed unverified candidate transfer."""
from .app498 import create_workspace_app498
from .transfer499 import attach_transfer499

def create_workspace_app499(*,base_dir=None,workspace_build="499.0"):
    app=create_workspace_app498(base_dir=base_dir,workspace_build=workspace_build)
    app.version=workspace_build;app.title=f"EagleEye – Build {workspace_build}"
    attach_transfer499(app,workspace_build,base_dir)
    return app

create_app=create_workspace_app499
