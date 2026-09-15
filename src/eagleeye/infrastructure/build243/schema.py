from __future__ import annotations
from typing import Any

SCHEMA_243 = r"""
CREATE TABLE IF NOT EXISTS opsec_profiles_243 (
  profile_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, revision_no INTEGER NOT NULL,
  identity_separation TEXT NOT NULL, browser_profile_mode TEXT NOT NULL, credential_scope TEXT NOT NULL,
  telemetry_mode TEXT NOT NULL, egress_mode TEXT NOT NULL, temp_data_mode TEXT NOT NULL,
  rationale TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  UNIQUE(case_id,revision_no), FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS opsec_profile_reviews_243 (
  review_id TEXT PRIMARY KEY, profile_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL, decision TEXT NOT NULL,
  rationale TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(profile_id) REFERENCES opsec_profiles_243(profile_id) ON DELETE CASCADE,
  CHECK(decision IN ('approved','rejected'))
);
CREATE TABLE IF NOT EXISTS opsec_profile_activations_243 (
  activation_id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, case_id TEXT NOT NULL, activated_by TEXT NOT NULL,
  activated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(profile_id) REFERENCES opsec_profiles_243(profile_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_opsec_profile243_case ON opsec_profiles_243(case_id,revision_no DESC);

CREATE TABLE IF NOT EXISTS opsec_egress_rules_243 (
  rule_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, destination_class TEXT NOT NULL, destination_ref TEXT NOT NULL,
  action TEXT NOT NULL, purpose TEXT NOT NULL, rationale TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL, FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(action IN ('allow','review','block'))
);
CREATE TABLE IF NOT EXISTS opsec_egress_rule_reviews_243 (
  review_id TEXT PRIMARY KEY, rule_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL, decision TEXT NOT NULL,
  rationale TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(rule_id) REFERENCES opsec_egress_rules_243(rule_id) ON DELETE CASCADE,
  CHECK(decision IN ('approved','rejected'))
);
CREATE INDEX IF NOT EXISTS idx_opsec_egress243_case ON opsec_egress_rules_243(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS opsec_secret_inventory_243 (
  secret_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, secret_ref TEXT NOT NULL, scope TEXT NOT NULL,
  storage_class TEXT NOT NULL, exposure_status TEXT NOT NULL, rotation_status TEXT NOT NULL,
  note TEXT NOT NULL, recorded_by TEXT NOT NULL, recorded_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  UNIQUE(case_id,secret_ref), FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(storage_class IN ('external_vault','os_keyring','app_reference_only')),
  CHECK(exposure_status IN ('unknown','clear','suspected','confirmed')),
  CHECK(rotation_status IN ('current','review_due','rotate_now'))
);

CREATE TABLE IF NOT EXISTS opsec_health_assessments_243 (
  assessment_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, profile_id TEXT NOT NULL,
  exposure_score REAL NOT NULL, efficiency_score REAL NOT NULL, risk_level TEXT NOT NULL,
  findings_json TEXT NOT NULL, recommendations_json TEXT NOT NULL, runtime_controls_json TEXT NOT NULL,
  assessed_by TEXT NOT NULL, assessed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(exposure_score>=0 AND exposure_score<=1), CHECK(efficiency_score>=0 AND efficiency_score<=1)
);
CREATE INDEX IF NOT EXISTS idx_opsec_health243_case ON opsec_health_assessments_243(case_id,assessed_at DESC);
CREATE TABLE IF NOT EXISTS opsec_health_reviews_243 (
  review_id TEXT PRIMARY KEY, assessment_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL, decision TEXT NOT NULL,
  rationale TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(assessment_id) REFERENCES opsec_health_assessments_243(assessment_id) ON DELETE CASCADE,
  CHECK(decision IN ('confirmed','false_positive','needs_context'))
);
CREATE TABLE IF NOT EXISTS opsec_runtime_state_243 (
  case_id TEXT PRIMARY KEY, mode TEXT NOT NULL, external_step_gate INTEGER NOT NULL DEFAULT 0,
  secret_use_gate INTEGER NOT NULL DEFAULT 0, last_assessment_id TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS opsec_training_links_243 (
  training_link_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, assessment_id TEXT NOT NULL UNIQUE,
  training_example_id TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(assessment_id) REFERENCES opsec_health_assessments_243(assessment_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS build243_events (
  event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL, object_type TEXT NOT NULL,
  object_id TEXT NOT NULL, actor TEXT NOT NULL, payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events243_case ON build243_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_profile243_no_update BEFORE UPDATE ON opsec_profiles_243 BEGIN SELECT RAISE(ABORT,'opsec_profiles_243 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_profile243_no_delete BEFORE DELETE ON opsec_profiles_243 BEGIN SELECT RAISE(ABORT,'opsec_profiles_243 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_profile_review243_no_update BEFORE UPDATE ON opsec_profile_reviews_243 BEGIN SELECT RAISE(ABORT,'opsec_profile_reviews_243 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_egress243_no_update BEFORE UPDATE ON opsec_egress_rules_243 BEGIN SELECT RAISE(ABORT,'opsec_egress_rules_243 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_egress_review243_no_update BEFORE UPDATE ON opsec_egress_rule_reviews_243 BEGIN SELECT RAISE(ABORT,'opsec_egress_rule_reviews_243 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_health243_no_update BEFORE UPDATE ON opsec_health_assessments_243 BEGIN SELECT RAISE(ABORT,'opsec_health_assessments_243 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_health_review243_no_update BEFORE UPDATE ON opsec_health_reviews_243 BEGIN SELECT RAISE(ABORT,'opsec_health_reviews_243 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events243_no_update BEFORE UPDATE ON build243_events BEGIN SELECT RAISE(ABORT,'build243_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events243_no_delete BEFORE DELETE ON build243_events BEGIN SELECT RAISE(ABORT,'build243_events is immutable'); END;
"""

def ensure_build243_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_243)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','243.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','243.0')")
    db.conn.commit()
