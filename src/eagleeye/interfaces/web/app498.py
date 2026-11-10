"""Build 498: typed local AI proposals and human acceptance."""
from .app497 import create_workspace_app497
from .ai498 import attach_ai498

def create_workspace_app498(*,base_dir=None,workspace_build="498.0"):
    app=create_workspace_app497(base_dir=base_dir,workspace_build=workspace_build)
    app.version=workspace_build;app.title=f"EagleEye – Build {workspace_build}"
    attach_ai498(app,workspace_build)
    return app

create_app=create_workspace_app498
