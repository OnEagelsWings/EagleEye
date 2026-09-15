from __future__ import annotations

from typing import Any

SCHEMA_149 = r'''
CREATE TABLE IF NOT EXISTS source_portfolio_149(
    source_key TEXT PRIMARY KEY,
    connector_id TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    source_family TEXT NOT NULL,
    category TEXT NOT NULL,
    jurisdiction TEXT NOT NULL DEFAULT 'global',
    geographic_scope TEXT NOT NULL DEFAULT 'global',
    access_tier TEXT NOT NULL,
    authority_score INTEGER NOT NULL DEFAULT 50,
    independence_score INTEGER NOT NULL DEFAULT 50,
    freshness_days INTEGER NOT NULL DEFAULT 30,
    risk_level TEXT NOT NULL DEFAULT 'low',
    persona_required INTEGER NOT NULL DEFAULT 0,
    exact_email_allowed INTEGER NOT NULL DEFAULT 0,
    bulk_capable INTEGER NOT NULL DEFAULT 0,
    input_types_json TEXT NOT NULL DEFAULT '[]',
    official_url TEXT NOT NULL,
    documentation_url TEXT NOT NULL DEFAULT '',
    legal_status TEXT NOT NULL,
    terms_profile TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 50,
    enabled INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(connector_id) REFERENCES connector_manifests_148(connector_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_source_portfolio149_family
    ON source_portfolio_149(source_family,priority DESC,authority_score DESC);
CREATE INDEX IF NOT EXISTS idx_source_portfolio149_access
    ON source_portfolio_149(access_tier,risk_level,enabled);

CREATE TABLE IF NOT EXISTS source_plans_149(
    plan_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    target_id TEXT,
    objective TEXT NOT NULL,
    purpose TEXT NOT NULL,
    legal_basis TEXT NOT NULL,
    requested_families_json TEXT NOT NULL DEFAULT '[]',
    anchors_json TEXT NOT NULL DEFAULT '{}',
    selected_connectors_json TEXT NOT NULL DEFAULT '[]',
    excluded_sources_json TEXT NOT NULL DEFAULT '[]',
    ai_brief_json TEXT NOT NULL DEFAULT '{}',
    opsec_assessment_json TEXT NOT NULL DEFAULT '{}',
    disclosure_budget INTEGER NOT NULL DEFAULT 3,
    max_external_actions INTEGER NOT NULL DEFAULT 10,
    allow_exact_email INTEGER NOT NULL DEFAULT 0,
    allow_licensed_sources INTEGER NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'draft',
    approved_by TEXT NOT NULL DEFAULT '',
    approved_at TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_source_plans149_case
    ON source_plans_149(case_id,status,updated_at DESC);

CREATE TABLE IF NOT EXISTS source_jobs_149(
    job_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    target_id TEXT,
    connector_id TEXT NOT NULL,
    source_key TEXT NOT NULL,
    source_family TEXT NOT NULL,
    query_text TEXT NOT NULL,
    anchor_types_json TEXT NOT NULL DEFAULT '[]',
    query_sha256 TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 50,
    expected_value REAL NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'low',
    status TEXT NOT NULL DEFAULT 'planned',
    build148_run_id TEXT NOT NULL DEFAULT '',
    result_count INTEGER NOT NULL DEFAULT 0,
    quarantine_count INTEGER NOT NULL DEFAULT 0,
    blocked_reason TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(plan_id) REFERENCES source_plans_149(plan_id) ON DELETE CASCADE,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
    FOREIGN KEY(connector_id) REFERENCES connector_manifests_148(connector_id),
    FOREIGN KEY(source_key) REFERENCES source_portfolio_149(source_key),
    UNIQUE(case_id,connector_id,query_sha256)
);
CREATE INDEX IF NOT EXISTS idx_source_jobs149_queue
    ON source_jobs_149(case_id,status,priority DESC,created_at);
CREATE INDEX IF NOT EXISTS idx_source_jobs149_plan
    ON source_jobs_149(plan_id,status,priority DESC);

CREATE TABLE IF NOT EXISTS source_opsec_assessments_149(
    assessment_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    blocked INTEGER NOT NULL DEFAULT 0,
    exposure_score REAL NOT NULL DEFAULT 0,
    findings_json TEXT NOT NULL DEFAULT '[]',
    mitigations_json TEXT NOT NULL DEFAULT '[]',
    active_persona_session_id TEXT NOT NULL DEFAULT '',
    assessed_by TEXT NOT NULL,
    assessed_at TEXT NOT NULL,
    FOREIGN KEY(plan_id) REFERENCES source_plans_149(plan_id) ON DELETE CASCADE,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_source_opsec149_plan
    ON source_opsec_assessments_149(plan_id,assessed_at DESC);

CREATE TABLE IF NOT EXISTS source_result_clusters_149(
    cluster_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    cluster_fingerprint TEXT NOT NULL,
    representative_title TEXT NOT NULL DEFAULT '',
    member_count INTEGER NOT NULL DEFAULT 0,
    independent_host_count INTEGER NOT NULL DEFAULT 0,
    independent_family_count INTEGER NOT NULL DEFAULT 0,
    assessment TEXT NOT NULL DEFAULT 'candidate_only',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(case_id,cluster_fingerprint),
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_source_clusters149_case
    ON source_result_clusters_149(case_id,member_count DESC,updated_at DESC);

CREATE TABLE IF NOT EXISTS source_result_cluster_members_149(
    cluster_id TEXT NOT NULL,
    quarantine_id TEXT NOT NULL,
    connector_id TEXT NOT NULL,
    source_family TEXT NOT NULL,
    source_host TEXT NOT NULL DEFAULT '',
    content_fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(cluster_id,quarantine_id),
    FOREIGN KEY(cluster_id) REFERENCES source_result_clusters_149(cluster_id) ON DELETE CASCADE,
    FOREIGN KEY(quarantine_id) REFERENCES connector_quarantine_148(quarantine_id) ON DELETE CASCADE,
    FOREIGN KEY(connector_id) REFERENCES connector_manifests_148(connector_id)
);

CREATE TABLE IF NOT EXISTS source_events_149(
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    case_id TEXT,
    plan_id TEXT NOT NULL DEFAULT '',
    job_id TEXT NOT NULL DEFAULT '',
    source_key TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    previous_hash TEXT NOT NULL,
    event_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_events149_chain
    ON source_events_149(case_id,sequence);
'''


def ensure_build149_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_149)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','149.0')")
    db.conn.commit()
