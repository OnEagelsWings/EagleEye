from __future__ import annotations
from typing import Any

SCHEMA_229 = r'''
CREATE TABLE IF NOT EXISTS verified_research_loops_229 (
  loop_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  objective TEXT NOT NULL,
  working_language TEXT NOT NULL DEFAULT 'de',
  status TEXT NOT NULL DEFAULT 'active',
  current_cycle INTEGER NOT NULL DEFAULT 0,
  max_cycles INTEGER NOT NULL DEFAULT 4,
  required_independent_origins INTEGER NOT NULL DEFAULT 2,
  min_verification_score REAL NOT NULL DEFAULT 0.72,
  require_counterevidence INTEGER NOT NULL DEFAULT 1,
  stop_reason TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_vrl229_case ON verified_research_loops_229(case_id,status,updated_at);

CREATE TABLE IF NOT EXISTS verified_research_cycles_229 (
  cycle_id TEXT PRIMARY KEY,
  loop_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  cycle_number INTEGER NOT NULL,
  query_text TEXT NOT NULL,
  target_type TEXT NOT NULL DEFAULT 'unknown',
  target_value_redacted TEXT NOT NULL DEFAULT '',
  retrieval_run_id TEXT NOT NULL DEFAULT '',
  source_query_id TEXT NOT NULL DEFAULT '',
  selected_refs_json TEXT NOT NULL DEFAULT '[]',
  supporting_refs_json TEXT NOT NULL DEFAULT '[]',
  contradicting_refs_json TEXT NOT NULL DEFAULT '[]',
  source_strategy_json TEXT NOT NULL DEFAULT '{}',
  verification_summary_json TEXT NOT NULL DEFAULT '{}',
  counterevidence_checked INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'evidence_ready',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT NOT NULL DEFAULT '',
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(loop_id) REFERENCES verified_research_loops_229(loop_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  UNIQUE(loop_id,cycle_number)
);
CREATE INDEX IF NOT EXISTS idx_vrc229_loop ON verified_research_cycles_229(loop_id,cycle_number,status);

CREATE TABLE IF NOT EXISTS verified_claims_229 (
  verified_claim_id TEXT PRIMARY KEY,
  loop_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  cycle_id TEXT NOT NULL,
  retrieval_claim_id TEXT NOT NULL DEFAULT '',
  claim_text TEXT NOT NULL,
  claim_kind TEXT NOT NULL DEFAULT 'observation',
  status TEXT NOT NULL DEFAULT 'candidate',
  confidence REAL NOT NULL DEFAULT 0.0,
  supporting_refs_json TEXT NOT NULL DEFAULT '[]',
  contradicting_refs_json TEXT NOT NULL DEFAULT '[]',
  independent_support_count INTEGER NOT NULL DEFAULT 0,
  independent_contradiction_count INTEGER NOT NULL DEFAULT 0,
  source_diversity REAL NOT NULL DEFAULT 0.0,
  verification_score REAL NOT NULL DEFAULT 0.0,
  counterevidence_checked INTEGER NOT NULL DEFAULT 0,
  rationale TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  reviewed_at TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(loop_id) REFERENCES verified_research_loops_229(loop_id) ON DELETE CASCADE,
  FOREIGN KEY(cycle_id) REFERENCES verified_research_cycles_229(cycle_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_vclaim229_loop ON verified_claims_229(loop_id,status,verification_score);

CREATE TABLE IF NOT EXISTS research_gaps_229 (
  gap_id TEXT PRIMARY KEY,
  loop_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  question TEXT NOT NULL,
  target_type TEXT NOT NULL DEFAULT 'unknown',
  target_value_redacted TEXT NOT NULL DEFAULT '',
  priority INTEGER NOT NULL DEFAULT 50,
  status TEXT NOT NULL DEFAULT 'open',
  source_strategy_json TEXT NOT NULL DEFAULT '{}',
  resolution_note TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  resolved_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  resolved_at TEXT NOT NULL DEFAULT '',
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(loop_id) REFERENCES verified_research_loops_229(loop_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_gap229_loop ON research_gaps_229(loop_id,status,priority);

CREATE TABLE IF NOT EXISTS build229_events (
  event_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL,
  previous_hash TEXT NOT NULL DEFAULT '',
  event_hash TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_events229_case ON build229_events(case_id,created_at);
CREATE TRIGGER IF NOT EXISTS trg_events229_no_update BEFORE UPDATE ON build229_events BEGIN SELECT RAISE(ABORT,'build229_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events229_no_delete BEFORE DELETE ON build229_events BEGIN SELECT RAISE(ABORT,'build229_events is immutable'); END;
'''


def ensure_build229_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_229)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','229.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','229.0')")
    db.conn.commit()
