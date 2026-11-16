"""Build 493 integration layer: one-way PersonOSINT 1.4 research-lead intake.

Build 492 retains all existing routes and source/evidence controls. The imported
JSON is never a replacement for EagleEye's canonical case database.
"""
from .app492 import create_workspace_app492
from .personosint493 import attach_personosint493


def create_workspace_app493(*, base_dir=None, workspace_build="493.0"):
    app = create_workspace_app492(base_dir=base_dir, workspace_build=workspace_build)
    app.version = workspace_build
    app.title = f"EagleEye – Build {workspace_build}"
    attach_personosint493(app, workspace_build)
    return app


create_app = create_workspace_app493
