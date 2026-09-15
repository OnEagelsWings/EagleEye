from __future__ import annotations
from typing import Any

SCHEMA_252 = r"""
CREATE TABLE IF NOT EXISTS financial_flows_252 (
  flow_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
  payer_influence_entity_id TEXT NOT NULL, payee_influence_entity_id TEXT NOT NULL,
  instrument TEXT NOT NULL, assertion_class TEXT NOT NULL,
  amount_min TEXT NOT NULL, amount_max TEXT NOT NULL, currency TEXT NOT NULL,
  amount_basis TEXT NOT NULL, transaction_date TEXT NOT NULL, period_from TEXT NOT NULL, period_to TEXT NOT NULL,
  purpose TEXT NOT NULL, program_or_contract_ref TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL, source_quality TEXT NOT NULL,
  notes TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_finflows252_case ON financial_flows_252(case_id,assertion_class,currency,transaction_date);

CREATE TABLE IF NOT EXISTS financial_flow_reviews_252 (
  review_id TEXT PRIMARY KEY, flow_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL,
  decision TEXT NOT NULL, rationale TEXT NOT NULL, reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL, relation_edge_id TEXT NOT NULL,
  kernel_review_still_required INTEGER NOT NULL DEFAULT 1,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(flow_id) REFERENCES financial_flows_252(flow_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS financial_flow_links_252 (
  chain_link_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
  upstream_flow_id TEXT NOT NULL, downstream_flow_id TEXT NOT NULL,
  derivation_class TEXT NOT NULL, evidence_refs_json TEXT NOT NULL,
  rationale TEXT NOT NULL, status TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_finflowlinks252_case ON financial_flow_links_252(case_id,status,derivation_class);

CREATE TABLE IF NOT EXISTS financial_events_252 (
  event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL,
  object_type TEXT NOT NULL, object_id TEXT NOT NULL, actor TEXT NOT NULL,
  payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_finevents252_case ON financial_events_252(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_finflow252_no_update BEFORE UPDATE ON financial_flows_252 BEGIN SELECT RAISE(ABORT,'financial_flows_252 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_finflow252_no_delete BEFORE DELETE ON financial_flows_252 BEGIN SELECT RAISE(ABORT,'financial_flows_252 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_finreview252_no_update BEFORE UPDATE ON financial_flow_reviews_252 BEGIN SELECT RAISE(ABORT,'financial_flow_reviews_252 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_finreview252_no_delete BEFORE DELETE ON financial_flow_reviews_252 BEGIN SELECT RAISE(ABORT,'financial_flow_reviews_252 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_finlink252_no_update BEFORE UPDATE ON financial_flow_links_252 BEGIN SELECT RAISE(ABORT,'financial_flow_links_252 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_finlink252_no_delete BEFORE DELETE ON financial_flow_links_252 BEGIN SELECT RAISE(ABORT,'financial_flow_links_252 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_finevt252_no_update BEFORE UPDATE ON financial_events_252 BEGIN SELECT RAISE(ABORT,'financial_events_252 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_finevt252_no_delete BEFORE DELETE ON financial_events_252 BEGIN SELECT RAISE(ABORT,'financial_events_252 is immutable'); END;
"""

def ensure_build252_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_252)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','252.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','252.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('phase10_pack','influence_funding_investigation')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('phase10_module','financial_flow_accounting')")
    db.conn.commit()
