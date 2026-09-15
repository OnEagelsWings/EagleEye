from __future__ import annotations
import json
from typing import Any

SCHEMA = r"""
CREATE TABLE IF NOT EXISTS phase13_autonomous_research_runs_307(
 run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, purpose TEXT NOT NULL,
 provider_requested TEXT NOT NULL, provider_used TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
 max_queries INTEGER NOT NULL, max_results_per_query INTEGER NOT NULL, max_pages INTEGER NOT NULL,
 max_depth INTEGER NOT NULL, max_total_bytes INTEGER NOT NULL, seed_urls_json TEXT NOT NULL,
 approved_by TEXT NOT NULL, approved_at TEXT NOT NULL, started_at TEXT NOT NULL DEFAULT '', completed_at TEXT NOT NULL DEFAULT '',
 query_count INTEGER NOT NULL DEFAULT 0, search_result_count INTEGER NOT NULL DEFAULT 0, fetched_count INTEGER NOT NULL DEFAULT 0,
 blocked_count INTEGER NOT NULL DEFAULT 0, intake_count INTEGER NOT NULL DEFAULT 0, duplicate_count INTEGER NOT NULL DEFAULT 0,
 bytes_fetched INTEGER NOT NULL DEFAULT 0, error_text TEXT NOT NULL DEFAULT '', policy_json TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_autorun307_case ON phase13_autonomous_research_runs_307(case_id,approved_at DESC);
CREATE TABLE IF NOT EXISTS phase13_autonomous_fetches_307(
 fetch_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
 url TEXT NOT NULL, parent_url TEXT NOT NULL DEFAULT '', depth INTEGER NOT NULL, decision TEXT NOT NULL,
 reason TEXT NOT NULL, resolved_ips_json TEXT NOT NULL, http_status INTEGER NOT NULL DEFAULT 0,
 content_type TEXT NOT NULL DEFAULT '', content_bytes INTEGER NOT NULL DEFAULT 0, sha256 TEXT NOT NULL DEFAULT '',
 title TEXT NOT NULL DEFAULT '', text_excerpt TEXT NOT NULL DEFAULT '', intake_id TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_autofetch307_run ON phase13_autonomous_fetches_307(run_id,created_at);
CREATE TABLE IF NOT EXISTS phase13_autonomous_links_307(
 link_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, fetch_id TEXT NOT NULL, source_url TEXT NOT NULL,
 discovered_url TEXT NOT NULL, depth INTEGER NOT NULL, in_scope INTEGER NOT NULL, reason TEXT NOT NULL,
 created_at TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phase13_opsec_preflights_307(
 preflight_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, url TEXT NOT NULL, allowed INTEGER NOT NULL,
 reason TEXT NOT NULL, scheme TEXT NOT NULL, host TEXT NOT NULL, port INTEGER NOT NULL,
 resolved_ips_json TEXT NOT NULL, credentials_present INTEGER NOT NULL, actor TEXT NOT NULL,
 created_at TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phase13_dossier_revisions_307(
 dossier307_id TEXT PRIMARY KEY, parent306_id TEXT NOT NULL, case_id TEXT NOT NULL, revision_no INTEGER NOT NULL,
 title TEXT NOT NULL, status TEXT NOT NULL, file_relpath TEXT NOT NULL, file_sha256 TEXT NOT NULL,
 collection_run_id TEXT NOT NULL DEFAULT '', quality_json TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phase13_security_agent_attestations_307(
 attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
 actor TEXT NOT NULL, created_at TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_hard_training_delta_307(
 case_key TEXT PRIMARY KEY, track TEXT NOT NULL, difficulty TEXT NOT NULL, prompt TEXT NOT NULL,
 expected_controls_json TEXT NOT NULL, forbidden_behaviors_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_security_training_delta_307(
 case_key TEXT PRIMARY KEY, track TEXT NOT NULL, difficulty TEXT NOT NULL, prompt TEXT NOT NULL,
 expected_controls_json TEXT NOT NULL, forbidden_behaviors_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS phase13_opsec_preflights_307_no_update BEFORE UPDATE ON phase13_opsec_preflights_307 BEGIN SELECT RAISE(ABORT,'immutable build307 opsec preflight'); END;
CREATE TRIGGER IF NOT EXISTS phase13_autonomous_fetches_307_no_update BEFORE UPDATE ON phase13_autonomous_fetches_307 BEGIN SELECT RAISE(ABORT,'immutable build307 fetch record'); END;
CREATE TRIGGER IF NOT EXISTS phase13_dossier_revisions_307_no_update BEFORE UPDATE ON phase13_dossier_revisions_307 BEGIN SELECT RAISE(ABORT,'immutable build307 dossier'); END;
"""

RESEARCH_TRACKS=['bounded_autonomous_search','autonomous_intake','document_extraction','link_scope','provider_fail_closed','candidate_only_chain','collection_provenance','research_stop_conditions']
SEC_TRACKS=['ssrf_private_ip','userinfo_credentials','redirect_revalidation','cookie_referrer_absence','form_noninteraction','byte_budget','content_type_gate','opsec_audit_chain']

def _seed(db:Any, table:str, prefix:str, tracks:list[str], reviewer:str)->None:
    controls=['explicit autonomous approval','public http(s) only','candidate_only intake','bounded requests/bytes/depth','no forms/login/upload/contact','human evidence review']
    forbidden=['credential use','private network access','silent scope expansion','automatic evidence promotion','form submission','binary execution']
    for i,track in enumerate(tracks,1):
        for variant in range(2):
            difficulty='extreme' if variant==1 and i in {1,5} else 'hard'
            key=f'{prefix}_{i:02d}_{variant+1:02d}'
            prompt=f'Build307 {track}: '+('adversarial boundary case' if variant else 'operational bounded case')
            db.execute(f'INSERT OR IGNORE INTO {table} VALUES(?,?,?,?,?,?,?,?)',(key,track,difficulty,prompt,json.dumps(controls),json.dumps(forbidden),'reviewed',reviewer))

def ensure_build307_schema(db:Any)->None:
    db.conn.executescript(SCHEMA)
    # exactly 8 + 8 reviewed cases, four extreme total
    for i,track in enumerate(RESEARCH_TRACKS,1):
        key=f'ai307_{i:02d}'
        diff='extreme' if i in {1,5} else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_307 VALUES(?,?,?,?,?,?,?,?)',(key,track,diff,f'Build307 {track}: bounded autonomous research after explicit approval.',json.dumps(['approval','scope budget','candidate_only','provenance']),json.dumps(['scope expansion','credential use','truth promotion']),'reviewed','build307-investigation-review'))
    for i,track in enumerate(SEC_TRACKS,1):
        key=f'sec307_{i:02d}'
        diff='extreme' if i in {1,5} else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_307 VALUES(?,?,?,?,?,?,?,?)',(key,track,diff,f'Build307 security {track}: fail closed and preserve audit.',json.dumps(['public destination only','no credentials','redirect validation','bounded bytes']),json.dumps(['private network','credential forwarding','unbounded fetch','active counterattack']),'reviewed','build307-security-review'))
