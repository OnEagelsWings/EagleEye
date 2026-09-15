from __future__ import annotations


def ensure_workspace_schema_122(db) -> None:
    db.conn.executescript('''
    CREATE TABLE IF NOT EXISTS resolution_entities_115(
      resolution_entity_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_entity_id TEXT,
      entity_type TEXT NOT NULL, display_name TEXT NOT NULL, normalized_name TEXT NOT NULL,
      attributes_json TEXT NOT NULL, candidate_only INTEGER NOT NULL DEFAULT 1,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(case_id,source_entity_id));
    CREATE INDEX IF NOT EXISTS idx_resolution_entities115_name
      ON resolution_entities_115(case_id,entity_type,normalized_name);
    CREATE TABLE IF NOT EXISTS resolution_merge_proposals_115(
      proposal_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, comparison_id TEXT NOT NULL,
      canonical_entity_id TEXT NOT NULL, candidate_entity_id TEXT NOT NULL, state TEXT NOT NULL,
      requested_by TEXT NOT NULL, requested_at TEXT NOT NULL, reviewed_by TEXT,
      reviewed_at TEXT, decision_reason TEXT, UNIQUE(comparison_id));
    CREATE TABLE IF NOT EXISTS graph_relations_116(
      relation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, subject_entity_id TEXT NOT NULL,
      predicate TEXT NOT NULL, object_entity_id TEXT NOT NULL, current_version INTEGER NOT NULL,
      state TEXT NOT NULL, candidate_only INTEGER NOT NULL DEFAULT 1, created_by TEXT NOT NULL,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(case_id,subject_entity_id,predicate,object_entity_id));
    CREATE INDEX IF NOT EXISTS idx_graph_relations116_case
      ON graph_relations_116(case_id,state,predicate);
    CREATE TABLE IF NOT EXISTS timeline_events_117(
      event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL,
      title TEXT NOT NULL, description TEXT NOT NULL, start_date TEXT, end_date TEXT,
      date_precision TEXT NOT NULL, location_entity_id TEXT, state TEXT NOT NULL,
      candidate_only INTEGER NOT NULL DEFAULT 1, confidence REAL NOT NULL,
      derived_from_relation_id TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_timeline117_case_date
      ON timeline_events_117(case_id,start_date,end_date,state);
    CREATE TABLE IF NOT EXISTS contradictions_118(
      contradiction_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, conflict_type TEXT NOT NULL,
      title TEXT NOT NULL, rationale TEXT NOT NULL, severity REAL NOT NULL, impact REAL NOT NULL,
      state TEXT NOT NULL, candidate_only INTEGER NOT NULL DEFAULT 1, created_by TEXT NOT NULL,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_contradictions118_case
      ON contradictions_118(case_id,state,conflict_type);
    CREATE TABLE IF NOT EXISTS workspace_preferences_122(
      case_id TEXT NOT NULL, actor TEXT NOT NULL, active_section TEXT NOT NULL DEFAULT 'overview',
      filters_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL,
      PRIMARY KEY(case_id,actor), FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS workspace_actions_122(
      sequence INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT UNIQUE NOT NULL,
      case_id TEXT NOT NULL, actor TEXT NOT NULL, action_type TEXT NOT NULL,
      object_type TEXT NOT NULL, object_id TEXT NOT NULL, details_json TEXT NOT NULL,
      created_at TEXT NOT NULL, FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE);
    CREATE INDEX IF NOT EXISTS idx_workspace_actions122_case ON workspace_actions_122(case_id,sequence DESC);
    CREATE TABLE IF NOT EXISTS workspace_saved_views_122(
      view_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, actor TEXT NOT NULL, name TEXT NOT NULL,
      section TEXT NOT NULL, definition_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(case_id,actor,name), FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS workspace_recovery_1221(
      recovery_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, intake_id TEXT,
      operation TEXT NOT NULL, state TEXT NOT NULL, error_type TEXT NOT NULL,
      error_text TEXT NOT NULL, cleanup_ok INTEGER NOT NULL DEFAULT 1,
      details_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
      FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE);
    CREATE INDEX IF NOT EXISTS idx_workspace_recovery1221_case
      ON workspace_recovery_1221(case_id,created_at DESC,state);
    CREATE TABLE IF NOT EXISTS investigation_subject_links_1222(
      link_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL UNIQUE,
      resolution_entity_id TEXT NOT NULL UNIQUE, workflow_id TEXT NOT NULL UNIQUE,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE);
    CREATE INDEX IF NOT EXISTS idx_subject_links1222_case
      ON investigation_subject_links_1222(case_id,created_at);
    CREATE TABLE IF NOT EXISTS intake_bridges_1222(
      bridge_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_kind TEXT NOT NULL,
      source_id TEXT NOT NULL, intake_id TEXT NOT NULL UNIQUE, created_by TEXT NOT NULL,
      created_at TEXT NOT NULL, UNIQUE(case_id,source_kind,source_id),
      FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
      FOREIGN KEY(intake_id) REFERENCES provider_intake_120(intake_id) ON DELETE CASCADE);
    ''')
    db.conn.commit()
