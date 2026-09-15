from __future__ import annotations
from typing import Any

SCHEMA_164 = r'''
CREATE TABLE IF NOT EXISTS crawl_authorizations_164(
 authorization_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, purpose TEXT NOT NULL,
 approved_by TEXT NOT NULL, seed_urls_json TEXT NOT NULL, allowed_hosts_json TEXT NOT NULL,
 scope_json TEXT NOT NULL, robots_mode TEXT NOT NULL, legal_basis TEXT,
 status TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crawl_runs_164(
 run_id TEXT PRIMARY KEY, authorization_id TEXT NOT NULL, case_id TEXT NOT NULL,
 status TEXT NOT NULL, started_at TEXT, finished_at TEXT, pages_fetched INTEGER NOT NULL,
 bytes_fetched INTEGER NOT NULL, errors INTEGER NOT NULL, frontier_remaining INTEGER NOT NULL,
 correlation_id TEXT, last_error TEXT, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crawl_frontier_164(
 frontier_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, url TEXT NOT NULL,
 canonical_url TEXT NOT NULL, host TEXT NOT NULL, depth INTEGER NOT NULL,
 priority REAL NOT NULL, parent_url TEXT, status TEXT NOT NULL,
 discovered_at TEXT NOT NULL, attempted_at TEXT, error TEXT,
 UNIQUE(run_id,canonical_url)
);
CREATE TABLE IF NOT EXISTS crawl_snapshots_164(
 snapshot_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL,
 url TEXT NOT NULL, final_url TEXT NOT NULL, host TEXT NOT NULL,
 http_status INTEGER NOT NULL, content_type TEXT, fetched_at TEXT NOT NULL,
 body_path TEXT NOT NULL, body_sha256 TEXT NOT NULL, response_headers_json TEXT NOT NULL,
 parent_snapshot_id TEXT, changed INTEGER NOT NULL, change_summary_json TEXT NOT NULL,
 provenance_json TEXT NOT NULL, chain_sha256 TEXT NOT NULL,
 UNIQUE(run_id,final_url,body_sha256)
);
CREATE TABLE IF NOT EXISTS robots_observations_164(
 observation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, host TEXT NOT NULL,
 robots_url TEXT NOT NULL, fetched_at TEXT NOT NULL, http_status INTEGER,
 body_sha256 TEXT, decision TEXT NOT NULL, rules_json TEXT NOT NULL,
 override_used INTEGER NOT NULL, legal_basis TEXT, payload_sha256 TEXT NOT NULL,
 UNIQUE(run_id,host)
);
CREATE TABLE IF NOT EXISTS crawl_events_164(
 event_id TEXT PRIMARY KEY, run_id TEXT, case_id TEXT NOT NULL,
 event_type TEXT NOT NULL, entity_id TEXT, details_json TEXT NOT NULL,
 created_at TEXT NOT NULL, previous_hash TEXT, event_hash TEXT NOT NULL
);
'''

def ensure_build164_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_164)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','164.0')")
    db.conn.commit()
