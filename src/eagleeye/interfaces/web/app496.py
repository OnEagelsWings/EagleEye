"""Build 496 integrates a review-gated plan board with Build 495."""
from .app495 import create_workspace_app495
from .plan496 import attach_plan496


def create_workspace_app496(*, base_dir=None, workspace_build="496.0"):
    app = create_workspace_app495(base_dir=base_dir, workspace_build=workspace_build)
    app.version = workspace_build
    app.title = f"EagleEye – Build {workspace_build}"
    app.state.integration_development_layer = "496-plan-review"
    attach_plan496(app, workspace_build)
    return app


create_app = create_workspace_app496
