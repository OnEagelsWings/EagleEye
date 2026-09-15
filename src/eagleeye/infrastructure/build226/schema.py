from __future__ import annotations
from typing import Any

SCHEMA_226 = r'''
CREATE TABLE IF NOT EXISTS source_intelligence_profiles_226(
 source_key TEXT PRIMARY KEY,
 title TEXT NOT NULL,
 route_class TEXT NOT NULL,
 adapter_family TEXT NOT NULL,
 target_types_json TEXT NOT NULL,
 expected_outputs_json TEXT NOT NULL,
 countries_json TEXT NOT NULL DEFAULT '["global"]',
 languages_json TEXT NOT NULL DEFAULT '["mul"]',
 network_capable INTEGER NOT NULL DEFAULT 0,
 requires_auth INTEGER NOT NULL DEFAULT 0,
 active INTEGER NOT NULL DEFAULT 0,
 health_state TEXT NOT NULL DEFAULT 'unknown',
 opsec_risk TEXT NOT NULL DEFAULT 'elevated',
 cost_class TEXT NOT NULL DEFAULT 'unknown',
 provenance_prior REAL NOT NULL DEFAULT 0.5,
 precision_prior REAL NOT NULL DEFAULT 0.5,
 recall_prior REAL NOT NULL DEFAULT 0.5,
 identity_risk REAL NOT NULL DEFAULT 0.5,
 source_group TEXT NOT NULL,
 notes TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 CHECK(opsec_risk IN ('low','elevated','high','critical')),
 CHECK(provenance_prior BETWEEN 0 AND 1),
 CHECK(precision_prior BETWEEN 0 AND 1),
 CHECK(recall_prior BETWEEN 0 AND 1),
 CHECK(identity_risk BETWEEN 0 AND 1)
);
CREATE INDEX IF NOT EXISTS idx_source_intel_profiles_226_route ON source_intelligence_profiles_226(route_class,active,health_state);

CREATE TABLE IF NOT EXISTS source_intelligence_queries_226(
 query_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 session_id TEXT NOT NULL DEFAULT '',
 plan_id TEXT NOT NULL DEFAULT '',
 objective TEXT NOT NULL,
 target_type TEXT NOT NULL,
 target_value_redacted TEXT NOT NULL,
 language TEXT NOT NULL DEFAULT 'und',
 countries_json TEXT NOT NULL DEFAULT '[]',
 budget_class TEXT NOT NULL DEFAULT 'standard',
 max_sources INTEGER NOT NULL DEFAULT 5,
 require_independence INTEGER NOT NULL DEFAULT 1,
 threat_level TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'ranked',
 selected_sources_json TEXT NOT NULL DEFAULT '[]',
 stop_conditions_json TEXT NOT NULL DEFAULT '[]',
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(budget_class IN ('minimal','standard','broad')),
 CHECK(max_sources BETWEEN 1 AND 12),
 CHECK(require_independence IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_source_intel_queries_226_case ON source_intelligence_queries_226(case_id,created_at);

CREATE TABLE IF NOT EXISTS query_expansions_226(
 expansion_id TEXT PRIMARY KEY,
 query_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 expansion_text TEXT NOT NULL,
 expansion_type TEXT NOT NULL,
 language TEXT NOT NULL DEFAULT 'und',
 country TEXT NOT NULL DEFAULT '',
 confidence REAL NOT NULL DEFAULT 0.5,
 selected INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(query_id) REFERENCES source_intelligence_queries_226(query_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(confidence BETWEEN 0 AND 1),
 CHECK(selected IN (0,1)),
 UNIQUE(query_id,expansion_text)
);
CREATE INDEX IF NOT EXISTS idx_query_expansions_226_query ON query_expansions_226(query_id,selected);

CREATE TABLE IF NOT EXISTS source_rankings_226(
 ranking_id TEXT PRIMARY KEY,
 query_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 source_key TEXT NOT NULL,
 rank_position INTEGER NOT NULL,
 eligible INTEGER NOT NULL DEFAULT 0,
 selected INTEGER NOT NULL DEFAULT 0,
 exclusion_reasons_json TEXT NOT NULL DEFAULT '[]',
 relevance_score REAL NOT NULL,
 information_gain_score REAL NOT NULL,
 precision_score REAL NOT NULL,
 recall_score REAL NOT NULL,
 provenance_score REAL NOT NULL,
 freshness_score REAL NOT NULL,
 independence_score REAL NOT NULL,
 locale_score REAL NOT NULL,
 stability_score REAL NOT NULL,
 latency_score REAL NOT NULL,
 cost_score REAL NOT NULL,
 opsec_score REAL NOT NULL,
 identity_risk_penalty REAL NOT NULL,
 final_score REAL NOT NULL,
 explanation_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(query_id) REFERENCES source_intelligence_queries_226(query_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(source_key) REFERENCES source_intelligence_profiles_226(source_key),
 CHECK(eligible IN (0,1)), CHECK(selected IN (0,1)),
 UNIQUE(query_id,source_key)
);
CREATE INDEX IF NOT EXISTS idx_source_rankings_226_query ON source_rankings_226(query_id,eligible,selected,rank_position);

CREATE TABLE IF NOT EXISTS source_routing_reviews_226(
 review_id TEXT PRIMARY KEY,
 query_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 decision TEXT NOT NULL,
 source_decisions_json TEXT NOT NULL,
 rationale TEXT NOT NULL,
 training_example_id TEXT NOT NULL DEFAULT '',
 reviewer TEXT NOT NULL,
 reviewed_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(query_id) REFERENCES source_intelligence_queries_226(query_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(decision IN ('approved','changes_requested','rejected'))
);
CREATE INDEX IF NOT EXISTS idx_source_routing_reviews_226_query ON source_routing_reviews_226(query_id,reviewed_at);

CREATE TABLE IF NOT EXISTS source_routing_preferences_226(
 preference_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 query_id TEXT NOT NULL,
 preferred_source_key TEXT NOT NULL,
 rejected_source_key TEXT NOT NULL DEFAULT '',
 context_json TEXT NOT NULL,
 rationale TEXT NOT NULL,
 reviewer TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(query_id) REFERENCES source_intelligence_queries_226(query_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_source_routing_preferences_226_source ON source_routing_preferences_226(preferred_source_key,created_at);

CREATE TABLE IF NOT EXISTS build226_events(
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
CREATE INDEX IF NOT EXISTS idx_build226_events_case ON build226_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_source_intel_queries_226_no_update BEFORE UPDATE ON source_intelligence_queries_226 BEGIN SELECT RAISE(ABORT,'source_intelligence_queries_226 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_intel_queries_226_no_delete BEFORE DELETE ON source_intelligence_queries_226 BEGIN SELECT RAISE(ABORT,'source_intelligence_queries_226 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_rankings_226_no_update BEFORE UPDATE ON source_rankings_226 BEGIN SELECT RAISE(ABORT,'source_rankings_226 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_rankings_226_no_delete BEFORE DELETE ON source_rankings_226 BEGIN SELECT RAISE(ABORT,'source_rankings_226 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_routing_reviews_226_no_update BEFORE UPDATE ON source_routing_reviews_226 BEGIN SELECT RAISE(ABORT,'source_routing_reviews_226 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_routing_reviews_226_no_delete BEFORE DELETE ON source_routing_reviews_226 BEGIN SELECT RAISE(ABORT,'source_routing_reviews_226 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_routing_preferences_226_no_update BEFORE UPDATE ON source_routing_preferences_226 BEGIN SELECT RAISE(ABORT,'source_routing_preferences_226 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_routing_preferences_226_no_delete BEFORE DELETE ON source_routing_preferences_226 BEGIN SELECT RAISE(ABORT,'source_routing_preferences_226 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build226_events_no_update BEFORE UPDATE ON build226_events BEGIN SELECT RAISE(ABORT,'build226_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build226_events_no_delete BEFORE DELETE ON build226_events BEGIN SELECT RAISE(ABORT,'build226_events is immutable'); END;
'''


def ensure_build226_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_226)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','226.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','226.0')")
    db.conn.commit()
