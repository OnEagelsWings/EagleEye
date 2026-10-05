import base64
import json
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
                            capture_output=True, env={}, cwd=tmp_path, timeout=10)
    assert result.returncode == 1
    assert result.stdout == result.stderr == b""


def test_response_and_process_boundary(monkeypatch):
    monkeypatch.setenv("EAGLEEYE_SECRET", "must-not-reach-worker")
    def run(args, **kwargs):
        assert args[1] == "-I"
        assert kwargs["env"] == {}
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
