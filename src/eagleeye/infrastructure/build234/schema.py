from __future__ import annotations
from typing import Any

SCHEMA_234 = r'''
CREATE TABLE IF NOT EXISTS remediation_plans_234 (
  plan_id TEXT PRIMARY KEY,
  ticket_id TEXT NOT NULL UNIQUE,
  cycle_id TEXT NOT NULL,
  campaign_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  metric_key TEXT NOT NULL,
  severity TEXT NOT NULL,
  root_cause TEXT NOT NULL,
  change_summary TEXT NOT NULL,
  verification_strategy TEXT NOT NULL,
  impacted_cases_json TEXT NOT NULL DEFAULT '[]',
  guardrail_metrics_json TEXT NOT NULL DEFAULT '[]',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(ticket_id) REFERENCES remediation_tickets_233(ticket_id),
  FOREIGN KEY(cycle_id) REFERENCES qualification_cycles_233(cycle_id),
  FOREIGN KEY(campaign_id) REFERENCES qualification_campaigns_233(campaign_id),
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(severity IN ('critical','high','medium','low'))
);
CREATE INDEX IF NOT EXISTS idx_plan234_case ON remediation_plans_234(case_id,severity,created_at);

CREATE TABLE IF NOT EXISTS remediation_plan_reviews_234 (
  review_id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  note TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(plan_id) REFERENCES remediation_plans_234(plan_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(decision IN ('approved','rejected'))
);

CREATE TABLE IF NOT EXISTS remediation_reruns_234 (
  rerun_id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL,
  ticket_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  suite_id TEXT NOT NULL,
  source_cycle_id TEXT NOT NULL,
  source_candidate_scorecard_id TEXT NOT NULL,
  baseline_scorecard_id TEXT NOT NULL,
  trial_id TEXT NOT NULL UNIQUE,
  target_metric TEXT NOT NULL,
  submitted_by TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(plan_id) REFERENCES remediation_plans_234(plan_id),
  FOREIGN KEY(ticket_id) REFERENCES remediation_tickets_233(ticket_id),
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(suite_id) REFERENCES qualification_suites_232(suite_id),
  FOREIGN KEY(source_cycle_id) REFERENCES qualification_cycles_233(cycle_id),
  FOREIGN KEY(source_candidate_scorecard_id) REFERENCES qualification_scorecards_232(scorecard_id),
  FOREIGN KEY(baseline_scorecard_id) REFERENCES qualification_scorecards_232(scorecard_id),
  FOREIGN KEY(trial_id) REFERENCES qualification_trials_232(trial_id)
);
CREATE INDEX IF NOT EXISTS idx_rerun234_plan ON remediation_reruns_234(plan_id,submitted_at);

CREATE TABLE IF NOT EXISTS remediation_rerun_reviews_234 (
  rerun_review_id TEXT PRIMARY KEY,
  rerun_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  note TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(rerun_id) REFERENCES remediation_reruns_234(rerun_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(decision IN ('accepted','rejected'))
);

CREATE TABLE IF NOT EXISTS remediation_verifications_234 (
  verification_id TEXT PRIMARY KEY,
  rerun_id TEXT NOT NULL UNIQUE,
  plan_id TEXT NOT NULL,
  ticket_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  target_metric TEXT NOT NULL,
  scorecard_id TEXT NOT NULL,
  comparison_id TEXT NOT NULL,
  target_gate_pass INTEGER NOT NULL,
  all_quality_gates_pass INTEGER NOT NULL,
  collateral_non_regression INTEGER NOT NULL,
  comparable_environment INTEGER NOT NULL,
  target_before REAL NOT NULL,
  target_after REAL NOT NULL,
  guardrail_deltas_json TEXT NOT NULL,
  failed_guardrails_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(rerun_id) REFERENCES remediation_reruns_234(rerun_id),
  FOREIGN KEY(plan_id) REFERENCES remediation_plans_234(plan_id),
  FOREIGN KEY(ticket_id) REFERENCES remediation_tickets_233(ticket_id),
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(scorecard_id) REFERENCES qualification_scorecards_232(scorecard_id),
  FOREIGN KEY(comparison_id) REFERENCES qualification_comparisons_232(comparison_id),
  CHECK(target_gate_pass IN (0,1)),
  CHECK(all_quality_gates_pass IN (0,1)),
  CHECK(collateral_non_regression IN (0,1)),
  CHECK(comparable_environment IN (0,1)),
  CHECK(status IN ('pass_pending_review','needs_revision','incomplete'))
);
CREATE INDEX IF NOT EXISTS idx_verify234_ticket ON remediation_verifications_234(ticket_id,created_at);

CREATE TABLE IF NOT EXISTS remediation_verification_reviews_234 (
  verification_review_id TEXT PRIMARY KEY,
  verification_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(verification_id) REFERENCES remediation_verifications_234(verification_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(decision IN ('resolved','needs_revision','rejected'))
);

CREATE TABLE IF NOT EXISTS build234_events (
  event_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_events234_case ON build234_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_plan234_no_update BEFORE UPDATE ON remediation_plans_234 BEGIN SELECT RAISE(ABORT,'remediation_plans_234 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_plan234_no_delete BEFORE DELETE ON remediation_plans_234 BEGIN SELECT RAISE(ABORT,'remediation_plans_234 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_planreview234_no_update BEFORE UPDATE ON remediation_plan_reviews_234 BEGIN SELECT RAISE(ABORT,'remediation_plan_reviews_234 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_planreview234_no_delete BEFORE DELETE ON remediation_plan_reviews_234 BEGIN SELECT RAISE(ABORT,'remediation_plan_reviews_234 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_rerun234_no_update BEFORE UPDATE ON remediation_reruns_234 BEGIN SELECT RAISE(ABORT,'remediation_reruns_234 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_rerun234_no_delete BEFORE DELETE ON remediation_reruns_234 BEGIN SELECT RAISE(ABORT,'remediation_reruns_234 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_rerunreview234_no_update BEFORE UPDATE ON remediation_rerun_reviews_234 BEGIN SELECT RAISE(ABORT,'remediation_rerun_reviews_234 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_rerunreview234_no_delete BEFORE DELETE ON remediation_rerun_reviews_234 BEGIN SELECT RAISE(ABORT,'remediation_rerun_reviews_234 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_verify234_no_update BEFORE UPDATE ON remediation_verifications_234 BEGIN SELECT RAISE(ABORT,'remediation_verifications_234 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_verify234_no_delete BEFORE DELETE ON remediation_verifications_234 BEGIN SELECT RAISE(ABORT,'remediation_verifications_234 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_verifyreview234_no_update BEFORE UPDATE ON remediation_verification_reviews_234 BEGIN SELECT RAISE(ABORT,'remediation_verification_reviews_234 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_verifyreview234_no_delete BEFORE DELETE ON remediation_verification_reviews_234 BEGIN SELECT RAISE(ABORT,'remediation_verification_reviews_234 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_events234_no_update BEFORE UPDATE ON build234_events BEGIN SELECT RAISE(ABORT,'build234_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events234_no_delete BEFORE DELETE ON build234_events BEGIN SELECT RAISE(ABORT,'build234_events is immutable'); END;
'''


def ensure_build234_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_234)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','234.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','234.0')")
    db.conn.commit()
