"""Build 479: reviewed working reports and offline recovery."""
from .app478 import create_workspace_app478
from .report479 import attach_report
def create_workspace_app479(*,base_dir=None,workspace_build="479.0"):
    app=create_workspace_app478(base_dir=base_dir,workspace_build=workspace_build)
    app.title="EagleEye – Quellenkritischer Arbeitsbericht "+workspace_build
    attach_report(app,workspace_build)
    return app
create_app=create_workspace_app479
