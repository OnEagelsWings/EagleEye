"""Bounded local ClamAV INSTREAM adapter; no shell and no payload files."""
from datetime import datetime, timezone
import hashlib
import socket
import struct
import time


class ScanWithheld451(RuntimeError):
    def __init__(self, body, reason, version=""):
        super().__init__("scanner gate withheld content")
        self.quarantine_metadata = {
            "policy": "retrieval451.scanner.v1", "reason": reason,
            "sha256": hashlib.sha256(body).hexdigest(), "bytes_count": len(body),
            "raw_payload_stored": False, "malware_scan_performed": reason == "scanner_detection",
            "scanner_version": version,
        }


class ClamdScanner451:
    def __init__(self, socket_path, *, timeout=10, max_signature_age_hours=48):
        self.socket_path = str(socket_path)
        self.timeout = timeout
        self.max_age = max_signature_age_hours

    def _remaining(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("scanner exceeded shared wall-clock budget")
        return remaining

    def _send(self, connection, payload, deadline):
        connection.settimeout(self._remaining(deadline))
        connection.sendall(payload)

    def _reply(self, connection, deadline):
        reply = bytearray()
        while len(reply) <= 4096:
            connection.settimeout(self._remaining(deadline))
            chunk = connection.recv(min(1024, 4097 - len(reply)))
            if not chunk:
                break
            reply.extend(chunk)
            if b"\0" in reply:
                return bytes(reply).split(b"\0", 1)[0].decode("ascii", errors="strict")
        raise ValueError("invalid scanner reply")

    def _connect(self, deadline):
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            connection.settimeout(self._remaining(deadline))
            connection.connect(self.socket_path)
        except Exception:
            connection.close()
            raise
        return connection

    def scan(self, body):
        version = ""
        deadline = time.monotonic() + self.timeout
        try:
            if len(body) > 2_000_000:
                raise ValueError("scanner byte budget exceeded")
            with self._connect(deadline) as connection:
                self._send(connection, b"zVERSION\0", deadline)
                version = self._reply(connection, deadline)
            # Clamd VERSION: ClamAV engine/database-version/database-date.
            parts = version.split("/", 2)
            if len(parts) != 3 or not parts[0].startswith("ClamAV ") or not parts[1].isdigit():
                raise ValueError("scanner version invalid")
            stamp = datetime.strptime(parts[2], "%a %b %d %H:%M:%S %Y").replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - stamp).total_seconds()
            if not 0 <= age <= self.max_age * 3600:
                raise ValueError("scanner signatures stale")
            with self._connect(deadline) as connection:
                self._send(connection, b"zINSTREAM\0", deadline)
                for offset in range(0, len(body), 65536):
                    chunk = body[offset:offset + 65536]
                    self._send(connection, struct.pack("!I", len(chunk)) + chunk, deadline)
                self._send(connection, struct.pack("!I", 0), deadline)
                reply = self._reply(connection, deadline)
            if reply == "stream: OK":
                return {"scanner": "clamd", "version": version, "result": "clean",
                        "sha256": hashlib.sha256(body).hexdigest()}
            if reply.startswith("stream: ") and reply.endswith(" FOUND"):
                raise ScanWithheld451(body, "scanner_detection", version)
            raise ValueError("scanner did not return clean")
        except ScanWithheld451:
            raise
        except Exception:
            raise ScanWithheld451(body, "scanner_unavailable_or_unqualified", version) from None
