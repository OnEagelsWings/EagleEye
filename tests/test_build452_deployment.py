from pathlib import Path
import threading
import time

import pytest
from fastapi.testclient import TestClient

import eagleeye_pro.phase19.surface_retrieval441 as surface441
from eagleeye.interfaces.web.app452 import create_workspace_app452

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_IP = "93.184.216.34"


class _DeadlineSock:
    def __init__(self):
        self.closed = threading.Event()
        self.timeout = None

    def settimeout(self, value):
        self.timeout = value

    def shutdown(self, *_args):
        self.closed.set()

    def close(self):
        self.closed.set()


def test_build452_health_contract_and_context_service(tmp_path):
    app = create_workspace_app452(base_dir=tmp_path)
    try:
        status = app.state.context.build452.deployment_status_452()
        assert status["build"] == "452.0"
        assert status["expected_package_version"] == "452.0.0"
        assert status["non_editable_runtime_expected"] is True
        assert status["next_hard_checkpoint"] == "455.0"
        assert status["production_release_ready"] is False
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"ok": True, "status": "ok", "build": "452.0"}
    finally:
        app.state.context.close()


def test_build452_installer_and_launchers_use_isolated_non_editable_runtime():
    installer = (ROOT / "INSTALL_EAGLEEYE_452.py").read_text(encoding="utf-8")
    sh = (ROOT / "START_EAGLEEYE_PRO.sh").read_text(encoding="utf-8")
    bat = (ROOT / "START_EAGLEEYE_PRO.bat").read_text(encoding="utf-8")
    server = (ROOT / "src/eagleeye/interfaces/web/server.py").read_text(encoding="utf-8")

    assert '"pip"' in installer
    assert '"install"' in installer
    assert "-e ." not in installer
    assert "editable" in installer
    assert ".eagleeye-runtime" in installer
    assert "source_fingerprint_sha256" in installer
    assert "INSTALL_EAGLEEYE_452.py" in sh
    assert "INSTALL_EAGLEEYE_452.py" in bat
    assert " -I -c " in sh
    assert " -I -c " in bat
    assert "app452 import create_workspace_app452" in server


def test_build452_header_parsing_cannot_extend_absolute_transport_deadline(monkeypatch):
    class Connection:
        def __init__(self, host, port=80, timeout=None, **_kwargs):
            self.host, self.port, self.timeout = host, port, timeout
            self.sock = _DeadlineSock()

        def putrequest(self, *_args, **_kwargs):
            pass

        def putheader(self, *_args, **_kwargs):
            pass

        def endheaders(self):
            pass

        def getresponse(self):
            self.sock.closed.wait(1.0)
            raise OSError("deadline socket aborted")

        def close(self):
            if self.sock is not None:
                self.sock.close()

    monkeypatch.setattr(surface441.http.client, "HTTPConnection", Connection)
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="wall-clock deadline"):
        surface441.PinnedSurfaceTransport441().fetch(
            "http://deadline-header.example.org/page",
            resolved_ips=[PUBLIC_IP],
            timeout_seconds=0.05,
            max_bytes=1000,
        )
    assert time.monotonic() - started < 0.5


def test_build452_detached_response_body_is_aborted_at_absolute_deadline(monkeypatch):
    class Raw:
        def __init__(self, sock):
            self._sock = sock

    class FP:
        def __init__(self, sock):
            self.raw = Raw(sock)

    class Response:
        status = 200

        def __init__(self, sock):
            self.fp = FP(sock)
            self.sock = sock

        def read1(self, _size=-1):
            self.sock.closed.wait(1.0)
            raise OSError("deadline socket aborted")

        def getheaders(self):
            return [("content-type", "text/plain")]

    class Connection:
        def __init__(self, host, port=80, timeout=None, **_kwargs):
            self.host, self.port, self.timeout = host, port, timeout
            self.sock = _DeadlineSock()
            self._captured = self.sock

        def putrequest(self, *_args, **_kwargs):
            pass

        def putheader(self, *_args, **_kwargs):
            pass

        def endheaders(self):
            pass

        def getresponse(self):
            response = Response(self._captured)
            self.sock = None
            return response

        def close(self):
            self._captured.close()

    monkeypatch.setattr(surface441.http.client, "HTTPConnection", Connection)
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="wall-clock deadline"):
        surface441.PinnedSurfaceTransport441().fetch(
            "http://deadline-body.example.org/page",
            resolved_ips=[PUBLIC_IP],
            timeout_seconds=0.05,
            max_bytes=1000,
        )
    assert time.monotonic() - started < 0.5


def test_build452_version_and_release_contract():
    assert 'version = "452.0.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'BUILD = "452.0"' in (ROOT / "eagleeye_pro/version.py").read_text(encoding="utf-8")
    assert (ROOT / "README_BUILD_452_0.md").exists()
    assert (ROOT / "RELEASE_MANIFEST_BUILD_452_0.json").exists()
