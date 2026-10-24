"""Build 476: desktop continuity and guided operational research."""
from .app475 import create_workspace_app475
from .operations476 import attach_workbench

def create_workspace_app476(*,base_dir=None,workspace_build='476.0'):
    app=create_workspace_app475(base_dir=base_dir,workspace_build=workspace_build)
    app.title='EagleEye – Ermittlungsarbeitsplatz '+workspace_build
    attach_workbench(app,workspace_build)
    return app

create_app=create_workspace_app476
