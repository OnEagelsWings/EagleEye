from __future__ import annotations
from typing import Any

SCHEMA_238 = r"""
CREATE TABLE IF NOT EXISTS graph_edge_annotations_238 (
  annotation_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  kernel_link_id TEXT NOT NULL,
  valid_from TEXT NOT NULL DEFAULT '',
  valid_to TEXT NOT NULL DEFAULT '',
  first_observed_at TEXT NOT NULL DEFAULT '',
  last_observed_at TEXT NOT NULL DEFAULT '',
  temporal_precision TEXT NOT NULL DEFAULT 'unknown',
  provenance_json TEXT NOT NULL DEFAULT '{}',
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(kernel_link_id) REFERENCES canonical_links_235(link_id) ON DELETE CASCADE,
  CHECK(temporal_precision IN ('exact','day','month','year','range','unknown')),
  UNIQUE(kernel_link_id)
);
CREATE INDEX IF NOT EXISTS idx_graph238_ann_case ON graph_edge_annotations_238(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS graph_hypotheses_238 (
  graph_hypothesis_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  source_object_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  target_object_id TEXT NOT NULL,
  confidence REAL NOT NULL,
  rationale TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  valid_from TEXT NOT NULL DEFAULT '',
  valid_to TEXT NOT NULL DEFAULT '',
  contradiction_refs_json TEXT NOT NULL DEFAULT '[]',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(source_object_id) REFERENCES canonical_objects_235(object_id) ON DELETE CASCADE,
  FOREIGN KEY(target_object_id) REFERENCES canonical_objects_235(object_id) ON DELETE CASCADE,
  CHECK(confidence>=0 AND confidence<=1),
  CHECK(source_object_id<>target_object_id),
  UNIQUE(case_id,source_object_id,relation_type,target_object_id)
);
CREATE INDEX IF NOT EXISTS idx_graph238_hyp_case ON graph_hypotheses_238(case_id,confidence DESC);

CREATE TABLE IF NOT EXISTS graph_hypothesis_reviews_238 (
  review_id TEXT PRIMARY KEY,
  graph_hypothesis_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  kernel_link_id TEXT NOT NULL DEFAULT '',
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(graph_hypothesis_id) REFERENCES graph_hypotheses_238(graph_hypothesis_id) ON DELETE CASCADE,
  CHECK(decision IN ('accepted_candidate','rejected','needs_more_evidence'))
);

CREATE TABLE IF NOT EXISTS graph_snapshots_238 (
  snapshot_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  node_count INTEGER NOT NULL,
  accepted_edge_count INTEGER NOT NULL,
  candidate_edge_count INTEGER NOT NULL,
  rejected_edge_count INTEGER NOT NULL,
  component_count INTEGER NOT NULL,
  isolated_node_count INTEGER NOT NULL,
  temporal_edge_count INTEGER NOT NULL,
  content_sha256 TEXT NOT NULL,
  metrics_json TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_graph238_snap_case ON graph_snapshots_238(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS graph_training_links_238 (
  training_link_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  item_type TEXT NOT NULL,
  item_id TEXT NOT NULL,
  training_example_id TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  UNIQUE(item_type,item_id)
);
CREATE INDEX IF NOT EXISTS idx_graph238_training_case ON graph_training_links_238(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS build238_events (
  event_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL DEFAULT '',
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events238_case ON build238_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_graph238_ann_no_update BEFORE UPDATE ON graph_edge_annotations_238 BEGIN SELECT RAISE(ABORT,'graph_edge_annotations_238 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_graph238_ann_no_delete BEFORE DELETE ON graph_edge_annotations_238 BEGIN SELECT RAISE(ABORT,'graph_edge_annotations_238 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_graph238_hyp_no_update BEFORE UPDATE ON graph_hypotheses_238 BEGIN SELECT RAISE(ABORT,'graph_hypotheses_238 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_graph238_hyp_no_delete BEFORE DELETE ON graph_hypotheses_238 BEGIN SELECT RAISE(ABORT,'graph_hypotheses_238 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_graph238_review_no_update BEFORE UPDATE ON graph_hypothesis_reviews_238 BEGIN SELECT RAISE(ABORT,'graph_hypothesis_reviews_238 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_graph238_review_no_delete BEFORE DELETE ON graph_hypothesis_reviews_238 BEGIN SELECT RAISE(ABORT,'graph_hypothesis_reviews_238 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_graph238_snap_no_update BEFORE UPDATE ON graph_snapshots_238 BEGIN SELECT RAISE(ABORT,'graph_snapshots_238 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_graph238_snap_no_delete BEFORE DELETE ON graph_snapshots_238 BEGIN SELECT RAISE(ABORT,'graph_snapshots_238 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_graph238_train_no_update BEFORE UPDATE ON graph_training_links_238 BEGIN SELECT RAISE(ABORT,'graph_training_links_238 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_graph238_train_no_delete BEFORE DELETE ON graph_training_links_238 BEGIN SELECT RAISE(ABORT,'graph_training_links_238 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events238_no_update BEFORE UPDATE ON build238_events BEGIN SELECT RAISE(ABORT,'build238_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events238_no_delete BEFORE DELETE ON build238_events BEGIN SELECT RAISE(ABORT,'build238_events is immutable'); END;
"""

def ensure_build238_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_238)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','238.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','238.0')")
    db.conn.commit()
