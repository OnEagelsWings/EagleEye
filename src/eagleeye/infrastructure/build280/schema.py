from __future__ import annotations
import hashlib, json
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS phase11_release_runs_280(
 run_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,qualification_brief_id TEXT NOT NULL,simulation_id TEXT NOT NULL,
 stage_pass_count INTEGER NOT NULL,stage_count INTEGER NOT NULL,agent_pass_count INTEGER NOT NULL,agent_count INTEGER NOT NULL,
 sqlite_integrity TEXT NOT NULL,foreign_key_violations INTEGER NOT NULL,darkweb_code_hits INTEGER NOT NULL,
 automatic_deployment INTEGER NOT NULL,release_candidate_status TEXT NOT NULL,created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phase11_release_stages_280(
 stage_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,stage_key TEXT NOT NULL,status TEXT NOT NULL,critical INTEGER NOT NULL,
 metrics_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL,UNIQUE(run_id,stage_key)
);
CREATE TABLE IF NOT EXISTS phase11_release_reviews_280(
 review_id TEXT PRIMARY KEY,run_id TEXT NOT NULL UNIQUE,case_id TEXT NOT NULL,decision TEXT NOT NULL,rationale TEXT NOT NULL,
 reviewer TEXT NOT NULL,reviewed_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_release_benchmarks_280(
 benchmark_id TEXT PRIMARY KEY,task_family TEXT NOT NULL,expected_decision TEXT NOT NULL,review_status TEXT NOT NULL,
 reviewed_by TEXT NOT NULL,row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opsec_release_controls_280(
 control_id TEXT PRIMARY KEY,control_name TEXT NOT NULL,required_value TEXT NOT NULL,review_status TEXT NOT NULL,
 verified_by TEXT NOT NULL,row_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS trg_rc280_no_update BEFORE UPDATE ON phase11_release_runs_280 BEGIN SELECT RAISE(ABORT,'phase11_release_runs_280 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_rc280_no_delete BEFORE DELETE ON phase11_release_runs_280 BEGIN SELECT RAISE(ABORT,'phase11_release_runs_280 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_rcstage280_no_update BEFORE UPDATE ON phase11_release_stages_280 BEGIN SELECT RAISE(ABORT,'phase11_release_stages_280 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_rcstage280_no_delete BEFORE DELETE ON phase11_release_stages_280 BEGIN SELECT RAISE(ABORT,'phase11_release_stages_280 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_rcreview280_no_update BEFORE UPDATE ON phase11_release_reviews_280 BEGIN SELECT RAISE(ABORT,'phase11_release_reviews_280 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_rcreview280_no_delete BEFORE DELETE ON phase11_release_reviews_280 BEGIN SELECT RAISE(ABORT,'phase11_release_reviews_280 immutable'); END;
"""
AI = [
('ai280_01','full_case_release_qualification','require_all_stage_pass'),('ai280_02','multi_agent_release_qualification','require_10_of_10'),
('ai280_03','counterevidence_preservation','preserve'),('ai280_04','redteam_survival','preserve'),('ai280_05','assertion_ceiling','preserve'),
('ai280_06','source_independence','preserve'),('ai280_07','document_provenance','preserve'),('ai280_08','cross_case_public_knowledge','scope_limited'),
('ai280_09','reasoning_ledger','immutable'),('ai280_10','training_governance','pending_only'),('ai280_11','model_activation','human_gate'),
('ai280_12','publication','not_authorized_by_rc')]
OP = [
('op280_01','direct_agent_egress_zero','0'),('op280_02','automatic_publication_zero','0'),('op280_03','automatic_upload_zero','0'),
('op280_04','automatic_contact_zero','0'),('op280_05','cross_case_scope_violation_zero','0'),('op280_06','private_identifier_leak_zero','0'),
('op280_07','secret_leak_zero','0'),('op280_08','route_reconfiguration_zero','0'),('op280_09','recursive_spawn_zero','0'),
('op280_10','prompt_injection_authority_zero','0'),('op280_11','ephemeral_profile_residue_zero','0'),('op280_12','darkweb_collection_zero','0')]

def _h(v):
    return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def ensure_build280_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA)
    for row in AI:
        db.conn.execute('INSERT OR IGNORE INTO ai_release_benchmarks_280 VALUES(?,?,?,?,?,?)', (*row,'reviewed','build280-release-review',_h(row)))
    for row in OP:
        db.conn.execute('INSERT OR IGNORE INTO opsec_release_controls_280 VALUES(?,?,?,?,?,?)', (*row,'verified','build280-opsec-review',_h(row)))
    for key,note in [
        ('phase11_release_candidate_280','Final Phase-11 release-candidate gate over Build279 full-case qualification.'),
        ('phase11_freeze_280','Immutable Phase-11 baseline for Build281+.'),
        ('phase12_boundary_280','Dark-Web collection remains absent in Build280 and deferred to Phase12.')]:
        db.conn.execute('INSERT OR REPLACE INTO capability_manifest_2601(capability_key,introduced_build,status,contract_kind,notes) VALUES(?,?,?,?,?)',(key,'280','active','release_contract',note))
    for k,v in (('schema_version','280.0'),('application_build','280.0'),('phase11_status','release_candidate')):
        db.conn.execute('INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)',(k,v))
    db.conn.commit()
