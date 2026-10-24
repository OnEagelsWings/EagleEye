"""Build 477: source provenance inventory attached to operational case."""
from .app476 import create_workspace_app476
from .sources477 import attach_sources

def create_workspace_app477(*,base_dir=None,workspace_build="477.0"):
    app=create_workspace_app476(base_dir=base_dir,workspace_build=workspace_build)
    app.title="EagleEye – Quellenarbeitsplatz "+workspace_build
    app.version=workspace_build
    attach_sources(app,workspace_build)
    return app

create_app=create_workspace_app477
