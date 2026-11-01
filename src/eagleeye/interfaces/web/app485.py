"""Build 485: first operational public-research pilot, no automatic customer release."""
from .app484 import create_workspace_app484
from .pilot485 import attach_pilot485

def create_workspace_app485(*, base_dir=None, workspace_build="485.0"):
    app=create_workspace_app484(base_dir=base_dir,workspace_build=workspace_build)
    app.version=workspace_build
    app.title="EagleEye – Quellenbasierte Fallbearbeitung und Pilotgate 485"
    attach_pilot485(app,workspace_build)
    return app

create_app=create_workspace_app485
