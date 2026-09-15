from __future__ import annotations
from typing import Any
SCHEMA_182=r'''
CREATE TABLE IF NOT EXISTS repository_source_profiles_182(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,access_mode TEXT NOT NULL,base_url TEXT NOT NULL,docs_url TEXT NOT NULL,constraints_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS secure_repositories_182(repository_id TEXT PRIMARY KEY,title TEXT NOT NULL,key_ref TEXT NOT NULL,algorithm TEXT NOT NULL,status TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS repository_objects_182(object_id TEXT PRIMARY KEY,repository_id TEXT NOT NULL,case_id TEXT NOT NULL,object_type TEXT NOT NULL,logical_name TEXT NOT NULL,ciphertext_path TEXT NOT NULL,plaintext_sha256 TEXT NOT NULL,ciphertext_sha256 TEXT NOT NULL,nonce_b64 TEXT NOT NULL,aad_json TEXT NOT NULL,size_bytes INTEGER NOT NULL,source_refs_json TEXT NOT NULL,classification TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS repository_access_grants_182(grant_id TEXT PRIMARY KEY,repository_id TEXT NOT NULL,case_id TEXT NOT NULL,principal TEXT NOT NULL,permission TEXT NOT NULL,status TEXT NOT NULL,expires_at TEXT NOT NULL,approved_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL,UNIQUE(repository_id,case_id,principal,permission));
CREATE TABLE IF NOT EXISTS federation_peers_182(peer_id TEXT PRIMARY KEY,title TEXT NOT NULL,trust_mode TEXT NOT NULL,public_key_ref TEXT,status TEXT NOT NULL,approved_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS federation_packages_182(package_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,direction TEXT NOT NULL,peer_id TEXT,manifest_json TEXT NOT NULL,package_path TEXT NOT NULL,package_sha256 TEXT NOT NULL,signature_b64 TEXT NOT NULL,status TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS authenticity_crosschecks_182(crosscheck_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,target_id TEXT NOT NULL,signals_json TEXT NOT NULL,score REAL NOT NULL,status TEXT NOT NULL,limitations_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS repository_events_182(event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,event_type TEXT NOT NULL,details_json TEXT NOT NULL,created_at TEXT NOT NULL,previous_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_repository_objects_182 ON repository_objects_182(case_id,object_type,classification);
CREATE INDEX IF NOT EXISTS idx_repository_grants_182 ON repository_access_grants_182(case_id,principal,status,expires_at);
'''
def ensure_build182_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_182);db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','182.0')");db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','182.0')");db.conn.commit()
