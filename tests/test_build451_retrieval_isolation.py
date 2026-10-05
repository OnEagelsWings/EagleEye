import base64
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from eagleeye_pro.phase20 import retrieval_isolation451 as module


def request(**changes):
    value = dict(url="https://example.org/", resolved_ips=["93.184.216.34"],
                 method="GET", headers={}, timeout_seconds=1, max_bytes=100)
    value.update(changes)
    return value


@pytest.mark.parametrize("changes", [
    {"resolved_ips": ["127.0.0.1"]}, {"resolved_ips": ["169.254.169.254"]},
    {"resolved_ips": ["::1"]}, {"resolved_ips": []}, {"method": "POST"},
    {"url": "https://user:password@example.org/"},
    {"headers": {"Authorization": "secret"}}, {"headers": {"Cookie": "secret"}},
    {"max_bytes": 0}, {"timeout_seconds": 31},
])
def test_request_rejected_before_process_or_network(changes, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid request spawned a retrieval process")
    monkeypatch.setattr(module.subprocess, "run", forbidden)
    with pytest.raises((PermissionError, ValueError)):
        module.ProcessSurfaceTransport451().fetch(**request(**changes))


def test_actual_worker_rejects_private_request_without_contacting_network(tmp_path):
    worker = Path(module.__file__).with_name("retrieval_worker451.py")
    result = subprocess.run([sys.executable, "-I", str(worker)],
                            input=json.dumps(request(resolved_ips=["127.0.0.1"])).encode(),
                            capture_output=True, env=module.worker_environment451(),
                            cwd=tmp_path, timeout=10)
    assert result.returncode == 1
    assert result.stdout == result.stderr == b""


def test_response_and_process_boundary(monkeypatch):
    monkeypatch.setenv("EAGLEEYE_SECRET", "must-not-reach-worker")
    def run(args, **kwargs):
        assert args[1] == "-I"
        assert kwargs["env"] == module.worker_environment451()
        assert "EAGLEEYE_SECRET" not in kwargs["env"]
        assert kwargs["close_fds"] is True
        assert Path(kwargs["cwd"]).is_dir()
        payload = json.loads(kwargs["input"])
        assert set(payload) == set(request())
        result = dict(url=payload["url"], status=200, headers={"content-type": "text/plain"},
                      body=base64.b64encode(b"public source").decode(), elapsed_ms=5)
        return subprocess.CompletedProcess(args, 0, json.dumps(result).encode(), b"")
    monkeypatch.setattr(module.subprocess, "run", run)
    response = module.ProcessSurfaceTransport451().fetch(**request())
    assert response.body == b"public source"


@pytest.mark.parametrize("body,media", [
    (b"MZmalware", "text/plain"), (b"\x7fELF", "text/html"),
    (b"PK\x03\x04", "application/pdf"), (b"content", "application/x-msdownload"),
])
def test_mislabelled_risky_content_is_withheld(body, media):
    with pytest.raises(module.ContentQuarantined451):
        module.inspect_response451(body, {"content-type": media})


def test_worker_timeout_is_fail_closed(monkeypatch):
    def run(args, **kwargs):
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])
    monkeypatch.setattr(module.subprocess, "run", run)
    with pytest.raises(TimeoutError):
        module.ProcessSurfaceTransport451().fetch(**request())


@pytest.mark.parametrize("failure", ["worker_exit", "wrong_url", "oversize", "executable"])
def test_worker_failure_or_untrusted_response_never_reaches_intake(monkeypatch, failure):
    def run(args, **kwargs):
        result = dict(url="https://example.org/", status=200,
                      headers={"content-type": "text/plain"}, elapsed_ms=0,
                      body=base64.b64encode(b"safe").decode())
        if failure == "worker_exit":
            return subprocess.CompletedProcess(args, 1, b"", b"untrusted content")
        if failure == "wrong_url":
            result["url"] = "https://another.example/"
        if failure == "oversize":
            result["body"] = base64.b64encode(b"x" * 101).decode()
        if failure == "executable":
            result["body"] = base64.b64encode(b"MZhidden executable").decode()
        return subprocess.CompletedProcess(args, 0, json.dumps(result).encode(), b"")
    monkeypatch.setattr(module.subprocess, "run", run)
    with pytest.raises((RuntimeError, ValueError)):
        module.ProcessSurfaceTransport451().fetch(**request())


def test_actual_worker_startup_without_environment_secrets(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "https://proxy.invalid/")
    monkeypatch.setenv("EAGLEEYE_SECRET", "private-value")
    report = module.ProcessSurfaceTransport451().probe()
    assert report["protocol"] == "retrieval451.v1"
    assert report["pid"] != os.getpid()
    assert report["external_network_contacted"] is False
    assert set(module.worker_environment451()) <= {"SystemRoot"}


@pytest.mark.parametrize("changes", [
    {"headers": {"X-Api-Key": "secret"}},
    {"headers": {"Accept": "text/plain\r\nAuthorization: secret"}},
    {"headers": {"Accept": "x" * 4097}},
    {"case_id": "not-for-worker"}, {"session_token": "not-for-worker"},
])
def test_worker_rejects_credentials_and_unknown_fields(changes):
    with pytest.raises((ValueError, PermissionError)):
        module.validate_request451(request(**changes))


@pytest.mark.parametrize("changes", [
    {"status": 700}, {"status": "200"}, {"elapsed_ms": -1},
    {"headers": {"Content-Type": ["text/plain"]}},
    {"unexpected": "field"},
])
def test_parent_rejects_invalid_worker_protocol(monkeypatch, changes):
    def run(args, **kwargs):
        response = dict(url="https://example.org/", status=200,
                        headers={"content-type": "text/plain"}, elapsed_ms=0,
                        body=base64.b64encode(b"safe").decode())
        response.update(changes)
        return subprocess.CompletedProcess(args, 0, json.dumps(response).encode(), b"")
    monkeypatch.setattr(module.subprocess, "run", run)
    with pytest.raises(ValueError):
        module.ProcessSurfaceTransport451().fetch(**request())


def test_content_gate_is_case_insensitive_for_mime():
    with pytest.raises(module.ContentQuarantined451):
        module.inspect_response451(b"hidden", {"Content-Type": "APPLICATION/X-MSDOWNLOAD"})


def test_quarantine_blocks_content_and_persists_failure_in_acquisition(tmp_path, monkeypatch):
    from eagleeye_pro.core.app_context import AppContext
    from test_build441_integrated import ident, case, source_and_task, resolver

    def run(args, **kwargs):
        payload = json.loads(kwargs["input"])
        body = (b"User-agent: *\nAllow: /\n" if payload["url"].endswith("/robots.txt")
                else b"MZunsafe source content")
        response = dict(url=payload["url"], status=200,
                        headers={"content-type": "text/plain"}, elapsed_ms=1,
                        body=base64.b64encode(body).decode())
        return subprocess.CompletedProcess(args, 0, json.dumps(response).encode(), b"")
    monkeypatch.setattr(module.subprocess, "run", run)
    with AppContext(base_dir=tmp_path) as ctx:
        identity = ident(ctx)
        case_id = case(ctx, "Quarantine 451")["case_id"]
        _, task, _ = source_and_task(ctx, identity, case_id, suffix="quarantine451")
        with pytest.raises(RuntimeError, match="ContentQuarantined451"):
            ctx.surface_retrieval_441.execute_replay(
                identity=identity, task_id=task["task_id"],
                transport=module.ProcessSurfaceTransport451(), resolver=resolver,
            )
        assert ctx.crawler_core_425.get(task["task_id"])["state"] == "failed"
        rows = ctx.surface_retrieval_441.case_runs(case_id)
        assert rows[-1]["state"] == "failed"
        assert rows[-1]["error_class"] == "ContentQuarantined451"
        event = ctx.acquisition_events_422.get(rows[-1]["event_id"])
        quarantine = event["provenance"]["content_quarantine"]
        assert quarantine["reason"] == "executable_or_archive"
        assert quarantine["raw_payload_stored"] is False
        assert quarantine["malware_scan_performed"] is False
        assert ctx.db.one("SELECT COUNT(*) n FROM content_observation_423 WHERE case_id=?",
                          (case_id,))["n"] == 0
    with AppContext(base_dir=tmp_path) as reopened:
        persisted = reopened.surface_retrieval_441.case_runs(case_id)[-1]
        assert persisted["state"] == "failed"
        assert reopened.acquisition_events_422.get(persisted["event_id"])["provenance"]["content_quarantine"] == quarantine


def test_all_public_phase20_live_entrypoints_choose_process_transport():
    # Inspect the real call arguments, not an unrelated status flag.
    import ast
    root = Path(module.__file__).parents[2]
    expected = {
        "phase19/surface_retrieval441.py": {"execute_live", "execute_authorized_loop_task"},
        "phase20/surface_hardening442.py": {"execute_live", "execute_authorized_loop_task", "validate_external_task"},
        "phase20/news_acquisition443.py": {"execute_live"},
        "phase20/social_acquisition444.py": {"execute_live"},
    }
    for filename, names in expected.items():
        tree = ast.parse((root / "eagleeye_pro" / filename).read_text())
        methods = {node.name: node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef) and node.name in names}
        assert set(methods) == names
        for method in methods.values():
            transports = [keyword.value for call in ast.walk(method)
                          if isinstance(call, ast.Call) for keyword in call.keywords
                          if keyword.arg == "transport"]
            assert len(transports) == 1
            assert isinstance(transports[0], ast.Call)
            assert isinstance(transports[0].func, ast.Name)
            assert transports[0].func.id == "ProcessSurfaceTransport451"
