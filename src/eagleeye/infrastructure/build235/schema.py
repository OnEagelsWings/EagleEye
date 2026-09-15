from __future__ import annotations
from typing import Any

SCHEMA_235 = r'''
CREATE TABLE IF NOT EXISTS canonical_objects_235 (
  object_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  object_type TEXT NOT NULL,
  subtype TEXT NOT NULL DEFAULT '',
  label TEXT NOT NULL,
  canonical_key TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(object_type IN ('entity','claim','evidence','source','hypothesis','task','finding')),
  UNIQUE(case_id,object_type,canonical_key)
);
CREATE INDEX IF NOT EXISTS idx_kernel235_objects_case_type ON canonical_objects_235(case_id,object_type,created_at);

CREATE TABLE IF NOT EXISTS canonical_object_revisions_235 (
  revision_id TEXT PRIMARY KEY,
  object_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  revision_no INTEGER NOT NULL,
  state TEXT NOT NULL,
  confidence REAL NOT NULL,
  payload_json TEXT NOT NULL,
  provenance_json TEXT NOT NULL,
  supersedes_revision_id TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(object_id) REFERENCES canonical_objects_235(object_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(confidence >= 0.0 AND confidence <= 1.0),
  UNIQUE(object_id,revision_no)
);
CREATE INDEX IF NOT EXISTS idx_kernel235_revisions_object ON canonical_object_revisions_235(object_id,revision_no DESC);

CREATE TABLE IF NOT EXISTS canonical_links_235 (
  link_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  source_object_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  target_object_id TEXT NOT NULL,
  confidence REAL NOT NULL,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(source_object_id) REFERENCES canonical_objects_235(object_id) ON DELETE CASCADE,
  FOREIGN KEY(target_object_id) REFERENCES canonical_objects_235(object_id) ON DELETE CASCADE,
  CHECK(confidence >= 0.0 AND confidence <= 1.0),
  CHECK(source_object_id <> target_object_id),
  UNIQUE(case_id,source_object_id,relation_type,target_object_id)
);
CREATE INDEX IF NOT EXISTS idx_kernel235_links_case ON canonical_links_235(case_id,relation_type,created_at);

CREATE TABLE IF NOT EXISTS canonical_link_reviews_235 (
  review_id TEXT PRIMARY KEY,
  link_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(link_id) REFERENCES canonical_links_235(link_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(decision IN ('accepted','rejected','needs_more_evidence')),
  UNIQUE(link_id)
);

CREATE TABLE IF NOT EXISTS canonical_aliases_235 (
  alias_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  namespace TEXT NOT NULL,
  legacy_type TEXT NOT NULL,
  legacy_id TEXT NOT NULL,
  object_id TEXT NOT NULL,
  adapter_version TEXT NOT NULL DEFAULT '235.0',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(object_id) REFERENCES canonical_objects_235(object_id) ON DELETE CASCADE,
  UNIQUE(case_id,namespace,legacy_type,legacy_id)
);
CREATE INDEX IF NOT EXISTS idx_kernel235_alias_object ON canonical_aliases_235(object_id,namespace);

CREATE TABLE IF NOT EXISTS canonical_snapshots_235 (
  snapshot_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  object_count INTEGER NOT NULL,
  link_count INTEGER NOT NULL,
  accepted_link_count INTEGER NOT NULL,
  unresolved_link_count INTEGER NOT NULL,
  object_counts_json TEXT NOT NULL,
  integrity_json TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_kernel235_snapshots_case ON canonical_snapshots_235(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS build235_events (
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
CREATE INDEX IF NOT EXISTS idx_events235_case ON build235_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_kernel235_object_no_update BEFORE UPDATE ON canonical_objects_235 BEGIN SELECT RAISE(ABORT,'canonical_objects_235 is immutable; create a revision'); END;
CREATE TRIGGER IF NOT EXISTS trg_kernel235_object_no_delete BEFORE DELETE ON canonical_objects_235 BEGIN SELECT RAISE(ABORT,'canonical_objects_235 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_kernel235_revision_no_update BEFORE UPDATE ON canonical_object_revisions_235 BEGIN SELECT RAISE(ABORT,'canonical_object_revisions_235 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_kernel235_revision_no_delete BEFORE DELETE ON canonical_object_revisions_235 BEGIN SELECT RAISE(ABORT,'canonical_object_revisions_235 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_kernel235_link_no_update BEFORE UPDATE ON canonical_links_235 BEGIN SELECT RAISE(ABORT,'canonical_links_235 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_kernel235_link_no_delete BEFORE DELETE ON canonical_links_235 BEGIN SELECT RAISE(ABORT,'canonical_links_235 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_kernel235_linkreview_no_update BEFORE UPDATE ON canonical_link_reviews_235 BEGIN SELECT RAISE(ABORT,'canonical_link_reviews_235 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_kernel235_linkreview_no_delete BEFORE DELETE ON canonical_link_reviews_235 BEGIN SELECT RAISE(ABORT,'canonical_link_reviews_235 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_kernel235_alias_no_update BEFORE UPDATE ON canonical_aliases_235 BEGIN SELECT RAISE(ABORT,'canonical_aliases_235 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_kernel235_alias_no_delete BEFORE DELETE ON canonical_aliases_235 BEGIN SELECT RAISE(ABORT,'canonical_aliases_235 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_kernel235_snapshot_no_update BEFORE UPDATE ON canonical_snapshots_235 BEGIN SELECT RAISE(ABORT,'canonical_snapshots_235 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_kernel235_snapshot_no_delete BEFORE DELETE ON canonical_snapshots_235 BEGIN SELECT RAISE(ABORT,'canonical_snapshots_235 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events235_no_update BEFORE UPDATE ON build235_events BEGIN SELECT RAISE(ABORT,'build235_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events235_no_delete BEFORE DELETE ON build235_events BEGIN SELECT RAISE(ABORT,'build235_events is immutable'); END;
'''


def ensure_build235_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_235)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','235.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','235.0')")
    db.conn.commit()
