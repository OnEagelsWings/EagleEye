"""Read-only access to onion services through a Tor service running on this computer.

- Only v3 onion addresses whose built-in checksum is correct are accepted.
- The connection goes exclusively to a local Tor SOCKS port (127.0.0.1 / ::1). The onion name is
  handed to Tor (SOCKS5 "domain" request); nothing is resolved locally.
- Every case gets its own Tor circuit: the SOCKS username/password is a per-case isolation token
  (Tor's IsolateSOCKSAuth, on by default). Tor is never configured or controlled from here.
- Only GET, no cookies, no referrer, no credentials; responses are size-limited. Images and other
  media are never requested: the evidence pipeline only accepts text pages.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import ipaddress
import socket
import ssl
import struct
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from eagleeye.application.intel492.webcapture import CaptureError, HttpResult

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0"  # Tor Browser's common value
DEFAULT_PORT = 9050          # Tor service; Tor Browser listens on 9150
TIMEOUT = 60                 # onion services are slow
MAX_BYTES = 3 * 1024 * 1024
ACCEPT = "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.5"


def onion_v3_valid(host: str) -> bool:
    """True for a syntactically and cryptographically valid v3 onion host (56 chars + .onion).

    Checksum per rend-spec-v3: base32(pubkey(32) | checksum(2) | version(1)),
    checksum = SHA3-256(".onion checksum" | pubkey | version)[:2], version = 3.
    """
    host = str(host or "").strip().lower().rstrip(".")
    if not host.endswith(".onion"):
        return False
    label = host[: -len(".onion")].rsplit(".", 1)[-1]  # subdomains of an onion are allowed
    if len(label) != 56:
        return False
    try:
        raw = base64.b32decode(label.upper())
    except (ValueError, base64.binascii.Error):
        return False
    pubkey, checksum, version = raw[:32], raw[32:34], raw[34]
    if version != 3:
        return False
    return hashlib.sha3_256(b".onion checksum" + pubkey + bytes([version])).digest()[:2] == checksum


def onion_host_of(value: str) -> str:
    """The onion host of a URL or bare address, lower-case; '' when it is not a valid v3 onion."""
    raw = str(value or "").strip()
    if "://" not in raw:
        raw = "http://" + raw
    try:
        host = (urlsplit(raw).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""
    return host if onion_v3_valid(host) else ""


def normalize_onion_url(value: str) -> str:
    """Absolute http(s) URL of a v3 onion service, without credentials, fragment or odd ports."""
    raw = str(value or "").strip()
    if not raw or len(raw) > 2000 or any(ch.isspace() or ord(ch) < 32 for ch in raw):
        raise CaptureError("Bitte eine vollständige Onion-Adresse eingeben (http://…onion/…).")
    if "://" not in raw:
        raw = "http://" + raw
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise CaptureError("Nur http- und https-Adressen sind erlaubt.")
    if parts.username or parts.password:
        raise CaptureError("Adressen mit Zugangsdaten werden nicht abgerufen.")
    try:
        port = parts.port
    except ValueError:
        raise CaptureError("Ungültiger Port in der Adresse.") from None
    if port not in (None, 80, 443):
        raise CaptureError("Nur die Standardports 80 und 443 sind erlaubt.")
    host = parts.hostname.lower().rstrip(".")
    if not onion_v3_valid(host):
        raise CaptureError("Keine gültige v3-Onion-Adresse (56 Zeichen + .onion, Prüfsumme stimmt nicht).")
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))


def _read_exact(sock: socket.socket, n: int) -> bytes:
    out = bytearray()
    while len(out) < n:
        chunk = sock.recv(n - len(out))
        if not chunk:
            raise ConnectionError("Der Tor-Dienst hat die Verbindung geschlossen.")
        out.extend(chunk)
    return bytes(out)


SOCKS_ERRORS = {1: "allgemeiner Fehler", 2: "nicht erlaubt", 3: "Netz nicht erreichbar", 4: "Onion-Dienst nicht erreichbar",
                5: "Verbindung abgelehnt", 6: "Zeitüberschreitung im Tor-Netz", 7: "Befehl nicht unterstützt",
                8: "Adresstyp nicht unterstützt"}


class TorTransport:
    """webcapture.Transport over a local Tor SOCKS5 port, with one Tor circuit per isolation key."""

    def __init__(self, *, socks_host: str = "127.0.0.1", socks_port: int = DEFAULT_PORT, isolation: str,
                 timeout: float = TIMEOUT, max_bytes: int = MAX_BYTES) -> None:
        try:
            ip = ipaddress.ip_address(str(socks_host).strip())
        except ValueError:
            raise ValueError("Der Tor-Dienst muss als IP-Adresse dieses Rechners angegeben werden (127.0.0.1).") from None
        if not ip.is_loopback:
            raise ValueError("Der Tor-Dienst muss auf diesem Rechner laufen (127.0.0.1).")
        if not 1 <= int(socks_port) <= 65535:
            raise ValueError("Ungültiger Port für den Tor-Dienst.")
        token = str(isolation or "").encode("utf-8")
        if not 1 <= len(token) <= 255:
            raise ValueError("Für jede Recherche wird ein eigener Isolationsschlüssel benötigt.")
        self.socks = (str(ip), int(socks_port))
        self.token = token
        self.timeout = float(timeout)
        self.max_bytes = int(max_bytes)

    def _connect(self, host: str, port: int) -> socket.socket:
        try:
            sock = socket.create_connection(self.socks, timeout=min(self.timeout, 15))
        except OSError:
            raise CaptureError(f"Der Tor-Dienst antwortet nicht auf {self.socks[0]}:{self.socks[1]}. Läuft Tor bzw. der Tor Browser?") from None
        sock.settimeout(self.timeout)
        try:
            sock.sendall(b"\x05\x01\x02")  # SOCKS5, offer only username/password (= circuit isolation)
            ver, method = _read_exact(sock, 2)
            if ver != 5 or method != 2:
                raise CaptureError("Der Dienst auf diesem Port ist kein Tor-SOCKS-Port mit Verbindungstrennung.")
            sock.sendall(b"\x01" + bytes([len(self.token)]) + self.token + b"\x01x")
            if _read_exact(sock, 2)[1] != 0:
                raise CaptureError("Der Tor-Dienst hat die Verbindungstrennung abgelehnt.")
            name = host.encode("ascii")
            sock.sendall(b"\x05\x01\x00\x03" + bytes([len(name)]) + name + struct.pack("!H", port))
            head = _read_exact(sock, 4)
            if head[1] != 0:
                raise CaptureError("Tor konnte den Onion-Dienst nicht erreichen (" + SOCKS_ERRORS.get(head[1], f"Code {head[1]}") + ").")
            _read_exact(sock, {1: 4, 4: 16}.get(head[3], 0) or _read_exact(sock, 1)[0])
            _read_exact(sock, 2)
            return sock
        except (OSError, ValueError) as exc:
            sock.close()
            if isinstance(exc, CaptureError):
                raise
            raise CaptureError("Verbindung über Tor fehlgeschlagen: " + (str(exc)[:120] or type(exc).__name__)) from None
        except BaseException:
            sock.close()
            raise

    def get(self, url: str, *, accept: str = ACCEPT) -> HttpResult:
        clean = normalize_onion_url(url)
        parts = urlsplit(clean)
        host = parts.hostname or ""
        port = parts.port or (443 if parts.scheme == "https" else 80)
        path = (parts.path or "/") + ("?" + parts.query if parts.query else "")
        request_headers = [("Host", host if parts.port is None else f"{host}:{port}"), ("User-Agent", USER_AGENT),
                           ("Accept", accept), ("Accept-Language", "en-US,en;q=0.5"), ("Connection", "close")]
        started = time.monotonic()
        raw = self._connect(host, port)
        stream = raw
        try:
            if parts.scheme == "https":
                stream = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
            stream.sendall(("GET " + path + " HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in request_headers)
                            + "\r\n").encode("ascii"))
            response = http.client.HTTPResponse(stream)
            response.begin()
            body = response.read(self.max_bytes + 1)
            if len(body) > self.max_bytes:
                raise CaptureError("Die Seite ist größer als 3 MB und wird nicht gesichert.")
            return HttpResult(url=clean, status=int(response.status), reason=str(response.reason or ""),
                              headers=[(str(k), str(v)) for k, v in response.getheaders()], body=body,
                              ip_address="Tor (" + str(round(time.monotonic() - started, 1)) + " s)",
                              request_headers=request_headers,
                              fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        except (OSError, http.client.HTTPException) as exc:
            raise CaptureError("Abruf über Tor abgebrochen: " + (str(exc)[:120] or type(exc).__name__)) from None
        finally:
            for s in {id(stream): stream, id(raw): raw}.values():
                try:
                    s.close()
                except OSError:
                    pass


def probe(socks_host: str = "127.0.0.1", socks_port: int = DEFAULT_PORT) -> dict:
    """Is a Tor SOCKS port listening here and does it accept circuit isolation? (no network request)"""
    try:
        sock = socket.create_connection((socks_host, int(socks_port)), timeout=5)
    except OSError:
        return {"ok": False, "detail": f"Auf {socks_host}:{socks_port} läuft kein Tor-Dienst."}
    try:
        sock.settimeout(5)
        sock.sendall(b"\x05\x01\x02")
        reply = _read_exact(sock, 2)
        if reply != b"\x05\x02":
            return {"ok": False, "detail": "Der Dienst auf diesem Port ist kein Tor-SOCKS-Port."}
        return {"ok": True, "detail": f"Tor-Dienst auf {socks_host}:{socks_port} gefunden."}
    except (OSError, ConnectionError):
        return {"ok": False, "detail": "Der Dienst auf diesem Port antwortet nicht wie Tor."}
    finally:
        sock.close()
