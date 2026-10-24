"""Build 480: five-build operational checkpoint with explicit production limits."""
from .app479 import create_workspace_app479
from .checkpoint480 import attach_checkpoint

def create_workspace_app480(*,base_dir=None):
    app=create_workspace_app479(base_dir=base_dir,workspace_build="480.0")
    app.version="480.0"
    app.title="EagleEye – Operational Case Checkpoint 480"
    attach_checkpoint(app,"480.0")
    return app

create_app=create_workspace_app480
