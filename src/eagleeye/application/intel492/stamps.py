"""Evidence additions for web captures: page image and trusted timestamp over a manifest.

The manifest is a short UTF-8 text that names the capture, its address, retrieval time and the
SHA-256 values of the WARC file, the server response and – if taken – the page image. One
RFC 3161 timestamp over the manifest therefore covers all of them. The manifest is stored
byte-exact so that ``openssl ts -verify -data manifest.txt -in stamp.tsr`` works later.

A timestamp proves that the manifest existed at the stamped time. A stamp requested later
for an older capture is labelled as such.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timezone

from . import captures, timestamps

TABLES = [
    """CREATE TABLE IF NOT EXISTS web_capture_image_492(capture_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
        png BLOB NOT NULL, sha256 TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL, browser TEXT NOT NULL,
        url TEXT NOT NULL, hosts TEXT NOT NULL, blocked INTEGER NOT NULL, complete INTEGER NOT NULL, truncated INTEGER NOT NULL,
        taken_at TEXT NOT NULL, created_by TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS web_capture_stamp_492(stamp_id TEXT PRIMARY KEY, capture_id TEXT NOT NULL,
        case_id TEXT NOT NULL, manifest TEXT NOT NULL, manifest_sha256 TEXT NOT NULL, tsa_url TEXT NOT NULL,
        request BLOB NOT NULL, response BLOB NOT NULL, nonce TEXT NOT NULL, gen_time TEXT NOT NULL, serial TEXT NOT NULL,
        tsa_name TEXT NOT NULL, later INTEGER NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS evidence_settings_492(key TEXT PRIMARY KEY, value TEXT NOT NULL,
        updated_by TEXT NOT NULL, updated_at TEXT NOT NULL)""",
]
DEFAULTS = {"tsa_url": timestamps.DEFAULT_URL, "browser_path": ""}


def initialize(ctx) -> None:
    for statement in TABLES:
        ctx.db.conn.execute(statement)
    ctx.db.conn.execute("CREATE INDEX IF NOT EXISTS web_capture_stamp_492_capture ON web_capture_stamp_492(capture_id)")
    ctx.db.conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def settings(ctx) -> dict:
    values = dict(DEFAULTS)
    for row in ctx.db.all("SELECT key, value FROM evidence_settings_492"):
        if row["key"] in values:
            values[row["key"]] = row["value"]
    return values


def save_settings(ctx, user: dict, form: dict) -> dict:
    if user.get("global_role") != "system_administrator":
        raise PermissionError("Die Beweissicherung stellt die Büroleitung (Administration) ein.")
    url = str(form.get("tsa_url") or "").strip() or timestamps.DEFAULT_URL
    if not url.startswith(("http://", "https://")) or len(url) > 300 or any(c.isspace() for c in url):
        raise ValueError("Zeitstempeldienst: bitte eine vollständige http- oder https-Adresse angeben.")
    browser = str(form.get("browser_path") or "").strip().strip('"')
    if len(browser) > 400:
        raise ValueError("Browserpfad ist zu lang.")
    if browser:
        name = os.path.basename(browser).lower()
        if not any(word in name for word in ("msedge", "edge", "chrome", "chromium")):
            raise ValueError("Bitte den Pfad zu Microsoft Edge (msedge.exe) oder Google Chrome (chrome.exe) angeben.")
        if not os.path.isfile(browser):
            raise ValueError("Browser nicht gefunden: Datei existiert nicht. Leer lassen, um automatisch zu suchen.")
    with ctx.db.transaction(immediate=True):
        for key, value in (("tsa_url", url), ("browser_path", browser)):
            ctx.db.execute("INSERT INTO evidence_settings_492(key,value,updated_by,updated_at) VALUES(?,?,?,?) ON CONFLICT(key) "
                           "DO UPDATE SET value=excluded.value, updated_by=excluded.updated_by, updated_at=excluded.updated_at",
                           (key, value, user["username"], _now()))
        ctx.audit.log("evidence_settings_saved_492", "evidence_settings", "web", None, {"tsa_host": url.split("/")[2]})
    return settings(ctx)


# ---------------------------------------------------------------- page image

def store_image(ctx, *, identity: dict, case_id: str, capture_id: str, shot: dict) -> dict:
    """Store the page image of a capture (one per capture; a capture with an image keeps it)."""
    row = captures.capture_row(ctx, capture_id)
    if row["case_id"] != case_id:
        raise ValueError("Web-Beleg gehört nicht zu diesem Fall.")
    png = shot["png"]
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Kein PNG-Bild.")
    image = {"capture_id": capture_id, "case_id": case_id, "png": png, "sha256": hashlib.sha256(png).hexdigest(),
             "width": int(shot["width"]), "height": int(shot["height"]), "browser": str(shot.get("browser", ""))[:200],
             "url": str(shot.get("url", row["url"]))[:2000], "hosts": json.dumps(list(shot.get("hosts", []))[:200]),
             "blocked": len(shot.get("blocked", [])), "complete": 1 if shot.get("complete") else 0,
             "truncated": 1 if shot.get("truncated") else 0, "taken_at": _now(), "created_by": identity["username"]}
    with ctx.db.transaction(immediate=True):
        if ctx.db.one("SELECT 1 FROM web_capture_image_492 WHERE capture_id=?", (capture_id,)):
            raise ValueError("Für diesen Web-Beleg gibt es schon ein Seitenbild.")
        ctx.db.execute("INSERT INTO web_capture_image_492(" + ",".join(image) + ") VALUES(" + ",".join("?" for _ in image) + ")",
                       tuple(image.values()))
        ctx.audit.log("web_capture_image_492", "web_capture", capture_id, case_id, {"sha256": image["sha256"], "bytes": len(png)})
    return {k: v for k, v in image.items() if k != "png"}


def image(ctx, capture_id: str) -> dict | None:
    row = ctx.db.one("SELECT * FROM web_capture_image_492 WHERE capture_id=?", (str(capture_id),))
    if not row:
        return None
    row = dict(row)
    row["intact"] = hashlib.sha256(row["png"]).hexdigest() == row["sha256"]
    row["hosts"] = json.loads(row["hosts"] or "[]")
    return row


def images(ctx, case_id: str) -> dict[str, dict]:
    """Image metadata per capture (without the PNG bytes)."""
    return {r["capture_id"]: dict(r) for r in ctx.db.all(
        "SELECT capture_id, sha256, width, height, taken_at, complete, truncated, blocked FROM web_capture_image_492 WHERE case_id=?",
        (case_id,))}


# ---------------------------------------------------------------- manifest and stamp

def manifest(ctx, capture_id: str) -> str:
    row = captures.capture_row(ctx, capture_id)
    shot = ctx.db.one("SELECT sha256, taken_at, browser FROM web_capture_image_492 WHERE capture_id=?", (capture_id,))
    lines = ["EagleEye Beweismanifest v1",
             f"Fall: {row['case_id']}",
             f"Web-Beleg: {row['capture_id']}",
             f"Adresse: {row['url']}",
             f"Archivadresse: {row['archive_url'] or '-'}",
             f"Abruf (UTC): {row['captured_at']}",
             f"Server-IP: {row['ip_address']}",
             f"WARC SHA-256: {row['warc_sha256']}",
             f"Antwort SHA-256: {row['body_sha256']}",
             f"Seitenbild SHA-256: {shot['sha256'] if shot else '-'}",
             f"Seitenbild aufgenommen (UTC): {shot['taken_at'] if shot else '-'}"]
    return "\n".join(lines) + "\n"


def stamp(ctx, *, identity: dict, case_id: str, capture_id: str, send=None, roots=None) -> dict:
    """Request and verify a timestamp over the capture's manifest; stores it only when it verifies."""
    row = captures.capture_row(ctx, capture_id)
    if row["case_id"] != case_id:
        raise ValueError("Web-Beleg gehört nicht zu diesem Fall.")
    if not captures.verify_capture(ctx, row):
        raise timestamps.TimestampError("Die WARC-Datei ist verändert – ein Zeitstempel würde einen beschädigten Beleg bestätigen.")
    text = manifest(ctx, capture_id)
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    url = settings(ctx)["tsa_url"]
    answer = timestamps.request(url, digest, send=send)
    facts = timestamps.verify(answer["response"], digest, nonce=answer["nonce"], roots=roots)
    captured = datetime.fromisoformat(row["captured_at"].replace("Z", "+00:00"))
    later = (datetime.fromisoformat(facts["gen_time"]) - captured).total_seconds() > 600
    entry = {"stamp_id": "stamp492_" + secrets.token_hex(10), "capture_id": capture_id, "case_id": case_id,
             "manifest": text, "manifest_sha256": digest.hex(), "tsa_url": url, "request": answer["request"],
             "response": answer["response"], "nonce": str(answer["nonce"]), "gen_time": facts["gen_time"],
             "serial": facts["serial"], "tsa_name": facts["tsa"], "later": 1 if later else 0,
             "created_by": identity["username"], "created_at": _now()}
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("INSERT INTO web_capture_stamp_492(" + ",".join(entry) + ") VALUES(" + ",".join("?" for _ in entry) + ")",
                       tuple(entry.values()))
        ctx.audit.log("web_capture_stamped_492", "web_capture", capture_id, case_id,
                      {"tsa": facts["tsa"], "gen_time": facts["gen_time"], "manifest_sha256": entry["manifest_sha256"],
                       "chain_trusted": facts["chain_trusted"]})
    return {**{k: v for k, v in entry.items() if k not in ("request", "response")}, "chain_trusted": facts["chain_trusted"]}


def latest(ctx, case_id: str, capture_ids=None) -> dict[str, dict]:
    rows = ctx.db.all("SELECT stamp_id, capture_id, gen_time, tsa_name, later, manifest_sha256 FROM web_capture_stamp_492 "
                      "WHERE case_id=? ORDER BY created_at", (case_id,))
    out = {}
    for row in rows:
        if capture_ids is None or row["capture_id"] in capture_ids:
            out[row["capture_id"]] = dict(row)
    return out


def stamp_row(ctx, stamp_id: str) -> dict:
    row = ctx.db.one("SELECT * FROM web_capture_stamp_492 WHERE stamp_id=?", (str(stamp_id),))
    if not row:
        raise KeyError("stamp not found")
    return dict(row)


def check(ctx, stamp_id: str, *, roots=None) -> dict:
    """Verify a stored stamp again: response against the stored manifest, manifest against the capture now."""
    row = stamp_row(ctx, stamp_id)
    digest = hashlib.sha256(row["manifest"].encode("utf-8")).digest()
    result = {"stamp_id": stamp_id, "ok": False, "chain_trusted": False, "current": False, "problem": ""}
    if digest.hex() != row["manifest_sha256"]:
        result["problem"] = "Gespeichertes Manifest verändert."
        return result
    try:
        facts = timestamps.verify(row["response"], digest, nonce=int(row["nonce"]), roots=roots)
    except timestamps.TimestampError as exc:
        result["problem"] = str(exc)
        return result
    result.update(ok=True, chain_trusted=facts["chain_trusted"], gen_time=facts["gen_time"], tsa=facts["tsa"])
    result["current"] = manifest(ctx, row["capture_id"]) == row["manifest"]
    if not result["current"]:
        result["problem"] = "Der Beleg hat sich seit dem Stempel geändert (z. B. Seitenbild ergänzt) – neuen Stempel einholen."
    return result


def report_fields(ctx, case_id: str, capture_id: str) -> list[tuple[str, str]]:
    """German label/value pairs for reports: page image and the current, verified timestamp."""
    fields = []
    shot = ctx.db.one("SELECT sha256, taken_at FROM web_capture_image_492 WHERE capture_id=?", (capture_id,))
    if shot:
        fields.append(("Seitenbild (SHA-256, aufgenommen UTC)", shot["sha256"] + " · " + shot["taken_at"]))
    current = latest(ctx, case_id, {capture_id}).get(capture_id)
    if current:
        state = check(ctx, current["stamp_id"])
        when = current["gen_time"].replace("T", " ").replace("+00:00", "")
        if state["ok"] and state["current"]:
            fields.append(("Unabhängiger Zeitstempel (RFC 3161)",
                           f"{when} UTC · {current['tsa_name']} · Manifest SHA-256 {current['manifest_sha256']}"
                           + (" · Zertifikatskette geprüft" if state["chain_trusted"] else " · Zertifikatskette nicht bis zur Wurzel geprüft")
                           + (" · nachträglich eingeholt" if current["later"] else "")))
        else:
            fields.append(("Unabhängiger Zeitstempel (RFC 3161)", "nicht aktuell oder nicht prüfbar – " + state["problem"]))
    return fields


def client_summary(ctx, case_id: str, capture_id: str) -> list[str]:
    """Short German phrases for the client report: only what verifies now."""
    out = []
    shot = image(ctx, capture_id)
    if shot and shot["intact"]:
        out.append("Seitenbild gesichert")
    current = latest(ctx, case_id, {capture_id}).get(capture_id)
    if current:
        state = check(ctx, current["stamp_id"])
        if state["ok"] and state["current"]:
            when = current["gen_time"][:16].replace("T", " ")
            out.append(f"unabhängiger Zeitstempel {when} UTC ({current['tsa_name']})"
                       + (", nachträglich" if current["later"] else ""))
    return out


def export(ctx, stamp_id: str) -> dict:
    """Files for the evidence package: byte-exact manifest, the TSA response and its certificate chain."""
    row = stamp_row(ctx, stamp_id)
    digest = hashlib.sha256(row["manifest"].encode("utf-8")).digest()
    facts = timestamps.verify(row["response"], digest, nonce=int(row["nonce"]))
    return {"manifest": row["manifest"].encode("utf-8"), "tsr": row["response"], "chain_pem": facts["chain_pem"],
            "capture_id": row["capture_id"], "case_id": row["case_id"]}
