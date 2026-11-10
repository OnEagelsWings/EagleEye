"""Regression: normal launcher must not silently select a legacy workspace.

Build number/package alignment is a separate release gate; this verifies the
real server entry point selects the latest integrated application (Build 493
layer on top of the integrated 489 workspace) and passes the installed build.
"""
from eagleeye.interfaces.web import server


def test_normal_server_selects_integrated_workspace(monkeypatch, tmp_path):
    calls = []
    sentinel = object()

    def integrated(*, base_dir=None, workspace_build=None):
        calls.append((base_dir, workspace_build))
        return sentinel

    monkeypatch.setattr(server, "create_workspace_app498", integrated)
    assert server.create_workspace_app(base_dir=tmp_path) is sentinel
    assert calls == [(tmp_path, server.BUILD)]


def test_normal_server_uses_integrated_498_factory():
    assert server.create_workspace_app498.__module__.endswith(".app498")
    from eagleeye.interfaces.web import app498
    # The 492 layer must still be built on the integrated 489 workspace.
    assert app498.create_workspace_app497.__module__.endswith(".app497")
