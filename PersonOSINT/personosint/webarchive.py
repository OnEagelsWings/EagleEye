"""Web-Belege im Archivstandard: WARC-Aufzeichnung, Wiedergabeprüfung, Haupttext und Wayback-Fassungen.

Übernommen aus EagleEye Build 492 (Chat „SpiderFoot Reverse Engineering“, Tool-Auswahl A2/A3) und an die
OPSEC-Regeln von PersonOSINT angepasst: Der Abruf selbst läuft immer über den Netzausgang des Falls
(``evidence.capture``); dieses Modul verarbeitet nur die bereits abgerufene Antwort.

* **WARC 1.1** (warcio): Anfrage und Antwort mit allen Kopfzeilen – das Format der Web-Archive.
* **Haupttext** (trafilatura): Artikeltext ohne Menü/Werbung, dazu Titel, Autor und Datum *laut Seite*.
  Das ist eine Extraktion zur Prüfung, keine bestätigte Aussage.
"""
from __future__ import annotations

import html as html_mod
import io
import json
import re
from typing import Any
from urllib.parse import quote, urlencode, urlsplit

WAYBACK_HOST = "web.archive.org"
_TIMESTAMP = re.compile(r"^\d{14}$")


class ArchiveError(ValueError):
    """Für Nutzer lesbarer Fehler ohne interne Details."""


def available() -> dict[str, str]:
    """Welche Bausteine sind installiert? (leer = fehlt)"""
    out = {"warc": "", "haupttext": ""}
    try:
        import warcio

        out["warc"] = "warcio " + str(getattr(warcio, "__version__", "") or "installiert")
    except Exception:  # noqa: BLE001
        pass
    try:
        import trafilatura

        out["haupttext"] = "trafilatura " + str(getattr(trafilatura, "__version__", "") or "installiert")
    except Exception:  # noqa: BLE001
        pass
    return out


# --------------------------------------------------------------------------- WARC

def build_warc(*, url: str, status: int, reason: str, headers: list[tuple[str, str]], body: bytes,
               request_headers: list[tuple[str, str]], captured_at: str, note: str, software: str) -> bytes:
    """Schreibt Anfrage und Antwort unverändert als WARC/1.1 (gzip)."""
    from warcio.statusandheaders import StatusAndHeaders
    from warcio.warcwriter import WARCWriter

    out = io.BytesIO()
    writer = WARCWriter(out, gzip=True, warc_version="1.1")
    warc_date = captured_at.replace("+00:00", "Z")
    writer.write_record(writer.create_warcinfo_record("eagleeye-beleg.warc.gz", {
        "software": software, "format": "WARC File Format 1.1", "description": note[:500],
        "robots": "nicht ausgewertet (Einzelabruf durch Analyst)"}))
    parts = urlsplit(url)
    target = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
    # Übertragungs-Kopfzeilen entfallen: der gespeicherte Körper ist bereits zusammengesetzt und ungekürzt lesbar
    clean = [(k, v) for k, v in headers if k.casefold() not in {"transfer-encoding", "content-length", "connection"}]
    clean.append(("Content-Length", str(len(body))))
    resp_headers = StatusAndHeaders(f"{status} {reason}".strip(), clean, protocol="HTTP/1.1")
    response = writer.create_warc_record(url, "response", payload=io.BytesIO(body), length=len(body), http_headers=resp_headers,
                                         warc_headers_dict={"WARC-Date": warc_date})
    writer.write_record(response)
    req = [("Host", parts.netloc)] + [(k, v) for k, v in request_headers if k.casefold() != "host"]
    request = writer.create_warc_record(url, "request", http_headers=StatusAndHeaders("GET " + target + " HTTP/1.1", req, is_http_request=True),
                                        warc_headers_dict={"WARC-Date": warc_date,
                                                           "WARC-Concurrent-To": response.rec_headers.get_header("WARC-Record-ID")})
    writer.write_record(request)
    return out.getvalue()


def read_warc_response(warc: bytes) -> tuple[str, int, bytes]:
    """Wiedergabeprüfung: liefert (Adresse, HTTP-Status, Körper) der gespeicherten Antwort."""
    from warcio.archiveiterator import ArchiveIterator

    for record in ArchiveIterator(io.BytesIO(warc)):
        if record.rec_type == "response":
            return record.rec_headers.get_header("WARC-Target-URI"), int(record.http_headers.get_statuscode()), record.content_stream().read()
    raise ArchiveError("WARC enthält keine Antwort.")


# --------------------------------------------------------------------------- Haupttext

def _fallback_text(text: str) -> dict[str, Any]:
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    title = html_mod.unescape(re.sub(r"\s+", " ", m.group(1)).strip())[:300] if m else ""
    body = re.sub(r"(?is)<(script|style|noscript|nav|header|footer)[^>]*>.*?</\1>", " ", text)
    body = html_mod.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))).strip()
    return {"title": title, "author": "", "published": "", "sitename": "", "language": "", "canonical_url": "", "text": body,
            "extractor": "einfach (ohne trafilatura)"}


def extract_main_text(page: str, url: str) -> dict[str, Any]:
    """Haupttext und Angaben laut Seite. Ohne trafilatura: einfache Textextraktion."""
    try:
        import trafilatura
    except Exception:  # noqa: BLE001 - Baustein nicht installiert
        return _fallback_text(page)
    try:
        doc = trafilatura.bare_extraction(page, url=url, with_metadata=True, include_comments=False, include_tables=True, favor_precision=True)
    except Exception:  # noqa: BLE001 - defektes HTML darf die Sicherung nicht verhindern
        doc = None
    data = doc.as_dict() if doc is not None and hasattr(doc, "as_dict") else (doc or {})
    text = str(data.get("text") or "").strip()
    if len(text) < 40:
        fb = _fallback_text(page)
        fb["extractor"] = "einfach (kein Haupttext erkannt)"
        return fb
    return {"title": str(data.get("title") or "").strip()[:300], "author": str(data.get("author") or "").strip()[:300],
            "published": str(data.get("date") or "").strip()[:40], "sitename": str(data.get("sitename") or "").strip()[:200],
            "language": str(data.get("language") or "").strip()[:20], "canonical_url": str(data.get("url") or "").strip()[:2000],
            "text": text, "extractor": "trafilatura " + str(getattr(trafilatura, "__version__", "?"))}


# --------------------------------------------------------------------------- Wayback (Internet Archive)

def wayback_snapshots(http: Any, url: str, limit: int = 30) -> list[dict[str, str]]:
    """Unterschiedliche archivierte Fassungen (nach Inhalts-Prüfsumme) aus der CDX-Schnittstelle."""
    query = urlencode({"url": url, "output": "json", "limit": str(max(1, min(limit, 50))), "fl": "timestamp,original,statuscode,mimetype,digest",
                       "filter": "statuscode:200", "collapse": "digest"})
    resp = http.get(f"https://{WAYBACK_HOST}/cdx/search/cdx?{query}")
    if resp.status != 200:
        raise ArchiveError(f"Das Internet Archive antwortete mit HTTP {resp.status}.")
    try:
        rows = json.loads(resp.body.decode("utf-8") or "[]")
    except (UnicodeError, ValueError):
        raise ArchiveError("Unerwartete Antwort des Internet Archive.") from None
    if not isinstance(rows, list):
        raise ArchiveError("Unerwartete Antwort des Internet Archive.")
    out = []
    for row in rows[1:] if rows and rows[0] and rows[0][0] == "timestamp" else rows:
        if not (isinstance(row, list) and len(row) >= 5 and _TIMESTAMP.match(str(row[0]))):
            continue
        ts = str(row[0])
        out.append({"timestamp": ts, "original": str(row[1])[:2000], "mimetype": str(row[3])[:80], "digest": str(row[4])[:64],
                    "label": f"{ts[6:8]}.{ts[4:6]}.{ts[0:4]} {ts[8:10]}:{ts[10:12]} UTC"})
    return out


def wayback_raw_url(timestamp: str, original: str) -> str:
    """Adresse der unveränderten Archivfassung (``id_`` = ohne Wayback-Banner und Link-Umschreibung)."""
    if not _TIMESTAMP.match(str(timestamp or "")):
        raise ArchiveError("Ungültiger Archivzeitpunkt.")
    return f"https://{WAYBACK_HOST}/web/{timestamp}id_/" + quote(original, safe=":/?&=%#+,;@")
