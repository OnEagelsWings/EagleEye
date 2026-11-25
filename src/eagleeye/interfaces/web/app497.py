"""Build 497: controlled provider action bridge layered on Build 496."""
from .app496 import create_workspace_app496
from .execution497 import attach_execution497

def create_workspace_app497(*,base_dir=None,workspace_build="497.0"):
    app=create_workspace_app496(base_dir=base_dir,workspace_build=workspace_build)
    app.version=workspace_build
    app.title=f"EagleEye – Build {workspace_build}"
    attach_execution497(app,workspace_build)
    return app

create_app=create_workspace_app497
