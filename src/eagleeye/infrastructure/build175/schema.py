from __future__ import annotations
from typing import Any

SCHEMA_175 = r'''
CREATE TABLE IF NOT EXISTS geo_source_profiles_175(
 source_id TEXT PRIMARY KEY, title TEXT NOT NULL, jurisdiction TEXT NOT NULL,
 category TEXT NOT NULL, access_mode TEXT NOT NULL, base_url TEXT NOT NULL,
 docs_url TEXT NOT NULL, terms_url TEXT NOT NULL, status TEXT NOT NULL,
 capabilities_json TEXT NOT NULL, constraints_json TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS geo_locations_175(
 location_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, label TEXT NOT NULL,
 normalized_label TEXT NOT NULL, latitude REAL, longitude REAL,
 uncertainty_meters REAL NOT NULL, confidence REAL NOT NULL,
 location_type TEXT NOT NULL, country_code TEXT, admin_path_json TEXT NOT NULL,
 source_refs_json TEXT NOT NULL, provenance_json TEXT NOT NULL,
 sensitive_precision INTEGER NOT NULL, review_status TEXT NOT NULL,
 observed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS geo_observations_175(
 observation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, entity_ref TEXT,
 location_id TEXT NOT NULL, valid_from TEXT, valid_to TEXT,
 observed_at TEXT NOT NULL, source_time TEXT, source_refs_json TEXT NOT NULL,
 confidence REAL NOT NULL, verification_status TEXT NOT NULL,
 details_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS geo_resolution_candidates_175(
 candidate_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, query_text TEXT NOT NULL,
 source_id TEXT NOT NULL, candidate_json TEXT NOT NULL, latitude REAL, longitude REAL,
 uncertainty_meters REAL NOT NULL, score REAL NOT NULL, evidence_json TEXT NOT NULL,
 review_status TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS geo_route_estimates_175(
 route_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, origin_location_id TEXT NOT NULL,
 destination_location_id TEXT NOT NULL, distance_meters REAL NOT NULL,
 mode TEXT NOT NULL, estimated_seconds REAL, method TEXT NOT NULL,
 assumptions_json TEXT NOT NULL, review_status TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS geo_exports_175(
 export_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, export_type TEXT NOT NULL,
 file_path TEXT NOT NULL, feature_count INTEGER NOT NULL,
 precision_policy TEXT NOT NULL, created_by TEXT NOT NULL,
 created_at TEXT NOT NULL, file_sha256 TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS geo_events_175(
 event_id TEXT PRIMARY KEY, case_id TEXT, event_type TEXT NOT NULL,
 entity_ref TEXT, details_json TEXT NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
'''

def ensure_build175_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_175)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','175.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','175.0')")
    db.conn.commit()
