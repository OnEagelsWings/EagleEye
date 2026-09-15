from __future__ import annotations
from typing import Any

SCHEMA_174 = r'''
CREATE TABLE IF NOT EXISTS media_items_174(
 media_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_ref TEXT,
 file_path TEXT NOT NULL, media_kind TEXT NOT NULL, mime_type TEXT NOT NULL,
 file_size INTEGER NOT NULL, exact_sha256 TEXT NOT NULL, perceptual_hash TEXT,
 width INTEGER, height INTEGER, duration_seconds REAL,
 metadata_json TEXT NOT NULL, provenance_json TEXT NOT NULL,
 observed_at TEXT NOT NULL, review_status TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS media_comparisons_174(
 comparison_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
 left_media_id TEXT NOT NULL, right_media_id TEXT NOT NULL,
 exact_match INTEGER NOT NULL, hamming_distance INTEGER,
 similarity REAL NOT NULL, classification TEXT NOT NULL,
 explanation_json TEXT NOT NULL, review_status TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS video_frames_174(
 frame_id TEXT PRIMARY KEY, media_id TEXT NOT NULL, timestamp_seconds REAL NOT NULL,
 file_path TEXT NOT NULL, exact_sha256 TEXT NOT NULL, perceptual_hash TEXT,
 width INTEGER, height INTEGER, created_at TEXT NOT NULL,
 review_status TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS media_source_profiles_174(
 source_id TEXT PRIMARY KEY, title TEXT NOT NULL, jurisdiction TEXT NOT NULL,
 category TEXT NOT NULL, access_mode TEXT NOT NULL, base_url TEXT NOT NULL,
 docs_url TEXT NOT NULL, terms_url TEXT NOT NULL, status TEXT NOT NULL,
 entity_kinds_json TEXT NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS media_forensics_events_174(
 event_id TEXT PRIMARY KEY, case_id TEXT, event_type TEXT NOT NULL,
 entity_ref TEXT, details_json TEXT NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
'''

def ensure_build174_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_174)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','174.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','174.0')")
    db.conn.commit()
