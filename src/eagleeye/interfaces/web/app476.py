"""Build 476: operative onboarding and desktop-start diagnostics."""
from .app475 import create_workspace_app475

def create_workspace_app476(*,base_dir=None,workspace_build='476.0'):
    return create_workspace_app475(base_dir=base_dir,workspace_build=workspace_build)

create_app=create_workspace_app476
