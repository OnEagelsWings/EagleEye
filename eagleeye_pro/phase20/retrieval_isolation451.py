"""Build 451 foundation: disposable retrieval process, not an OS sandbox.

The existing task/GO, robots, DNS and review contracts remain in the parent.
Only bounded public GET requests and responses cross this process boundary.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

from eagleeye.crawler.engine import FetchResponse, USER_AGENT
from eagleeye_pro.phase19.surface_retrieval441 import MAX_BYTES_HARD, MAX_TIMEOUT_HARD


class ContentQuarantined451(ValueError):
    """Response rejected before it can enter acquisition/evidence intake."""

    def __init__(self, body, media_type):
        super().__init__("executable/archive response quarantined")
        self.quarantine_metadata = {
            "policy": "retrieval451.content-risk.v1",
            "reason": "executable_or_archive",
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes_count": len(body),
            "media_type": media_type,
            "raw_payload_stored": False,
            "malware_scan_performed": False,
        }


def validate_request451(request):
    if not isinstance(request, dict) or set(request) != {
        "url", "resolved_ips", "method", "headers", "timeout_seconds", "max_bytes"
    }:
        raise ValueError("unexpected retrieval request fields")
    parsed = urlsplit(request["url"])
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in {None, 80, 443}):
        raise PermissionError("invalid public retrieval URL")
    if request.get("method") != "GET":
        raise PermissionError("retrieval worker is GET-only")
    ips = request.get("resolved_ips")
    if not isinstance(ips, list) or not 1 <= len(ips) <= 16:
        raise PermissionError("bounded pinned public IPs required")
    if any(not ipaddress.ip_address(address).is_global for address in ips):
        raise PermissionError("non-public retrieval IP forbidden")
    if not 1 <= request["max_bytes"] <= MAX_BYTES_HARD:
        raise ValueError("invalid retrieval byte budget")
    if not 1 <= request["timeout_seconds"] <= MAX_TIMEOUT_HARD:
        raise ValueError("invalid retrieval timeout")
    forbidden = {"authorization", "proxy-authorization", "cookie", "set-cookie",
                 "host", "origin", "referer"}
    if any(str(key).casefold() in forbidden for key in request.get("headers", {})):
        raise PermissionError("credentials/session headers forbidden")
    allowed = {"user-agent", "accept", "accept-language", "if-none-match", "if-modified-since"}
    headers = request["headers"]
    if not isinstance(headers, dict) or any(
        not isinstance(key, str) or key.casefold() not in allowed
        or not isinstance(value, str) or len(value) > 4096
        or "\r" in value or "\n" in value
        for key, value in headers.items()
    ):
        raise PermissionError("only bounded public retrieval headers allowed")
    if any(key.casefold() == "user-agent" and value != USER_AGENT
           for key, value in headers.items()):
        raise PermissionError("only the fixed crawler user agent allowed")


def worker_environment451():
    # Windows needs its OS directory for native runtime/TLS initialization.
    # Do not inherit PATH, PYTHONPATH, user directories, proxies or secrets.
    if os.name == "nt":
        root = os.environ.get("SystemRoot")
        if not root:
            raise RuntimeError("Windows SystemRoot unavailable")
        return {"SystemRoot": root}
    return {}


def inspect_response451(body, headers):
    """Conservative executable/archive gate; does not claim malware detection."""
    normalized = {str(key).lower(): value for key, value in headers.items()}
    media = str(normalized.get("content-type", "")).split(";", 1)[0].strip().lower()
    blocked = {"application/x-msdownload", "application/x-dosexec",
               "application/x-executable", "application/x-sharedlib",
               "application/zip", "application/x-7z-compressed",
               "application/x-rar-compressed"}
    if media in blocked or body.startswith((b"MZ", b"\x7fELF", b"PK\x03\x04",
                                           b"7z\xbc\xaf\x27\x1c", b"Rar!")):
        raise ContentQuarantined451(body, media)


class ProcessSurfaceTransport451:
    transport_kind = "surface451_disposable_process_pinned_get"
    externally_configured = True
    requires_resolved_ips = True

    def probe(self):
        """Offline startup check; neither contacts sources nor grants a GO."""
        worker = Path(__file__).with_name("retrieval_worker451.py")
        with tempfile.TemporaryDirectory(prefix="eagleeye-probe451-") as workdir:
            result = subprocess.run(
                [sys.executable, "-I", str(worker), "--probe"],
                capture_output=True, cwd=workdir, env=worker_environment451(),
                close_fds=True, timeout=10, check=False,
            )
        if result.returncode or len(result.stdout) > 1024:
            raise RuntimeError("retrieval worker startup check failed")
        report = json.loads(result.stdout)
        if report.get("protocol") != "retrieval451.v1" or report.get("pid") == os.getpid():
            raise RuntimeError("retrieval worker startup protocol mismatch")
        return report

    def fetch(self, url, *, resolved_ips, method="GET", headers=None,
              timeout_seconds=20, max_bytes=1_000_000):
        request = {"url": url, "resolved_ips": list(resolved_ips), "method": method,
                   "headers": dict(headers or {}), "timeout_seconds": int(timeout_seconds),
                   "max_bytes": int(max_bytes)}
        validate_request451(request)
        payload = json.dumps(request).encode("utf-8")
        if len(payload) > 32_768:
            raise ValueError("retrieval request exceeds IPC budget")
        worker = Path(__file__).with_name("retrieval_worker451.py")
        # -I disables user site/PYTHONPATH. No inherited secrets or proxy settings.
        # A disposable cwd is separation of process state, not filesystem isolation.
        with tempfile.TemporaryDirectory(prefix="eagleeye-retrieval451-") as workdir:
            try:
                result = subprocess.run(
                    [sys.executable, "-I", str(worker)], input=payload,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=workdir, env=worker_environment451(), close_fds=True,
                    timeout=request["timeout_seconds"] + 5, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError("retrieval worker exceeded wall-clock budget") from exc
        if result.returncode != 0:
            raise RuntimeError("retrieval worker failed; response withheld")
        if len(result.stdout) > MAX_BYTES_HARD * 2 + 65_536:
            raise ValueError("retrieval response exceeds IPC budget")
        response = json.loads(result.stdout)
        if not isinstance(response, dict) or set(response) != {
            "url", "status", "headers", "body", "elapsed_ms"
        }:
            raise ValueError("unexpected retrieval response fields")
        if response["url"] != url:
            raise ValueError("retrieval response URL mismatch")
        if type(response["status"]) is not int or not 100 <= response["status"] <= 599:
            raise ValueError("invalid retrieval HTTP status")
        if type(response["elapsed_ms"]) is not int or response["elapsed_ms"] < 0:
            raise ValueError("invalid retrieval elapsed time")
        response_headers = response["headers"]
        if not isinstance(response_headers, dict) or len(response_headers) > 100:
            raise ValueError("invalid retrieval headers")
        if any(not isinstance(key, str) or not isinstance(value, str)
               or len(key) > 256 or len(value) > 8192
               for key, value in response_headers.items()):
            raise ValueError("invalid retrieval header value")
        body = base64.b64decode(response["body"], validate=True)
        if len(body) > max_bytes:
            raise ValueError("retrieval response exceeds byte budget")
        inspect_response451(body, response["headers"])
        return FetchResponse(url, int(response["status"]), response["headers"],
                             body, int(response["elapsed_ms"]))
