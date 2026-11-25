"""Build 484: connected image similarity review and case graph navigation."""
from .app483 import create_workspace_app483
from .media484 import attach_media484

def create_workspace_app484(*,base_dir=None,workspace_build="484.0"):
    app=create_workspace_app483(base_dir=base_dir,workspace_build=workspace_build)
    app.version=workspace_build
    app.title="EagleEye – Bildvergleich und Beziehungsprüfung 484"
    attach_media484(app,workspace_build)
    return app

create_app=create_workspace_app484
