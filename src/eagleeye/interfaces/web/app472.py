"""Build 472: persistent questions answered only from selected case evidence."""
from .app471 import create_workspace_app471

def create_workspace_app472(*, base_dir=None):
    return create_workspace_app471(base_dir=base_dir, workspace_build='472.0', questions_enabled=True)

create_app = create_workspace_app472
