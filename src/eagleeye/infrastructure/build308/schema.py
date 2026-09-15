from __future__ import annotations
import json
from typing import Any

SCHEMA = r'''
CREATE TABLE IF NOT EXISTS phase13_crawl_authorizations_308(
 authorization_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, purpose TEXT NOT NULL,
 provider_requested TEXT NOT NULL, scope_mode TEXT NOT NULL, allowed_hosts_json TEXT NOT NULL, seed_urls_json TEXT NOT NULL,
 max_queries INTEGER NOT NULL, max_results_per_query INTEGER NOT NULL, max_pages INTEGER NOT NULL,
 max_depth INTEGER NOT NULL, max_total_bytes INTEGER NOT NULL, max_frontier INTEGER NOT NULL,
 approved_by TEXT NOT NULL, approved_at TEXT NOT NULL, status TEXT NOT NULL, policy_json TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phase13_crawl_runs_308(
 run_id TEXT PRIMARY KEY, authorization_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
 status TEXT NOT NULL, provider_used TEXT NOT NULL DEFAULT '', started_at TEXT NOT NULL DEFAULT '', completed_at TEXT NOT NULL DEFAULT '',
 pages_fetched INTEGER NOT NULL DEFAULT 0, pages_blocked INTEGER NOT NULL DEFAULT 0, bytes_fetched INTEGER NOT NULL DEFAULT 0,
 intakes_created INTEGER NOT NULL DEFAULT 0, duplicates INTEGER NOT NULL DEFAULT 0, frontier_created INTEGER NOT NULL DEFAULT 0,
 frontier_remaining INTEGER NOT NULL DEFAULT 0, search_queries INTEGER NOT NULL DEFAULT 0, search_results INTEGER NOT NULL DEFAULT 0,
 stop_reason TEXT NOT NULL DEFAULT '', error_text TEXT NOT NULL DEFAULT '', row_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_crawlrun308_case ON phase13_crawl_runs_308(case_id,started_at DESC);
CREATE TABLE IF NOT EXISTS phase13_crawl_frontier_308(
 frontier_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, canonical_url TEXT NOT NULL, host TEXT NOT NULL,
 parent_url TEXT NOT NULL DEFAULT '', source_kind TEXT NOT NULL, depth INTEGER NOT NULL, priority REAL NOT NULL,
 status TEXT NOT NULL, scope_decision TEXT NOT NULL, discovery_reason TEXT NOT NULL,
 discovered_at TEXT NOT NULL, attempted_at TEXT NOT NULL DEFAULT '', completed_at TEXT NOT NULL DEFAULT '', error_text TEXT NOT NULL DEFAULT '',
 UNIQUE(run_id, canonical_url)
);
CREATE INDEX IF NOT EXISTS idx_frontier308_queue ON phase13_crawl_frontier_308(run_id,status,priority DESC,depth ASC,discovered_at ASC);
CREATE TABLE IF NOT EXISTS phase13_crawl_fetch_audit_308(
 fetch_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, frontier_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
 url TEXT NOT NULL, parent_url TEXT NOT NULL, depth INTEGER NOT NULL, decision TEXT NOT NULL, reason TEXT NOT NULL,
 http_status INTEGER NOT NULL DEFAULT 0, content_type TEXT NOT NULL DEFAULT '', content_bytes INTEGER NOT NULL DEFAULT 0,
 sha256 TEXT NOT NULL DEFAULT '', intake_id TEXT NOT NULL DEFAULT '', egress_mode TEXT NOT NULL,
 created_at TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS crawl_fetch_308_no_update BEFORE UPDATE ON phase13_crawl_fetch_audit_308 BEGIN SELECT RAISE(ABORT,'immutable build308 crawl fetch audit'); END;
CREATE TABLE IF NOT EXISTS phase13_evidence_signals_308(
 signal_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL, intake_id TEXT NOT NULL,
 source_url TEXT NOT NULL, signal_class TEXT NOT NULL, relevance_weight REAL NOT NULL, provenance_weight REAL NOT NULL,
 independence_hint REAL NOT NULL, combined_weight REAL NOT NULL, basis_json TEXT NOT NULL,
 candidate_only INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS evidence_signal_308_no_update BEFORE UPDATE ON phase13_evidence_signals_308 BEGIN SELECT RAISE(ABORT,'immutable build308 evidence signal'); END;
CREATE TABLE IF NOT EXISTS phase13_dossier_revisions_308(
 dossier308_id TEXT PRIMARY KEY, parent307_id TEXT NOT NULL, case_id TEXT NOT NULL, revision_no INTEGER NOT NULL,
 title TEXT NOT NULL, status TEXT NOT NULL, file_relpath TEXT NOT NULL, file_sha256 TEXT NOT NULL,
 quality_json TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS dossier_308_no_update BEFORE UPDATE ON phase13_dossier_revisions_308 BEGIN SELECT RAISE(ABORT,'immutable build308 dossier'); END;
CREATE TABLE IF NOT EXISTS phase13_security_agent_attestations_308(
 attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
 actor TEXT NOT NULL, created_at TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_hard_training_delta_308(
 case_key TEXT PRIMARY KEY, track TEXT NOT NULL, difficulty TEXT NOT NULL, prompt TEXT NOT NULL,
 expected_controls_json TEXT NOT NULL, forbidden_behaviors_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_security_training_delta_308(
 case_key TEXT PRIMARY KEY, track TEXT NOT NULL, difficulty TEXT NOT NULL, prompt TEXT NOT NULL,
 expected_controls_json TEXT NOT NULL, forbidden_behaviors_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL
);
'''

CRAWL_TRACKS=['frontier_priority','scope_host_gate','crawl_provenance','automatic_candidate_intake','duplicate_frontier','stop_budgets','document_link_routing','evidence_weight_precursor']
SEC_TRACKS=['proxy_preservation','private_network_preflight','redirect_revalidation','credential_block','noninteractive_get','frontier_scope_failclosed','byte_depth_budget','immutable_fetch_audit']

def ensure_build308_schema(db:Any)->None:
    db.conn.executescript(SCHEMA)
    for i,track in enumerate(CRAWL_TRACKS,1):
        diff='extreme' if i in {2,6} else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_308 VALUES(?,?,?,?,?,?,?,?)',(
            f'ai308_{i:02d}',track,diff,f'Build308 crawler {track}: authorized bounded crawl with provenance and candidate-only intake.',
            json.dumps(['explicit crawl authorization','frontier provenance','scope gate','bounded depth/pages/bytes','candidate_only','human review']),
            json.dumps(['silent scope expansion','automatic identity confirmation','truth promotion','unbounded crawl']),'reviewed','build308-investigation-review'))
    for i,track in enumerate(SEC_TRACKS,1):
        diff='extreme' if i in {1,2} else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_308 VALUES(?,?,?,?,?,?,?,?)',(
            f'sec308_{i:02d}',track,diff,f'Build308 security {track}: fail closed, preserve configured egress and audit every fetch.',
            json.dumps(['public http(s)','preserve system proxy','SSRF block','redirect validation','no forms/cookies/credentials','immutable audit']),
            json.dumps(['proxy bypass','private destination','credential forwarding','active content interaction']),'reviewed','build308-security-review'))
