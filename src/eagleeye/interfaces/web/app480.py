"""Build 480: integrated operational case checkpoint."""
from .app479 import create_workspace_app479
from .checkpoint480 import attach_checkpoint
def create_workspace_app480(*,base_dir=None,workspace_build="480.0"):
    app=create_workspace_app479(base_dir=base_dir,workspace_build=workspace_build)
    app.title="EagleEye – Operativer Prüfpunkt "+workspace_build
    attach_checkpoint(app,workspace_build)
    return app
create_app=create_workspace_app480
