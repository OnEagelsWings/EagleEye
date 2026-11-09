"""Verschlüsselte, datenbankunabhängige Sicherung und Wiederherstellung.

Eine Sicherung enthält alle Tabellen (als JSON) und die Fotos. Fotos und 2FA-Geheimnisse
werden entschlüsselt in das *verschlüsselte* Archiv gelegt und beim Einspielen mit dem
Schlüssel der Zielinstallation neu verschlüsselt. Damit taugt eine Sicherung auch für den
Umzug von SQLite nach PostgreSQL oder auf einen neuen Server.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .crypto import MAGIC, InvalidToken, Vault, passphrase_fernet
from .db import SCHEMA_VERSION, Database

HEADER_PASS = b"EEBAK1P"
HEADER_KEY = b"EEBAK1K"
#: Reihenfolge nach Fremdschlüsseln; Sitzungen werden bewusst nicht gesichert
TABLE_ORDER = ["users", "cases", "case_members", "entities", "identifiers", "searches", "findings", "links",
               "events", "tasks", "audit", "settings", "opsec_acks", "egress_log", "exports", "facts", "evidence"]


#: Einstellungen, die verschlüsselt gespeichert werden (z. B. Proxy-Zugangsdaten)
ENCRYPTED_SETTINGS = {"egress_profiles", "api_keys"}


class BackupError(Exception):
    pass


def _columns(db: Database, table: str) -> list[str]:
    if db.dialect == "postgres":
        rows = db.all("SELECT column_name AS name FROM information_schema.columns WHERE table_name = ? ORDER BY ordinal_position", (table,))
    else:
        rows = db.all(f"PRAGMA table_info({table})")
    return [r["name"] for r in rows]


def _raw_rows(db: Database, table: str) -> list[dict[str, Any]]:
    """Zeilen ohne JSON-Dekodierung (Werte bleiben wie gespeichert)."""
    with db._lock:  # noqa: SLF001 - bewusst direkter Zugriff für verlustfreie Kopie
        cur = db._run(f"SELECT * FROM {table} ORDER BY 1")  # noqa: SLF001
        rows = [dict(r) for r in cur.fetchall()]
        if db.dialect == "postgres":
            db._conn.commit()  # noqa: SLF001
    return rows


def create_backup(db: Database, vault: Vault, data_dir: Path, out_dir: Path, passphrase: str = "") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    manifest: dict[str, Any] = {"format": 1, "schema_version": SCHEMA_VERSION, "source_dialect": db.dialect,
                                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tables": {}, "files": {}}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for table in TABLE_ORDER:
            rows = _raw_rows(db, table)
            if table == "users":
                for r in rows:
                    if r.get("totp_secret"):
                        r["totp_secret"] = "PLAIN:" + vault.decrypt_text(r["totp_secret"])
            if table == "settings":
                for r in rows:
                    if r["key"] in ENCRYPTED_SETTINGS and r["value"]:
                        r["value"] = "PLAIN:" + vault.decrypt_text(r["value"])
            payload = json.dumps(rows, ensure_ascii=False, default=str).encode()
            z.writestr(f"tables/{table}.json", payload)
            manifest["tables"][table] = {"rows": len(rows), "sha256": hashlib.sha256(payload).hexdigest()}
        photos = data_dir / "photos"
        if photos.exists():
            for f in sorted(photos.iterdir()):
                if f.is_file():
                    content = vault.decrypt(f.read_bytes())
                    z.writestr(f"photos/{f.name}", content)
                    manifest["files"][f.name] = hashlib.sha256(content).hexdigest()
        # Belege (verschlüsselt gespeichert) und Firmenlogo (unkritisch) – getrennt aufgeführt
        for folder, encrypted in (("evidence", True), ("branding", False)):
            src_dir = data_dir / folder
            entries = manifest.setdefault(f"{folder}_files", {})
            if src_dir.exists():
                for f in sorted(src_dir.iterdir()):
                    if f.is_file():
                        content = vault.decrypt(f.read_bytes()) if encrypted else f.read_bytes()
                        z.writestr(f"{folder}/{f.name}", content)
                        entries[f.name] = hashlib.sha256(content).hexdigest()
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    raw = buf.getvalue()
    if passphrase:
        salt = os.urandom(16)
        blob = HEADER_PASS + salt + passphrase_fernet(passphrase, salt).encrypt(raw)
    else:
        blob = HEADER_KEY + vault.encrypt(raw)[len(MAGIC):]
    name = f"eagleeye-backup-{datetime.now():%Y%m%d-%H%M%S}.eebak"
    target = out_dir / name
    tmp = target.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(blob)
    tmp.replace(target)
    return target


def _open(path: Path, vault: Vault | None, passphrase: str) -> tuple[zipfile.ZipFile, dict[str, Any]]:
    blob = Path(path).read_bytes()
    try:
        if blob.startswith(HEADER_PASS):
            if not passphrase:
                raise BackupError("Diese Sicherung ist mit einer Passphrase geschützt – bitte angeben.")
            salt = blob[len(HEADER_PASS):len(HEADER_PASS) + 16]
            raw = passphrase_fernet(passphrase, salt).decrypt(blob[len(HEADER_PASS) + 16:])
        elif blob.startswith(HEADER_KEY):
            if vault is None:
                raise BackupError("Schlüsseldatei der Quellinstallation wird benötigt.")
            raw = vault.decrypt(MAGIC + blob[len(HEADER_KEY):])
        else:
            raise BackupError("Keine EagleEye-Sicherung.")
    except InvalidToken as exc:
        raise BackupError("Entschlüsselung fehlgeschlagen – falsche Passphrase bzw. falscher Schlüssel oder Datei beschädigt.") from exc
    z = zipfile.ZipFile(io.BytesIO(raw))
    return z, json.loads(z.read("manifest.json"))


def verify_backup(path: Path, vault: Vault | None = None, passphrase: str = "") -> dict[str, Any]:
    z, manifest = _open(path, vault, passphrase)
    problems = []
    for table, info in manifest["tables"].items():
        if hashlib.sha256(z.read(f"tables/{table}.json")).hexdigest() != info["sha256"]:
            problems.append(f"Tabelle {table} beschädigt")
    for name, digest in manifest["files"].items():
        if hashlib.sha256(z.read(f"photos/{name}")).hexdigest() != digest:
            problems.append(f"Foto {name} beschädigt")
    for folder in ("evidence", "branding"):
        for name, digest in (manifest.get(f"{folder}_files") or {}).items():
            if hashlib.sha256(z.read(f"{folder}/{name}")).hexdigest() != digest:
                problems.append(f"Datei {folder}/{name} beschädigt")
    return {"ok": not problems, "problems": problems, "created_at": manifest["created_at"],
            "tables": {k: v["rows"] for k, v in manifest["tables"].items()}, "photos": len(manifest["files"]),
            "source_dialect": manifest["source_dialect"]}


def restore_backup(path: Path, db: Database, vault: Vault, data_dir: Path, passphrase: str = "", source_vault: Vault | None = None,
                   force: bool = False) -> dict[str, Any]:
    check = verify_backup(path, source_vault or vault, passphrase)
    if not check["ok"]:
        raise BackupError("Sicherung ist beschädigt: " + "; ".join(check["problems"]))
    existing = int(db.scalar("SELECT COUNT(*) AS n FROM cases") or 0) + int(db.scalar("SELECT COUNT(*) AS n FROM users") or 0)
    if existing and not force:
        raise BackupError("Die Zieldatenbank enthält bereits Daten. Wiederherstellung nur in eine leere Installation (oder --force).")
    z, manifest = _open(path, source_vault or vault, passphrase)
    if manifest["schema_version"] > SCHEMA_VERSION:
        raise BackupError("Die Sicherung stammt von einer neueren Programmversion. Bitte zuerst aktualisieren.")
    with db.tx():
        if force:
            for table in reversed(TABLE_ORDER + ["sessions"]):
                db.run_in_tx(f"DELETE FROM {table}")
        for table in TABLE_ORDER:
            rows = json.loads(z.read(f"tables/{table}.json")) if f"tables/{table}.json" in z.namelist() else []
            if not rows:
                continue
            cols = [c for c in _columns(db, table) if c in rows[0]]
            sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
            for r in rows:
                if table == "users" and str(r.get("totp_secret", "")).startswith("PLAIN:"):
                    r["totp_secret"] = vault.encrypt_text(r["totp_secret"][6:])
                if table == "settings" and r.get("key") in ENCRYPTED_SETTINGS and str(r.get("value", "")).startswith("PLAIN:"):
                    r["value"] = vault.encrypt_text(r["value"][6:])
                db.run_in_tx(sql, [r.get(c) for c in cols])
    db.reset_sequences()
    photos = data_dir / "photos"
    photos.mkdir(parents=True, exist_ok=True)
    for name in manifest["files"]:
        safe = Path(name).name  # keine Pfadangaben aus dem Archiv übernehmen
        (photos / safe).write_bytes(vault.encrypt(z.read(f"photos/{name}")))
    for folder, encrypted in (("evidence", True), ("branding", False)):
        target = data_dir / folder
        for name in manifest.get(f"{folder}_files") or {}:
            target.mkdir(parents=True, exist_ok=True)
            content = z.read(f"{folder}/{name}")
            (target / Path(name).name).write_bytes(vault.encrypt(content) if encrypted else content)
    return check


def list_backups(out_dir: Path) -> list[dict[str, Any]]:
    if not out_dir.exists():
        return []
    return [{"name": f.name, "size": f.stat().st_size, "created_at": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")}
            for f in sorted(out_dir.glob("*.eebak"), reverse=True)]


def prune_backups(out_dir: Path, keep: int) -> int:
    files = sorted(out_dir.glob("*.eebak"), reverse=True)
    for f in files[keep:]:
        f.unlink(missing_ok=True)
    return max(0, len(files) - keep)
