from __future__ import annotations

from typing import Any

SCHEMA_227 = r'''
CREATE TABLE IF NOT EXISTS conversational_states_227 (
  session_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  investigation_goal TEXT NOT NULL DEFAULT '',
  working_language TEXT NOT NULL DEFAULT 'de',
  status TEXT NOT NULL DEFAULT 'active',
  turn_count INTEGER NOT NULL DEFAULT 0,
  conversation_summary TEXT NOT NULL DEFAULT '',
  active_thread_id TEXT NOT NULL DEFAULT '',
  last_context_snapshot_id TEXT NOT NULL DEFAULT '',
  last_turn_id TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES ai_chat_sessions_216(session_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_conv227_state_case ON conversational_states_227(case_id,updated_at);

CREATE TABLE IF NOT EXISTS investigation_threads_227 (
  thread_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  title TEXT NOT NULL,
  objective TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  priority INTEGER NOT NULL DEFAULT 50,
  resolution_note TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES conversational_states_227(session_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_conv227_threads ON investigation_threads_227(session_id,status,priority,updated_at);

CREATE TABLE IF NOT EXISTS investigation_hypotheses_227 (
  hypothesis_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  thread_id TEXT NOT NULL DEFAULT '',
  case_id TEXT NOT NULL,
  hypothesis_text TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  confidence REAL NOT NULL DEFAULT 0.5,
  supporting_refs_json TEXT NOT NULL DEFAULT '[]',
  contradicting_refs_json TEXT NOT NULL DEFAULT '[]',
  origin TEXT NOT NULL DEFAULT 'investigator',
  supersedes_hypothesis_id TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES conversational_states_227(session_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_conv227_hypotheses ON investigation_hypotheses_227(session_id,status,updated_at);

CREATE TABLE IF NOT EXISTS conversational_turns_227 (
  turn_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  sequence_no INTEGER NOT NULL,
  user_message TEXT NOT NULL,
  message_language TEXT NOT NULL DEFAULT 'de',
  status TEXT NOT NULL DEFAULT 'queued',
  retry_of_turn_id TEXT NOT NULL DEFAULT '',
  correction_target_turn_id TEXT NOT NULL DEFAULT '',
  base_user_message_id TEXT NOT NULL DEFAULT '',
  base_assistant_message_id TEXT NOT NULL DEFAULT '',
  retrieval_run_id TEXT NOT NULL DEFAULT '',
  source_query_id TEXT NOT NULL DEFAULT '',
  response_json TEXT NOT NULL DEFAULT '{}',
  citations_json TEXT NOT NULL DEFAULT '[]',
  error_text TEXT NOT NULL DEFAULT '',
  stop_requested INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT '',
  completed_at TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  UNIQUE(session_id,sequence_no),
  FOREIGN KEY(session_id) REFERENCES conversational_states_227(session_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_conv227_turns ON conversational_turns_227(session_id,sequence_no,status);

CREATE TABLE IF NOT EXISTS conversational_context_snapshots_227 (
  snapshot_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  summary_text TEXT NOT NULL,
  active_threads_json TEXT NOT NULL,
  active_hypotheses_json TEXT NOT NULL,
  retrieved_sources_json TEXT NOT NULL,
  selected_refs_json TEXT NOT NULL,
  source_strategy_json TEXT NOT NULL,
  context_budget_json TEXT NOT NULL,
  reviewed_corrections_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES conversational_states_227(session_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(turn_id) REFERENCES conversational_turns_227(turn_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_conv227_snapshots ON conversational_context_snapshots_227(session_id,created_at);

CREATE TABLE IF NOT EXISTS conversational_stream_chunks_227 (
  chunk_id TEXT PRIMARY KEY,
  turn_id TEXT NOT NULL,
  sequence_no INTEGER NOT NULL,
  chunk_type TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  UNIQUE(turn_id,sequence_no),
  FOREIGN KEY(turn_id) REFERENCES conversational_turns_227(turn_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_conv227_chunks ON conversational_stream_chunks_227(turn_id,sequence_no);

CREATE TABLE IF NOT EXISTS conversational_corrections_227 (
  correction_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  target_turn_id TEXT NOT NULL,
  corrected_turn_id TEXT NOT NULL DEFAULT '',
  correction_text TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'reviewed',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES conversational_states_227(session_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_turn_id) REFERENCES conversational_turns_227(turn_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_conv227_corrections ON conversational_corrections_227(session_id,created_at);

CREATE TABLE IF NOT EXISTS build227_events (
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
CREATE INDEX IF NOT EXISTS idx_build227_events ON build227_events(case_id,created_at);

CREATE TRIGGER IF NOT EXISTS trg_conv227_corrections_no_update BEFORE UPDATE ON conversational_corrections_227 BEGIN SELECT RAISE(ABORT,'conversational_corrections_227 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_conv227_corrections_no_delete BEFORE DELETE ON conversational_corrections_227 BEGIN SELECT RAISE(ABORT,'conversational_corrections_227 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build227_events_no_update BEFORE UPDATE ON build227_events BEGIN SELECT RAISE(ABORT,'build227_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build227_events_no_delete BEFORE DELETE ON build227_events BEGIN SELECT RAISE(ABORT,'build227_events is immutable'); END;
'''


def ensure_build227_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_227)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','227.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','227.0')")
    db.conn.commit()
