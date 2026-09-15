from __future__ import annotations
from typing import Any

SCHEMA_152 = r"""
CREATE TABLE IF NOT EXISTS domain_ports_152(
    port_name TEXT PRIMARY KEY,
    canonical_service TEXT NOT NULL,
    compatibility_services_json TEXT NOT NULL DEFAULT '[]',
    policy TEXT NOT NULL DEFAULT 'review_first',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS domain_migrations_152(
    migration_id TEXT PRIMARY KEY,
    port_name TEXT NOT NULL,
    source_service TEXT NOT NULL,
    target_service TEXT NOT NULL,
    state TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(port_name, source_service)
);
CREATE TABLE IF NOT EXISTS consolidation_snapshots_152(
    snapshot_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    canonical_ports INTEGER NOT NULL,
    available_ports INTEGER NOT NULL,
    missing_ports INTEGER NOT NULL,
    compatibility_bindings INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL
);
"""

def ensure_build152_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_152)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','152.0')")
    db.conn.commit()
