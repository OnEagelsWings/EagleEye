"""SQLite-Persistenz für EagleEye PersonOSINT.

Bewusst ohne ORM: ein lokales Ein-Datei-Archiv pro Installation, das sich
einfach sichern und weitergeben lässt.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference TEXT NOT NULL,
    title TEXT NOT NULL,
    case_type TEXT NOT NULL,
    purpose TEXT NOT NULL,
    legal_basis TEXT NOT NULL,
    client TEXT NOT NULL DEFAULT '',
    analyst TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'offen',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    label TEXT NOT NULL,
    is_subject INTEGER NOT NULL DEFAULT 0,
    data TEXT NOT NULL DEFAULT '{}',
    photo TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    normalized TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'Analyst',
    verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation TEXT NOT NULL,
    confidence INTEGER NOT NULL DEFAULT 50,
    evidence TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    entity_id INTEGER REFERENCES entities(id) ON DELETE SET NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    queries TEXT NOT NULL DEFAULT '[]',
    source_status TEXT NOT NULL DEFAULT '[]',
    result_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    search_id INTEGER REFERENCES searches(id) ON DELETE SET NULL,
    source TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    snippet TEXT NOT NULL DEFAULT '',
    query TEXT NOT NULL DEFAULT '',
    data TEXT NOT NULL DEFAULT '{}',
    score INTEGER NOT NULL DEFAULT 0,
    reasons TEXT NOT NULL DEFAULT '[]',
    fingerprint TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'neu',
    review_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    reviewed_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_findings_fp ON findings(case_id, entity_id, fingerprint);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    entity_id INTEGER REFERENCES entities(id) ON DELETE SET NULL,
    occurred_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    lat REAL,
    lon REAL,
    description TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    reliability TEXT NOT NULL DEFAULT 'ungeprüft',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL DEFAULT 'normal',
    done INTEGER NOT NULL DEFAULT 0,
    origin TEXT NOT NULL DEFAULT 'Analyst',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    ts TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
"""

JSON_FIELDS = {"data", "reasons", "queries", "source_status"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    for key in JSON_FIELDS & out.keys():
        try:
            out[key] = json.loads(out[key] or "null")
        except (TypeError, json.JSONDecodeError):
            pass
    return out


class Database:
    """Kleine Fassade über sqlite3, thread-sicher für den lokalen Betrieb."""

    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def all(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [_row(r) for r in self._conn.execute(sql, params).fetchall()]  # type: ignore[misc]

    def one(self, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
        with self._lock:
            return _row(self._conn.execute(sql, params).fetchone())

    def insert(self, table: str, values: dict[str, Any]) -> int:
        values = {k: (json.dumps(v, ensure_ascii=False) if k in JSON_FIELDS and not isinstance(v, str) else v)
                  for k, v in values.items()}
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        with self.tx() as conn:
            cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(values.values()))
            return int(cur.lastrowid)

    def update(self, table: str, row_id: int, values: dict[str, Any]) -> None:
        if not values:
            return
        values = {k: (json.dumps(v, ensure_ascii=False) if k in JSON_FIELDS and not isinstance(v, str) else v)
                  for k, v in values.items()}
        sets = ", ".join(f"{k} = ?" for k in values)
        with self.tx() as conn:
            conn.execute(f"UPDATE {table} SET {sets} WHERE id = ?", [*values.values(), row_id])

    def execute(self, sql: str, params: tuple | list = ()) -> int:
        with self.tx() as conn:
            return conn.execute(sql, params).rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.close()
