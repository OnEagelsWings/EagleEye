from __future__ import annotations
import hashlib, json
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS phase12_missions_281(
 mission_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, objective TEXT NOT NULL, mission_type TEXT NOT NULL,
 autonomy_mode TEXT NOT NULL, max_cycles INTEGER NOT NULL, max_queries INTEGER NOT NULL, max_results INTEGER NOT NULL,
 status TEXT NOT NULL, approved_by TEXT NOT NULL DEFAULT '', approved_at TEXT NOT NULL DEFAULT '', created_by TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phase12_mission_steps_281(
 step_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, step_no INTEGER NOT NULL, step_type TEXT NOT NULL,
 surface TEXT NOT NULL, description TEXT NOT NULL, requires_external_access INTEGER NOT NULL,
 status TEXT NOT NULL, result_ref TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 UNIQUE(mission_id,step_no)
);
CREATE TABLE IF NOT EXISTS phase12_mission_events_281(
 event_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, event_type TEXT NOT NULL, actor TEXT NOT NULL,
 details_json TEXT NOT NULL, created_at TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS darkweb_artifacts_281(
 artifact_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, mission_id TEXT NOT NULL DEFAULT '', source_locator TEXT NOT NULL,
 locator_class TEXT NOT NULL, title TEXT NOT NULL, observed_text TEXT NOT NULL, observation_mode TEXT NOT NULL,
 content_sha256 TEXT NOT NULL, risk_class TEXT NOT NULL, review_status TEXT NOT NULL, created_by TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS darkweb_analysis_281(
 analysis_id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL, case_id TEXT NOT NULL, summary TEXT NOT NULL,
 indicator_count INTEGER NOT NULL, indicators_json TEXT NOT NULL, caveats_json TEXT NOT NULL,
 prohibited_action_count INTEGER NOT NULL, analyst_status TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS infrastructure_snapshots_281(
 snapshot_id TEXT PRIMARY KEY, sqlite_integrity TEXT NOT NULL, foreign_key_violations INTEGER NOT NULL,
 db_write_ok INTEGER NOT NULL, free_disk_mb INTEGER NOT NULL, phase11_gate INTEGER NOT NULL,
 mission_controller_ready INTEGER NOT NULL, direct_darkweb_fetch_enabled INTEGER NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_phase12_benchmarks_281(
 benchmark_id TEXT PRIMARY KEY, task_family TEXT NOT NULL, expected_control TEXT NOT NULL, review_status TEXT NOT NULL,
 reviewed_by TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opsec_phase12_controls_281(
 control_id TEXT PRIMARY KEY, control_name TEXT NOT NULL, required_value TEXT NOT NULL, review_status TEXT NOT NULL,
 verified_by TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS trg_p12event281_no_update BEFORE UPDATE ON phase12_mission_events_281 BEGIN SELECT RAISE(ABORT,'phase12_mission_events_281 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_p12event281_no_delete BEFORE DELETE ON phase12_mission_events_281 BEGIN SELECT RAISE(ABORT,'phase12_mission_events_281 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_dwartifact281_no_update BEFORE UPDATE ON darkweb_artifacts_281 BEGIN SELECT RAISE(ABORT,'darkweb_artifacts_281 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_dwartifact281_no_delete BEFORE DELETE ON darkweb_artifacts_281 BEGIN SELECT RAISE(ABORT,'darkweb_artifacts_281 immutable'); END;
"""
AI = [
('ai281_01','mission_planning','plan_before_execute'),('ai281_02','explicit_ok_gate','required'),
('ai281_03','bounded_autonomy','budget_enforced'),('ai281_04','followup_planning','within_approved_scope'),
('ai281_05','source_surface_selection','web_local_darkweb_intake'),('ai281_06','evidence_first_analysis','required'),
('ai281_07','counterevidence','required'),('ai281_08','uncertainty','explicit'),
('ai281_09','darkweb_artifact_analysis','offline_first'),('ai281_10','provenance','hash_and_locator'),
('ai281_11','mission_stop_condition','budget_or_investigator'),('ai281_12','human_override','always_available'),
('ai281_13','cross_surface_fusion','planned'),('ai281_14','autonomous_external_contact','forbidden'),
('ai281_15','model_activation','human_gate'),('ai281_16','audit_ledger','immutable_events')]
OP = [
('op281_01','explicit_ok_before_autonomy','1'),('op281_02','mission_query_budget_enforced','1'),
('op281_03','mission_cycle_budget_enforced','1'),('op281_04','direct_darkweb_fetch_default','0'),
('op281_05','automatic_tor_reconfiguration','0'),('op281_06','automatic_identity_rotation','0'),
('op281_07','credential_use_or_bypass','0'),('op281_08','automatic_download_execution','0'),
('op281_09','automatic_purchase','0'),('op281_10','automatic_contact','0'),
('op281_11','automatic_publication','0'),('op281_12','cross_case_access','0'),
('op281_13','artifact_hash_required','1'),('op281_14','immutable_mission_event_log','1'),
('op281_15','investigator_stop_override','1'),('op281_16','phase11_baseline_preserved','1')]

def _h(v):
    return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def ensure_build281_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA)
    for row in AI:
        db.conn.execute('INSERT OR IGNORE INTO ai_phase12_benchmarks_281 VALUES(?,?,?,?,?,?)',(*row,'reviewed','build281-ai-review',_h(row)))
    for row in OP:
        db.conn.execute('INSERT OR IGNORE INTO opsec_phase12_controls_281 VALUES(?,?,?,?,?,?)',(*row,'verified','build281-opsec-review',_h(row)))
    caps=[
      ('phase12_mission_controller_281','Phase-12 bounded autonomous mission controller; explicit investigator OK required.'),
      ('darkweb_offline_intake_281','Hash-preserving dark-web/onion artifact intake and local analysis; no direct onion fetch.'),
      ('infrastructure_readiness_281','Operational health snapshot for SQLite, filesystem capacity and Phase-11 baseline.'),
      ('bounded_ai_autonomy_281','AI may plan and continue approved local analysis within mission budgets; human stop/override retained.')]
    for key,note in caps:
        db.conn.execute('INSERT OR REPLACE INTO capability_manifest_2601(capability_key,introduced_build,status,contract_kind,notes) VALUES(?,?,?,?,?)',(key,'281','active','phase12_contract',note))
    for k,v in (('schema_version','281.0'),('application_build','281.0'),('phase12_status','started'),('phase12_current_build','281.0')):
        db.conn.execute('INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)',(k,v))
    db.conn.commit()
