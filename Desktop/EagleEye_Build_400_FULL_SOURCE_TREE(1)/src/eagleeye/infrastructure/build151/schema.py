from __future__ import annotations

from typing import Any

SCHEMA_151 = r"""
CREATE TABLE IF NOT EXISTS architecture_snapshots_151(
    snapshot_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    repository_root TEXT NOT NULL,
    module_count INTEGER NOT NULL DEFAULT 0,
    python_file_count INTEGER NOT NULL DEFAULT 0,
    python_lines INTEGER NOT NULL DEFAULT 0,
    canonical_count INTEGER NOT NULL DEFAULT 0,
    legacy_count INTEGER NOT NULL DEFAULT 0,
    adapter_count INTEGER NOT NULL DEFAULT 0,
    experimental_count INTEGER NOT NULL DEFAULT 0,
    deprecated_count INTEGER NOT NULL DEFAULT 0,
    silent_exception_count INTEGER NOT NULL DEFAULT 0,
    oversized_module_count INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL DEFAULT '{}',
    payload_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_arch151_created ON architecture_snapshots_151(created_at DESC);

CREATE TABLE IF NOT EXISTS reliability_baselines_151(
    baseline_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    initialized_services INTEGER NOT NULL DEFAULT 0,
    registered_services INTEGER NOT NULL DEFAULT 0,
    active_threads INTEGER NOT NULL DEFAULT 0,
    non_daemon_threads INTEGER NOT NULL DEFAULT 0,
    open_db_transaction INTEGER NOT NULL DEFAULT 0,
    process_rss_bytes INTEGER NOT NULL DEFAULT 0,
    elapsed_ms INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL DEFAULT '{}',
    payload_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rel151_created ON reliability_baselines_151(created_at DESC);

CREATE TABLE IF NOT EXISTS architecture_decisions_151(
    decision_id TEXT PRIMARY KEY,
    module_pattern TEXT NOT NULL,
    classification TEXT NOT NULL,
    canonical_target TEXT NOT NULL DEFAULT '',
    rationale TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(module_pattern)
);
"""

def ensure_build151_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_151)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','151.0')")
    db.conn.commit()
