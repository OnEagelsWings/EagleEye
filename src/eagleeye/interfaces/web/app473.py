"""Build 473: case-scoped competing hypotheses and counter-evidence."""
from .app471 import create_workspace_app471

def create_workspace_app473(*,base_dir=None):
    return create_workspace_app471(base_dir=base_dir,workspace_build='473.0',questions_enabled=True,hypotheses_enabled=True)

create_app=create_workspace_app473
