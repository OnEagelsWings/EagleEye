"""Build 495: one operator workflow combining EagleEye and PersonOSINT tools.

The installed Build 490 version remains unchanged until independently validated
runtime/installer release; the integrated application is a development preview.
"""
from .app494 import create_workspace_app494
from .personosint495 import attach_personosint495


def create_workspace_app495(*, base_dir=None, workspace_build="495.0"):
    app = create_workspace_app494(base_dir=base_dir, workspace_build=workspace_build)
    app.version = workspace_build
    app.title = f"EagleEye – Build {workspace_build}"
    app.state.integration_development_layer = "495-source-handoff"
    attach_personosint495(app, workspace_build)
    return app


create_app = create_workspace_app495
