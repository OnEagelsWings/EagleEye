from __future__ import annotations

from typing import Any

SCHEMA_150 = r'''
CREATE TABLE IF NOT EXISTS capture_policies_150(
    policy_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    target_id TEXT,
    label TEXT NOT NULL,
    purpose TEXT NOT NULL,
    legal_basis TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'manual',
    allowed_hosts_json TEXT NOT NULL DEFAULT '[]',
    excluded_hosts_json TEXT NOT NULL DEFAULT '[]',
    include_html INTEGER NOT NULL DEFAULT 1,
    include_visible_text INTEGER NOT NULL DEFAULT 1,
    include_screenshot INTEGER NOT NULL DEFAULT 1,
    include_resource_inventory INTEGER NOT NULL DEFAULT 1,
    include_jsonld INTEGER NOT NULL DEFAULT 1,
    capture_delay_ms INTEGER NOT NULL DEFAULT 1500,
    min_interval_seconds INTEGER NOT NULL DEFAULT 30,
    max_captures INTEGER NOT NULL DEFAULT 100,
    retention_days INTEGER NOT NULL DEFAULT 365,
    status TEXT NOT NULL DEFAULT 'draft',
    approved_by TEXT NOT NULL DEFAULT '',
    approved_at TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_capture_policy150_case ON capture_policies_150(case_id,status,updated_at DESC);

CREATE TABLE IF NOT EXISTS capture_sessions_150(
    session_id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    target_id TEXT,
    companion_case_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    max_captures INTEGER NOT NULL DEFAULT 100,
    captured_count INTEGER NOT NULL DEFAULT 0,
    started_by TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT '',
    expires_at TEXT NOT NULL,
    paused_at TEXT NOT NULL DEFAULT '',
    stopped_at TEXT NOT NULL DEFAULT '',
    last_capture_at TEXT NOT NULL DEFAULT '',
    stop_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(policy_id) REFERENCES capture_policies_150(policy_id) ON DELETE CASCADE,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_capture_session150_active_case ON capture_sessions_150(case_id) WHERE status='active';
CREATE INDEX IF NOT EXISTS idx_capture_session150_case ON capture_sessions_150(case_id,status,updated_at DESC);

CREATE TABLE IF NOT EXISTS browser_capture_records_150(
    record_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    target_id TEXT NOT NULL DEFAULT '',
    capture_id_129 TEXT NOT NULL UNIQUE,
    trigger_mode TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    source_host TEXT NOT NULL,
    title TEXT NOT NULL,
    page_language TEXT NOT NULL DEFAULT '',
    document_type TEXT NOT NULL DEFAULT 'html',
    dom_sha256 TEXT NOT NULL DEFAULT '',
    resource_inventory_sha256 TEXT NOT NULL DEFAULT '',
    metadata_sha256 TEXT NOT NULL DEFAULT '',
    previous_record_id TEXT,
    change_state TEXT NOT NULL DEFAULT 'first_capture',
    integrity_state TEXT NOT NULL DEFAULT 'verified',
    package_relpath TEXT NOT NULL DEFAULT '',
    package_sha256 TEXT NOT NULL DEFAULT '',
    candidate_only INTEGER NOT NULL DEFAULT 1,
    captured_by TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES capture_sessions_150(session_id) ON DELETE CASCADE,
    FOREIGN KEY(policy_id) REFERENCES capture_policies_150(policy_id) ON DELETE CASCADE,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY(capture_id_129) REFERENCES browser_captures_129(capture_id) ON DELETE CASCADE,
    FOREIGN KEY(previous_record_id) REFERENCES browser_capture_records_150(record_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_capture_record150_case ON browser_capture_records_150(case_id,captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_capture_record150_url ON browser_capture_records_150(case_id,canonical_url,captured_at DESC);

CREATE TABLE IF NOT EXISTS capture_resource_inventory_150(
    resource_id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    source_host TEXT NOT NULL DEFAULT '',
    url_sha256 TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT '',
    candidate_only INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(record_id,resource_type,url_sha256),
    FOREIGN KEY(record_id) REFERENCES browser_capture_records_150(record_id) ON DELETE CASCADE,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_capture_resource150_record ON capture_resource_inventory_150(record_id,resource_type);

CREATE TABLE IF NOT EXISTS capture_diffs_150(
    diff_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    previous_record_id TEXT NOT NULL,
    current_record_id TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    text_changed INTEGER NOT NULL DEFAULT 0,
    html_changed INTEGER NOT NULL DEFAULT 0,
    screenshot_changed INTEGER NOT NULL DEFAULT 0,
    metadata_changed INTEGER NOT NULL DEFAULT 0,
    resources_added INTEGER NOT NULL DEFAULT 0,
    resources_removed INTEGER NOT NULL DEFAULT 0,
    summary_json TEXT NOT NULL DEFAULT '{}',
    review_status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY(previous_record_id) REFERENCES browser_capture_records_150(record_id) ON DELETE CASCADE,
    FOREIGN KEY(current_record_id) REFERENCES browser_capture_records_150(record_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_capture_diff150_case ON capture_diffs_150(case_id,review_status,created_at DESC);

CREATE TABLE IF NOT EXISTS capture_events_150(
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    case_id TEXT,
    session_id TEXT NOT NULL DEFAULT '',
    record_id TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    previous_hash TEXT NOT NULL,
    event_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_capture_event150_chain ON capture_events_150(case_id,sequence);
'''


def ensure_build150_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_150)
    # Build-149 hotfix columns: bounded approvals and auditable retry state.
    db._ensure_column('source_plans_149', 'expires_at', "TEXT NOT NULL DEFAULT ''")
    db._ensure_column('source_jobs_149', 'run_attempts', 'INTEGER NOT NULL DEFAULT 0')
    db._ensure_column('source_jobs_149', 'completed_at', "TEXT NOT NULL DEFAULT ''")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','150.0')")
    db.conn.commit()
