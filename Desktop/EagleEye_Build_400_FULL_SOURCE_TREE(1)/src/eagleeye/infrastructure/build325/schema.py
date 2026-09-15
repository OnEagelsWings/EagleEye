from __future__ import annotations
import json
from typing import Any


def ensure_build325_schema(db: Any) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_source_registry_325(
      source_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, publisher TEXT NOT NULL,
      jurisdiction TEXT NOT NULL, source_class TEXT NOT NULL, access_mode TEXT NOT NULL,
      official_domain TEXT NOT NULL, base_url TEXT NOT NULL, documentation_url TEXT NOT NULL,
      auth_class TEXT NOT NULL, license_class TEXT NOT NULL, cost_class TEXT NOT NULL,
      freshness_class TEXT NOT NULL, source_authority TEXT NOT NULL, machine_readable INTEGER NOT NULL,
      independence_group TEXT NOT NULL, provenance_grade TEXT NOT NULL, automation_policy TEXT NOT NULL,
      review_status TEXT NOT NULL, catalog_standard TEXT NOT NULL, notes TEXT NOT NULL,
      last_reviewed_at TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_source_capabilities_325(
      capability_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, capability TEXT NOT NULL,
      record_family TEXT NOT NULL, query_dimension TEXT NOT NULL, method_class TEXT NOT NULL,
      supports_bulk INTEGER NOT NULL, supports_incremental INTEGER NOT NULL, supports_historical INTEGER NOT NULL,
      languages_json TEXT NOT NULL, identifier_types_json TEXT NOT NULL, coverage_json TEXT NOT NULL,
      rate_policy_json TEXT NOT NULL, limitations_json TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL, FOREIGN KEY(source_id) REFERENCES phase14_source_registry_325(source_id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_source_health_observations_325(
      observation_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, case_id TEXT NOT NULL,
      outcome TEXT NOT NULL, failure_class TEXT NOT NULL, latency_ms INTEGER NOT NULL,
      note TEXT NOT NULL, reviewed INTEGER NOT NULL, actor TEXT NOT NULL, observed_at TEXT NOT NULL,
      record_hash TEXT NOT NULL, FOREIGN KEY(source_id) REFERENCES phase14_source_registry_325(source_id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_source_selection_runs_325(
      run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, objective TEXT NOT NULL,
      need_json TEXT NOT NULL, candidates_json TEXT NOT NULL, selected_json TEXT NOT NULL,
      human_approval_required INTEGER NOT NULL, external_execution INTEGER NOT NULL,
      actor TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_source_catalog_exports_325(
      export_id TEXT PRIMARY KEY, export_format TEXT NOT NULL, catalog_json TEXT NOT NULL,
      source_count INTEGER NOT NULL, generated_by TEXT NOT NULL, generated_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_source_registry_attestations_325(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_security_attestations_325(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_325(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_325(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    for sql in (
      'CREATE INDEX IF NOT EXISTS idx_source_registry_325_class_jurisdiction ON phase14_source_registry_325(source_class,jurisdiction,review_status)',
      'CREATE INDEX IF NOT EXISTS idx_source_caps_325_capability ON phase14_source_capabilities_325(capability,record_family,source_id)',
      'CREATE INDEX IF NOT EXISTS idx_source_health_325_source ON phase14_source_health_observations_325(source_id,observed_at)',
      'CREATE INDEX IF NOT EXISTS idx_source_selection_325_case ON phase14_source_selection_runs_325(case_id,target_id,created_at)'
    ): db.execute(sql)

    hard = [
      ('Source routing must prefer a primary company register when the need is authoritative legal-entity identity.', ['primary-source-first','jurisdiction-match','candidate-only'], ['secondary-only conclusion','identity probability']),
      ('A bulk-capable source may be preferred for ingestion planning but not treated as more truthful because it is bulk.', ['bulk capability metadata','routing utility only'], ['bulk equals evidence strength']),
      ('Two mirrors in the same independence group must not count as two independent corroborators.', ['independence-group diversity'], ['source echo inflation']),
      ('Zero results from one provider must remain distinct from provider failure or coverage mismatch.', ['outcome taxonomy','broaden or reroute'], ['zero result equals false hypothesis']),
      ('Restricted or authenticated APIs may be catalogued without storing credential values.', ['auth metadata only','secret reference boundary'], ['credential persistence']),
      ('A local source catalog should be exportable in an interoperable DCAT-inspired representation.', ['dataset/data service metadata','stable identifiers'], ['automatic remote publication']),
      ('Source selection must explain why each source was chosen.', ['capability fit','authority','jurisdiction','independence'], ['opaque ranking']),
      ('Unreviewed custom sources remain candidates and are excluded from automated routing.', ['human review gate'], ['automatic activation']),
    ]
    sec = [
      ('Source registry URLs must not embed credentials or userinfo.', ['reject userinfo','https preferred'], ['secret-in-url']),
      ('No source is contacted while merely ranking catalog entries.', ['offline routing'], ['network side effect']),
      ('Provider failure must not trigger proxy bypass or direct fallback.', ['fail closed','egress policy preserved'], ['direct fallback']),
      ('API keys are requirements, not values, in the registry.', ['auth class only'], ['key material']),
      ('External execution requires existing human-gated connector workflow.', ['approval required'], ['silent execution']),
      ('Private-network sources cannot be promoted as public OSINT sources.', ['public-source boundary'], ['private pivot']),
      ('Source-health observations cannot automatically downgrade evidential credibility.', ['availability != truth'], ['health score equals evidence score']),
      ('OpenAPI/DCAT metadata ingestion cannot execute referenced remote resources automatically.', ['metadata parsing only'], ['reference fetching']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (2,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_325 VALUES(?,?,?,?,?,?,?)',(f'b325-source-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build325-source-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (2,5) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_325 VALUES(?,?,?,?,?,?,?)',(f'b325-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build325-security-review'))
