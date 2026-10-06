import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from eagleeye_pro.phase20.retrieval_isolation451 import ProcessSurfaceTransport451
from eagleeye_pro.phase20.scanner451 import ClamdScanner451, ScanWithheld451
from eagleeye.interfaces.web.app451 import create_workspace_app451
from eagleeye_pro.core.app_context import AppContext

ROOT = Path(__file__).resolve().parents[1]


def require_kernel():
    try:
        return ProcessSurfaceTransport451().containment_probe()
    except RuntimeError:
        if os.environ.get("EAGLEEYE_REQUIRE_KERNEL_TEST") == "1":
            pytest.fail("required real kernel confinement unavailable")
        pytest.skip("kernel profile unavailable in this environment")


def test_kernel_denies_files_network_and_processes():
    report = require_kernel()
    assert report["landlock_abi"] >= 3
    assert all(report["denied"].values())
    assert not report["external_network_contacted"]


def test_kernel_preconnected_http_still_works():
    require_kernel()
    parent, child = socket.socketpair()
    parent.settimeout(10)
    received = []

    def server():
        with parent:
            request = b""
            while b"\r\n\r\n" not in request:
                request += parent.recv(4096)
            received.append(request)
            parent.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 5\r\n\r\nhello")

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    request = {"url": "http://example.org/item", "resolved_ips": ["9.9.9.9"],
               "method": "GET", "headers": {}, "timeout_seconds": 5, "max_bytes": 100}
    try:
        result = subprocess.run([sys.executable, "-I", str(ROOT / "eagleeye_pro/phase20/retrieval_worker451.py"),
                                 "--connected-fd", str(child.fileno())], pass_fds=(child.fileno(),),
                                input=json.dumps(request).encode(), capture_output=True, timeout=10)
    finally:
        child.close()
        thread.join(timeout=10)
    assert result.returncode == 0, result.stdout
    response = json.loads(result.stdout)
    assert response["status"] == 200
    assert response["body"] == "aGVsbG8="
    assert b"GET /item HTTP/1.1" in received[0]
    assert b"Host: example.org" in received[0]


@pytest.mark.parametrize("reason", ["no_kernel", "no_scanner"])
def test_contained_profile_refuses_before_source_contact(monkeypatch, reason):
    transport = ProcessSurfaceTransport451(profile="contained")
    def probe(**kwargs):
        if reason == "no_kernel":
            raise RuntimeError("unavailable")
        return {}
    monkeypatch.setattr(transport, "containment_probe", probe)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("source contacted"))
    with pytest.raises(RuntimeError):
        transport.fetch("https://example.org/", resolved_ips=["9.9.9.9"])


class FakeConnection:
    def __init__(self, reply):
        self.reply, self.sent = reply, bytearray()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def sendall(self, data):
        self.sent.extend(data)
    def recv(self, size):
        value, self.reply = self.reply[:size], self.reply[size:]
        return value


def version(days=0):
    stamp = datetime.now(timezone.utc) - timedelta(days=days, seconds=1)
    return ("ClamAV 1.4.3/27900/" + stamp.strftime("%a %b %d %H:%M:%S %Y") + "\0").encode()


@pytest.mark.parametrize("reply,expected", [
    (b"stream: OK\0", "clean"),
    (b"stream: Eicar-Signature FOUND\0", "scanner_detection"),
    (b"stream: size limit exceeded ERROR\0", "scanner_unavailable_or_unqualified"),
    (b"garbage\0", "scanner_unavailable_or_unqualified"),
    (b"stream: OK", "scanner_unavailable_or_unqualified"),
    (b"x" * 5000, "scanner_unavailable_or_unqualified"),
])
def test_scanner_bounded_protocol_and_fail_closed(monkeypatch, reply, expected):
    scanner = ClamdScanner451("local-scanner")
    connections = [FakeConnection(version()), FakeConnection(reply)]
    pending = iter(connections)
    monkeypatch.setattr(scanner, "_connect", lambda: next(pending))
    if expected == "clean":
        assert scanner.scan(b"benign")["result"] == "clean"
    else:
        with pytest.raises(ScanWithheld451) as caught:
            scanner.scan(b"test bytes")
        assert caught.value.quarantine_metadata["reason"] == expected
        assert not caught.value.quarantine_metadata["raw_payload_stored"]
    assert connections[1].sent.startswith(b"zINSTREAM\0")
    assert connections[1].sent.endswith(b"\0\0\0\0")


@pytest.mark.parametrize("reply", [version(3), b"ClamAV malformed\0", b"ClamAV 1/1/Sun Jan 01 00:00:00 2099\0"])
def test_scanner_stale_or_invalid_database_withholds_before_stream(monkeypatch, reply):
    scanner = ClamdScanner451("local-scanner")
    connection = FakeConnection(reply)
    monkeypatch.setattr(scanner, "_connect", lambda: connection)
    with pytest.raises(ScanWithheld451):
        scanner.scan(b"benign")
    assert connection.sent == b"zVERSION\0"


def test_real_clamd_clean_and_eicar():
    path = os.environ.get("EAGLEEYE_TEST_CLAMD_SOCKET")
    if not path:
        pytest.skip("real ClamAV fixture gate runs in scanner CI")
    scanner = ClamdScanner451(path)
    assert scanner.scan(b"EagleEye benign scanner qualification text")["result"] == "clean"
    eicar = b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
    with pytest.raises(ScanWithheld451) as caught:
        scanner.scan(eicar)
    assert caught.value.quarantine_metadata["reason"] == "scanner_detection"
    assert caught.value.quarantine_metadata["malware_scan_performed"]


def test_build451_version_launcher_status_and_auth(tmp_path):
    from eagleeye_pro.version import BUILD, SCHEMA_VERSION
    assert BUILD == SCHEMA_VERSION == "451.0"
    with AppContext(base_dir=tmp_path / "ctx") as ctx:
        status = ctx.build451.retrieval_isolation_status_451()
        assert status["next_hard_checkpoint"] == "455.0"
        assert status["operational_qualification"] == "HOLD"
        assert not status["native_windows_kernel_profile_qualified"]
    app = create_workspace_app451(base_dir=tmp_path / "web")
    try:
        with TestClient(app) as client:
            assert client.get("/health").json()["build"] == "451.0"
            assert client.get("/api/build451/status").status_code == 401
            assert client.post("/api/build451/diagnose").status_code == 401
    finally:
        app.state.context.close()
    assert 'app451 import create_workspace_app451' in (ROOT / "src/eagleeye/interfaces/web/server.py").read_text()
    assert 'EAGLEEYE_PRO_451_0.py' in (ROOT / "START_EAGLEEYE_PRO.sh").read_text()


def test_admin_diagnostics_require_role_and_same_origin(tmp_path, monkeypatch):
    app = create_workspace_app451(base_dir=tmp_path)
    ctx = app.state.context
    current = {"username": "reviewer451", "global_role": "investigator"}
    monkeypatch.setattr(ctx.team_identity_359, "validate_session", lambda *a, **k: dict(current))
    calls = []
    monkeypatch.setattr(ctx.build451, "diagnose_retrieval_isolation_451", lambda: calls.append(True) or {"ok": True})
    try:
        with TestClient(app) as client:
            assert client.get("/api/build451/status").status_code == 200
            assert client.post("/api/build451/diagnose").status_code == 403
            current["global_role"] = "system_administrator"
            assert client.post("/api/build451/diagnose", headers={"origin": "https://other.example"}).status_code == 403
            assert calls == []
            assert client.post("/api/build451/diagnose").status_code == 200
            assert calls == [True]
    finally:
        ctx.close()


def test_scanner_withheld_content_persists_without_intake(tmp_path, monkeypatch):
    import base64
    from test_build441_integrated import ident, case, source_and_task, resolver

    class RejectScanner:
        def scan(self, body):
            if body.startswith(b"User-agent:"):
                return {"result": "clean"}
            raise ScanWithheld451(body, "scanner_detection", "test-engine")

    def run(args, **kwargs):
        payload = json.loads(kwargs["input"])
        body = b"User-agent: *\nAllow: /\n" if payload["url"].endswith("/robots.txt") else b"scanner test content"
        response = dict(url=payload["url"], status=200, headers={"content-type": "text/plain"},
                        elapsed_ms=1, body=base64.b64encode(body).decode())
        return subprocess.CompletedProcess(args, 0, json.dumps(response).encode(), b"")
    monkeypatch.setattr(subprocess, "run", run)
    with AppContext(base_dir=tmp_path) as ctx:
        identity = ident(ctx)
        case_id = case(ctx, "Scanner 451")["case_id"]
        _, task, _ = source_and_task(ctx, identity, case_id, suffix="scanner451")
        with pytest.raises(RuntimeError, match="ScanWithheld451"):
            ctx.surface_retrieval_441.execute_replay(
                identity=identity, task_id=task["task_id"], resolver=resolver,
                transport=ProcessSurfaceTransport451(scanner=RejectScanner()))
        run = ctx.surface_retrieval_441.case_runs(case_id)[-1]
        quarantine = ctx.acquisition_events_422.get(run["event_id"])["provenance"]["content_quarantine"]
        assert quarantine["reason"] == "scanner_detection"
        assert ctx.db.one("SELECT COUNT(*) n FROM content_observation_423 WHERE case_id=?", (case_id,))["n"] == 0
    with AppContext(base_dir=tmp_path) as ctx:
        run = ctx.surface_retrieval_441.case_runs(case_id)[-1]
        assert ctx.acquisition_events_422.get(run["event_id"])["provenance"]["content_quarantine"] == quarantine


@pytest.mark.parametrize("succeed_on", [None, 2, 3], ids=["exhausted", "remaining-worker-budget", "no-worker-after-expiry"])
def test_contained_connection_attempts_share_deadline(monkeypatch, succeed_on):
    import base64
    import eagleeye_pro.phase20.retrieval_isolation451 as module
    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    transport = ProcessSurfaceTransport451(profile="contained", scanner=object())
    probe_budgets = []
    monkeypatch.setattr(transport, "containment_probe", lambda **kw: probe_budgets.append(kw["timeout_seconds"]))
    attempts, worker_budgets, closed = [], [], []

    class Wire:
        def fileno(self):
            return 42
        def close(self):
            closed.append(True)

    def connect(address, timeout):
        attempts.append(timeout)
        clock[0] += 4
        if len(attempts) == succeed_on:
            return Wire()
        raise TimeoutError("simulated unreachable public address")

    def run(command, **kwargs):
        worker_budgets.append(kwargs["timeout"])
        assert kwargs["pass_fds"] == (42,)
        payload = json.loads(kwargs["input"])
        return subprocess.CompletedProcess(command, 0, json.dumps({
            "url": payload["url"], "status": 200, "headers": {},
            "body": base64.b64encode(b"benign").decode(), "elapsed_ms": 0,
        }).encode(), b"")

    class Scanner:
        def scan(self, body):
            return {"result": "clean"}
    transport.scanner = Scanner()
    monkeypatch.setattr(module.socket, "create_connection", connect)
    monkeypatch.setattr(module.subprocess, "run", run)
    if succeed_on == 2:
        assert transport.fetch("https://example.org/", resolved_ips=["9.9.9.9"] * 16,
                               timeout_seconds=10).body == b"benign"
        assert attempts == [10, 6]
        assert worker_budgets == [2]
        assert closed == [True]
    else:
        with pytest.raises(TimeoutError, match="shared wall-clock"):
            transport.fetch("https://example.org/", resolved_ips=["9.9.9.9"] * 16,
                            timeout_seconds=10)
        assert attempts == [10, 6, 2]
        assert worker_budgets == []
        assert closed == ([True] if succeed_on == 3 else [])
    assert probe_budgets == [10]


def test_containment_probe_consumes_same_deadline(monkeypatch):
    import eagleeye_pro.phase20.retrieval_isolation451 as module
    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    transport = ProcessSurfaceTransport451(profile="contained", scanner=object())
    def probe(**kwargs):
        assert kwargs["timeout_seconds"] == 1
        clock[0] = 1
    monkeypatch.setattr(transport, "containment_probe", probe)
    monkeypatch.setattr(module.socket, "create_connection", lambda *a, **k: pytest.fail("expired request contacted source"))
    with pytest.raises(TimeoutError, match="shared wall-clock"):
        transport.fetch("https://example.org/", resolved_ips=["9.9.9.9"], timeout_seconds=1)
