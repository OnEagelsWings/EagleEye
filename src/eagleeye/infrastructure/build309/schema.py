from __future__ import annotations
import json
from typing import Any

SCHEMA = r'''
CREATE TABLE IF NOT EXISTS phase13_query_plans_309(
 plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, purpose TEXT NOT NULL,
 primary_language TEXT NOT NULL, languages_json TEXT NOT NULL, status TEXT NOT NULL,
 query_count INTEGER NOT NULL DEFAULT 0, generated_by TEXT NOT NULL, created_at TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_qplan309_case ON phase13_query_plans_309(case_id,created_at DESC);
CREATE TABLE IF NOT EXISTS phase13_query_items_309(
 query_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
 language TEXT NOT NULL, category TEXT NOT NULL, query_text TEXT NOT NULL, objective TEXT NOT NULL,
 anchor_json TEXT NOT NULL, source_focus TEXT NOT NULL, stance TEXT NOT NULL, priority_score REAL NOT NULL,
 translation_basis TEXT NOT NULL, created_at TEXT NOT NULL, row_hash TEXT NOT NULL,
 UNIQUE(plan_id, query_text)
);
CREATE INDEX IF NOT EXISTS idx_qitem309_plan ON phase13_query_items_309(plan_id,priority_score DESC,language,category);
CREATE TABLE IF NOT EXISTS phase13_crawl_query_links_309(
 link_id TEXT PRIMARY KEY, authorization_id TEXT NOT NULL, plan_id TEXT NOT NULL, case_id TEXT NOT NULL,
 target_id TEXT NOT NULL, created_at TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phase13_evidence_features_309(
 feature_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, intake_id TEXT NOT NULL,
 feature_class TEXT NOT NULL, polarity TEXT NOT NULL, weight REAL NOT NULL, basis_json TEXT NOT NULL,
 probability_claim INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS evidence_feature_309_no_update BEFORE UPDATE ON phase13_evidence_features_309 BEGIN SELECT RAISE(ABORT,'immutable build309 evidence feature'); END;
CREATE TABLE IF NOT EXISTS phase13_dossier_revisions_309(
 dossier309_id TEXT PRIMARY KEY, parent308_id TEXT NOT NULL, case_id TEXT NOT NULL, revision_no INTEGER NOT NULL,
 title TEXT NOT NULL, status TEXT NOT NULL, file_relpath TEXT NOT NULL, file_sha256 TEXT NOT NULL,
 quality_json TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS dossier_309_no_update BEFORE UPDATE ON phase13_dossier_revisions_309 BEGIN SELECT RAISE(ABORT,'immutable build309 dossier'); END;
CREATE TABLE IF NOT EXISTS phase13_security_agent_attestations_309(
 attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
 actor TEXT NOT NULL, created_at TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_hard_training_delta_309(
 case_key TEXT PRIMARY KEY, track TEXT NOT NULL, difficulty TEXT NOT NULL, prompt TEXT NOT NULL,
 expected_controls_json TEXT NOT NULL, forbidden_behaviors_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_security_training_delta_309(
 case_key TEXT PRIMARY KEY, track TEXT NOT NULL, difficulty TEXT NOT NULL, prompt TEXT NOT NULL,
 expected_controls_json TEXT NOT NULL, forbidden_behaviors_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL
);
'''

QUERY_TRACKS=['multilingual_query_generation','country_language_routing','counterevidence_queries','official_record_queries','corporate_queries','finance_flow_queries','query_provenance','anchor_preservation']
SEC_TRACKS=['query_scope_anchor_gate','blocked_term_rejection','no_sensitive_guessing','provider_scope_preservation','crawler_private_network_gate','proxy_preservation','single_use_crawl_auth','immutable_query_audit']

def ensure_build309_schema(db:Any)->None:
    db.conn.executescript(SCHEMA)
    for i,track in enumerate(QUERY_TRACKS,1):
        diff='extreme' if i in {3,6} else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_309 VALUES(?,?,?,?,?,?,?,?)',(
            f'ai309_{i:02d}',track,diff,f'Build309 query-generation {track}: generate explainable multilingual public-source queries while preserving verified identity anchors.',
            json.dumps(['verified anchor required','language provenance','counterevidence branch','public-source scope','human review','no probability claim']),
            json.dumps(['invented identifier','private-account targeting','credential search','identity confirmation','uncalibrated probability']),'reviewed','build309-investigation-review'))
    for i,track in enumerate(SEC_TRACKS,1):
        diff='extreme' if i in {1,3} else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_309 VALUES(?,?,?,?,?,?,?,?)',(
            f'sec309_{i:02d}',track,diff,f'Build309 security {track}: fail closed for query planning and retain Build308 crawler egress controls.',
            json.dumps(['anchor validation','blocked-term filter','public-source scope','private-network block','proxy preservation','immutable audit']),
            json.dumps(['scope drift','invented sensitive data','proxy bypass','private destination','silent authorization reuse']),'reviewed','build309-security-review'))
