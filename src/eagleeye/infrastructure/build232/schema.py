from __future__ import annotations
from typing import Any

SCHEMA_232 = r'''
CREATE TABLE IF NOT EXISTS qualification_suites_232 (
  suite_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  title TEXT NOT NULL,
  suite_version INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'frozen',
  case_count INTEGER NOT NULL DEFAULT 0,
  fixture_kind TEXT NOT NULL DEFAULT 'synthetic_redacted',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(status='frozen'),
  UNIQUE(case_id,suite_version)
);

CREATE TABLE IF NOT EXISTS qualification_cases_232 (
  qualification_case_id TEXT PRIMARY KEY,
  suite_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  metric_family TEXT NOT NULL,
  title TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'und',
  cross_script INTEGER NOT NULL DEFAULT 0,
  input_json TEXT NOT NULL DEFAULT '{}',
  expected_json TEXT NOT NULL DEFAULT '{}',
  weight REAL NOT NULL DEFAULT 1.0,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(suite_id) REFERENCES qualification_suites_232(suite_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(metric_family IN ('retrieval_precision','counterevidence_recall','identity_resolution','grounding','opsec','dialogue_correction')),
  CHECK(cross_script IN (0,1)),
  CHECK(weight > 0),
  UNIQUE(suite_id,ordinal)
);
CREATE INDEX IF NOT EXISTS idx_qual_cases_232_suite ON qualification_cases_232(suite_id,ordinal);

CREATE TABLE IF NOT EXISTS qualification_trials_232 (
  trial_id TEXT PRIMARY KEY,
  suite_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  system_label TEXT NOT NULL,
  build_label TEXT NOT NULL,
  result_count INTEGER NOT NULL DEFAULT 0,
  environment_json TEXT NOT NULL DEFAULT '{}',
  environment_sha256 TEXT NOT NULL,
  results_json TEXT NOT NULL DEFAULT '{}',
  submitted_by TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(suite_id) REFERENCES qualification_suites_232(suite_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_qual_trials_232_suite ON qualification_trials_232(suite_id,system_label,submitted_at);

CREATE TABLE IF NOT EXISTS qualification_trial_reviews_232 (
  review_id TEXT PRIMARY KEY,
  trial_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  note TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(trial_id) REFERENCES qualification_trials_232(trial_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(decision IN ('accepted','rejected'))
);

CREATE TABLE IF NOT EXISTS qualification_scorecards_232 (
  scorecard_id TEXT PRIMARY KEY,
  trial_id TEXT NOT NULL UNIQUE,
  suite_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  system_label TEXT NOT NULL,
  build_label TEXT NOT NULL,
  metrics_json TEXT NOT NULL,
  per_case_json TEXT NOT NULL,
  complete INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(trial_id) REFERENCES qualification_trials_232(trial_id) ON DELETE CASCADE,
  FOREIGN KEY(suite_id) REFERENCES qualification_suites_232(suite_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(complete IN (0,1))
);

CREATE TABLE IF NOT EXISTS qualification_comparisons_232 (
  comparison_id TEXT PRIMARY KEY,
  suite_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  baseline_scorecard_id TEXT NOT NULL,
  candidate_scorecard_id TEXT NOT NULL,
  gates_json TEXT NOT NULL,
  deltas_json TEXT NOT NULL,
  status TEXT NOT NULL,
  comparable_environment INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(suite_id) REFERENCES qualification_suites_232(suite_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(baseline_scorecard_id) REFERENCES qualification_scorecards_232(scorecard_id),
  FOREIGN KEY(candidate_scorecard_id) REFERENCES qualification_scorecards_232(scorecard_id),
  CHECK(status IN ('pass_pending_review','needs_revision','incomplete')),
  CHECK(comparable_environment IN (0,1))
);

CREATE TABLE IF NOT EXISTS qualification_comparison_reviews_232 (
  comparison_review_id TEXT PRIMARY KEY,
  comparison_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(comparison_id) REFERENCES qualification_comparisons_232(comparison_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(decision IN ('qualified','needs_revision','rejected'))
);

CREATE TABLE IF NOT EXISTS build232_events (
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
CREATE INDEX IF NOT EXISTS idx_events232_case ON build232_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_qual_suites232_no_update BEFORE UPDATE ON qualification_suites_232 BEGIN SELECT RAISE(ABORT,'qualification_suites_232 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_qual_suites232_no_delete BEFORE DELETE ON qualification_suites_232 BEGIN SELECT RAISE(ABORT,'qualification_suites_232 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_qual_cases232_no_update BEFORE UPDATE ON qualification_cases_232 BEGIN SELECT RAISE(ABORT,'qualification_cases_232 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_qual_cases232_no_delete BEFORE DELETE ON qualification_cases_232 BEGIN SELECT RAISE(ABORT,'qualification_cases_232 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_qual_trials232_no_update BEFORE UPDATE ON qualification_trials_232 BEGIN SELECT RAISE(ABORT,'qualification_trials_232 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_qual_trials232_no_delete BEFORE DELETE ON qualification_trials_232 BEGIN SELECT RAISE(ABORT,'qualification_trials_232 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_qual_trial_reviews232_no_update BEFORE UPDATE ON qualification_trial_reviews_232 BEGIN SELECT RAISE(ABORT,'qualification_trial_reviews_232 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_qual_trial_reviews232_no_delete BEFORE DELETE ON qualification_trial_reviews_232 BEGIN SELECT RAISE(ABORT,'qualification_trial_reviews_232 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_qual_scorecards232_no_update BEFORE UPDATE ON qualification_scorecards_232 BEGIN SELECT RAISE(ABORT,'qualification_scorecards_232 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_qual_scorecards232_no_delete BEFORE DELETE ON qualification_scorecards_232 BEGIN SELECT RAISE(ABORT,'qualification_scorecards_232 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_qual_comparisons232_no_update BEFORE UPDATE ON qualification_comparisons_232 BEGIN SELECT RAISE(ABORT,'qualification_comparisons_232 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_qual_comparisons232_no_delete BEFORE DELETE ON qualification_comparisons_232 BEGIN SELECT RAISE(ABORT,'qualification_comparisons_232 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_qual_comp_reviews232_no_update BEFORE UPDATE ON qualification_comparison_reviews_232 BEGIN SELECT RAISE(ABORT,'qualification_comparison_reviews_232 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_qual_comp_reviews232_no_delete BEFORE DELETE ON qualification_comparison_reviews_232 BEGIN SELECT RAISE(ABORT,'qualification_comparison_reviews_232 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_events232_no_update BEFORE UPDATE ON build232_events BEGIN SELECT RAISE(ABORT,'build232_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events232_no_delete BEFORE DELETE ON build232_events BEGIN SELECT RAISE(ABORT,'build232_events is immutable'); END;
'''


def ensure_build232_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_232)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','232.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','232.0')")
    db.conn.commit()
