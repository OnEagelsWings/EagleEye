"""Single-page public web capture (HTML, text or PDF) with WARC preservation.

Security model (explicit user action, one URL at a time):
* only http/https on the default ports, no credentials in URLs;
* every resolved address must be globally routable; the TCP connection is pinned to a
  validated address so a second DNS answer cannot redirect it (DNS rebinding);
* redirects to the same server are followed a few times and recorded; a redirect to a
  different server is never followed automatically, the target is shown to the user;
* bounded size (also after decompression), time and content types.

The received bytes are stored unchanged as a WARC/1.1 file (request + response per
fetch). Extracted text is material to review, never a confirmed statement.
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
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol, Sequence
from urllib.parse import quote, unquote, urlencode, urljoin, urlsplit, urlunsplit

USER_AGENT = "EagleEye/492 (authorized public-source research; single page capture)"
MAX_BODY = 3 * 1024 * 1024          # HTML / text, also after decompression
MAX_PDF = 12 * 1024 * 1024          # same bound as the Build-458 document import
MAX_FETCH = MAX_PDF
MAX_ADDRESSES = 4
MAX_SAME_HOST_HOPS = 3
MAX_CONFIRMED_HOPS = 3
ACCEPT = "text/html,application/xhtml+xml;q=0.9,application/pdf;q=0.8,text/plain;q=0.5"
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
    fetched_at: str = ""

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
    """Direct, address-pinned GET. No proxy, no cookies, no redirects.

    Every resolved address is validated first; they are then tried in order until one
    accepts the connection (e.g. unreachable IPv6 falls back to IPv4).
    """

    connection_classes = {"http": _PinnedHTTPConnection, "https": _PinnedHTTPSConnection}

    def __init__(self, resolver: Callable[[str], Sequence[str]] | None = None) -> None:
        self.resolver = resolver

    def get(self, url: str, *, accept: str) -> HttpResult:
        parts = urlsplit(url)
        host = parts.hostname or ""
        addresses = public_addresses(host, self.resolver)
        cls = self.connection_classes[parts.scheme]
        target = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
        headers = [("Host", parts.netloc), ("User-Agent", USER_AGENT), ("Accept", accept),
                   ("Accept-Encoding", "identity"), ("Connection", "close")]
        conn, used = None, ""
        for ip in addresses[:MAX_ADDRESSES]:
            candidate = cls(host, ip, port=parts.port, timeout=TIMEOUT)
            try:
                candidate.connect()
            except (OSError, ssl.SSLError):
                candidate.close()
                continue
            conn, used = candidate, ip
            break
        if conn is None:
            raise CaptureError("Die Seite war nicht erreichbar oder die TLS-Prüfung schlug fehl.")
        try:
            conn.putrequest("GET", target, skip_host=True, skip_accept_encoding=True)
            for key, value in headers:
                conn.putheader(key, value)
            conn.endheaders()
            response = conn.getresponse()
            body = response.read(MAX_FETCH + 1)
            return HttpResult(url=url, status=response.status, reason=response.reason or "",
                              headers=list(response.getheaders()), body=body, ip_address=used,
                              request_headers=headers, fetched_at=_now())
        except (OSError, http.client.HTTPException, ssl.SSLError):
            raise CaptureError("Die Verbindung zur Seite wurde unterbrochen.") from None
        finally:
            conn.close()


def content_type(result: HttpResult) -> str:
    return result.header("Content-Type").split(";", 1)[0].strip().casefold()


def decoded_body(result: HttpResult, limit: int) -> bytes:
    """Undo gzip/deflate transfer coding with a hard output limit (decompression bombs)."""
    encoding = result.header("Content-Encoding").strip().casefold()
    if encoding in ("", "identity"):
        return result.body
    if encoding in ("gzip", "x-gzip"):
        modes = (31,)
    elif encoding == "deflate":
        modes = (15, -15)  # zlib-wrapped, then raw deflate as sent by some servers
    else:
        raise CaptureError("Die Seite wurde mit einem nicht unterstützten Verfahren komprimiert (" + encoding[:20] + ").")
    for wbits in modes:
        try:
            engine = zlib.decompressobj(wbits)
            out = engine.decompress(result.body, limit + 1)
        except zlib.error:
            continue
        if len(out) > limit or engine.unconsumed_tail:
            raise CaptureError("Der entpackte Inhalt ist zu groß und wird nicht gesichert.")
        return out
    raise CaptureError("Die komprimierte Antwort der Seite ist beschädigt.")


_META_CHARSET = re.compile(rb"""<meta[^>]{0,200}?charset\s*=\s*["']?\s*([A-Za-z0-9_.:-]{2,40})""", re.I)
# Only encodings that actually occur on the web; exotic guesses garble short texts.
_DETECTABLE = ["cp1252", "cp1251", "cp1250", "iso8859_15", "iso8859_2", "koi8_r", "cp1253", "cp1254",
               "cp1255", "cp1256", "cp1257", "shift_jis", "euc_jp", "gb18030", "big5", "euc_kr"]
_BOMS = ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16"))


def decode_text(body: bytes, header_value: str = "") -> tuple[str, str]:
    """Return (text, how). Order: BOM, HTTP header, <meta charset>, UTF-8, detection."""
    for mark, name in _BOMS:
        if body.startswith(mark):
            try:
                return body.decode(name), "BOM"
            except UnicodeError:
                break
    candidates = []
    match = re.search(r"charset=\s*[\"']?([\w.:-]+)", header_value or "", re.I)
    if match:
        candidates.append((match.group(1), "HTTP-Header"))
    meta = _META_CHARSET.search(body[:4096])
    if meta:
        candidates.append((meta.group(1).decode("ascii", "replace"), "Meta-Angabe der Seite"))
    candidates.append(("utf-8", "UTF-8"))
    for name, how in candidates:
        try:
            return body.decode(name), how + " (" + name.lower() + ")"
        except (UnicodeError, LookupError):
            continue
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(body, cp_isolation=_DETECTABLE).best()
        if best is not None:
            return str(best), "automatisch erkannt (" + str(best.encoding) + ")"
    except Exception:  # detection is best effort only
        pass
    return body.decode("cp1252", errors="replace"), "Ersatz (windows-1252)"


def _host_key(url: str) -> str:
    host = (urlsplit(url).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def resolve_redirect(base: str, location: str) -> tuple[str, str]:
    """Return (absolute public target, problem). Relative targets are resolved against base."""
    if not location:
        return "", "Die Seite nennt kein Weiterleitungsziel."
    try:
        return normalize_public_url(urljoin(base, location.strip())), ""
    except CaptureError as exc:
        return "", str(exc)


def _records(results) -> list[HttpResult]:
    return [results] if isinstance(results, HttpResult) else list(results)


def build_warc(results, *, captured_at: str, note: str) -> bytes:
    """WARC/1.1 with a request/response pair per fetch (redirect hops first, final last)."""
    from warcio.statusandheaders import StatusAndHeaders
    from warcio.warcwriter import WARCWriter

    out = io.BytesIO()
    writer = WARCWriter(out, gzip=True, warc_version="1.1")
    info = writer.create_warcinfo_record("eagleeye-capture.warc.gz", {
        "software": "EagleEye Build 492 (warcio)", "format": "WARC File Format 1.1",
        "description": note[:900], "robots": "not-evaluated-single-user-capture"})
    writer.write_record(info)
    for result in _records(results):
        warc_date = (result.fetched_at or captured_at).replace("+00:00", "Z")
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


def read_warc_responses(warc: bytes) -> list[tuple[str, int, bytes]]:
    from warcio.archiveiterator import ArchiveIterator

    found = []
    for record in ArchiveIterator(io.BytesIO(warc)):
        if record.rec_type == "response":
            # raw_stream: the payload exactly as received. content_stream() would undo gzip
            # and the stored hash of the original bytes could never be verified.
            found.append((record.rec_headers.get_header("WARC-Target-URI"),
                          int(record.http_headers.get_statuscode()), record.raw_stream.read()))
    return found


def read_warc_response(warc: bytes) -> tuple[str, int, bytes]:
    """Replay check: (url, status, payload) of the final stored response."""
    found = read_warc_responses(warc)
    if not found:
        raise CaptureError("WARC enthält keine Antwort.")
    return found[-1]


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


def pdf_metadata(raw: bytes, url: str) -> dict:
    """Title, author and creation date as stated by the PDF itself (unverified)."""
    name = unquote(urlsplit(url).path.rsplit("/", 1)[-1]) or (urlsplit(url).hostname or "PDF")
    meta = {"title": name[:300], "author": "", "published": "", "sitename": urlsplit(url).hostname or "",
            "language": "", "canonical_url": "", "text": "", "extractor": "PDF-Original (Fundstellen aus dem PDF)"}
    try:
        import fitz
        with fitz.open(stream=raw, filetype="pdf") as doc:
            info = doc.metadata or {}
        if str(info.get("title") or "").strip():
            meta["title"] = " ".join(str(info["title"]).split())[:300]
        meta["author"] = " ".join(str(info.get("author") or "").split())[:300]
        stamp = re.match(r"D:(\d{4})(\d{2})(\d{2})", str(info.get("creationDate") or ""))
        if stamp:
            meta["published"] = "-".join(stamp.groups())
    except Exception:  # metadata is optional; the import validates the file itself
        pass
    return meta


def _snapshot_text(*, kind: str, url: str, requested: str, archive_url: str, captured_at: str,
                   result: HttpResult, body_sha: str, warc_sha: str, meta: dict, charset: str,
                   auto_hops: list[str], via: list[str]) -> bytes:
    head = [
        "Web-Beleg – ungeprüfte Extraktion (" + kind + ")",
        "Erfasste Adresse: " + url,
    ]
    if requested and requested != url:
        head.append("Angefragte Adresse: " + requested)
    if via:
        head.append("Weiterleitungskette (einzeln bestätigt): " + " → ".join(via + [requested or url]))
    if auto_hops:
        head.append("Automatisch gefolgt (gleicher Server): " + " → ".join(auto_hops + [archive_url or url]))
    if archive_url:
        head.append("Archivquelle: " + archive_url)
    head += [
        "Erfasst (UTC): " + captured_at,
        "HTTP-Status: " + str(result.status) + " · Server-IP: " + result.ip_address,
        "SHA-256 Originalantwort: " + body_sha,
        "SHA-256 WARC-Datei: " + warc_sha,
        "Extraktion: " + meta["extractor"] + " · Zeichensatz: " + charset,
        "Titel laut Seite: " + (meta["title"] or "nicht erkannt"),
        "Autor laut Seite: " + (meta["author"] or "nicht erkannt"),
        "Veröffentlichungsdatum laut Seite: " + (meta["published"] or "nicht erkannt"),
        "Website: " + (meta["sitename"] or "nicht erkannt"),
    ]
    paragraphs = [p.strip() for p in meta["text"].split("\n") if p.strip()]
    return ("\n".join(head) + "\n\n" + "\n\n".join(paragraphs) + "\n").encode("utf-8")


def capture(url: str, *, transport: Transport | None = None, archive_url: str = "",
            kind: str = "Live-Seite", via: Sequence[str] = ()) -> dict:
    """Fetch one page or PDF and return WARC bytes, the document to import and metadata.

    Redirects to the same server (including http→https and the www variant) are followed
    up to MAX_SAME_HOST_HOPS times and recorded in the WARC. A redirect to a different
    server is returned to the caller, so the user decides whether to contact that host.
    """
    requested = normalize_public_url(url)
    current = normalize_public_url(archive_url or url)
    chain = [normalize_public_url(v) for v in list(via)[:MAX_CONFIRMED_HOPS]]
    transport = transport or PinnedTransport()
    hops: list[HttpResult] = []
    while True:
        result = transport.get(current, accept=ACCEPT)
        if 300 <= result.status < 400 and result.status != 304:
            target, problem = resolve_redirect(current, result.header("Location"))
            if target and (target == current or target in [h.url for h in hops] or target in chain):
                target, problem = "", "Die Seite leitet im Kreis weiter (Weiterleitungsschleife)."
            if target and _host_key(target) == _host_key(current) and len(hops) < MAX_SAME_HOST_HOPS:
                hops.append(result)
                current = target
                continue
            return {"redirect": True, "status": result.status, "from": current,
                    "location": target or result.header("Location")[:2000],
                    "followable": bool(target) and not archive_url, "problem": problem,
                    "via": chain + [requested] if not archive_url else chain}
        break
    if result.status != 200:
        raise CaptureError(f"Die Seite antwortete mit HTTP {result.status}; es wurde nichts gespeichert.")
    ctype = content_type(result)
    is_pdf = ctype == "application/pdf" or (ctype in ("application/octet-stream", "binary/octet-stream")
                                            and result.body.startswith(b"%PDF-"))
    if not is_pdf and ctype not in TEXT_TYPES:
        raise CaptureError("Nicht unterstützter Inhaltstyp: " + (ctype or "unbekannt") + ".")
    limit = MAX_PDF if is_pdf else MAX_BODY
    if len(result.body) > limit:
        raise CaptureError(("Das PDF ist größer als 12 MB" if is_pdf else "Die Seite ist größer als 3 MB")
                           + " und wird nicht gesichert.")
    payload = decoded_body(result, limit)
    captured_at = _now()
    auto_hops = [h.url for h in hops]
    final_url = requested if archive_url else current
    note = f"{kind}: {final_url}"
    if chain:
        note += " | bestätigte Weiterleitungen: " + " -> ".join(chain + [requested])
    warc = build_warc(hops + [result], captured_at=captured_at, note=note)
    body_sha = hashlib.sha256(result.body).hexdigest()
    warc_sha = hashlib.sha256(warc).hexdigest()
    host = urlsplit(final_url).hostname or ""
    base = {"redirect": False, "url": final_url, "requested_url": requested,
            "archive_url": current if archive_url else "", "captured_at": captured_at,
            "status": result.status, "ip_address": result.ip_address, "body_sha256": body_sha,
            "warc": warc, "warc_sha256": warc_sha, "auto_hops": auto_hops, "via": chain}
    if is_pdf:
        if not payload.startswith(b"%PDF-"):
            raise CaptureError("Die Adresse liefert kein gültiges PDF; es wurde nichts gespeichert.")
        meta = pdf_metadata(payload, final_url)
        return {**base, "content_type": "application/pdf", "document": payload, "document_suffix": ".pdf",
                "title": (meta["title"] or host)[:240], "metadata": meta}
    text, charset = decode_text(payload, result.header("Content-Type"))
    if ctype in HTML_TYPES:
        meta = extract_main_text(text, final_url)
    else:
        meta = {"title": "", "author": "", "published": "", "sitename": "", "language": "",
                "canonical_url": "", "text": text, "extractor": "Klartext"}
    if len(meta["text"]) < 40:
        raise CaptureError("Auf der Seite wurde kein auswertbarer Haupttext gefunden; es wurde nichts gespeichert.")
    document = _snapshot_text(kind=kind, url=final_url, requested=requested if not archive_url else "",
                              archive_url=current if archive_url else "", captured_at=captured_at,
                              result=result, body_sha=body_sha, warc_sha=warc_sha, meta=meta,
                              charset=charset, auto_hops=auto_hops, via=chain)
    return {**base, "content_type": ctype, "document": document, "document_suffix": ".txt",
            "title": (meta["title"] or host)[:240], "metadata": meta}


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
        rows = json.loads(decoded_body(result, MAX_BODY).decode("utf-8") or "[]")
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
