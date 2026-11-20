"""Current Build 500 loopback browser launch validation (no OS browser required)."""
import pytest
from eagleeye.interfaces.web import server


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:0/workbench",
    "http://localhost:0/",
    "http://localhost:99999/",
    "http://user@localhost:8765/",
    "http://localhost:8765/\n",
    "https://localhost:8765/",
    "http://example.com:8765/",
])
def test_launcher_rejects_invalid_targets_without_os_launch(monkeypatch, url):
    launched = []
    monkeypatch.setattr(server, "_firefox_candidates", lambda: ())
    monkeypatch.setattr(server.subprocess, "Popen", lambda *a, **kw: launched.append(a))
    assert server.open_local_browser(url) == "unavailable"
    assert not launched


def test_launcher_accepts_valid_loopback_url(monkeypatch):
    launched = []
    monkeypatch.setattr(server, "_firefox_candidates", lambda: ())
    monkeypatch.setattr(server.subprocess, "Popen", lambda command, **kw: launched.append(command))
    url = "http://127.0.0.1:8765/workbench"
    assert server.open_local_browser(url) == "default"
    assert launched and launched[0][-1] == url
