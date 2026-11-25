"""Beweissicherung: Fundstellen über den OPSEC-Netzausgang abrufen, verschlüsselt archivieren,
mit SHA-256 versiegeln und als prüfbares Beweispaket exportieren.

Seit Version 1.5 (Zusammenführung mit Build 492): jede Web-Sicherung wird zusätzlich als **WARC**
(Archivstandard, Anfrage + Antwort mit Kopfzeilen) abgelegt, der **Haupttext** der Seite wird ohne
Menü/Werbung extrahiert, und **frühere Fassungen** aus dem Internet Archive lassen sich gezielt sichern.
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

from . import webarchive
from .db import now_iso

MAX_BYTES = 2_000_000  # entspricht dem Lese-Limit des HTTP-Clients
KINDS = {"web": "Webseite", "archiv": "Archivfassung", "dokument": "Dokument"}


class EvidenceError(Exception):
    pass


def check_target(url: str, resolve: bool = True) -> str:
    """Schutz vor Missbrauch des Servers (SSRF): nur öffentliche http(s)-Ziele."""
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise EvidenceError("Nur http(s)-Adressen können gesichert werden.")
    from .opsec import is_internal_host

    if is_internal_host(parts.hostname, resolve):
        raise EvidenceError("Interne Adressen können nicht gesichert werden.")
    return url.strip()


def _extract(content: bytes) -> tuple[str, str, str]:
    """Titel, Textauszug und Dateityp aus dem Abruf."""
    head = content[:2048].lstrip().lower()
    if head.startswith((b"<!doctype html", b"<html")) or b"<html" in head:
        text = content.decode("utf-8", "replace")
        m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
        title = html.unescape(re.sub(r"\s+", " ", m.group(1)).strip())[:300] if m else ""
        body = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", text)
        body = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))).strip()
        return title, body[:1500], "text/html"
    if head.startswith((b"{", b"[")):
        return "", content[:1500].decode("utf-8", "replace"), "application/json"
    if head.startswith(b"%pdf"):
        return "", "", "application/pdf"
    try:
        return "", content[:1500].decode("utf-8"), "text/plain"
    except UnicodeDecodeError:
        return "", "", "application/octet-stream"


def _charset(headers: list[tuple[str, str]]) -> str:
    ctype = next((v for k, v in headers if k.casefold() == "content-type"), "")
    m = re.search(r"charset=([\w.-]+)", ctype, re.I)
    if m:
        try:
            "".encode(m.group(1))
            return m.group(1)
        except LookupError:
            pass
    return "utf-8"


def _csv_safe(value: Any) -> Any:
    """Tabellenkalkulationen werten =, +, -, @ am Zellanfang als Formel – entschärfen."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


EXT = {"text/html": ".html", "application/json": ".json", "application/pdf": ".pdf", "text/plain": ".txt",
       "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx", "image/png": ".png", "image/jpeg": ".jpg",
       "image/tiff": ".tif", "message/rfc822": ".eml"}


def _folder(p) -> Path:
    folder = Path(p.data_dir) / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def capture(p, case_id: int, url: str, finding_id: int | None = None, fact_id: int | None = None, note: str = "",
            wayback_timestamp: str = "") -> dict[str, Any]:
    """Sichert eine Seite (oder mit ``wayback_timestamp`` eine frühere Fassung aus dem Internet Archive)."""
    from . import __version__
    from .service import current_user
    from .sources import SourceError

    case = p.get_case(case_id)
    prof = p.case_profile(case)
    url = check_target(url, resolve=prof.kind == "direkt")  # mit Proxy löst der Proxy auf – keine lokale DNS-Spur
    http = p.case_http(case).for_source("beweissicherung")  # OPSEC: Ausgang des Falls, fail closed, protokolliert
    kind = "web"
    fetch_url = url
    if wayback_timestamp:
        try:
            fetch_url = webarchive.wayback_raw_url(wayback_timestamp, url)
        except webarchive.ArchiveError as exc:
            raise EvidenceError(str(exc)) from exc
        kind = "archiv"
    try:
        resp = http.get(fetch_url)
    except SourceError as exc:
        raise EvidenceError(f"Abruf fehlgeschlagen: {exc}") from exc
    if kind == "archiv" and resp.status != 200:
        raise EvidenceError(f"Das Internet Archive antwortete mit HTTP {resp.status}; es wurde nichts gespeichert.")
    content = resp.body
    digest = hashlib.sha256(content).hexdigest()
    title, excerpt, ctype = _extract(content)
    captured_at = now_iso()
    meta: dict[str, Any] = {}
    text = ""
    if ctype == "text/html":
        found = webarchive.extract_main_text(content.decode(_charset(resp.headers), "replace"), url)
        text = found.pop("text")
        meta = {k: v for k, v in found.items() if v}
        title = found.get("title") or title
        excerpt = text[:1500] or excerpt
    elif ctype == "text/plain":
        text = content.decode(_charset(resp.headers), "replace")
    if wayback_timestamp:
        ts = wayback_timestamp
        meta["archiv_zeitpunkt"] = f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}T{ts[8:10]}:{ts[10:12]}:{ts[12:14]}Z"
    archive_url = fetch_url if kind == "archiv" else ""
    if kind == "web":
        try:
            wb = http.get("https://archive.org/wayback/available?" + urlencode({"url": url}))
            if wb.status == 200:
                snap = (wb.json().get("archived_snapshots") or {}).get("closest") or {}
                archive_url = snap.get("url", "") if snap.get("available") else ""
        except Exception:  # noqa: BLE001 - Archiv-Verweis ist optional
            archive_url = ""
    warc = b""
    try:
        warc = webarchive.build_warc(url=fetch_url, status=resp.status, reason=resp.reason or "", headers=resp.headers, body=content,
                                     request_headers=resp.request_headers, captured_at=captured_at,
                                     note=f"{KINDS[kind]}: {url} · Fall {case['reference']} · Netzausgang {http.egress}",
                                     software=f"EagleEye PersonOSINT {__version__} (warcio)")
    except ImportError:
        meta["warc_hinweis"] = "WARC nicht erstellt – Baustein warcio ist nicht installiert."
    except Exception as exc:  # noqa: BLE001 - die Sicherung selbst darf an der Archivkopie nicht scheitern
        meta["warc_hinweis"] = f"WARC nicht erstellt: {exc}"[:200]
    user = current_user.get()
    eid = p.db.insert("evidence", {
        "case_id": case_id, "finding_id": finding_id, "fact_id": fact_id, "url": url, "final_url": resp.url, "status": resp.status,
        "content_type": ctype, "size": len(content), "sha256": digest, "title": title, "excerpt": excerpt, "file": "",
        "archive_url": archive_url, "egress": http.egress, "username": user["username"] if user else "system",
        "retrieved_at": captured_at, "note": (note or "")[:500] + (" [auf 2 MB gekürzt]" if len(content) >= MAX_BYTES else ""),
        "kind": kind, "meta": meta, "warc_sha256": hashlib.sha256(warc).hexdigest() if warc else ""})
    folder = _folder(p)
    base = f"{eid}_{digest[:16]}"
    (folder / f"{base}.enc").write_bytes(p.vault.encrypt(content))
    values = {"file": f"{base}.enc"}
    if warc:
        (folder / f"{base}.warc.enc").write_bytes(p.vault.encrypt(warc))
        values["warc_file"] = f"{base}.warc.enc"
    if text.strip():
        (folder / f"{base}.txt.enc").write_bytes(p.vault.encrypt(text.encode("utf-8")))
        values["text_file"] = f"{base}.txt.enc"
    p.db.update("evidence", eid, values)
    p.log(case_id, "Beleg gesichert", f"{KINDS[kind]} {url} · HTTP {resp.status} · {len(content)} Bytes · SHA-256 {digest}"
          + (" · WARC" if warc else "") + f" · über „{http.egress}“")
    return p.db.one("SELECT * FROM evidence WHERE id = ?", (eid,))


def capture_confirmed(p, case_id: int, limit: int = 30) -> dict[str, Any]:
    rows = p.db.all("SELECT f.id, f.url FROM findings f WHERE f.case_id = ? AND f.status = 'bestätigt' AND f.url LIKE 'http%' "
                    "AND NOT EXISTS (SELECT 1 FROM evidence e WHERE e.finding_id = f.id) ORDER BY f.id LIMIT ?", (case_id, limit))
    ok, errors = 0, []
    for r in rows:
        try:
            capture(p, case_id, r["url"], finding_id=r["id"])
            ok += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{r['url']}: {exc}")
    return {"captured": ok, "errors": errors, "remaining": max(0, len(rows) - ok - len(errors))}


def wayback_versions(p, case_id: int, url: str) -> list[dict[str, str]]:
    """Frühere Fassungen einer Adresse im Internet Archive (Abfrage über den Netzausgang des Falls)."""
    from .sources import SourceError

    case = p.get_case(case_id)
    url = check_target(url, resolve=p.case_profile(case).kind == "direkt")
    http = p.case_http(case).for_source("wayback")
    try:
        return webarchive.wayback_snapshots(http, url)
    except (webarchive.ArchiveError, SourceError) as exc:
        raise EvidenceError(str(exc)) from exc


def _row(p, case_id: int, evidence_id: int) -> dict[str, Any]:
    row = p.db.one("SELECT * FROM evidence WHERE id = ? AND case_id = ?", (evidence_id, case_id))
    if not row or not row["file"]:
        from .service import NotFound
        raise NotFound("Beleg nicht gefunden.")
    return row


def content_of(p, case_id: int, evidence_id: int) -> tuple[dict[str, Any], bytes]:
    row = _row(p, case_id, evidence_id)
    data = p.vault.decrypt((_folder(p) / row["file"]).read_bytes())
    if hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise EvidenceError("Integritätsprüfung fehlgeschlagen – die gespeicherte Datei weicht vom versiegelten Hash ab.")
    return row, data


def warc_of(p, case_id: int, evidence_id: int) -> tuple[dict[str, Any], bytes]:
    row = _row(p, case_id, evidence_id)
    if not row["warc_file"]:
        raise EvidenceError("Zu diesem Beleg gibt es keine WARC-Aufzeichnung.")
    data = p.vault.decrypt((_folder(p) / row["warc_file"]).read_bytes())
    if hashlib.sha256(data).hexdigest() != row["warc_sha256"]:
        raise EvidenceError("Integritätsprüfung fehlgeschlagen – die WARC-Datei weicht vom versiegelten Hash ab.")
    return row, data


def text_pages(p, row: dict[str, Any]) -> list[dict[str, Any]]:
    """Text eines Belegs als Seitenliste. Webseiten haben eine „Seite“, Dokumente eine je Seite."""
    if not row.get("text_file"):
        return []
    try:
        raw = p.vault.decrypt((_folder(p) / row["text_file"]).read_bytes())
    except Exception:  # noqa: BLE001 - fehlende/defekte Textkopie ist kein Integritätsfehler des Originals
        return []
    if row.get("kind") == "dokument":
        try:
            return list(json.loads(raw.decode("utf-8")).get("pages") or [])
        except ValueError:
            return []
    return [{"page": 1, "text": raw.decode("utf-8", "replace"), "method": "haupttext"}]


def text_of(p, row: dict[str, Any]) -> str:
    return "\n\n".join(pg.get("text", "") for pg in text_pages(p, row)).strip()


def verify(p, case_id: int, evidence_id: int) -> dict[str, Any]:
    """Prüft Original, WARC-Datei und ob die WARC-Aufzeichnung genau das versiegelte Original wiedergibt."""
    row = _row(p, case_id, evidence_id)
    out: dict[str, Any] = {"id": evidence_id, "original": False, "warc": None, "wiedergabe": None, "message": ""}
    try:
        _, data = content_of(p, case_id, evidence_id)
        out["original"] = True
    except Exception as exc:  # noqa: BLE001
        out["message"] = str(exc)
        return out
    if row["warc_file"]:
        try:
            _, warc = warc_of(p, case_id, evidence_id)
            out["warc"] = True
            _, status, payload = webarchive.read_warc_response(warc)
            out["wiedergabe"] = status == row["status"] and hashlib.sha256(payload).hexdigest() == row["sha256"]
            if not out["wiedergabe"]:
                out["message"] = "Die WARC-Aufzeichnung gibt nicht das versiegelte Original wieder."
        except Exception as exc:  # noqa: BLE001
            out["warc"] = False
            out["message"] = str(exc)
    out["ok"] = out["original"] and out["warc"] is not False and out["wiedergabe"] is not False
    return out


def delete_files(p, row: dict[str, Any]) -> None:
    for key in ("file", "warc_file", "text_file"):
        if row.get(key):
            (_folder(p) / row[key]).unlink(missing_ok=True)


def package(p, case_id: int, export_id: str) -> bytes:
    """ZIP mit allen Belegen, WARC-Aufzeichnungen, Textfassungen, Manifest (CSV/JSON) und Prüfanleitung."""
    case = p.get_case(case_id)
    rows = p.db.all("SELECT * FROM evidence WHERE case_id = ? ORDER BY id", (case_id,))
    buf = io.BytesIO()
    manifest = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for r in rows:
            try:
                _, data = content_of(p, case_id, r["id"])
            except Exception as exc:  # noqa: BLE001
                manifest.append({"id": r["id"], "url": r["url"], "fehler": str(exc)})
                continue
            ident = f"B{r['id']:04d}"
            name = f"belege/{ident}{EXT.get(r['content_type'], '.bin')}"
            z.writestr(name, data)
            meta = r.get("meta") or {}
            entry = {"id": ident, "art": KINDS.get(r.get("kind") or "web", "Webseite"), "datei": name, "url": r["url"], "final_url": r["final_url"],
                     "http_status": r["status"], "abgerufen_utc": r["retrieved_at"], "sha256": r["sha256"], "bytes": r["size"], "titel": r["title"],
                     "autor_laut_seite": meta.get("author", ""), "datum_laut_seite": meta.get("published", ""),
                     "originaldatei": r.get("filename") or "", "warc_datei": "", "warc_sha256": "", "textfassung": "",
                     "archivkopie": r["archive_url"], "netzausgang": r["egress"], "gesichert_von": r["username"], "notiz": r["note"]}
            if r.get("warc_file"):
                try:
                    _, warc = warc_of(p, case_id, r["id"])
                    entry["warc_datei"] = f"warc/{ident}.warc.gz"
                    entry["warc_sha256"] = r["warc_sha256"]
                    z.writestr(entry["warc_datei"], warc)
                except Exception as exc:  # noqa: BLE001
                    entry["warc_datei"] = f"FEHLER: {exc}"
            text = text_of(p, r)
            if text:
                entry["textfassung"] = f"text/{ident}.txt"
                z.writestr(entry["textfassung"], text)
            manifest.append(entry)
        out = io.StringIO()
        if manifest:
            w = csv.DictWriter(out, fieldnames=list({k: None for m in manifest for k in m}), delimiter=";")
            w.writeheader()
            w.writerows([{k: _csv_safe(v) for k, v in m.items()} for m in manifest])
        z.writestr("manifest.csv", out.getvalue())
        z.writestr("manifest.json", json.dumps({"fall": case["reference"], "export_id": export_id, "erstellt": datetime.now().isoformat(timespec="seconds"),
                                                "belege": manifest}, ensure_ascii=False, indent=2))
        z.writestr("PRUEFANLEITUNG.txt", "Beweispaket EagleEye PersonOSINT\n\n"
                   f"Fall: {case['reference']} · Export-ID: {export_id}\n\n"
                   "Jede Datei im Ordner 'belege' wurde zum angegebenen Zeitpunkt (UTC) über den genannten Netzausgang abgerufen\n"
                   "bzw. als Dokument importiert und unmittelbar mit SHA-256 versiegelt. Prüfung unter Linux/macOS:  sha256sum belege/*\n"
                   "Windows (PowerShell):  Get-FileHash belege\\* -Algorithm SHA256\n"
                   "Die Werte müssen mit manifest.csv übereinstimmen. Archivkopien (Internet Archive) dienen als unabhängiger Vergleich.\n\n"
                   "Ordner 'warc': Aufzeichnung von Anfrage und Antwort im Archivstandard WARC 1.1 (ISO 28500). Die Dateien lassen sich mit\n"
                   "gängigen Werkzeugen wiedergeben (z. B. ReplayWeb.page, pywb, warcio). Der Antwort-Körper in der WARC-Datei entspricht\n"
                   "byte-genau der Datei im Ordner 'belege'.\n"
                   "Ordner 'text': automatisch extrahierter Haupttext bzw. erkannter Dokumenttext – Lesehilfe, kein Original.\n")
    return buf.getvalue()
