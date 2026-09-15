from __future__ import annotations
from typing import Any
SCHEMA_155 = r'''
CREATE TABLE IF NOT EXISTS source_contract_reviews_155(
 review_id TEXT PRIMARY KEY, connector_id TEXT NOT NULL, review_type TEXT NOT NULL,
 status TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, valid_until TEXT,
 evidence_reference TEXT NOT NULL, findings_json TEXT NOT NULL DEFAULT '{}',
 evidence_sha256 TEXT NOT NULL, supersedes_review_id TEXT,
 FOREIGN KEY(connector_id) REFERENCES connector_specs_154(connector_id)
);
CREATE INDEX IF NOT EXISTS idx_reviews155_connector ON source_contract_reviews_155(connector_id,review_type,reviewed_at);
CREATE TABLE IF NOT EXISTS source_gate_decisions_155(
 decision_id TEXT PRIMARY KEY, connector_id TEXT NOT NULL, decision TEXT NOT NULL,
 reason TEXT NOT NULL, actor TEXT NOT NULL, decided_at TEXT NOT NULL,
 legal_review_id TEXT, technical_review_id TEXT, expires_at TEXT,
 snapshot_sha256 TEXT NOT NULL,
 FOREIGN KEY(connector_id) REFERENCES connector_specs_154(connector_id)
);
CREATE INDEX IF NOT EXISTS idx_gate155_connector ON source_gate_decisions_155(connector_id,decided_at);
CREATE TABLE IF NOT EXISTS source_status_events_155(
 event_id TEXT PRIMARY KEY, connector_id TEXT NOT NULL, previous_status TEXT,
 new_status TEXT NOT NULL, reason TEXT NOT NULL, actor TEXT NOT NULL,
 occurred_at TEXT NOT NULL, correlation_id TEXT,
 FOREIGN KEY(connector_id) REFERENCES connector_specs_154(connector_id)
);
'''
def ensure_build155_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_155)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','155.0')")
    db.conn.commit()
