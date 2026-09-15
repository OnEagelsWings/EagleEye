from __future__ import annotations
import json
from typing import Any

def ensure_build324_schema(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_graph_backend_profiles_324(
      profile_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, backend TEXT NOT NULL, mode TEXT NOT NULL,
      remote_adapter TEXT NOT NULL, config_json TEXT NOT NULL, connected INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_graph_nodes_324(
      node_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, node_type TEXT NOT NULL,
      canonical_key TEXT NOT NULL, label TEXT NOT NULL, properties_json TEXT NOT NULL, source_layer TEXT NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_graph_node_324 ON phase14_graph_nodes_324(case_id,target_id,node_type,canonical_key)")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_graph_assertions_324(
      assertion_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      subject_node_id TEXT NOT NULL, predicate TEXT NOT NULL, object_node_id TEXT NOT NULL, literal_value TEXT NOT NULL,
      polarity TEXT NOT NULL, assertion_status TEXT NOT NULL, valid_from TEXT NOT NULL, valid_to TEXT NOT NULL,
      observed_at TEXT NOT NULL, recorded_at TEXT NOT NULL, source_group TEXT NOT NULL, source_ref TEXT NOT NULL,
      evidence_object_id TEXT NOT NULL, dependency_key TEXT NOT NULL, discrimination_class TEXT NOT NULL,
      provenance_json TEXT NOT NULL, created_by TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_graph_assertions_324_sp ON phase14_graph_assertions_324(case_id,target_id,subject_node_id,predicate)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_graph_assertions_324_obj ON phase14_graph_assertions_324(case_id,target_id,object_node_id)")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_graph_imports_324(
      import_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, source_type TEXT NOT NULL,
      source_ref TEXT NOT NULL, nodes_created INTEGER NOT NULL, assertions_created INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_graph_conflicts_324(
      conflict_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, subject_node_id TEXT NOT NULL,
      predicate TEXT NOT NULL, assertion_a TEXT NOT NULL, assertion_b TEXT NOT NULL, temporal_relation TEXT NOT NULL,
      independent_sources INTEGER NOT NULL, rationale TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_graph_path_runs_324(
      run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, start_node_id TEXT NOT NULL,
      end_node_id TEXT NOT NULL, max_hops INTEGER NOT NULL, path_count INTEGER NOT NULL, result_json TEXT NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_graph_assessments_324(
      assessment_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, node_count INTEGER NOT NULL,
      assertion_count INTEGER NOT NULL, independent_source_groups INTEGER NOT NULL, provenance_coverage REAL NOT NULL,
      temporal_coverage REAL NOT NULL, weak_infrastructure_assertions INTEGER NOT NULL, conflict_count INTEGER NOT NULL,
      dependency_duplicate_groups INTEGER NOT NULL, open_questions_json TEXT NOT NULL, graph_readiness_score REAL NOT NULL,
      probability_claim_generated INTEGER NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_ai_graph_plans_324(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, objective TEXT NOT NULL,
      plan_json TEXT NOT NULL, human_approval_required INTEGER NOT NULL, external_execution INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_graph_attestations_324(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
      created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_security_attestations_324(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
      created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_hard_training_delta_324(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_security_training_delta_324(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)""")
    hard=[
      ('reified_assertions','Conflicting sources must coexist as distinct first-class assertions.', ['statement_identity','source_specific_provenance'], ['overwrite_conflict']),
      ('property_graph','Entities and directed typed relationships must remain queryable without flattening provenance.', ['typed_nodes','typed_directed_assertions'], ['untyped_blob_graph']),
      ('temporal','Temporal relations must distinguish before/after/overlap/containment rather than treating all dates as strings.', ['allen_interval_relation'], ['timeless_match']),
      ('dependency','Repeated assertions from one dependency group must not count as independent corroboration.', ['dependency_key'], ['echo_as_independent']),
      ('bounded_paths','Path exploration must be bounded and return provenance/source diversity for every path.', ['bounded_bfs','path_provenance'], ['unbounded_traversal']),
      ('weak_infrastructure','Shared hosting/ASN/certificate infrastructure must remain weak non-ownership evidence.', ['weak_discrimination_class'], ['shared_ip_equals_owner']),
      ('counterevidence','Counter assertions must remain traversable and visible in graph conflict analysis.', ['counter_polarity'], ['support_only_graph']),
      ('graph_metrics','Structural graph scores must not be converted into guilt, identity or probability claims.', ['structure_only_metrics'], ['centrality_equals_suspicion'])]
    sec=[
      ('local_graph','Portable graph backend stays local and no remote graph server auto-connects.', ['sqlite_local_graph'], ['automatic_remote_graph']),
      ('query_boundary','Graph traversal uses parameterized local SQL and bounded algorithms, not user-supplied Cypher.', ['no_dynamic_cypher'], ['raw_cypher_execution']),
      ('scope','Every node/assertion remains case and target scoped.', ['case_target_scope'], ['cross_case_leak']),
      ('evidence','Evidence object references must belong to the same case.', ['same_case_evidence'], ['foreign_case_evidence']),
      ('path_limit','Traversal hop and path counts are capped.', ['bounded_paths'], ['unbounded_walk']),
      ('source_echo','Dependency groups are retained through path analysis.', ['dependency_preserved'], ['echo_amplification']),
      ('weak_edge','Low-discrimination infrastructure edges cannot imply ownership automatically.', ['weak_edge_guard'], ['auto_ownership']),
      ('external','Graph operations do not fetch URLs or activate external reconnaissance.', ['no_graph_side_fetch'], ['graph_to_scan'])]
    for i,(_,sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (5,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_324 VALUES(?,?,?,?,?,?,?)',(f'b324-graph-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build324-graph-review'))
    for i,(_,sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (6,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_324 VALUES(?,?,?,?,?,?,?)',(f'b324-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build324-security-review'))
