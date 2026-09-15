from __future__ import annotations
from typing import Any

SCHEMA_231 = r'''
CREATE TABLE IF NOT EXISTS source_outcomes_231 (
  outcome_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  query_id TEXT NOT NULL,
  source_key TEXT NOT NULL,
  country TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT 'und',
  target_type TEXT NOT NULL DEFAULT 'unknown',
  outcome_kind TEXT NOT NULL,
  precision_signal REAL NOT NULL DEFAULT 0.5,
  counterevidence_signal REAL NOT NULL DEFAULT 0.0,
  latency_ms INTEGER NOT NULL DEFAULT 0,
  error_signal REAL NOT NULL DEFAULT 0.0,
  opsec_incident INTEGER NOT NULL DEFAULT 0,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  origin_domains_json TEXT NOT NULL DEFAULT '[]',
  rationale TEXT NOT NULL,
  submitted_by TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(query_id) REFERENCES source_intelligence_queries_226(query_id) ON DELETE CASCADE,
  CHECK(outcome_kind IN ('useful','counterevidence','not_useful','error','opsec_blocked','deferred')),
  CHECK(precision_signal BETWEEN 0 AND 1),
  CHECK(counterevidence_signal BETWEEN 0 AND 1),
  CHECK(error_signal BETWEEN 0 AND 1),
  CHECK(opsec_incident IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_source_outcomes_231_source ON source_outcomes_231(source_key,country,language,target_type,submitted_at);
CREATE INDEX IF NOT EXISTS idx_source_outcomes_231_case ON source_outcomes_231(case_id,submitted_at);

CREATE TABLE IF NOT EXISTS source_outcome_reviews_231 (
  review_id TEXT PRIMARY KEY,
  outcome_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  review_note TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(outcome_id) REFERENCES source_outcomes_231(outcome_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(decision IN ('accepted','rejected'))
);
CREATE INDEX IF NOT EXISTS idx_outcome_reviews_231_case ON source_outcome_reviews_231(case_id,reviewed_at);

CREATE TABLE IF NOT EXISTS source_policy_snapshots_231 (
  policy_id TEXT PRIMARY KEY,
  policy_version INTEGER NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'draft',
  half_life_days INTEGER NOT NULL DEFAULT 120,
  min_sample INTEGER NOT NULL DEFAULT 5,
  max_adjustment REAL NOT NULL DEFAULT 0.10,
  max_domain_share REAL NOT NULL DEFAULT 0.55,
  max_reviewer_share REAL NOT NULL DEFAULT 0.60,
  exploration_rate REAL NOT NULL DEFAULT 0.08,
  accepted_outcome_count INTEGER NOT NULL DEFAULT 0,
  profile_count INTEGER NOT NULL DEFAULT 0,
  configuration_json TEXT NOT NULL DEFAULT '{}',
  created_case_id TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(created_case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(status='draft'),
  CHECK(half_life_days BETWEEN 7 AND 730),
  CHECK(min_sample BETWEEN 2 AND 100),
  CHECK(max_adjustment BETWEEN 0 AND 0.20),
  CHECK(max_domain_share BETWEEN 0.20 AND 1.0),
  CHECK(max_reviewer_share BETWEEN 0.20 AND 1.0),
  CHECK(exploration_rate BETWEEN 0 AND 0.25)
);
CREATE INDEX IF NOT EXISTS idx_policy_snapshots_231_created ON source_policy_snapshots_231(created_at,policy_version);

CREATE TABLE IF NOT EXISTS source_policy_reviews_231 (
  policy_review_id TEXT PRIMARY KEY,
  policy_id TEXT NOT NULL UNIQUE,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(policy_id) REFERENCES source_policy_snapshots_231(policy_id) ON DELETE CASCADE,
  CHECK(decision IN ('approved','rejected'))
);
CREATE INDEX IF NOT EXISTS idx_policy_reviews_231_decision ON source_policy_reviews_231(decision,reviewed_at);

CREATE TABLE IF NOT EXISTS source_learning_profiles_231 (
  profile_id TEXT PRIMARY KEY,
  policy_id TEXT NOT NULL,
  source_key TEXT NOT NULL,
  country TEXT NOT NULL DEFAULT '*',
  language TEXT NOT NULL DEFAULT '*',
  target_type TEXT NOT NULL DEFAULT '*',
  sample_size INTEGER NOT NULL DEFAULT 0,
  weighted_sample REAL NOT NULL DEFAULT 0.0,
  precision_score REAL NOT NULL DEFAULT 0.5,
  counterevidence_rate REAL NOT NULL DEFAULT 0.0,
  evidence_yield_rate REAL NOT NULL DEFAULT 0.0,
  error_rate REAL NOT NULL DEFAULT 0.0,
  latency_score REAL NOT NULL DEFAULT 0.5,
  opsec_incident_rate REAL NOT NULL DEFAULT 0.0,
  quality_score REAL NOT NULL DEFAULT 0.5,
  confidence REAL NOT NULL DEFAULT 0.0,
  score_delta REAL NOT NULL DEFAULT 0.0,
  hard_block_recommended INTEGER NOT NULL DEFAULT 0,
  poison_flags_json TEXT NOT NULL DEFAULT '[]',
  reviewer_distribution_json TEXT NOT NULL DEFAULT '{}',
  origin_distribution_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(policy_id) REFERENCES source_policy_snapshots_231(policy_id) ON DELETE CASCADE,
  CHECK(precision_score BETWEEN 0 AND 1),
  CHECK(counterevidence_rate BETWEEN 0 AND 1),
  CHECK(evidence_yield_rate BETWEEN 0 AND 1),
  CHECK(error_rate BETWEEN 0 AND 1),
  CHECK(latency_score BETWEEN 0 AND 1),
  CHECK(opsec_incident_rate BETWEEN 0 AND 1),
  CHECK(quality_score BETWEEN 0 AND 1),
  CHECK(confidence BETWEEN 0 AND 1),
  CHECK(hard_block_recommended IN (0,1)),
  UNIQUE(policy_id,source_key,country,language,target_type)
);
CREATE INDEX IF NOT EXISTS idx_learning_profiles_231_lookup ON source_learning_profiles_231(policy_id,source_key,country,language,target_type,sample_size);

CREATE TABLE IF NOT EXISTS source_exploration_proposals_231 (
  proposal_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  query_id TEXT NOT NULL,
  source_key TEXT NOT NULL,
  reason TEXT NOT NULL,
  current_rank INTEGER NOT NULL DEFAULT 0,
  current_score REAL NOT NULL DEFAULT 0.0,
  sample_size INTEGER NOT NULL DEFAULT 0,
  opsec_risk TEXT NOT NULL DEFAULT 'elevated',
  policy_id TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(query_id) REFERENCES source_intelligence_queries_226(query_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_exploration_231_case ON source_exploration_proposals_231(case_id,created_at);

CREATE TABLE IF NOT EXISTS source_exploration_reviews_231 (
  exploration_review_id TEXT PRIMARY KEY,
  proposal_id TEXT NOT NULL UNIQUE,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(proposal_id) REFERENCES source_exploration_proposals_231(proposal_id) ON DELETE CASCADE,
  CHECK(decision IN ('approved_for_manual_trial','rejected','deferred'))
);

CREATE TABLE IF NOT EXISTS build231_events (
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
CREATE INDEX IF NOT EXISTS idx_events231_case ON build231_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_outcomes231_no_update BEFORE UPDATE ON source_outcomes_231 BEGIN SELECT RAISE(ABORT,'source_outcomes_231 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_outcomes231_no_delete BEFORE DELETE ON source_outcomes_231 BEGIN SELECT RAISE(ABORT,'source_outcomes_231 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_reviews231_no_update BEFORE UPDATE ON source_outcome_reviews_231 BEGIN SELECT RAISE(ABORT,'source_outcome_reviews_231 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_reviews231_no_delete BEFORE DELETE ON source_outcome_reviews_231 BEGIN SELECT RAISE(ABORT,'source_outcome_reviews_231 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_policy231_no_update BEFORE UPDATE ON source_policy_snapshots_231 BEGIN SELECT RAISE(ABORT,'source_policy_snapshots_231 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_policy231_no_delete BEFORE DELETE ON source_policy_snapshots_231 BEGIN SELECT RAISE(ABORT,'source_policy_snapshots_231 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_policy_reviews231_no_update BEFORE UPDATE ON source_policy_reviews_231 BEGIN SELECT RAISE(ABORT,'source_policy_reviews_231 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_policy_reviews231_no_delete BEFORE DELETE ON source_policy_reviews_231 BEGIN SELECT RAISE(ABORT,'source_policy_reviews_231 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_profiles231_no_update BEFORE UPDATE ON source_learning_profiles_231 BEGIN SELECT RAISE(ABORT,'source_learning_profiles_231 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_profiles231_no_delete BEFORE DELETE ON source_learning_profiles_231 BEGIN SELECT RAISE(ABORT,'source_learning_profiles_231 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_exploration231_no_update BEFORE UPDATE ON source_exploration_proposals_231 BEGIN SELECT RAISE(ABORT,'source_exploration_proposals_231 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_exploration231_no_delete BEFORE DELETE ON source_exploration_proposals_231 BEGIN SELECT RAISE(ABORT,'source_exploration_proposals_231 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_exploration_reviews231_no_update BEFORE UPDATE ON source_exploration_reviews_231 BEGIN SELECT RAISE(ABORT,'source_exploration_reviews_231 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_exploration_reviews231_no_delete BEFORE DELETE ON source_exploration_reviews_231 BEGIN SELECT RAISE(ABORT,'source_exploration_reviews_231 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_events231_no_update BEFORE UPDATE ON build231_events BEGIN SELECT RAISE(ABORT,'build231_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events231_no_delete BEFORE DELETE ON build231_events BEGIN SELECT RAISE(ABORT,'build231_events is immutable'); END;
'''


def ensure_build231_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_231)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','231.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','231.0')")
    db.conn.commit()
