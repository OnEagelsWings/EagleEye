"""Regression: normal launcher must not silently select legacy app487.

Build number/package alignment is a separate release gate; this verifies the
real server entry point selects the existing integrated 489 application.
"""
from eagleeye.interfaces.web import server


def test_normal_server_selects_integrated_workspace(monkeypatch, tmp_path):
    calls = []
    sentinel = object()

    def integrated(*, base_dir=None, workspace_build=None):
        calls.append((base_dir, workspace_build))
        return sentinel

    monkeypatch.setattr(server, "create_workspace_app489", integrated)
    assert server.create_workspace_app(base_dir=tmp_path) is sentinel
    assert calls == [(tmp_path, server.BUILD)]


def test_normal_server_uses_integrated_489_factory():
    assert server.create_workspace_app489.__module__.endswith(".app489")
