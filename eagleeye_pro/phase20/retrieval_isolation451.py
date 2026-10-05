"""Build 451 foundation: disposable retrieval process, not an OS sandbox.

The existing task/GO, robots, DNS and review contracts remain in the parent.
Only bounded public GET requests and responses cross this process boundary.
"""
from __future__ import annotations

import base64
import ipaddress
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

from eagleeye.crawler.engine import FetchResponse
from eagleeye_pro.phase19.surface_retrieval441 import MAX_BYTES_HARD, MAX_TIMEOUT_HARD


class ContentQuarantined451(ValueError):
    """Response rejected before it can enter acquisition/evidence intake."""


def validate_request451(request):
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


def inspect_response451(body, headers):
    """Conservative executable/archive gate; does not claim malware detection."""
    media = str(headers.get("content-type", "")).split(";", 1)[0].strip().lower()
    blocked = {"application/x-msdownload", "application/x-dosexec",
               "application/x-executable", "application/x-sharedlib",
               "application/zip", "application/x-7z-compressed",
               "application/x-rar-compressed"}
    if media in blocked or body.startswith((b"MZ", b"\x7fELF", b"PK\x03\x04",
                                           b"7z\xbc\xaf\x27\x1c", b"Rar!")):
        raise ContentQuarantined451("executable/archive response quarantined")


class ProcessSurfaceTransport451:
    transport_kind = "surface451_disposable_process_pinned_get"
    externally_configured = True
    requires_resolved_ips = True

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
                    cwd=workdir, env={}, close_fds=True,
                    timeout=request["timeout_seconds"] + 5, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError("retrieval worker exceeded wall-clock budget") from exc
        if result.returncode != 0:
            raise RuntimeError("retrieval worker failed; response withheld")
        if len(result.stdout) > MAX_BYTES_HARD * 2 + 65_536:
            raise ValueError("retrieval response exceeds IPC budget")
        response = json.loads(result.stdout)
        if response["url"] != url:
            raise ValueError("retrieval response URL mismatch")
        body = base64.b64decode(response["body"], validate=True)
        if len(body) > max_bytes:
            raise ValueError("retrieval response exceeds byte budget")
        inspect_response451(body, response["headers"])
        return FetchResponse(url, int(response["status"]), response["headers"],
                             body, int(response["elapsed_ms"]))
