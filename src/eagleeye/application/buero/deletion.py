"""Final deletion of a closed mandate's case after its retention period (GDPR storage limitation).

What is deleted: every row carrying the case's ``case_id`` in every workspace database, rows
of tables without a ``case_id`` column that point at a deleted row's primary key (documents,
anchors, captures …), and files whose name carries the case or one of those keys. SQLite
``secure_delete`` overwrites the freed pages; the WAL is checkpointed afterwards.

What is kept, and said so: hash chains that span all cases (the security access log and the
legacy event journal) – removing entries would break their verification for every other case.
They are counted as residual entries. Backups made earlier still contain the case until they
are rotated; the confirmation page says this. The deletion log keeps only the file number,
dates, counts and the operator – no content.
"""
from __future__ import annotations

import json
import re
import secrets
import shutil
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

from . import service as buero

# Cross-case hash chains: deleting rows would break verification for all other cases.
GLOBAL_CHAINS = {"phase15_access_events", "event_journal_109"}
NEVER_TOUCH = {"buero_deletions", "buero_clients", "buero_settings", "sqlite_sequence"}
# Identity columns are never followed, even when they are a primary key somewhere.
IDENTITY_COLUMNS = {"user_id", "session_id", "username", "actor", "created_by", "client_id", "membership_id_user"}
SKIP_DIRS = ("recovery", "backup", "sicherung", "snapshot")
DB_SUFFIXES = (".db", ".sqlite", ".sqlite3")
MIN_KEY = 12  # random ids only; short or numeric keys are never followed
DELETION_TABLE = """CREATE TABLE IF NOT EXISTS buero_deletions(deletion_id TEXT PRIMARY KEY, case_ref TEXT NOT NULL,
    aktenzeichen TEXT NOT NULL, client_id TEXT NOT NULL, closed_on TEXT NOT NULL, retention_until TEXT NOT NULL,
    early_reason TEXT NOT NULL, rows_deleted INTEGER NOT NULL, files_deleted INTEGER NOT NULL, residual_json TEXT NOT NULL,
    deleted_by TEXT NOT NULL, deleted_at TEXT NOT NULL)"""


def initialize(ctx) -> None:
    ctx.db.conn.execute(DELETION_TABLE)
    ctx.db.conn.commit()


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _databases(ctx) -> list[Path]:
    base = Path(ctx.base_dir)
    main = Path(ctx.db.path).resolve()
    found = []
    for path in sorted(base.rglob("*")):
        if path.suffix.lower() not in DB_SUFFIXES or not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(base).as_posix().lower()
        if any(part in relative for part in SKIP_DIRS):
            continue
        if path.resolve() != main:
            found.append(path)
    return found


def _tables(con) -> list[tuple[str, list[str], list[str]]]:
    """(table, columns, primary-key columns) for ordinary tables."""
    out = []
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        info = con.execute(f"PRAGMA table_info({_q(name)})").fetchall()
        out.append((name, [r[1] for r in info], [r[1] for r in info if r[5]]))
    return out


def _chained_audit_ids(con) -> set[str]:
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_chain_hashes'").fetchone():
        return set()
    return {r[0] for r in con.execute("SELECT event_id FROM audit_chain_hashes").fetchall()}


def _plan_or_purge(con, case_id: str, *, execute: bool) -> dict:
    """Count (and optionally delete) the case's rows in one database connection.

    Foreign keys are checked at commit (deferred), so the order of tables does not matter;
    anything still pointing at a deleted row makes the whole deletion roll back.
    """
    if execute:
        con.execute("PRAGMA defer_foreign_keys=ON")
    tables = _tables(con)
    chained_audit = _chained_audit_ids(con)
    counts: dict[str, int] = {}
    kept: dict[str, int] = {}
    keys: dict[str, set[str]] = {}

    def collect(table, columns, pks, where, params):
        followed = [c for c in pks if c.endswith("_id") and c != "case_id" and c not in IDENTITY_COLUMNS]
        if not followed:
            return
        for row in con.execute(f"SELECT {', '.join(_q(c) for c in followed)} FROM {_q(table)} WHERE {where}", params):
            for column, value in zip(followed, row):
                if isinstance(value, str) and len(value) >= MIN_KEY:
                    keys.setdefault(column, set()).add(value)

    for table, columns, pks in tables:
        if "case_id" not in columns or table in NEVER_TOUCH:
            continue
        n = con.execute(f"SELECT COUNT(*) FROM {_q(table)} WHERE case_id=?", (case_id,)).fetchone()[0]
        if not n:
            continue
        if table in GLOBAL_CHAINS:
            kept[table] = n
            continue
        where, params = "case_id=?", [case_id]
        if table == "audit_events" and chained_audit:
            marks = ",".join("?" for _ in chained_audit)
            locked = con.execute(f"SELECT COUNT(*) FROM audit_events WHERE case_id=? AND event_id IN ({marks})",
                                 (case_id, *chained_audit)).fetchone()[0]
            if locked:
                kept["audit_events (verkettet)"] = locked
                where, params = f"case_id=? AND event_id NOT IN ({marks})", [case_id, *chained_audit]
                n -= locked
        collect(table, columns, pks, where, params)
        counts[table] = n
        if execute and n:
            con.execute(f"DELETE FROM {_q(table)} WHERE {where}", params)

    # Follow primary keys of deleted rows into tables without a case_id column (bounded rounds).
    seen: set[tuple[str, str]] = set()
    for _ in range(3):
        new_keys: dict[str, set[str]] = {}
        for table, columns, pks in tables:
            if "case_id" in columns or table in NEVER_TOUCH or table in GLOBAL_CHAINS or table == "audit_chain_hashes":
                continue
            for column in columns:
                values = keys.get(column)
                if not values or (table, column) in seen:
                    continue
                values = sorted(values)
                total = 0
                for start in range(0, len(values), 500):
                    chunk = values[start:start + 500]
                    marks = ",".join("?" for _ in chunk)
                    where = f"{_q(column)} IN ({marks})"
                    n = con.execute(f"SELECT COUNT(*) FROM {_q(table)} WHERE {where}", chunk).fetchone()[0]
                    if not n:
                        continue
                    before = {k: set(v) for k, v in keys.items()}
                    collect(table, columns, pks, where, chunk)
                    for k, v in keys.items():
                        new_keys.setdefault(k, set()).update(v - before.get(k, set()))
                    if execute:
                        con.execute(f"DELETE FROM {_q(table)} WHERE {where}", chunk)
                    total += n
                if total:
                    counts[table] = counts.get(table, 0) + total
                seen.add((table, column))
        if not any(new_keys.values()):
            break
    return {"counts": counts, "kept": kept, "keys": keys}


def _files(ctx, case_id: str, keys: dict[str, set[str]]) -> list[Path]:
    base = Path(ctx.base_dir)
    tokens = {case_id} | {v for values in keys.values() for v in values if len(v) >= MIN_KEY}
    hits = []
    data = base / "data"
    if not data.is_dir():
        return hits
    for path in data.rglob("*"):
        if path.is_symlink() or path.suffix.lower() in DB_SUFFIXES or path.name.endswith(("-wal", "-shm", "-journal")):
            continue
        relative = path.relative_to(base).as_posix().lower()
        if any(part in relative for part in SKIP_DIRS):
            continue
        name = path.name
        if any(token in name for token in tokens):
            hits.append(path)
    # A directory named after the case or a key covers its contents.
    dirs = [p for p in hits if p.is_dir()]
    return [p for p in hits if not any(d in p.parents for d in dirs)]


def _residual(con, case_id: str) -> dict[str, int]:
    found: dict[str, int] = {}
    pattern = "%" + case_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    for table, columns, _ in _tables(con):
        if table in NEVER_TOUCH:
            continue
        clauses = " OR ".join(f"CAST({_q(c)} AS TEXT) LIKE ? ESCAPE '\\'" for c in columns)
        if not clauses:
            continue
        try:
            n = con.execute(f"SELECT COUNT(*) FROM {_q(table)} WHERE {clauses}", [pattern] * len(columns)).fetchone()[0]
        except sqlite3.DatabaseError:
            continue
        if n:
            found[table] = n
    return found


def _check(ctx, user: dict, case_id: str, *, today: date | None = None) -> dict:
    if not buero._is_admin(user):
        raise PermissionError("Endgültig löschen darf nur die Büroleitung (Administration).")
    row = buero._mandate_row(ctx, case_id)
    if row["status"] not in {"abgeschlossen", "abgelehnt"}:
        raise buero.BueroError("Gelöscht werden nur abgeschlossene oder abgelehnte Aufträge.")
    return row


def due(row: dict, today: date | None = None) -> bool:
    day = (today or date.today()).isoformat()
    return bool(row["retention_until"]) and row["retention_until"] <= day


def plan(ctx, user: dict, case_id: str, *, today: date | None = None) -> dict:
    """What a deletion would remove, without changing anything."""
    row = _check(ctx, user, case_id, today=today)
    totals: dict[str, int] = {}
    kept: dict[str, int] = {}
    keys: dict[str, set[str]] = {}
    with ctx.db.transaction():
        result = _plan_or_purge(ctx.db.conn, case_id, execute=False)
    for name, value in result["counts"].items():
        totals[name] = totals.get(name, 0) + value
    kept.update(result["kept"])
    for column, values in result["keys"].items():
        keys.setdefault(column, set()).update(values)
    for path in _databases(ctx):
        with closing(sqlite3.connect(path, timeout=10)) as con:
            result = _plan_or_purge(con, case_id, execute=False)
        for name, value in result["counts"].items():
            totals[path.name + ": " + name] = value
        kept.update({path.name + ": " + k: v for k, v in result["kept"].items()})
        for column, values in result["keys"].items():
            keys.setdefault(column, set()).update(values)
    files = _files(ctx, case_id, keys)
    return {"mandate": row, "rows": totals, "row_total": sum(totals.values()), "kept": kept, "files": len(files),
            "due": due(row, today), "documents": len(keys.get("document_id", set()))}


def delete_case(ctx, user: dict, case_id: str, form: dict, *, today: date | None = None) -> dict:
    """Delete the case for good. Returns the deletion log entry."""
    row = _check(ctx, user, case_id, today=today)
    if str(form.get("confirm") or "").strip() != row["aktenzeichen"]:
        raise buero.BueroError("Zur Bestätigung bitte das Aktenzeichen genau abtippen.")
    if str(form.get("checked") or "") not in {"on", "1", "true"}:
        raise buero.BueroError("Bitte bestätigen, dass keine Aufbewahrungspflicht entgegensteht.")
    early_reason = ""
    if not due(row, today):
        early_reason = buero._text(form.get("reason"), 600, field="Begründung")
        if len(early_reason) < buero.MIN_REASON:
            raise buero.BueroError("Die Aufbewahrungsfrist läuft noch: Löschung vorab nur mit Begründung "
                                   f"(z. B. Löschverlangen der betroffenen Person), mindestens {buero.MIN_REASON} Zeichen.")
    keys: dict[str, set[str]] = {}
    rows_deleted = 0
    kept: dict[str, int] = {}
    con = ctx.db.conn
    con.execute("PRAGMA secure_delete=ON")
    try:
        with ctx.db.transaction(immediate=True):
            result = _plan_or_purge(con, case_id, execute=True)
    finally:
        con.execute("PRAGMA secure_delete=OFF")
    rows_deleted += sum(result["counts"].values())
    kept.update(result["kept"])
    for column, values in result["keys"].items():
        keys.setdefault(column, set()).update(values)
    for path in _databases(ctx):
        with closing(sqlite3.connect(path, timeout=30)) as other:
            other.execute("PRAGMA secure_delete=ON")
            with other:
                result = _plan_or_purge(other, case_id, execute=True)
            other.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        rows_deleted += sum(result["counts"].values())
        kept.update({path.name + ": " + k: v for k, v in result["kept"].items()})
        for column, values in result["keys"].items():
            keys.setdefault(column, set()).update(values)
    files_deleted = 0
    for path in _files(ctx, case_id, keys):
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            files_deleted += 1
        except OSError:
            continue
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except sqlite3.DatabaseError:
        pass
    residual = _residual(con, case_id)
    for path in _databases(ctx):
        with closing(sqlite3.connect(path, timeout=10)) as other:
            residual.update({path.name + ": " + k: v for k, v in _residual(other, case_id).items()})
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry = {"deletion_id": "deletion_" + secrets.token_hex(8), "case_ref": case_id, "aktenzeichen": row["aktenzeichen"],
             "client_id": row["client_id"], "closed_on": row["closed_on"], "retention_until": row["retention_until"],
             "early_reason": early_reason, "rows_deleted": rows_deleted, "files_deleted": files_deleted,
             "residual_json": json.dumps(residual, sort_keys=True), "deleted_by": user["username"], "deleted_at": stamp}
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("INSERT INTO buero_deletions(" + ",".join(entry) + ") VALUES(" + ",".join("?" for _ in entry) + ")",
                       tuple(entry.values()))
        ctx.audit.log("buero_case_deleted", "buero_deletion", entry["deletion_id"], None,
                      {"aktenzeichen": row["aktenzeichen"], "rows_deleted": rows_deleted, "files_deleted": files_deleted,
                       "residual_tables": sorted(residual), "early": bool(early_reason)})
    return {**entry, "residual": residual, "kept": kept}


def deletions(ctx, user: dict) -> list[dict]:
    if not buero._is_admin(user):
        raise PermissionError("Das Löschprotokoll sieht nur die Büroleitung (Administration).")
    out = []
    for row in ctx.db.all("SELECT * FROM buero_deletions ORDER BY deleted_at DESC LIMIT 200"):
        row = dict(row)
        row["residual"] = json.loads(row.pop("residual_json"))
        out.append(row)
    return out


RESIDUAL_LABELS = {
    "phase15_access_events": "Zugriffsprotokoll (fallübergreifend verkettet; nur Kennungen und Prüfsummen, keine Inhalte)",
    "event_journal_109": "Ereignisjournal älterer Werkzeuge (fallübergreifend verkettet)",
    "audit_events": "Änderungsprotokoll",
}


def residual_label(table: str) -> str:
    plain = re.sub(r"^[^:]+: ", "", table)
    return RESIDUAL_LABELS.get(plain.split(" ")[0], plain)
