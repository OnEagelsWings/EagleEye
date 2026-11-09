"""Schritt 3 – Beweissicherung: Fundstellen über den OPSEC-Netzausgang abrufen, verschlüsselt
archivieren, mit SHA-256 versiegeln und als prüfbares Beweispaket exportieren.
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import ipaddress
import json
import re
import socket
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

from .db import now_iso

MAX_BYTES = 2_000_000  # entspricht dem Lese-Limit des HTTP-Clients


class EvidenceError(Exception):
    pass


def check_target(url: str, resolve: bool = True) -> str:
    """Schutz vor Missbrauch des Servers (SSRF): nur öffentliche http(s)-Ziele."""
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise EvidenceError("Nur http(s)-Adressen können gesichert werden.")
    host = parts.hostname.lower()
    if host in {"localhost"} or host.endswith((".local", ".internal", ".localhost", ".lan")):
        raise EvidenceError("Interne Adressen können nicht gesichert werden.")
    try:
        ips = [ipaddress.ip_address(host)]
    except ValueError:
        ips = []
        if resolve:
            try:
                ips = [ipaddress.ip_address(i[4][0]) for i in socket.getaddrinfo(host, None)]
            except OSError:
                ips = []  # nicht auflösbar: der Abruf schlägt dann ohnehin fehl
    for ip in ips:
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
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


EXT = {"text/html": ".html", "application/json": ".json", "application/pdf": ".pdf", "text/plain": ".txt"}


def capture(p, case_id: int, url: str, finding_id: int | None = None, fact_id: int | None = None, note: str = "") -> dict[str, Any]:
    from .service import current_user

    case = p.get_case(case_id)
    prof = p.case_profile(case)
    url = check_target(url, resolve=prof.kind == "direkt")  # mit Proxy löst der Proxy auf – keine lokale DNS-Spur
    http = p.case_http(case).for_source("beweissicherung")  # OPSEC: Ausgang des Falls, fail closed, protokolliert
    from .sources import SourceError

    try:
        resp = http.get(url)
    except SourceError as exc:
        raise EvidenceError(f"Abruf fehlgeschlagen: {exc}") from exc
    content = resp.body
    digest = hashlib.sha256(content).hexdigest()
    title, excerpt, ctype = _extract(content)
    archive_url = ""
    try:
        wb = http.get("https://archive.org/wayback/available?" + urlencode({"url": url}))
        if wb.status == 200:
            snap = (wb.json().get("archived_snapshots") or {}).get("closest") or {}
            archive_url = snap.get("url", "") if snap.get("available") else ""
    except Exception:  # noqa: BLE001 - Archiv-Verweis ist optional
        archive_url = ""
    user = current_user.get()
    eid = p.db.insert("evidence", {
        "case_id": case_id, "finding_id": finding_id, "fact_id": fact_id, "url": url, "final_url": resp.url, "status": resp.status,
        "content_type": ctype, "size": len(content), "sha256": digest, "title": title, "excerpt": excerpt, "file": "",
        "archive_url": archive_url, "egress": http.egress, "username": user["username"] if user else "system",
        "retrieved_at": now_iso(), "note": (note or "")[:500] + (" [auf 2 MB gekürzt]" if len(content) >= MAX_BYTES else "")})
    folder = Path(p.data_dir) / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"{eid}_{digest[:16]}.enc"
    (folder / fname).write_bytes(p.vault.encrypt(content))
    p.db.update("evidence", eid, {"file": fname})
    p.log(case_id, "Beleg gesichert", f"{url} · HTTP {resp.status} · {len(content)} Bytes · SHA-256 {digest} · über „{http.egress}“")
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


def content_of(p, case_id: int, evidence_id: int) -> tuple[dict[str, Any], bytes]:
    row = p.db.one("SELECT * FROM evidence WHERE id = ? AND case_id = ?", (evidence_id, case_id))
    if not row or not row["file"]:
        from .service import NotFound
        raise NotFound("Beleg nicht gefunden.")
    data = p.vault.decrypt((Path(p.data_dir) / "evidence" / row["file"]).read_bytes())
    if hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise EvidenceError("Integritätsprüfung fehlgeschlagen – die gespeicherte Datei weicht vom versiegelten Hash ab.")
    return row, data


def package(p, case_id: int, export_id: str) -> bytes:
    """ZIP mit allen Belegen, Manifest (CSV/JSON) und Prüfanleitung."""
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
            name = f"belege/B{r['id']:04d}{EXT.get(r['content_type'], '.bin')}"
            z.writestr(name, data)
            manifest.append({"id": f"B{r['id']:04d}", "datei": name, "url": r["url"], "final_url": r["final_url"], "http_status": r["status"],
                             "abgerufen_utc": r["retrieved_at"], "sha256": r["sha256"], "bytes": r["size"], "titel": r["title"],
                             "archivkopie": r["archive_url"], "netzausgang": r["egress"], "gesichert_von": r["username"], "notiz": r["note"]})
        out = io.StringIO()
        if manifest:
            w = csv.DictWriter(out, fieldnames=list({k: None for m in manifest for k in m}), delimiter=";")
            w.writeheader()
            w.writerows(manifest)
        z.writestr("manifest.csv", out.getvalue())
        z.writestr("manifest.json", json.dumps({"fall": case["reference"], "export_id": export_id, "erstellt": datetime.now().isoformat(timespec="seconds"),
                                                "belege": manifest}, ensure_ascii=False, indent=2))
        z.writestr("PRUEFANLEITUNG.txt", "Beweispaket EagleEye PersonOSINT\n\n"
                   f"Fall: {case['reference']} · Export-ID: {export_id}\n\n"
                   "Jede Datei im Ordner 'belege' wurde zum angegebenen Zeitpunkt (UTC) über den genannten Netzausgang abgerufen\n"
                   "und unmittelbar mit SHA-256 versiegelt. Prüfung unter Linux/macOS:  sha256sum belege/*\n"
                   "Windows (PowerShell):  Get-FileHash belege\\* -Algorithm SHA256\n"
                   "Die Werte müssen mit manifest.csv übereinstimmen. Archivkopien (Internet Archive) dienen als unabhängiger Vergleich.\n")
    return buf.getvalue()
