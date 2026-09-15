from __future__ import annotations
from typing import Any
SCHEMA_198=r'''
CREATE TABLE IF NOT EXISTS enterprise_source_profiles_198(source_id TEXT PRIMARY KEY,name TEXT NOT NULL,region TEXT NOT NULL,source_class TEXT NOT NULL,access_mode TEXT NOT NULL,status TEXT NOT NULL,terms_status TEXT NOT NULL,parser_status TEXT NOT NULL,live_status TEXT NOT NULL,blockers_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enterprise_tenants_198(tenant_id TEXT PRIMARY KEY,name TEXT NOT NULL,status TEXT NOT NULL,policy_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enterprise_roles_198(role_id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,name TEXT NOT NULL,permissions_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enterprise_memberships_198(membership_id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,user_id TEXT NOT NULL,role_id TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enterprise_credentials_198(credential_id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,source_id TEXT NOT NULL,secret_ref TEXT NOT NULL,status TEXT NOT NULL,metadata_json TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enterprise_release_manifests_198(release_id TEXT PRIMARY KEY,version TEXT NOT NULL,artifact_sha256 TEXT NOT NULL,sbom_ref TEXT NOT NULL,signature_status TEXT NOT NULL,gate_status TEXT NOT NULL,checks_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enterprise_audit_exports_198(export_id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,format TEXT NOT NULL,target TEXT NOT NULL,status TEXT NOT NULL,filters_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enterprise_security_events_198(event_id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,event_type TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL,payload_json TEXT NOT NULL,prev_hash TEXT NOT NULL,event_hash TEXT NOT NULL);
'''
def ensure_build198_schema(db:Any)->None:
    db.conn.executescript(SCHEMA_198)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','198.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','198.0')")
    db.conn.commit()
