from __future__ import annotations
from typing import Any

SCHEMA_230 = r'''
CREATE TABLE IF NOT EXISTS multilingual_identity_records_230 (
  multilingual_record_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  base_record_id TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  record_ref TEXT NOT NULL,
  original_label TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'und',
  script_profile_json TEXT NOT NULL DEFAULT '{}',
  transliterations_json TEXT NOT NULL DEFAULT '[]',
  explicit_aliases_json TEXT NOT NULL DEFAULT '[]',
  anchors_json TEXT NOT NULL DEFAULT '{}',
  statement_refs_json TEXT NOT NULL DEFAULT '[]',
  source_reliability REAL NOT NULL DEFAULT 0.5,
  status TEXT NOT NULL DEFAULT 'candidate',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(base_record_id) REFERENCES identity_records_212(record_id) ON DELETE RESTRICT,
  CHECK(source_reliability >= 0 AND source_reliability <= 1)
);
CREATE INDEX IF NOT EXISTS idx_multi_identity230_case ON multilingual_identity_records_230(case_id,status,created_at);

CREATE TABLE IF NOT EXISTS multilingual_identity_pairs_230 (
  pair_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  left_record_id TEXT NOT NULL,
  right_record_id TEXT NOT NULL,
  base_comparison_id TEXT NOT NULL,
  script_relation TEXT NOT NULL,
  transliteration_similarity REAL NOT NULL DEFAULT 0.0,
  phonetic_similarity REAL NOT NULL DEFAULT 0.0,
  anchor_support REAL NOT NULL DEFAULT 0.0,
  conflicts_json TEXT NOT NULL DEFAULT '[]',
  fusion_score REAL NOT NULL DEFAULT 0.0,
  candidate_state TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'review_required',
  created_by TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  review_decision TEXT NOT NULL DEFAULT '',
  rationale TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  reviewed_at TEXT NOT NULL DEFAULT '',
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(left_record_id) REFERENCES multilingual_identity_records_230(multilingual_record_id) ON DELETE RESTRICT,
  FOREIGN KEY(right_record_id) REFERENCES multilingual_identity_records_230(multilingual_record_id) ON DELETE RESTRICT,
  FOREIGN KEY(base_comparison_id) REFERENCES identity_comparisons_212(comparison_id) ON DELETE RESTRICT,
  CHECK(transliteration_similarity >= 0 AND transliteration_similarity <= 1),
  CHECK(phonetic_similarity >= 0 AND phonetic_similarity <= 1),
  CHECK(anchor_support >= 0 AND anchor_support <= 1),
  CHECK(fusion_score >= 0 AND fusion_score <= 1),
  UNIQUE(case_id,left_record_id,right_record_id)
);
CREATE INDEX IF NOT EXISTS idx_multi_pair230_case ON multilingual_identity_pairs_230(case_id,status,fusion_score);

CREATE TABLE IF NOT EXISTS statement_renderings_230 (
  rendering_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  statement_id TEXT NOT NULL,
  source_language TEXT NOT NULL DEFAULT 'und',
  target_language TEXT NOT NULL,
  original_text TEXT NOT NULL,
  translated_text TEXT NOT NULL,
  transliteration_text TEXT NOT NULL DEFAULT '',
  engine TEXT NOT NULL,
  engine_version TEXT NOT NULL DEFAULT '',
  uncertainties_json TEXT NOT NULL DEFAULT '[]',
  named_entities_preserved INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'review_required',
  created_by TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  review_note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  reviewed_at TEXT NOT NULL DEFAULT '',
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(statement_id) REFERENCES evidence_statements_211(statement_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_rendering230_statement ON statement_renderings_230(case_id,statement_id,status,created_at);

CREATE TABLE IF NOT EXISTS multilingual_source_fusions_230 (
  fusion_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  subject_ref TEXT NOT NULL,
  predicate TEXT NOT NULL,
  working_language TEXT NOT NULL,
  canonical_value_json TEXT NOT NULL DEFAULT '{}',
  supporting_refs_json TEXT NOT NULL DEFAULT '[]',
  contradicting_refs_json TEXT NOT NULL DEFAULT '[]',
  context_refs_json TEXT NOT NULL DEFAULT '[]',
  language_map_json TEXT NOT NULL DEFAULT '{}',
  rendering_map_json TEXT NOT NULL DEFAULT '{}',
  independent_origin_count INTEGER NOT NULL DEFAULT 0,
  language_count INTEGER NOT NULL DEFAULT 0,
  source_diversity REAL NOT NULL DEFAULT 0.0,
  average_confidence REAL NOT NULL DEFAULT 0.0,
  fusion_score REAL NOT NULL DEFAULT 0.0,
  contradiction_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'candidate',
  created_by TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  review_decision TEXT NOT NULL DEFAULT '',
  review_note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  reviewed_at TEXT NOT NULL DEFAULT '',
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(source_diversity >= 0 AND source_diversity <= 1),
  CHECK(average_confidence >= 0 AND average_confidence <= 1),
  CHECK(fusion_score >= 0 AND fusion_score <= 1)
);
CREATE INDEX IF NOT EXISTS idx_fusion230_case ON multilingual_source_fusions_230(case_id,status,fusion_score,created_at);

CREATE TABLE IF NOT EXISTS build230_events (
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
CREATE INDEX IF NOT EXISTS idx_events230_case ON build230_events(case_id,created_at);
CREATE TRIGGER IF NOT EXISTS trg_events230_no_update BEFORE UPDATE ON build230_events BEGIN SELECT RAISE(ABORT,'build230_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events230_no_delete BEFORE DELETE ON build230_events BEGIN SELECT RAISE(ABORT,'build230_events is immutable'); END;
'''


def ensure_build230_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_230)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','230.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','230.0')")
    db.conn.commit()
