"""Persistenz für EagleEye PersonOSINT: SQLite (Einzelplatz) oder PostgreSQL (Teambetrieb).

Die Fachlogik schreibt portables SQL mit ``?``-Platzhaltern; diese Schicht übersetzt
es für PostgreSQL und führt versionierte Schema-Migrationen aus.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

JSON_FIELDS = {"data", "reasons", "queries", "source_status", "sources", "facts_used", "checks", "meta", "snapshot", "pivot"}

# --------------------------------------------------------------------------- Schema-Migrationen
# Platzhalter: {PK} = automatisch hochzählender Primärschlüssel, {REAL} = Gleitkommazahl

MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS cases (
    id {PK}, reference TEXT NOT NULL, title TEXT NOT NULL, case_type TEXT NOT NULL,
    purpose TEXT NOT NULL, legal_basis TEXT NOT NULL, client TEXT NOT NULL DEFAULT '',
    analyst TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'offen', notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entities (
    id {PK}, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE, type TEXT NOT NULL,
    label TEXT NOT NULL, is_subject INTEGER NOT NULL DEFAULT 0, data TEXT NOT NULL DEFAULT '{{}}',
    photo TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS identifiers (
    id {PK}, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE, kind TEXT NOT NULL, value TEXT NOT NULL,
    normalized TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'Analyst', verified INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS links (
    id {PK}, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE, relation TEXT NOT NULL,
    confidence INTEGER NOT NULL DEFAULT 50, evidence TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS searches (
    id {PK}, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    entity_id INTEGER REFERENCES entities(id) ON DELETE SET NULL, started_at TEXT NOT NULL, finished_at TEXT,
    queries TEXT NOT NULL DEFAULT '[]', source_status TEXT NOT NULL DEFAULT '[]', result_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS findings (
    id {PK}, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE, search_id INTEGER REFERENCES searches(id) ON DELETE SET NULL,
    source TEXT NOT NULL, category TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL DEFAULT '', snippet TEXT NOT NULL DEFAULT '',
    query TEXT NOT NULL DEFAULT '', data TEXT NOT NULL DEFAULT '{{}}', score INTEGER NOT NULL DEFAULT 0, reasons TEXT NOT NULL DEFAULT '[]',
    fingerprint TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'neu', review_note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, reviewed_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_findings_fp ON findings(case_id, entity_id, fingerprint);
CREATE TABLE IF NOT EXISTS events (
    id {PK}, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    entity_id INTEGER REFERENCES entities(id) ON DELETE SET NULL, occurred_at TEXT NOT NULL, kind TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '', lat {REAL}, lon {REAL}, description TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',
    reliability TEXT NOT NULL DEFAULT 'ungeprüft', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id {PK}, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE, title TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '', priority TEXT NOT NULL DEFAULT 'normal', done INTEGER NOT NULL DEFAULT 0,
    origin TEXT NOT NULL DEFAULT 'Analyst', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id {PK}, case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE, ts TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL DEFAULT ''
);
"""

MIGRATION_2 = """
CREATE TABLE users (
    id {PK}, username TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL, role TEXT NOT NULL,
    password_hash TEXT NOT NULL, totp_secret TEXT NOT NULL DEFAULT '', totp_enabled INTEGER NOT NULL DEFAULT 0,
    must_change_password INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
    failed_logins INTEGER NOT NULL DEFAULT 0, locked_until TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, last_login TEXT NOT NULL DEFAULT ''
);
CREATE TABLE sessions (
    id {PK}, token_hash TEXT NOT NULL UNIQUE, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL, mfa_passed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, last_seen TEXT NOT NULL,
    expires_at TEXT NOT NULL, ip TEXT NOT NULL DEFAULT '', user_agent TEXT NOT NULL DEFAULT ''
);
CREATE TABLE case_members (
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'bearbeiter', added_at TEXT NOT NULL, PRIMARY KEY (case_id, user_id)
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
ALTER TABLE cases ADD COLUMN owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE cases ADD COLUMN reviewer_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE cases ADD COLUMN due_date TEXT NOT NULL DEFAULT '';
ALTER TABLE cases ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal';
ALTER TABLE cases ADD COLUMN restricted INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cases ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE entities ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE findings ADD COLUMN reviewed_by TEXT NOT NULL DEFAULT '';
CREATE TABLE audit_v2 (
    id {PK}, case_id INTEGER, ts TEXT NOT NULL, user_id INTEGER, username TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', detail_hash TEXT NOT NULL DEFAULT '',
    redacted INTEGER NOT NULL DEFAULT 0, prev_hash TEXT NOT NULL DEFAULT '', hash TEXT NOT NULL DEFAULT ''
);
INSERT INTO audit_v2 (id, case_id, ts, action, detail) SELECT id, case_id, ts, action, detail FROM audit ORDER BY id;
DROP TABLE audit;
ALTER TABLE audit_v2 RENAME TO audit;
CREATE INDEX ix_audit_case ON audit(case_id);
CREATE INDEX ix_cases_owner ON cases(owner_id);
"""

MIGRATION_3 = """
ALTER TABLE cases ADD COLUMN opsec_level INTEGER NOT NULL DEFAULT 1;
ALTER TABLE cases ADD COLUMN codename TEXT NOT NULL DEFAULT '';
ALTER TABLE cases ADD COLUMN egress_profile TEXT NOT NULL DEFAULT '';
CREATE TABLE opsec_acks (
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    level INTEGER NOT NULL, acked_at TEXT NOT NULL, PRIMARY KEY (case_id, user_id, level)
);
CREATE TABLE egress_log (
    id {PK}, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE, ts TEXT NOT NULL, username TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '', host TEXT NOT NULL, path TEXT NOT NULL DEFAULT '', query TEXT NOT NULL DEFAULT '',
    status INTEGER NOT NULL DEFAULT 0, egress TEXT NOT NULL DEFAULT '', exposure TEXT NOT NULL DEFAULT ''
);
CREATE INDEX ix_egress_case ON egress_log(case_id);
CREATE TABLE exports (
    id {PK}, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE, export_id TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
    username TEXT NOT NULL, ts TEXT NOT NULL, sha256 TEXT NOT NULL DEFAULT '', options TEXT NOT NULL DEFAULT ''
);
CREATE INDEX ix_exports_case ON exports(case_id)
"""

MIGRATION_4 = """
CREATE TABLE facts (
    id {PK}, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    finding_id INTEGER REFERENCES findings(id) ON DELETE CASCADE,
    subject_entity_id INTEGER REFERENCES entities(id) ON DELETE SET NULL, subject_label TEXT NOT NULL, subject_type TEXT NOT NULL DEFAULT 'person',
    predicate TEXT NOT NULL, object_label TEXT NOT NULL, object_type TEXT NOT NULL DEFAULT 'wert',
    object_entity_id INTEGER REFERENCES entities(id) ON DELETE SET NULL,
    valid_from TEXT NOT NULL DEFAULT '', valid_to TEXT NOT NULL DEFAULT '', data TEXT NOT NULL DEFAULT '{{}}',
    source_key TEXT NOT NULL DEFAULT '', source_label TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '', retrieved_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'neu', reliability TEXT NOT NULL DEFAULT '', credibility INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '', norm_key TEXT NOT NULL DEFAULT '', reviewed_by TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE INDEX ix_facts_case ON facts(case_id);
CREATE INDEX ix_facts_finding ON facts(finding_id);
CREATE INDEX ix_facts_norm ON facts(case_id, norm_key);
CREATE TABLE ref_datasets (
    name TEXT PRIMARY KEY, label TEXT NOT NULL, license TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '',
    imported_at TEXT NOT NULL DEFAULT '', records INTEGER NOT NULL DEFAULT 0, links INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'leer', message TEXT NOT NULL DEFAULT ''
);
CREATE TABLE ref_records (
    id {PK}, dataset TEXT NOT NULL, ext_id TEXT NOT NULL, kind TEXT NOT NULL DEFAULT '', name TEXT NOT NULL,
    birth_date TEXT NOT NULL DEFAULT '', countries TEXT NOT NULL DEFAULT '', data TEXT NOT NULL DEFAULT '{{}}'
);
CREATE INDEX ix_ref_records_ext ON ref_records(dataset, ext_id);
CREATE TABLE ref_terms (term TEXT NOT NULL, record_id INTEGER NOT NULL);
CREATE INDEX ix_ref_terms ON ref_terms(term, record_id);
CREATE TABLE ref_links (dataset TEXT NOT NULL, src_ext TEXT NOT NULL, dst_ext TEXT NOT NULL, rel TEXT NOT NULL, data TEXT NOT NULL DEFAULT '{{}}');
CREATE INDEX ix_ref_links_src ON ref_links(dataset, src_ext);
CREATE INDEX ix_ref_links_dst ON ref_links(dataset, dst_ext)
"""

#: (Version, SQL, optionale Python-Nacharbeit) – Nacharbeit wird von außen registriert (Hash-Kette versiegeln)
MIGRATION_5 = """
CREATE TABLE evidence (
    id {PK}, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    finding_id INTEGER REFERENCES findings(id) ON DELETE SET NULL, fact_id INTEGER REFERENCES facts(id) ON DELETE SET NULL,
    url TEXT NOT NULL, final_url TEXT NOT NULL DEFAULT '', status INTEGER NOT NULL DEFAULT 0, content_type TEXT NOT NULL DEFAULT '',
    size INTEGER NOT NULL DEFAULT 0, sha256 TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '', excerpt TEXT NOT NULL DEFAULT '',
    file TEXT NOT NULL DEFAULT '', archive_url TEXT NOT NULL DEFAULT '', egress TEXT NOT NULL DEFAULT '', username TEXT NOT NULL DEFAULT '',
    retrieved_at TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX ix_evidence_case ON evidence(case_id)
"""

MIGRATION_6 = """
CREATE TABLE watches (
    id {PK}, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE, entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    sources TEXT NOT NULL DEFAULT '[]', interval_hours INTEGER NOT NULL DEFAULT 24, active INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL, created_at TEXT NOT NULL, last_run TEXT NOT NULL DEFAULT '',
    next_run TEXT NOT NULL, last_result TEXT NOT NULL DEFAULT '', last_new INTEGER NOT NULL DEFAULT 0, runs INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE notifications (
    id {PK}, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    ts TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'info', text TEXT NOT NULL, link TEXT NOT NULL DEFAULT '', seen INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_notifications_user ON notifications(user_id, seen);
CREATE TABLE ai_drafts (
    id {PK}, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE, kind TEXT NOT NULL DEFAULT 'zusammenfassung',
    text TEXT NOT NULL, model TEXT NOT NULL DEFAULT '', facts_used TEXT NOT NULL DEFAULT '[]', checks TEXT NOT NULL DEFAULT '{{}}',
    status TEXT NOT NULL DEFAULT 'entwurf', created_by TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
    approved_by TEXT NOT NULL DEFAULT '', approved_at TEXT NOT NULL DEFAULT ''
)
"""

MIGRATION_7 = """
ALTER TABLE users ADD COLUMN totp_last INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cases ADD COLUMN retention_until TEXT NOT NULL DEFAULT '';
ALTER TABLE cases ADD COLUMN mandate_check TEXT NOT NULL DEFAULT ''
"""

#: Version 1.5 – Zusammenführung mit Build 492 / SpiderFoot-Analyse:
#: Belege mit WARC, Haupttext und importierten Dokumenten; Suchläufe mit Konfigurations-Snapshot und Herkunft (Folgesuche)
MIGRATION_8 = """
ALTER TABLE evidence ADD COLUMN kind TEXT NOT NULL DEFAULT 'web';
ALTER TABLE evidence ADD COLUMN warc_file TEXT NOT NULL DEFAULT '';
ALTER TABLE evidence ADD COLUMN warc_sha256 TEXT NOT NULL DEFAULT '';
ALTER TABLE evidence ADD COLUMN text_file TEXT NOT NULL DEFAULT '';
ALTER TABLE evidence ADD COLUMN filename TEXT NOT NULL DEFAULT '';
ALTER TABLE evidence ADD COLUMN meta TEXT NOT NULL DEFAULT '{{}}';
ALTER TABLE evidence ADD COLUMN entity_id INTEGER;
ALTER TABLE searches ADD COLUMN snapshot TEXT NOT NULL DEFAULT '{{}}';
ALTER TABLE searches ADD COLUMN pivot TEXT NOT NULL DEFAULT '{{}}';
ALTER TABLE identifiers ADD COLUMN finding_id INTEGER;
CREATE TABLE pivots (
    id {PK}, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE, entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    kind TEXT NOT NULL, value TEXT NOT NULL, normalized TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'verworfen',
    decided_by TEXT NOT NULL DEFAULT '', decided_at TEXT NOT NULL
);
CREATE UNIQUE INDEX ix_pivots_key ON pivots(entity_id, kind, normalized);
CREATE TABLE correlation_rules (
    id {PK}, rule_key TEXT NOT NULL UNIQUE, definition TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
)
"""

MIGRATIONS: list[tuple[int, str]] = [(1, MIGRATION_1), (2, MIGRATION_2), (3, MIGRATION_3), (4, MIGRATION_4), (5, MIGRATION_5), (6, MIGRATION_6),
                                     (7, MIGRATION_7), (8, MIGRATION_8)]
SCHEMA_VERSION = MIGRATIONS[-1][0]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _decode(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    for key in JSON_FIELDS & out.keys():
        if isinstance(out[key], str):
            try:
                out[key] = json.loads(out[key] or "null")
            except json.JSONDecodeError:
                pass
    return out


def _encode(values: dict[str, Any]) -> dict[str, Any]:
    return {k: (json.dumps(v, ensure_ascii=False) if k in JSON_FIELDS and not isinstance(v, str) else v) for k, v in values.items()}


class ConflictError(Exception):
    """Datensatz wurde zwischenzeitlich geändert (optimistisches Sperren)."""


class Database:
    """Thread-sichere Fassade über sqlite3 bzw. psycopg (eine Verbindung, serialisiert)."""

    def __init__(self, url_or_path: Path | str, post_migrations: dict[int, Callable[["Database"], None]] | None = None):
        target = str(url_or_path)
        self.dialect = "postgres" if target.startswith(("postgres://", "postgresql://")) else "sqlite"
        self.target = target
        self._lock = threading.RLock()
        self._connect()
        self.migrate(post_migrations or {})

    # ------------------------------------------------------------------ Verbindung
    def _connect(self) -> None:
        if self.dialect == "postgres":
            import psycopg
            from psycopg.rows import dict_row

            self._conn = psycopg.connect(self.target, row_factory=dict_row, autocommit=False)
        else:
            if self.target != ":memory:":
                Path(self.target).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.target, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")

    def _sql(self, sql: str) -> str:
        if self.dialect == "postgres":
            return sql.replace("%", "%%").replace("?", "%s")
        return sql

    def _rows(self, cur) -> list[dict[str, Any]]:
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    def _run(self, sql: str, params: tuple | list = ()):
        try:
            return self._conn.execute(self._sql(sql), list(params))
        except Exception as exc:  # Verbindung zu PostgreSQL verloren -> einmal neu verbinden
            if self.dialect == "postgres" and self._conn.closed:
                self._connect()
                return self._conn.execute(self._sql(sql), list(params))
            raise exc

    @contextmanager
    def tx(self) -> Iterator["Database"]:
        with self._lock:
            try:
                yield self
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    # ------------------------------------------------------------------ Abfragen
    def all(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        with self._lock:
            try:
                rows = self._rows(self._run(sql, params))
            finally:
                if self.dialect == "postgres":
                    self._conn.commit()  # Lese-Transaktion beenden
            return [_decode(r) for r in rows]  # type: ignore[misc]

    def one(self, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: tuple | list = ()) -> Any:
        row = self.one(sql, params)
        return next(iter(row.values())) if row else None

    def insert(self, table: str, values: dict[str, Any], returning: bool = True) -> int:
        values = _encode(values)
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        sql = f"INSERT INTO {table} ({cols}) VALUES ({marks})"
        with self.tx():
            if self.dialect == "postgres":
                cur = self._run(sql + (" RETURNING id" if returning else ""), list(values.values()))
                return int(cur.fetchone()["id"]) if returning else 0
            cur = self._run(sql, list(values.values()))
            return int(cur.lastrowid or 0)

    def update(self, table: str, row_id: int, values: dict[str, Any], expected_version: int | None = None) -> None:
        """Aktualisiert eine Zeile. Mit ``expected_version`` wird optimistisch gesperrt."""
        if not values:
            return
        values = _encode(values)
        sets = ", ".join(f"{k} = ?" for k in values)
        params = [*values.values(), row_id]
        sql = f"UPDATE {table} SET {sets}"
        if expected_version is not None:
            sql += ", version = version + 1 WHERE id = ? AND version = ?"
            params.append(expected_version)
        else:
            sql += " WHERE id = ?"
        with self.tx():
            cur = self._run(sql, params)
            if expected_version is not None and cur.rowcount == 0:
                raise ConflictError("Der Datensatz wurde inzwischen von jemand anderem geändert. Bitte neu laden.")

    def executemany(self, sql: str, rows: list[list[Any]]) -> None:
        """Massen-Einfügen (Referenzdaten) in einer Transaktion."""
        with self.tx():
            if self.dialect == "postgres":
                with self._conn.cursor() as cur:
                    cur.executemany(self._sql(sql), rows)
            else:
                self._conn.executemany(sql, rows)

    def execute(self, sql: str, params: tuple | list = ()) -> int:
        with self.tx():
            return self._run(sql, params).rowcount

    def executescript(self, sql: str) -> None:
        with self.tx():
            if self.dialect == "sqlite":
                # executescript würde committen; Anweisungen einzeln ausführen
                for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
                    self._conn.execute(stmt)
            else:
                for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
                    self._conn.execute(stmt)

    # ------------------------------------------------------------------ Migrationen
    def _render(self, sql: str) -> str:
        if self.dialect == "postgres":
            return sql.format(PK="BIGSERIAL PRIMARY KEY", REAL="DOUBLE PRECISION")
        return sql.format(PK="INTEGER PRIMARY KEY AUTOINCREMENT", REAL="REAL")

    def schema_version(self) -> int:
        with self.tx():
            self._run("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL, applied_at TEXT NOT NULL)")
        return int(self.scalar("SELECT COALESCE(MAX(version), 0) AS v FROM schema_version") or 0)

    def migrate(self, post: dict[int, Callable[["Database"], None]]) -> None:
        current = self.schema_version()
        for version, sql in MIGRATIONS:
            if version <= current:
                continue
            if self.dialect == "sqlite":
                self._conn.execute("PRAGMA foreign_keys = OFF")
            try:
                self.executescript(self._render(sql))
                if self.dialect == "postgres":
                    for table in ("audit",):
                        with self.tx():
                            self._run(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")
            finally:
                if self.dialect == "sqlite":
                    self._conn.execute("PRAGMA foreign_keys = ON")
            if version in post:
                post[version](self)
            self.insert("schema_version", {"version": version, "applied_at": now_iso()}, returning=False)

    def tables(self) -> list[str]:
        if self.dialect == "postgres":
            rows = self.all("SELECT tablename AS name FROM pg_tables WHERE schemaname = 'public'")
        else:
            rows = self.all("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
        return sorted(r["name"] for r in rows)

    def reset_sequences(self) -> None:
        """Nach dem Einspielen von Daten mit festen IDs (Wiederherstellung) die Zähler nachziehen."""
        if self.dialect != "postgres":
            return
        for table in self.tables():
            if table in {"schema_version", "settings", "case_members", "opsec_acks", "ref_datasets", "ref_terms", "ref_links"}:
                continue
            with self.tx():
                self._run(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")

    def advisory_lock(self, key: int) -> None:
        """Serialisiert Schreibvorgänge über mehrere Prozesse (nur PostgreSQL, innerhalb einer Transaktion)."""
        if self.dialect == "postgres":
            self._run("SELECT pg_advisory_xact_lock(?)", [key])

    def run_in_tx(self, sql: str, params: tuple | list = ()):
        """Nur innerhalb von ``with db.tx():`` verwenden."""
        return self._run(sql, params)

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def redact_url(url: str) -> str:
    return re.sub(r"//([^:/@]+):([^@]+)@", r"//\1:***@", url)
