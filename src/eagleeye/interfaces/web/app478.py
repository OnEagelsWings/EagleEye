"""Build 478: investigator-authored source anchored findings."""
from .app477 import create_workspace_app477
from .findings478 import attach_findings

def create_workspace_app478(*,base_dir=None,workspace_build="478.0"):
    app=create_workspace_app477(base_dir=base_dir,workspace_build=workspace_build)
    app.version=workspace_build
    app.title="EagleEye – Quellenbelegte Arbeitsbefunde "+workspace_build
    attach_findings(app,workspace_build)
    return app
create_app=create_workspace_app478
