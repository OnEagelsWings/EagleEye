"""Build 474: item-level human review and current-source validation."""
from .app471 import create_workspace_app471

def create_workspace_app474(*,base_dir=None):
    return create_workspace_app471(base_dir=base_dir,workspace_build='474.0',questions_enabled=True,
                                  hypotheses_enabled=True,review_matrix_enabled=True)

create_app=create_workspace_app474
