"""Single-page public web capture with WARC preservation and main-text extraction.

Security model (explicit user action, one URL at a time):
* only http/https on the default ports, no credentials in URLs;
* every resolved address must be globally routable; the TCP connection is pinned to
  the validated address so a second DNS answer cannot redirect it (DNS rebinding);
* redirects are never followed automatically, the target is shown to the user;
* bounded size, time and content types; ``Accept-Encoding: identity``.

The captured bytes are stored unchanged as a WARC/1.1 file (request + response).
Trafilatura output is an extraction to review, never a confirmed statement.
"""
from __future__ import annotations

import hashlib
import http.client
import io
import ipaddress
import json
import re
import socket
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol, Sequence
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

USER_AGENT = "EagleEye/492 (authorized public-source research; single page capture)"
MAX_BODY = 3 * 1024 * 1024
TIMEOUT = 15
HTML_TYPES = ("text/html", "application/xhtml+xml")
TEXT_TYPES = HTML_TYPES + ("text/plain",)
WAYBACK_HOST = "web.archive.org"
_TIMESTAMP = re.compile(r"^\d{14}$")


class CaptureError(ValueError):
    """User-facing, non-sensitive capture failure."""


@dataclass
class HttpResult:
    url: str
    status: int
    reason: str
    headers: list[tuple[str, str]]
    body: bytes
    ip_address: str
    request_headers: list[tuple[str, str]] = field(default_factory=list)

    def header(self, name: str) -> str:
        name = name.casefold()
        return next((v for k, v in self.headers if k.casefold() == name), "")


class Transport(Protocol):
    def get(self, url: str, *, accept: str) -> HttpResult: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_public_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw or len(raw) > 2000 or any(ch.isspace() or ord(ch) < 32 for ch in raw):
        raise CaptureError("Bitte eine vollständige öffentliche Adresse (http/https) eingeben.")
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
    host = parts.hostname.rstrip(".").casefold()
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global or literal.is_multicast:
            raise CaptureError("Die Adresse zeigt auf ein nicht-öffentliches Netz und wird nicht abgerufen.")
        host_part = f"[{literal}]" if literal.version == 6 else str(literal)
    else:
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            raise CaptureError("Ungültiger Hostname.") from None
        if host in ("localhost",) or host.endswith((".local", ".internal", ".localhost", ".onion")):
            raise CaptureError("Interne oder anonymisierte Adressen werden hier nicht abgerufen.")
        host_part = host
    netloc = host_part if port is None else f"{host_part}:{port}"
    return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))


def public_addresses(host: str, resolver: Callable[[str], Sequence[str]] | None = None) -> list[str]:
    try:
        literal = ipaddress.ip_address(host)
        candidates = [str(literal)]
    except ValueError:
        if resolver is not None:
            candidates = list(resolver(host))
        else:
            try:
                infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            except socket.gaierror:
                raise CaptureError("Der Hostname konnte nicht aufgelöst werden.") from None
            candidates = [info[4][0] for info in infos]
    if not candidates:
        raise CaptureError("Der Hostname konnte nicht aufgelöst werden.")
    clean = []
    for candidate in candidates:
        ip = ipaddress.ip_address(candidate.split("%", 1)[0])
        if not ip.is_global or ip.is_multicast:
            raise CaptureError("Die Adresse zeigt auf ein nicht-öffentliches Netz und wird nicht abgerufen.")
        clean.append(str(ip))
    return list(dict.fromkeys(clean))


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, ip, **kw):
        super().__init__(host, **kw)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, ip, **kw):
        super().__init__(host, context=ssl.create_default_context(), **kw)
        self._ip = ip

    def connect(self):
        raw = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


class PinnedTransport:
    """Direct, address-pinned GET. No proxy, no cookies, no redirects."""

    def __init__(self, resolver: Callable[[str], Sequence[str]] | None = None) -> None:
        self.resolver = resolver

    def get(self, url: str, *, accept: str) -> HttpResult:
        parts = urlsplit(url)
        host = parts.hostname or ""
        ip = public_addresses(host, self.resolver)[0]
        cls = _PinnedHTTPSConnection if parts.scheme == "https" else _PinnedHTTPConnection
        conn = cls(host, ip, port=parts.port, timeout=TIMEOUT)
        target = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
        headers = [("Host", parts.netloc), ("User-Agent", USER_AGENT), ("Accept", accept),
                   ("Accept-Encoding", "identity"), ("Connection", "close")]
        try:
            conn.putrequest("GET", target, skip_host=True, skip_accept_encoding=True)
            for key, value in headers:
                conn.putheader(key, value)
            conn.endheaders()
            response = conn.getresponse()
            body = response.read(MAX_BODY + 1)
            result = HttpResult(url=url, status=response.status, reason=response.reason or "",
                                headers=list(response.getheaders()), body=body, ip_address=ip,
                                request_headers=headers)
        except (OSError, http.client.HTTPException, ssl.SSLError):
            raise CaptureError("Die Seite war nicht erreichbar oder die TLS-Prüfung schlug fehl.") from None
        finally:
            conn.close()
        return result


def _check_response(result: HttpResult, allowed_types: tuple[str, ...]) -> str:
    if len(result.body) > MAX_BODY:
        raise CaptureError("Die Seite ist größer als 3 MB und wird nicht gesichert.")
    if result.header("Content-Encoding").strip().casefold() not in ("", "identity"):
        raise CaptureError("Die Seite wurde komprimiert geliefert; bitte später erneut versuchen.")
    ctype = result.header("Content-Type").split(";", 1)[0].strip().casefold()
    if ctype not in allowed_types:
        raise CaptureError("Nicht unterstützter Inhaltstyp: " + (ctype or "unbekannt") + ".")
    return ctype


def _charset(result: HttpResult) -> str:
    match = re.search(r"charset=([\w.-]+)", result.header("Content-Type"), re.I)
    if match:
        try:
            "".encode(match.group(1))
            return match.group(1)
        except LookupError:
            pass
    return "utf-8"


def build_warc(result: HttpResult, *, captured_at: str, note: str) -> bytes:
    from warcio.statusandheaders import StatusAndHeaders
    from warcio.warcwriter import WARCWriter

    out = io.BytesIO()
    writer = WARCWriter(out, gzip=True, warc_version="1.1")
    warc_date = captured_at.replace("+00:00", "Z")
    info = writer.create_warcinfo_record("eagleeye-capture.warc.gz", {
        "software": "EagleEye Build 492 (warcio)", "format": "WARC File Format 1.1",
        "description": note[:500], "robots": "not-evaluated-single-user-capture"})
    writer.write_record(info)
    parts = urlsplit(result.url)
    target = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
    req_headers = StatusAndHeaders("GET " + target + " HTTP/1.1", result.request_headers, is_http_request=True)
    request = writer.create_warc_record(result.url, "request", http_headers=req_headers,
        warc_headers_dict={"WARC-Date": warc_date, "WARC-IP-Address": result.ip_address})
    proto = f"{result.status} {result.reason}".strip()
    resp_headers = StatusAndHeaders(proto, result.headers, protocol="HTTP/1.1")
    response = writer.create_warc_record(result.url, "response", payload=io.BytesIO(result.body),
        length=len(result.body), http_headers=resp_headers,
        warc_headers_dict={"WARC-Date": warc_date, "WARC-IP-Address": result.ip_address})
    writer.write_record(response)
    request.rec_headers.replace_header("WARC-Concurrent-To", response.rec_headers.get_header("WARC-Record-ID"))
    writer.write_record(request)
    return out.getvalue()


def read_warc_response(warc: bytes) -> tuple[str, int, bytes]:
    """Replay check: return (url, status, payload) of the stored response record."""
    from warcio.archiveiterator import ArchiveIterator

    for record in ArchiveIterator(io.BytesIO(warc)):
        if record.rec_type == "response":
            status = int(record.http_headers.get_statuscode())
            return record.rec_headers.get_header("WARC-Target-URI"), status, record.content_stream().read()
    raise CaptureError("WARC enthält keine Antwort.")


def extract_main_text(html: str, url: str) -> dict:
    import trafilatura

    doc = trafilatura.bare_extraction(html, url=url, with_metadata=True, include_comments=False,
                                      include_tables=True, favor_precision=True)
    data = doc.as_dict() if doc is not None and hasattr(doc, "as_dict") else (doc or {})
    text = str(data.get("text") or "").strip()
    return {
        "title": str(data.get("title") or "").strip()[:300],
        "author": str(data.get("author") or "").strip()[:300],
        "published": str(data.get("date") or "").strip()[:40],
        "sitename": str(data.get("sitename") or "").strip()[:200],
        "language": str(data.get("language") or "").strip()[:20],
        "canonical_url": str(data.get("url") or "").strip()[:2000],
        "text": text,
        "extractor": "trafilatura " + getattr(trafilatura, "__version__", "?"),
    }


def _snapshot_text(*, kind: str, url: str, archive_url: str, captured_at: str, result: HttpResult,
                   body_sha: str, warc_sha: str, meta: dict) -> bytes:
    head = [
        "Web-Beleg – ungeprüfte Extraktion (" + kind + ")",
        "Erfasste Adresse: " + url,
    ]
    if archive_url:
        head.append("Archivquelle: " + archive_url)
    head += [
        "Erfasst (UTC): " + captured_at,
        "HTTP-Status: " + str(result.status) + " · Server-IP: " + result.ip_address,
        "SHA-256 Originalantwort: " + body_sha,
        "SHA-256 WARC-Datei: " + warc_sha,
        "Extraktion: " + meta["extractor"],
        "Titel laut Seite: " + (meta["title"] or "nicht erkannt"),
        "Autor laut Seite: " + (meta["author"] or "nicht erkannt"),
        "Veröffentlichungsdatum laut Seite: " + (meta["published"] or "nicht erkannt"),
        "Website: " + (meta["sitename"] or "nicht erkannt"),
    ]
    paragraphs = [p.strip() for p in meta["text"].split("\n") if p.strip()]
    return ("\n".join(head) + "\n\n" + "\n\n".join(paragraphs) + "\n").encode("utf-8")


def capture(url: str, *, transport: Transport | None = None, archive_url: str = "", kind: str = "Live-Seite") -> dict:
    """Fetch one page and return WARC bytes, extracted text document and metadata."""
    clean = normalize_public_url(archive_url or url)
    result = (transport or PinnedTransport()).get(clean, accept="text/html,application/xhtml+xml;q=0.9,text/plain;q=0.5")
    if 300 <= result.status < 400:
        location = result.header("Location")
        return {"redirect": True, "status": result.status, "location": location[:2000]}
    if result.status != 200:
        raise CaptureError(f"Die Seite antwortete mit HTTP {result.status}; es wurde nichts gespeichert.")
    ctype = _check_response(result, TEXT_TYPES)
    captured_at = _now()
    original = normalize_public_url(url)
    warc = build_warc(result, captured_at=captured_at, note=f"{kind}: {original}")
    body_sha = hashlib.sha256(result.body).hexdigest()
    warc_sha = hashlib.sha256(warc).hexdigest()
    html = result.body.decode(_charset(result), errors="replace")
    if ctype in HTML_TYPES:
        meta = extract_main_text(html, original)
    else:
        meta = {"title": "", "author": "", "published": "", "sitename": "", "language": "",
                "canonical_url": "", "text": html, "extractor": "plain text"}
    if len(meta["text"]) < 40:
        raise CaptureError("Auf der Seite wurde kein auswertbarer Haupttext gefunden; es wurde nichts gespeichert.")
    document = _snapshot_text(kind=kind, url=original, archive_url=clean if archive_url else "",
                              captured_at=captured_at, result=result, body_sha=body_sha,
                              warc_sha=warc_sha, meta=meta)
    host = urlsplit(original).hostname or ""
    return {"redirect": False, "url": original, "archive_url": clean if archive_url else "",
            "captured_at": captured_at, "status": result.status, "ip_address": result.ip_address,
            "content_type": ctype, "body_sha256": body_sha, "warc": warc, "warc_sha256": warc_sha,
            "document": document, "title": (meta["title"] or host)[:240], "metadata": meta}


def wayback_snapshots(url: str, *, transport: Transport | None = None, limit: int = 30) -> list[dict]:
    """List distinct archived versions (by content digest) from the Wayback CDX API."""
    original = normalize_public_url(url)
    query = urlencode({"url": original, "output": "json", "limit": str(max(1, min(limit, 50))),
                       "fl": "timestamp,original,statuscode,mimetype,digest",
                       "filter": "statuscode:200", "collapse": "digest"})
    result = (transport or PinnedTransport()).get(f"https://{WAYBACK_HOST}/cdx/search/cdx?{query}",
                                                  accept="application/json")
    if result.status != 200:
        raise CaptureError(f"Das Internet Archive antwortete mit HTTP {result.status}.")
    if len(result.body) > MAX_BODY:
        raise CaptureError("Antwort des Internet Archive zu groß.")
    try:
        rows = json.loads(result.body.decode("utf-8") or "[]")
    except (UnicodeError, ValueError):
        raise CaptureError("Unerwartete Antwort des Internet Archive.") from None
    if not isinstance(rows, list):
        raise CaptureError("Unerwartete Antwort des Internet Archive.")
    out = []
    for row in rows[1:] if rows and rows[0] and rows[0][0] == "timestamp" else rows:
        if not (isinstance(row, list) and len(row) >= 5 and _TIMESTAMP.match(str(row[0]))):
            continue
        ts = str(row[0])
        out.append({"timestamp": ts, "original": str(row[1])[:2000], "mimetype": str(row[3])[:80],
                    "digest": str(row[4])[:64],
                    "label": f"{ts[6:8]}.{ts[4:6]}.{ts[0:4]} {ts[8:10]}:{ts[10:12]} UTC"})
    return out


def wayback_raw_url(timestamp: str, original: str) -> str:
    if not _TIMESTAMP.match(str(timestamp or "")):
        raise CaptureError("Ungültiger Archivzeitpunkt.")
    clean = normalize_public_url(original)
    return f"https://{WAYBACK_HOST}/web/{timestamp}id_/" + quote(clean, safe=":/?&=%#+,;@")
