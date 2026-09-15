from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class SpearheadArchitecture66Service:
    """Build 66.0 strategic platform architecture for top-tier lawful PersonOSINT.

    This service does not perform live collection. It creates a versioned target
    architecture, capability map, maturity model and build roadmap so future
    work is constrained toward a review-first, evidence-grade PersonOSINT
    platform rather than uncontrolled data scraping.
    """
    BUILD = "66.0"

    CAPABILITIES: List[Dict[str, Any]] = [
        {"key": "legal_public_only_intake", "layer": "governance", "target": 95, "text": "Purpose binding, legal scope, prohibited-scope gate and public-only defaults."},
        {"key": "real_capture_vault", "layer": "collection", "target": 90, "text": "URL-normalized captures with HTML/text/screenshot/PDF metadata, hashing and custody."},
        {"key": "source_adapter_market", "layer": "collection", "target": 85, "text": "Pluggable lawful source adapters with budget, scope and review contracts."},
        {"key": "entity_resolution_doppler", "layer": "analysis", "target": 92, "text": "Identity anchors, alias handling, counter-evidence and Doppelgänger stress tests."},
        {"key": "investigation_graph", "layer": "analysis", "target": 90, "text": "Entity/identifier/source/finding/claim graph with confidence-aware edges."},
        {"key": "claim_evidence_matrix", "layer": "analysis", "target": 92, "text": "Every reportable statement traces to evidence, uncertainty and counter-checks."},
        {"key": "bias_quality_control", "layer": "analysis", "target": 88, "text": "Single-source bias, overclaiming risk and checklist-based analyst review."},
        {"key": "redaction_export_policy", "layer": "release", "target": 93, "text": "Export modes, redaction protocol, sensitive/minor/location gates."},
        {"key": "tamper_evident_casefile", "layer": "release", "target": 90, "text": "Hash-chain, manifest v2+, artifact hashes and verification report."},
        {"key": "analyst_cockpit", "layer": "ux", "target": 85, "text": "Case dashboard, graph, capture timeline, review board, report/export assistant."},
    ]

    ROADMAP: List[Dict[str, Any]] = [
        {"build": "66.0", "name": "Spearhead Platform Architecture", "outcome": "Capability model, target architecture, maturity gates."},
        {"build": "67.0", "name": "Source Adapter Architecture", "outcome": "Adapter contract, lawful source catalogue, validation gates."},
        {"build": "68.0", "name": "Investigation Graph Workspace", "outcome": "Graph v2 nodes/edges for persons, identifiers, sources, findings and claims."},
        {"build": "69.0", "name": "Capture Vault Foundation", "outcome": "Artifact metadata registry, hashes, custody and verification."},
        {"build": "70.0", "name": "Analyst Cockpit Backbone", "outcome": "Unified dashboard model for case readiness and next actions."},
    ]

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS spearhead_architecture_blueprints_66 (
          blueprint_id TEXT PRIMARY KEY, case_id TEXT DEFAULT '', goal TEXT NOT NULL,
          build_version TEXT NOT NULL, capabilities_json TEXT NOT NULL,
          roadmap_json TEXT NOT NULL, principles_json TEXT NOT NULL,
          maturity_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_spearhead_arch66_case ON spearhead_architecture_blueprints_66(case_id, created_at);
        """)
        self.db.conn.commit()

    def build_blueprint(self, case_id: str = "", goal: str = "top_tier_person_osint_platform", current_state: Dict[str, Any] | None = None, persist: bool = True) -> Dict[str, Any]:
        maturity = self.assess_maturity(current_state or {})
        principles = [
            "public_only_by_default",
            "review_first_not_auto_truth",
            "identity_before_claim",
            "capture_before_report",
            "source_chain_for_every_claim",
            "redaction_before_export",
            "tamper_evident_casefile",
            "bias_and_counter_evidence_visible",
            "operator_actions_audited",
        ]
        bid = new_id("arch66")
        result = {
            "blueprint_id": bid,
            "case_id": case_id,
            "goal": goal,
            "build_version": self.BUILD,
            "capabilities": self.CAPABILITIES,
            "roadmap": self.ROADMAP,
            "principles": principles,
            "maturity": maturity,
            "created_at": now_ts(),
        }
        if persist:
            self.db.execute("""INSERT INTO spearhead_architecture_blueprints_66
            (blueprint_id,case_id,goal,build_version,capabilities_json,roadmap_json,principles_json,maturity_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""", [bid, case_id, goal, self.BUILD, dumps(self.CAPABILITIES), dumps(self.ROADMAP), dumps(principles), dumps(maturity), result["created_at"]])
            self.audit.log("build", "spearhead_architecture_66", bid, case_id or None, {"goal": goal, "maturity_score": maturity["score"]})
        return result

    def assess_maturity(self, current_state: Dict[str, Any] | None = None) -> Dict[str, Any]:
        state = current_state or {}
        scores: Dict[str, int] = {}
        for cap in self.CAPABILITIES:
            key = cap["key"]
            raw = state.get(key, state.get(cap["layer"], 0))
            try:
                score = int(raw)
            except Exception:
                score = 0
            scores[key] = max(0, min(100, score))
        # Existing Build 65 baseline: architecture/compliance stronger than data/capture/UX.
        if not state:
            baseline = {
                "legal_public_only_intake": 82,
                "entity_resolution_doppler": 70,
                "claim_evidence_matrix": 72,
                "bias_quality_control": 75,
                "redaction_export_policy": 78,
                "tamper_evident_casefile": 70,
                "real_capture_vault": 35,
                "source_adapter_market": 30,
                "investigation_graph": 45,
                "analyst_cockpit": 40,
            }
            scores.update(baseline)
        weighted = sum(scores.values()) / max(1, len(scores))
        blockers = [k for k, v in scores.items() if v < 60]
        next_actions = self._next_actions(blockers)
        label = "market_alpha" if weighted < 55 else "controlled_beta" if weighted < 72 else "professional_beta" if weighted < 85 else "top_tier_candidate"
        return {"score": int(weighted), "label": label, "capability_scores": scores, "blockers": blockers, "next_actions": next_actions}

    def latest_blueprint(self, case_id: str = "") -> Dict[str, Any] | None:
        row = self.db.one("SELECT * FROM spearhead_architecture_blueprints_66 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id]) if case_id else self.db.one("SELECT * FROM spearhead_architecture_blueprints_66 ORDER BY created_at DESC LIMIT 1")
        if not row:
            return None
        row["capabilities"] = loads(row.pop("capabilities_json", "[]"), [])
        row["roadmap"] = loads(row.pop("roadmap_json", "[]"), [])
        row["principles"] = loads(row.pop("principles_json", "[]"), [])
        row["maturity"] = loads(row.pop("maturity_json", "{}"), {})
        return row

    def _next_actions(self, blockers: List[str]) -> List[str]:
        mapping = {
            "real_capture_vault": "implement_capture_artifact_hashing_and_verification",
            "source_adapter_market": "define_and_validate_lawful_source_adapter_contracts",
            "investigation_graph": "promote_graph_v2_as_core_workspace",
            "analyst_cockpit": "aggregate_case_readiness_into_cockpit",
        }
        return [mapping.get(b, f"raise_{b}_maturity") for b in blockers[:6]]
