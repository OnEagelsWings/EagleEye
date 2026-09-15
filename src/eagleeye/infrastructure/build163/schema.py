from __future__ import annotations
from typing import Any

SCHEMA_163 = r'''
CREATE TABLE IF NOT EXISTS social_accounts_163(
 account_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_id TEXT NOT NULL,
 platform_account_id TEXT, handle TEXT, display_name TEXT, profile_uri TEXT,
 profile_json TEXT NOT NULL, normalized_handle TEXT, alias_keys_json TEXT NOT NULL,
 first_observed_at TEXT NOT NULL, last_observed_at TEXT NOT NULL,
 provenance_json TEXT NOT NULL, content_sha256 TEXT NOT NULL,
 review_status TEXT NOT NULL, UNIQUE(case_id,source_id,platform_account_id)
);
CREATE TABLE IF NOT EXISTS social_media_163(
 media_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_id TEXT NOT NULL,
 record_id TEXT, media_type TEXT NOT NULL, canonical_uri TEXT,
 perceptual_key TEXT, metadata_json TEXT NOT NULL, provenance_json TEXT NOT NULL,
 observed_at TEXT NOT NULL, review_status TEXT NOT NULL, content_sha256 TEXT NOT NULL,
 UNIQUE(case_id,source_id,content_sha256)
);
CREATE TABLE IF NOT EXISTS social_interactions_163(
 interaction_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_id TEXT NOT NULL,
 interaction_type TEXT NOT NULL, actor_account_id TEXT, target_account_id TEXT,
 source_record_id TEXT, target_record_id TEXT, observed_at TEXT NOT NULL,
 confidence REAL NOT NULL, evidence_class TEXT NOT NULL,
 provenance_json TEXT NOT NULL, review_status TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 UNIQUE(case_id,source_id,interaction_type,actor_account_id,target_account_id,source_record_id,target_record_id)
);
CREATE TABLE IF NOT EXISTS social_identity_clusters_163(
 cluster_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, subject_label TEXT,
 member_accounts_json TEXT NOT NULL, signals_json TEXT NOT NULL,
 contradictions_json TEXT NOT NULL, score REAL NOT NULL,
 risk_adjusted_score REAL NOT NULL, confidence_band TEXT NOT NULL,
 review_status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_key_person_scores_163(
 score_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, account_id TEXT NOT NULL,
 score REAL NOT NULL, rank_position INTEGER NOT NULL, factors_json TEXT NOT NULL,
 limitations_json TEXT NOT NULL, computed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 UNIQUE(case_id,account_id)
);
CREATE TABLE IF NOT EXISTS social_correlation_events_163(
 event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL,
 entity_id TEXT, details_json TEXT NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
'''

def ensure_build163_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_163)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','163.0')")
    db.conn.commit()
