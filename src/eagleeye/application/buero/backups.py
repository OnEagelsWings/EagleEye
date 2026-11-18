"""Encrypted backups from inside the office: run, check, keep the last N, remind when due.

Only the office management (administration) runs, checks and downloads backups. The password
is used for the run only and never stored. The backup folder defaults to a folder next to the
workspace; an external drive (e.g. ``E:\\EagleEye-Sicherung``) is recommended.
"""
from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timezone
from pathlib import Path

from eagleeye.bootstrap import recovery479, securebackup
from . import service as buero

DEFAULTS = {"sicherung_ordner": "", "sicherung_behalten": "10", "sicherung_intervall_tage": "7"}
NAME = re.compile(r"^EagleEye-Sicherung_\d{4}-\d{2}-\d{2}_\d{6}_[0-9a-f]{4}\.eebak$")
TABLE = """CREATE TABLE IF NOT EXISTS buero_backups(backup_id TEXT PRIMARY KEY, file_name TEXT NOT NULL,
    folder TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL, files INTEGER NOT NULL, bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL, created_by TEXT NOT NULL, verified_at TEXT NOT NULL DEFAULT '',
    verified_by TEXT NOT NULL DEFAULT '', removed_at TEXT NOT NULL DEFAULT '')"""


def initialize(ctx) -> None:
    ctx.db.conn.execute(TABLE)
    ctx.db.conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require_admin(user: dict) -> None:
    if not buero._is_admin(user):
        raise PermissionError("Datensicherungen verwaltet die Büroleitung (Administration).")


def default_folder(ctx) -> Path:
    return Path(ctx.base_dir).resolve().parent / "EagleEye-Sicherungen"


def settings(ctx) -> dict:
    values = dict(DEFAULTS)
    for row in ctx.db.all("SELECT key, value FROM buero_settings WHERE key IN (?,?,?)", tuple(DEFAULTS)):
        values[row["key"]] = row["value"]
    values["ordner_wirksam"] = values["sicherung_ordner"] or str(default_folder(ctx))
    return values


def _folder(ctx, value: str) -> Path:
    text = str(value or "").strip()
    if not text:
        return default_folder(ctx)
    try:
        folder = recovery479.local_path(text)
    except ValueError as exc:
        raise buero.BueroError(str(exc)) from None
    if not Path(text).expanduser().is_absolute():
        raise buero.BueroError("Bitte einen vollständigen Ordnerpfad angeben, z. B. E:\\EagleEye-Sicherung.")
    workspace = Path(ctx.base_dir).resolve()
    if folder == workspace or workspace in folder.parents:
        raise buero.BueroError("Der Sicherungsordner darf nicht im Arbeitsordner liegen.")
    return folder


def save_settings(ctx, user: dict, form: dict) -> dict:
    _require_admin(user)
    folder = str(form.get("sicherung_ordner") or "").strip()
    _folder(ctx, folder)
    keep = str(form.get("sicherung_behalten") or "").strip()
    days = str(form.get("sicherung_intervall_tage") or "").strip()
    if not re.fullmatch(r"\d{1,3}", keep) or not 1 <= int(keep) <= 365:
        raise buero.BueroError("Aufbewahren: Anzahl zwischen 1 und 365.")
    if not re.fullmatch(r"\d{1,3}", days) or not 1 <= int(days) <= 90:
        raise buero.BueroError("Erinnerung: alle 1 bis 90 Tage.")
    stamp = _now()
    with ctx.db.transaction(immediate=True):
        for key, value in (("sicherung_ordner", folder), ("sicherung_behalten", keep), ("sicherung_intervall_tage", days)):
            ctx.db.execute("INSERT INTO buero_settings(key,value,updated_by,updated_at) VALUES(?,?,?,?) ON CONFLICT(key) "
                           "DO UPDATE SET value=excluded.value, updated_by=excluded.updated_by, updated_at=excluded.updated_at",
                           (key, value, user["username"], stamp))
        ctx.audit.log("buero_backup_settings_saved", "buero_settings", "backup", None, {"custom_folder": bool(folder)})
    return settings(ctx)


def backups(ctx, user: dict) -> list[dict]:
    _require_admin(user)
    out = []
    for row in ctx.db.all("SELECT * FROM buero_backups ORDER BY created_at DESC LIMIT 200"):
        row = dict(row)
        row["present"] = not row["removed_at"] and (Path(row["folder"]) / row["file_name"]).is_file()
        out.append(row)
    return out


def run(ctx, user: dict, form: dict) -> dict:
    """Make an encrypted backup now, record it, and remove backups beyond the kept number."""
    _require_admin(user)
    password = str(form.get("password") or "")
    try:
        securebackup.check_password(password, str(form.get("repeat") or ""))
    except securebackup.BackupError as exc:
        raise buero.BueroError(str(exc)) from None
    if str(form.get("notiert") or "") not in {"on", "1", "true"}:
        raise buero.BueroError("Bitte bestätigen, dass das Passwort getrennt von der Sicherung aufbewahrt wird.")
    values = settings(ctx)
    folder = _folder(ctx, values["sicherung_ordner"])
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise buero.BueroError(f"Der Sicherungsordner {folder} ist nicht erreichbar (Laufwerk angeschlossen?).") from None
    try:
        result = securebackup.create(ctx.base_dir, folder, password)
    except (securebackup.BackupError, ValueError) as exc:
        raise buero.BueroError(str(exc)) from None
    row = {"backup_id": "backup_" + secrets.token_hex(8), "file_name": result["file_name"], "folder": str(folder),
           "size": result["size"], "sha256": result["sha256"], "files": result["files"], "bytes": result["bytes"],
           "created_at": _now(), "created_by": user["username"]}
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("INSERT INTO buero_backups(" + ",".join(row) + ") VALUES(" + ",".join("?" for _ in row) + ")",
                       tuple(row.values()))
        ctx.audit.log("buero_backup_created", "buero_backup", row["backup_id"], None,
                      {"files": row["files"], "bytes": row["bytes"], "sha256": row["sha256"]})
    row["removed"] = _rotate(ctx, user, int(values["sicherung_behalten"]))
    return row


def _rotate(ctx, user: dict, keep: int) -> int:
    """Remove EagleEye's own backups beyond the newest ``keep`` (also so deleted cases age out)."""
    rows = [dict(r) for r in ctx.db.all("SELECT * FROM buero_backups WHERE removed_at='' ORDER BY created_at DESC")]
    removed = 0
    for row in rows[keep:]:
        path = Path(row["folder"]) / row["file_name"]
        if NAME.match(row["file_name"]) and path.is_file():
            try:
                path.unlink()
            except OSError:
                continue
        with ctx.db.transaction(immediate=True):
            ctx.db.execute("UPDATE buero_backups SET removed_at=? WHERE backup_id=?", (_now(), row["backup_id"]))
            ctx.audit.log("buero_backup_removed", "buero_backup", row["backup_id"], None, {"reason": "rotation"})
        removed += 1
    return removed


def path_of(ctx, user: dict, backup_id: str) -> Path:
    _require_admin(user)
    row = ctx.db.one("SELECT * FROM buero_backups WHERE backup_id=? AND removed_at=''", (str(backup_id),))
    if not row or not NAME.match(row["file_name"]):
        raise buero.BueroError("Sicherung nicht gefunden.")
    path = Path(row["folder"]) / row["file_name"]
    if not path.is_file():
        raise buero.BueroError("Die Sicherungsdatei ist nicht mehr am Ablageort (verschoben oder Laufwerk getrennt).")
    return path


def verify(ctx, user: dict, form: dict) -> dict:
    path = path_of(ctx, user, str(form.get("backup_id") or ""))
    row = ctx.db.one("SELECT * FROM buero_backups WHERE backup_id=?", (str(form.get("backup_id")),))
    if recovery479.sha_file(path) != row["sha256"]:
        raise buero.BueroError("Die Sicherungsdatei wurde seit dem Erstellen verändert (Prüfsumme weicht ab).")
    try:
        facts = securebackup.verify(path, str(form.get("password") or ""))
    except (securebackup.BackupError, ValueError) as exc:
        raise buero.BueroError(str(exc)) from None
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("UPDATE buero_backups SET verified_at=?, verified_by=? WHERE backup_id=?",
                       (_now(), user["username"], row["backup_id"]))
        ctx.audit.log("buero_backup_verified", "buero_backup", row["backup_id"], None, {"files": facts["files"]})
    return facts


def reminder(ctx, *, today: date | None = None) -> str:
    """'' if a backup is recent enough, otherwise a short German reminder."""
    last = ctx.db.one("SELECT created_at FROM buero_backups WHERE removed_at='' ORDER BY created_at DESC LIMIT 1")
    if not last:
        return "Noch keine verschlüsselte Sicherung angelegt."
    days = int(settings(ctx)["sicherung_intervall_tage"])
    made = date.fromisoformat(last["created_at"][:10])
    age = ((today or date.today()) - made).days
    if age >= days:
        return f"Letzte verschlüsselte Sicherung vor {age} Tagen ({made.strftime('%d.%m.%Y')}) – Sicherung fällig."
    return ""
