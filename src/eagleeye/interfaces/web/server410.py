from __future__ import annotations

from . import server as _server
from .app410 import create_workspace_app410


def serve_workspace(**kwargs):
    previous=_server.create_workspace_app
    _server.create_workspace_app=create_workspace_app410
    try:
        return _server.serve_workspace(**kwargs)
    finally:
        _server.create_workspace_app=previous

open_existing_workspace=_server.open_existing_workspace
