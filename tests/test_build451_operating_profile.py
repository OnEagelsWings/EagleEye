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


@pytest.mark.parametrize("authority", ["example.org", "example.org:80", "example.org:443"])
def test_kernel_preconnected_http_still_works(authority):
    require_kernel()
    parent, child = socket.socketpair()
    parent.settimeout(10)
    received = []

    def server():
        with parent:
            request = b""
            while b"\r\n\r\n" not in request:
                chunk = parent.recv(4096)
                if not chunk:
                    return
                request += chunk
            received.append(request)
            parent.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 5\r\n\r\nhello")

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    request = {"url": f"http://{authority}/item", "resolved_ips": ["9.9.9.9"],
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
    assert (f"Host: {authority}\r\n".encode()) in received[0]
    assert response["headers"]["content-type"] == "text/plain"
    assert "Content-Type" not in response["headers"]


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
    def settimeout(self, timeout):
        self.timeout = timeout
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
    monkeypatch.setattr(scanner, "_connect", lambda *args: next(pending))
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
    monkeypatch.setattr(scanner, "_connect", lambda *args: connection)
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


@pytest.mark.skipif(sys.platform != "linux", reason="contained worker is Linux-only")
@pytest.mark.parametrize("url,authority,sni", [
    ("http://example.org:443/item", "example.org:443", None),
    ("https://example.org:80/item", "example.org:80", "example.org"),
    ("https://example.org/item", "example.org", "example.org"),
])
def test_contained_worker_authority_header_contract(monkeypatch, url, authority, sni):
    # HTTP/TLS dispatch contract test; kernel enforcement has separate real probes.
    import resource
    from eagleeye_pro.phase20 import retrieval_worker451 as worker
    parent, child = socket.socketpair()
    parent.settimeout(10)
    received, wrapped = [], []
    monkeypatch.setattr(resource, "setrlimit", lambda *a: None)
    monkeypatch.setattr(worker, "confine_worker451", lambda: {})
    class TrustContext:
        def wrap_socket(self, wire, *, server_hostname):
            wrapped.append(server_hostname)
            return wire
    monkeypatch.setattr(worker.ssl, "create_default_context", lambda: TrustContext())
    def server():
        with parent:
            request = b""
            while b"\r\n\r\n" not in request:
                chunk = parent.recv(4096)
                if not chunk:
                    return
                request += chunk
            received.append(request)
            parent.sendall(b"HTTP/1.1 200 OK\r\nCoNtEnT-TyPe: text/plain\r\nContent-Length: 5\r\n\r\nhello")
    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    try:
        response = worker.contained_fetch451({"url": url, "headers": {}, "timeout_seconds": 5,
                                              "max_bytes": 100}, child.detach())
    finally:
        child.close()
        thread.join(timeout=10)
    assert response.headers["content-type"] == "text/plain"
    assert response.body == b"hello"
    assert f"Host: {authority}\r\n".encode() in received[0]
    assert wrapped == ([sni] if sni else [])


@pytest.mark.parametrize("detected", [False, True], ids=["benign", "eicar"])
def test_real_clamd_contained_acquisition_intake(tmp_path, monkeypatch, detected):
    path = os.environ.get("EAGLEEYE_TEST_CLAMD_SOCKET")
    if not path:
        pytest.skip("combined real kernel/scanner intake runs in scanner CI")
    require_kernel()
    import hashlib
    from test_build441_integrated import ident, case, resolver
    body = (b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
            if detected else b"benign public source fixture")
    threads, requested = [], []
    def connect(address, timeout):
        # Preserve validation/worker/scanner/intake; replace only external TCP with
        # a controlled inherited socket. No real source contacts or TLS claim.
        parent, child = socket.socketpair()
        parent.settimeout(10)
        def server():
            with parent:
                request = b""
                while b"\r\n\r\n" not in request:
                    chunk = parent.recv(4096)
                    if not chunk:
                        return
                    request += chunk
                requested.append(request)
                payload = b"User-agent: *\nAllow: /\n" if b"GET /robots.txt " in request else body
                parent.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: "
                               + str(len(payload)).encode() + b"\r\n\r\n" + payload)
        thread = threading.Thread(target=server, daemon=True)
        threads.append(thread)
        thread.start()
        return child
    monkeypatch.setattr(socket, "create_connection", connect)
    try:
        with AppContext(base_dir=tmp_path) as ctx:
            identity = ident(ctx)
            case_id = case(ctx, "Contained scanner intake 451")["case_id"]
            source = ctx.build421.register_source(
                identity=identity, name="Controlled contained HTTP fixture", source_type="website",
                access_mode="public", base_url="http://contained451.example.org/",
                capabilities=["public_pages"], coverage={"fixture_only": True})
            task = ctx.crawler_core_425.create_task(
                identity=identity, case_id=case_id, source_id=source["source_id"],
                target="http://contained451.example.org/page", objective="controlled kernel/scanner intake",
                scope={"allowed_hosts": ["contained451.example.org"]},
                budget={"max_pages": 1, "max_bytes": 100000, "max_seconds": 10})
            transport = ProcessSurfaceTransport451(profile="contained", scanner=ClamdScanner451(path))
            if detected:
                with pytest.raises(RuntimeError, match="ScanWithheld451"):
                    ctx.surface_retrieval_441.execute_replay(identity=identity, task_id=task["task_id"],
                                                            transport=transport, resolver=resolver)
                run = ctx.surface_retrieval_441.case_runs(case_id)[-1]
                event = ctx.acquisition_events_422.get(run["event_id"])
                persisted_key = "content_quarantine"
                security = event["provenance"][persisted_key]
                assert security["reason"] == "scanner_detection"
                assert security["malware_scan_performed"]
            else:
                result = ctx.surface_retrieval_441.execute_replay(identity=identity, task_id=task["task_id"],
                                                                 transport=transport, resolver=resolver)
                assert result["run"]["state"] == "completed"
                event = ctx.acquisition_events_422.get(result["accepted"]["event_id"])
                persisted_key = "retrieval_security451"
                security = event["provenance"][persisted_key]
                assert security["kernel_contained"]
                assert security["scanner"]["result"] == "clean"
                assert security["scanner"]["sha256"] == hashlib.sha256(body).hexdigest()
            assert ctx.db.one("SELECT COUNT(*) n FROM content_observation_423 WHERE case_id=?", (case_id,))["n"] == (0 if detected else 1)
        with AppContext(base_dir=tmp_path) as ctx:
            run = ctx.surface_retrieval_441.case_runs(case_id)[-1]
            assert ctx.acquisition_events_422.get(run["event_id"])["provenance"][persisted_key] == security
        assert any(b"GET /page " in request for request in requested)
    finally:
        for thread in threads:
            thread.join(timeout=10)


def test_scanner_trickle_reply_cannot_renew_timeout(monkeypatch):
    from eagleeye_pro.phase20 import scanner451 as module
    clock, budgets = [0.0], []
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    class Trickle(FakeConnection):
        calls = 0
        def settimeout(self, timeout):
            budgets.append(timeout)
        def recv(self, size):
            self.calls += 1
            clock[0] += 6
            return super().recv(1)
    connection = Trickle(version())
    scanner = ClamdScanner451("fixture", timeout=10)
    monkeypatch.setattr(scanner, "_connect", lambda *a: connection)
    with pytest.raises(ScanWithheld451) as caught:
        scanner.scan(b"benign")
    assert caught.value.quarantine_metadata["reason"] == "scanner_unavailable_or_unqualified"
    assert connection.calls == 2
    assert budgets[-1] == 4
    assert connection.sent == b"zVERSION\0"


def test_scanner_version_and_stream_share_one_deadline(monkeypatch):
    from eagleeye_pro.phase20 import scanner451 as module
    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    class Version(FakeConnection):
        def recv(self, size):
            clock[0] += 4
            return super().recv(size)
    class Stream(FakeConnection):
        def sendall(self, data):
            super().sendall(data)
            clock[0] += 2 if data == b"zINSTREAM\0" else 4
    connection = Stream(b"stream: OK\0")
    connections = iter([Version(version()), connection])
    scanner = ClamdScanner451("fixture", timeout=10)
    monkeypatch.setattr(scanner, "_connect", lambda *a: next(connections))
    with pytest.raises(ScanWithheld451) as caught:
        scanner.scan(b"benign")
    assert caught.value.quarantine_metadata["reason"] == "scanner_unavailable_or_unqualified"
    assert connection.reply == b"stream: OK\0"  # no verdict read after expiry
    assert not connection.sent.endswith(b"\0\0\0\0")  # no additional frame
