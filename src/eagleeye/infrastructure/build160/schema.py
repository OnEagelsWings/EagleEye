from __future__ import annotations
from typing import Any
SCHEMA_160=r'''
CREATE TABLE IF NOT EXISTS social_source_profiles_160(source_id TEXT PRIMARY KEY,display_name TEXT NOT NULL,access_mode TEXT NOT NULL,official_docs TEXT NOT NULL,auth_required INTEGER NOT NULL,public_only INTEGER NOT NULL,crawl_allowed INTEGER NOT NULL,terms_review_required INTEGER NOT NULL,status TEXT NOT NULL,capabilities_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS crawl_authorizations_160(authorization_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,scope_json TEXT NOT NULL,purpose TEXT NOT NULL,approved_by TEXT NOT NULL,approved_at TEXT NOT NULL,expires_at TEXT,budget_json TEXT NOT NULL,status TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cockpit_snapshots_160(snapshot_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,summary_json TEXT NOT NULL,risk_json TEXT NOT NULL,next_steps_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS profile_fusion_160(fusion_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,subject_label TEXT NOT NULL,source_record_ids_json TEXT NOT NULL,claims_json TEXT NOT NULL,conflicts_json TEXT NOT NULL,confidence_band TEXT NOT NULL,review_status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS authority_dossiers_160(dossier_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,title TEXT NOT NULL,classification TEXT NOT NULL,export_path TEXT NOT NULL,manifest_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
'''
def ensure_build160_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_160); db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','160.0')"); db.conn.commit()
