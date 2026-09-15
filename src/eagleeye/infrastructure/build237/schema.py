from __future__ import annotations
from typing import Any

SCHEMA_237 = r'''
CREATE TABLE IF NOT EXISTS social_profiles_237 (
  profile_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  source_key TEXT NOT NULL,
  handle_normalized TEXT NOT NULL,
  canonical_profile_url TEXT NOT NULL DEFAULT '',
  canonical_entity_object_id TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  UNIQUE(case_id,platform,handle_normalized)
);
CREATE INDEX IF NOT EXISTS idx_social237_profiles_case ON social_profiles_237(case_id,platform,handle_normalized);

CREATE TABLE IF NOT EXISTS social_profile_observations_237 (
  observation_id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  handle TEXT NOT NULL,
  display_name TEXT NOT NULL DEFAULT '',
  bio TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT 'und',
  aliases_json TEXT NOT NULL DEFAULT '[]',
  location TEXT NOT NULL DEFAULT '',
  website TEXT NOT NULL DEFAULT '',
  follower_count INTEGER NOT NULL DEFAULT -1,
  following_count INTEGER NOT NULL DEFAULT -1,
  observed_at TEXT NOT NULL,
  confidence REAL NOT NULL,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  provenance_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(profile_id) REFERENCES social_profiles_237(profile_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(confidence>=0 AND confidence<=1)
);
CREATE INDEX IF NOT EXISTS idx_social237_obs_profile ON social_profile_observations_237(profile_id,observed_at DESC);

CREATE TABLE IF NOT EXISTS social_profile_reviews_237 (
  review_id TEXT PRIMARY KEY,
  observation_id TEXT NOT NULL UNIQUE,
  profile_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(observation_id) REFERENCES social_profile_observations_237(observation_id) ON DELETE CASCADE,
  CHECK(decision IN ('accepted','rejected','deferred'))
);

CREATE TABLE IF NOT EXISTS social_posts_237 (
  post_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  source_key TEXT NOT NULL,
  platform_post_id TEXT NOT NULL DEFAULT '',
  canonical_url TEXT NOT NULL DEFAULT '',
  content_original TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'und',
  published_at TEXT NOT NULL DEFAULT '',
  observed_at TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  provenance_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(profile_id) REFERENCES social_profiles_237(profile_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  UNIQUE(case_id,profile_id,content_sha256)
);
CREATE INDEX IF NOT EXISTS idx_social237_posts_case ON social_posts_237(case_id,published_at,observed_at);

CREATE TABLE IF NOT EXISTS social_post_reviews_237 (
  review_id TEXT PRIMARY KEY,
  post_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(post_id) REFERENCES social_posts_237(post_id) ON DELETE CASCADE,
  CHECK(decision IN ('accepted','rejected','deferred'))
);

CREATE TABLE IF NOT EXISTS social_identity_candidates_237 (
  candidate_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  left_profile_id TEXT NOT NULL,
  right_profile_id TEXT NOT NULL,
  signals_json TEXT NOT NULL,
  contradictions_json TEXT NOT NULL,
  score REAL NOT NULL,
  confidence_band TEXT NOT NULL,
  candidate_state TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(left_profile_id) REFERENCES social_profiles_237(profile_id) ON DELETE CASCADE,
  FOREIGN KEY(right_profile_id) REFERENCES social_profiles_237(profile_id) ON DELETE CASCADE,
  CHECK(score>=0 AND score<=1),
  UNIQUE(case_id,left_profile_id,right_profile_id)
);
CREATE INDEX IF NOT EXISTS idx_social237_identity_case ON social_identity_candidates_237(case_id,score DESC);

CREATE TABLE IF NOT EXISTS social_identity_reviews_237 (
  review_id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  kernel_link_id TEXT NOT NULL DEFAULT '',
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(candidate_id) REFERENCES social_identity_candidates_237(candidate_id) ON DELETE CASCADE,
  CHECK(decision IN ('match_candidate','no_match','uncertain'))
);

CREATE TABLE IF NOT EXISTS social_relationship_candidates_237 (
  relationship_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  actor_profile_id TEXT NOT NULL,
  target_profile_id TEXT NOT NULL DEFAULT '',
  target_label TEXT NOT NULL DEFAULT '',
  relation_type TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  confidence REAL NOT NULL,
  observed_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(actor_profile_id) REFERENCES social_profiles_237(profile_id) ON DELETE CASCADE,
  CHECK(confidence>=0 AND confidence<=1)
);
CREATE INDEX IF NOT EXISTS idx_social237_rel_case ON social_relationship_candidates_237(case_id,observed_at DESC);

CREATE TABLE IF NOT EXISTS social_relationship_reviews_237 (
  review_id TEXT PRIMARY KEY,
  relationship_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  kernel_link_id TEXT NOT NULL DEFAULT '',
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(relationship_id) REFERENCES social_relationship_candidates_237(relationship_id) ON DELETE CASCADE,
  CHECK(decision IN ('accepted','rejected','needs_more_evidence'))
);

CREATE TABLE IF NOT EXISTS social_kernel_bindings_237 (
  binding_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  profile_id TEXT NOT NULL UNIQUE,
  canonical_entity_object_id TEXT NOT NULL,
  bound_by TEXT NOT NULL,
  bound_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(profile_id) REFERENCES social_profiles_237(profile_id) ON DELETE CASCADE,
  FOREIGN KEY(canonical_entity_object_id) REFERENCES canonical_objects_235(object_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS social_training_links_237 (
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
CREATE INDEX IF NOT EXISTS idx_social237_training_case ON social_training_links_237(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS build237_events (
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
CREATE INDEX IF NOT EXISTS idx_events237_case ON build237_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_social237_profiles_no_update BEFORE UPDATE ON social_profiles_237 BEGIN SELECT RAISE(ABORT,'social_profiles_237 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_profiles_no_delete BEFORE DELETE ON social_profiles_237 BEGIN SELECT RAISE(ABORT,'social_profiles_237 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_obs_no_update BEFORE UPDATE ON social_profile_observations_237 BEGIN SELECT RAISE(ABORT,'social_profile_observations_237 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_obs_no_delete BEFORE DELETE ON social_profile_observations_237 BEGIN SELECT RAISE(ABORT,'social_profile_observations_237 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_profile_review_no_update BEFORE UPDATE ON social_profile_reviews_237 BEGIN SELECT RAISE(ABORT,'social_profile_reviews_237 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_profile_review_no_delete BEFORE DELETE ON social_profile_reviews_237 BEGIN SELECT RAISE(ABORT,'social_profile_reviews_237 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_post_no_update BEFORE UPDATE ON social_posts_237 BEGIN SELECT RAISE(ABORT,'social_posts_237 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_post_no_delete BEFORE DELETE ON social_posts_237 BEGIN SELECT RAISE(ABORT,'social_posts_237 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_post_review_no_update BEFORE UPDATE ON social_post_reviews_237 BEGIN SELECT RAISE(ABORT,'social_post_reviews_237 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_post_review_no_delete BEFORE DELETE ON social_post_reviews_237 BEGIN SELECT RAISE(ABORT,'social_post_reviews_237 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_identity_no_update BEFORE UPDATE ON social_identity_candidates_237 BEGIN SELECT RAISE(ABORT,'social_identity_candidates_237 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_identity_no_delete BEFORE DELETE ON social_identity_candidates_237 BEGIN SELECT RAISE(ABORT,'social_identity_candidates_237 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_identity_review_no_update BEFORE UPDATE ON social_identity_reviews_237 BEGIN SELECT RAISE(ABORT,'social_identity_reviews_237 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_identity_review_no_delete BEFORE DELETE ON social_identity_reviews_237 BEGIN SELECT RAISE(ABORT,'social_identity_reviews_237 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_rel_no_update BEFORE UPDATE ON social_relationship_candidates_237 BEGIN SELECT RAISE(ABORT,'social_relationship_candidates_237 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_rel_no_delete BEFORE DELETE ON social_relationship_candidates_237 BEGIN SELECT RAISE(ABORT,'social_relationship_candidates_237 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_rel_review_no_update BEFORE UPDATE ON social_relationship_reviews_237 BEGIN SELECT RAISE(ABORT,'social_relationship_reviews_237 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_rel_review_no_delete BEFORE DELETE ON social_relationship_reviews_237 BEGIN SELECT RAISE(ABORT,'social_relationship_reviews_237 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_binding_no_update BEFORE UPDATE ON social_kernel_bindings_237 BEGIN SELECT RAISE(ABORT,'social_kernel_bindings_237 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_binding_no_delete BEFORE DELETE ON social_kernel_bindings_237 BEGIN SELECT RAISE(ABORT,'social_kernel_bindings_237 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_training_no_update BEFORE UPDATE ON social_training_links_237 BEGIN SELECT RAISE(ABORT,'social_training_links_237 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_social237_training_no_delete BEFORE DELETE ON social_training_links_237 BEGIN SELECT RAISE(ABORT,'social_training_links_237 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events237_no_update BEFORE UPDATE ON build237_events BEGIN SELECT RAISE(ABORT,'build237_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events237_no_delete BEFORE DELETE ON build237_events BEGIN SELECT RAISE(ABORT,'build237_events is immutable'); END;
'''


def ensure_build237_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_237)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','237.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','237.0')")
    db.conn.commit()
