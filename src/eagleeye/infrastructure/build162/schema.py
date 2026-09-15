from __future__ import annotations
from typing import Any
SCHEMA_162 = r'''
CREATE TABLE IF NOT EXISTS social_collection_authorizations_162(
 authorization_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_id TEXT NOT NULL,
 purpose TEXT NOT NULL, scope_json TEXT NOT NULL, approved_by TEXT NOT NULL,
 approved_at TEXT NOT NULL, expires_at TEXT, status TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_collection_runs_162(
 run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_id TEXT NOT NULL,
 operation TEXT NOT NULL, query_json TEXT NOT NULL, status TEXT NOT NULL,
 outcome TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
 cursor_in TEXT, cursor_out TEXT, item_count INTEGER NOT NULL DEFAULT 0,
 rate_limit_json TEXT NOT NULL, provenance_json TEXT NOT NULL,
 error_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_records_162(
 record_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL,
 source_id TEXT NOT NULL, record_type TEXT NOT NULL, source_record_id TEXT,
 canonical_uri TEXT, author_id TEXT, author_handle TEXT, published_at TEXT,
 content_text TEXT, raw_json TEXT NOT NULL, provenance_json TEXT NOT NULL,
 content_sha256 TEXT NOT NULL, review_status TEXT NOT NULL,
 created_at TEXT NOT NULL,
 UNIQUE(case_id,source_id,content_sha256)
);
CREATE TABLE IF NOT EXISTS social_pagination_162(
 pagination_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, source_id TEXT NOT NULL,
 cursor_value TEXT, next_url_hash TEXT, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_collection_events_162(
 event_id TEXT PRIMARY KEY, run_id TEXT, case_id TEXT NOT NULL, source_id TEXT NOT NULL,
 event_type TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
'''
def ensure_build162_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_162)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','162.0')")
    db.conn.commit()
