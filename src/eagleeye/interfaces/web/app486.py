"""Build 486 – case-preserving startup, with the complete Build-485 pilot workflow."""
from .app485 import create_workspace_app485


def create_workspace_app486(*, base_dir=None, workspace_build="486.0"):
    app = create_workspace_app485(base_dir=base_dir, workspace_build=workspace_build)
    app.version = workspace_build
    app.title = "EagleEye – sicherer Windows-Erststart und Bestandsdaten 486"
    return app


create_app = create_workspace_app486
