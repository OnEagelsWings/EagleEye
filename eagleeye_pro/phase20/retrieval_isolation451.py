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
import ssl
import socket
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

from eagleeye.crawler.engine import FetchResponse, USER_AGENT
from eagleeye_pro.phase19.surface_retrieval441 import MAX_BYTES_HARD, MAX_TIMEOUT_HARD


def remaining_seconds451(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("retrieval exceeded shared wall-clock budget")
    return remaining


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
               "application/x-rar-compressed", "application/vnd.rar",
               "application/gzip", "application/x-gzip", "application/x-tar",
               "application/x-gtar", "application/x-bzip", "application/x-bzip2",
               "application/x-xz", "application/zstd", "application/x-zstd",
               "application/x-compress", "application/x-lzip", "application/x-cpio",
               "application/x-archive", "application/vnd.ms-cab-compressed",
               "application/x-iso9660-image"}
    signatures = (b"MZ", b"\x7fELF", b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08",
                  b"7z\xbc\xaf\x27\x1c", b"Rar!", b"\x1f\x8b", b"\x1f\x9d",
                  b"BZh", b"\xfd7zXZ\x00", b"\x28\xb5\x2f\xfd", b"LZIP",
                  b"MSCF", b"!<arch>\n", b"070701", b"070702", b"070707")
    # POSIX tar identifies itself at byte 257, not at the start of the payload.
    tar = len(body) >= 512 and body[257:262] == b"ustar"
    # Older tar formats have no magic; recognize their checksummed header.
    if len(body) >= 512 and not tar:
        checksum = body[148:156].strip(b"\x00 ")
        if checksum and all(byte in b"01234567" for byte in checksum):
            expected = sum(body[:148]) + 8 * ord(" ") + sum(body[156:512])
            tar = int(checksum, 8) == expected
    iso = len(body) >= 32774 and body[32769:32774] == b"CD001"
    if media in blocked or body.startswith(signatures) or tar or iso:
        raise ContentQuarantined451(body, media)


def worker_error_category451(exc):
    """Fixed IPC categories only: never transmit exception text or source data."""
    if isinstance(exc, ssl.SSLCertVerificationError):
        return "tls_certificate"
    if isinstance(exc, (PermissionError, ValueError)):
        return "invalid_request"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, ConnectionError):
        return "connection"
    if isinstance(exc, OSError):
        return "os_error"
    return "worker_failure"


def raise_worker_error451(result):
    if result.returncode != 1 or len(result.stdout) > 1024:
        raise RuntimeError("retrieval worker failed; response withheld")
    try:
        response = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise RuntimeError("retrieval worker failed; response withheld") from None
    if not isinstance(response, dict) or set(response) != {"error"}:
        raise RuntimeError("retrieval worker failure protocol invalid")
    category = response["error"]
    if category == "tls_certificate":
        raise ssl.SSLCertVerificationError("retrieval worker TLS certificate rejected")
    if category == "timeout":
        raise TimeoutError("retrieval worker network timeout")
    if category == "connection":
        raise ConnectionError("retrieval worker connection failure")
    if category == "os_error":
        raise OSError("retrieval worker network OS failure")
    # Invalid requests, protocol errors and all unknown categories are nonretryable.
    raise RuntimeError("retrieval worker failed; response withheld")


class ProcessSurfaceTransport451:
    transport_kind = "surface451_disposable_process_pinned_get"
    externally_configured = True
    requires_resolved_ips = True

    def __init__(self, *, profile=None, scanner=None):
        self.profile = profile or os.environ.get("EAGLEEYE_RETRIEVAL_PROFILE", "process")
        if self.profile not in {"process", "contained"}:
            raise RuntimeError("unknown retrieval isolation profile")
        scanner_path = os.environ.get("EAGLEEYE_CLAMD_SOCKET", "")
        if scanner is None and scanner_path:
            from .scanner451 import ClamdScanner451
            scanner = ClamdScanner451(scanner_path)
        self.scanner = scanner
        self.last_scan = None
        self.security_report = {}
        if self.profile == "contained":
            self.transport_kind = "surface451_kernel_contained_pinned_get"

    def containment_probe(self, *, timeout_seconds=10):
        worker = Path(__file__).with_name("retrieval_worker451.py")
        result = subprocess.run([sys.executable, "-I", str(worker), "--containment-probe"],
                                capture_output=True, env=worker_environment451(),
                                close_fds=True, timeout=timeout_seconds, check=False)
        if result.returncode or len(result.stdout) > 4096:
            raise RuntimeError("retrieval kernel containment unavailable")
        report = json.loads(result.stdout)
        if not all(report.get("denied", {}).get(key) is True for key in
                   ("file_read", "file_write", "new_socket", "new_process")):
            raise RuntimeError("retrieval containment probe invalid")
        return report

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
        self.last_scan = None
        self.security_report = {}
        request = {"url": url, "resolved_ips": list(resolved_ips), "method": method,
                   "headers": dict(headers or {}), "timeout_seconds": int(timeout_seconds),
                   "max_bytes": int(max_bytes)}
        validate_request451(request)
        payload = json.dumps(request).encode("utf-8")
        if len(payload) > 32_768:
            raise ValueError("retrieval request exceeds IPC budget")
        worker = Path(__file__).with_name("retrieval_worker451.py")
        connected = None
        options = {}
        command = [sys.executable, "-I", str(worker)]
        deadline = None
        if self.profile == "contained":
            # Qualify confinement BEFORE opening any source connection.
            deadline = time.monotonic() + request["timeout_seconds"]
            self.containment_probe(timeout_seconds=min(10, remaining_seconds451(deadline)))
            if self.scanner is None:
                raise RuntimeError("contained retrieval requires a configured malware scanner")
            parsed = urlsplit(url)
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            last_error = None
            for address in request["resolved_ips"]:
                remaining = remaining_seconds451(deadline)
                try:
                    connected = socket.create_connection((address, port), remaining)
                    break
                except OSError as exc:
                    last_error = exc
            if connected is None:
                raise last_error or ConnectionError("pinned connection unavailable")
            options["pass_fds"] = (connected.fileno(),)
            command += ["--connected-fd", str(connected.fileno())]
        # -I disables user site/PYTHONPATH. No inherited secrets or proxy settings.
        # A disposable cwd is separation of process state, not filesystem isolation.
        with tempfile.TemporaryDirectory(prefix="eagleeye-retrieval451-") as workdir:
            try:
                result = subprocess.run(
                    command, input=payload,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=workdir, env=worker_environment451(), close_fds=True,
                    timeout=(remaining_seconds451(deadline) if deadline is not None
                             else request["timeout_seconds"] + 5), check=False, **options,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError("retrieval worker exceeded wall-clock budget") from exc
            finally:
                if connected is not None:
                    connected.close()
        if result.returncode != 0:
            raise_worker_error451(result)
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
        self.last_scan = self.scanner.scan(body) if self.scanner is not None else None
        self.security_report = {"profile": self.profile, "kernel_contained": self.profile == "contained",
                                "content_sha256": hashlib.sha256(body).hexdigest(),
                                "scanner": self.last_scan, "content_risk_gate_pass": True}
        return FetchResponse(url, int(response["status"]), response["headers"],
                             body, int(response["elapsed_ms"]))
