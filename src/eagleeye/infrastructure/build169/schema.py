from __future__ import annotations
from typing import Any

SCHEMA_169 = r'''
CREATE TABLE IF NOT EXISTS hardening_audits_169(
 audit_id TEXT PRIMARY KEY, scope TEXT NOT NULL, status TEXT NOT NULL,
 score REAL NOT NULL, findings_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opsec_findings_169(
 finding_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, category TEXT NOT NULL,
 severity TEXT NOT NULL, component TEXT NOT NULL, description TEXT NOT NULL,
 remediation TEXT NOT NULL, status TEXT NOT NULL, evidence_json TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_guardrail_assessments_169(
 assessment_id TEXT PRIMARY KEY, case_id TEXT, task_type TEXT NOT NULL,
 input_sha256 TEXT NOT NULL, sanitized_context_json TEXT NOT NULL,
 recommendations_json TEXT NOT NULL, guardrails_json TEXT NOT NULL,
 status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ux_hardening_manifest_169(
 manifest_id TEXT PRIMARY KEY, version TEXT NOT NULL, sections_json TEXT NOT NULL,
 shortcuts_json TEXT NOT NULL, hidden_legacy_json TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS release_gates_169(
 gate_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, status TEXT NOT NULL,
 blockers_json TEXT NOT NULL, approvals_json TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runtime_cleanup_checks_169(
 check_id TEXT PRIMARY KEY, active_threads INTEGER NOT NULL,
 non_daemon_threads INTEGER NOT NULL, open_jobs INTEGER NOT NULL,
 db_ok INTEGER NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_opsec169_audit ON opsec_findings_169(audit_id,severity,status);
CREATE INDEX IF NOT EXISTS idx_ai169_case ON ai_guardrail_assessments_169(case_id,created_at);
CREATE INDEX IF NOT EXISTS idx_gate169_audit ON release_gates_169(audit_id,created_at);
'''

def ensure_build169_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_169)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','169.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','169.0')")
    db.conn.commit()
