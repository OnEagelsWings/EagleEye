from __future__ import annotations
from typing import Any
SCHEMA_158 = r'''
CREATE TABLE IF NOT EXISTS multilingual_names_158(
 name_id TEXT PRIMARY KEY, case_id TEXT, original_name TEXT NOT NULL, locale TEXT,
 detected_scripts_json TEXT NOT NULL, normalized_json TEXT NOT NULL,
 transliterations_json TEXT NOT NULL, security_flags_json TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS multilingual_comparisons_158(
 comparison_id TEXT PRIMARY KEY, left_name_id TEXT, right_name_id TEXT,
 left_input_json TEXT NOT NULL, right_input_json TEXT NOT NULL,
 score REAL NOT NULL, confidence_band TEXT NOT NULL, signals_json TEXT NOT NULL,
 warnings_json TEXT NOT NULL, review_required INTEGER NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transliteration_profiles_158(
 profile_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL UNIQUE, source_script TEXT NOT NULL,
 target_script TEXT NOT NULL, locale TEXT, version TEXT NOT NULL,
 rules_sha256 TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
'''
def ensure_build158_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_158)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','158.0')")
    db.conn.commit()
