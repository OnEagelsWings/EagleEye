from __future__ import annotations
import json
from typing import Any

CAPABILITIES = {
    "phase4_core": "145",
    "identity_access": "146",
    "evidence_capture": "150",
    "crime_threat_workflow": "167",
    "social_platform_depth": "173",
    "geospatial_intelligence": "175",
    "verified_claims": "229",
    "coai_context": "227",
    "training_governance": "228",
    "canonical_objects_links": "235",
    "evidence_vault_provenance": "239",
    "opsec_agent": "243",
    "influence_research_foundation": "251",
    "financial_flow": "252",
    "german_sources": "253",
    "global_sources": "254",
    "document_provenance": "255",
    "entity_resolution": "256",
    "framing_analysis": "257",
    "claim_integrity": "258",
    "publication_review": "259",
    "phase10_qualification": "260",
    "test_contract_compatibility": "260.1",
}

SCHEMA = r'''
CREATE TABLE IF NOT EXISTS capability_manifest_2601(
 capability_key TEXT PRIMARY KEY,
 introduced_build TEXT NOT NULL,
 status TEXT NOT NULL,
 contract_kind TEXT NOT NULL,
 notes TEXT NOT NULL
);
'''

def ensure_build2601_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA)
    for key, introduced in CAPABILITIES.items():
        db.conn.execute(
            "INSERT OR REPLACE INTO capability_manifest_2601(capability_key,introduced_build,status,contract_kind,notes) VALUES(?,?,?,?,?)",
            (key, introduced, "active", "feature_contract", "Capability remains testable independently of current schema/build label."),
        )
    payload = json.dumps(CAPABILITIES, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    for key, value in (
        ("schema_version", "260.1"),
        ("application_build", "260.1"),
        ("maintenance_release", "test_debt_cleanup_feature_contracts"),
        ("capability_manifest", payload),
        ("test_contract_policy", "current_build_dynamic_historical_feature_contracts_migration_versions_explicit"),
    ):
        db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, value))
    db.conn.commit()
