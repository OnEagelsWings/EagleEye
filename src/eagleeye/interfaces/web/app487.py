"""Build 487: case-bound manual source provenance without inferred Evidence."""
from .app486 import create_workspace_app486
from .sources487 import attach_sources487

def create_workspace_app487(*, base_dir=None, workspace_build="487.0"):
    app = create_workspace_app486(base_dir=base_dir, workspace_build=workspace_build)
    app.version = workspace_build
    app.title = "EagleEye – Quellenzuordnung und Provenienz 487"
    attach_sources487(app, workspace_build)
    return app

create_app = create_workspace_app487
