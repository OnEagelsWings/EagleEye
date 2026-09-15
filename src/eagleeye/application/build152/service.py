from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from eagleeye_pro.core.database import dumps, new_id, now_ts

BUILD152_CONFIRMATION = "DOMAINKONSOLIDIERUNG 152 SPEICHERN"

DOMAIN_PORTS: dict[str, dict[str, Any]] = {
    "identity": {
        "canonical": "entity_resolution_115",
        "compatibility": ["identity", "entity_resolution_55_7", "identity_resolution_v3_78"],
        "contract": "candidate_generation_review_first",
    },
    "graph": {
        "canonical": "graph_hypothesis_130",
        "compatibility": ["graph", "graph_workspace_68", "advanced_graph_analytics_96", "knowledge_graph_116"],
        "contract": "provenance_aware_graph",
    },
    "evidence": {
        "canonical": "evidence_preservation_121",
        "compatibility": ["evidence", "evidence_integrity_91", "evidence_fusion_100"],
        "contract": "immutable_candidate_then_review",
    },
    "capture": {
        "canonical": "build150",
        "compatibility": ["browser_capture_60", "capture_identity_129", "browser_evidence_capture_150"],
        "contract": "public_only_opsec_gated",
    },
    "search": {
        "canonical": "research_strategy_128",
        "compatibility": ["search_workbench", "search_spearhead_58_1", "osint_core_59_0", "intelligence_orchestrator_127"],
        "contract": "plan_collect_normalize_review",
    },
}


def _digest(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

@dataclass(frozen=True)
class DomainBinding:
    port_name: str
    selected_service: str
    canonical: bool
    contract: str

class Build152DomainConsolidationService:
    BUILD = "152.0"
    MISSION = "Domain Consolidation"

    def __init__(self, db: Any, audit: Any, *, registry: Any) -> None:
        self.db = db
        self.audit = audit
        self.registry = registry
        self._seed_ports()

    def _seed_ports(self) -> None:
        now = now_ts()
        for name, spec in DOMAIN_PORTS.items():
            existing = self.db.one("SELECT created_at FROM domain_ports_152 WHERE port_name=?", (name,))
            created = (existing or {}).get("created_at") or now
            self.db.execute(
                "INSERT OR REPLACE INTO domain_ports_152(port_name,canonical_service,compatibility_services_json,policy,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (name, spec["canonical"], dumps(spec["compatibility"]), spec["contract"], "active", created, now),
            )

    def binding(self, port_name: str) -> DomainBinding:
        name = port_name.strip().casefold()
        if name not in DOMAIN_PORTS:
            raise KeyError(f"Unbekannter Domain-Port: {port_name}")
        spec = DOMAIN_PORTS[name]
        registered = {item.name for item in self.registry.descriptors()}
        candidates = [spec["canonical"], *spec["compatibility"]]
        selected = next((item for item in candidates if item in registered), "")
        if not selected:
            raise RuntimeError(f"Kein Service für Domain-Port {name} registriert")
        return DomainBinding(name, selected, selected == spec["canonical"], spec["contract"])

    def resolve(self, port_name: str) -> Any:
        binding = self.binding(port_name)
        return self.registry.get(binding.selected_service)

    def consolidation_report(self) -> dict[str, Any]:
        descriptors = {item.name: item for item in self.registry.descriptors()}
        ports: list[dict[str, Any]] = []
        compatibility_bindings = 0
        for name, spec in DOMAIN_PORTS.items():
            available = [service for service in [spec["canonical"], *spec["compatibility"]] if service in descriptors]
            selected = available[0] if available else ""
            is_canonical = selected == spec["canonical"]
            if selected and not is_canonical:
                compatibility_bindings += 1
            ports.append({
                "port": name,
                "canonical_service": spec["canonical"],
                "selected_service": selected,
                "canonical_available": spec["canonical"] in descriptors,
                "canonical_selected": is_canonical,
                "contract": spec["contract"],
                "available_compatibility_services": [s for s in spec["compatibility"] if s in descriptors],
            })
        return {
            "build": self.BUILD,
            "mission": self.MISSION,
            "person_osint_core_preserved": True,
            "review_first": True,
            "firefox_workflow_unchanged": True,
            "ports": ports,
            "canonical_ports": len(ports),
            "available_ports": sum(1 for p in ports if p["selected_service"]),
            "missing_ports": sum(1 for p in ports if not p["selected_service"]),
            "compatibility_bindings": compatibility_bindings,
        }

    def record_migration(self, *, port_name: str, source_service: str, state: str, rationale: str, actor: str) -> dict[str, Any]:
        name = port_name.strip().casefold()
        if name not in DOMAIN_PORTS:
            raise KeyError("Unbekannter Domain-Port")
        allowed = {"planned", "adapter", "validated", "retired"}
        state = state.strip().casefold()
        if state not in allowed:
            raise ValueError("Ungültiger Migrationsstatus")
        source = source_service.strip()
        if source not in DOMAIN_PORTS[name]["compatibility"]:
            raise ValueError("Quellservice gehört nicht zum Domain-Port")
        target = DOMAIN_PORTS[name]["canonical"]
        now = now_ts()
        existing = self.db.one("SELECT migration_id,created_at FROM domain_migrations_152 WHERE port_name=? AND source_service=?", (name, source))
        migration_id = (existing or {}).get("migration_id") or new_id("migration152")
        created = (existing or {}).get("created_at") or now
        self.db.execute(
            "INSERT OR REPLACE INTO domain_migrations_152(migration_id,port_name,source_service,target_service,state,rationale,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (migration_id, name, source, target, state, rationale.strip(), created, now),
        )
        self.audit.log("domain_migration_152", "domain_migration", migration_id, None, {"port": name, "source": source, "target": target, "state": state, "actor": actor})
        return self.db.one("SELECT * FROM domain_migrations_152 WHERE migration_id=?", (migration_id,))

    def save_snapshot(self, *, confirmation: str, actor: str) -> dict[str, Any]:
        if confirmation != BUILD152_CONFIRMATION:
            raise PermissionError("Explizite Bestätigung für die Domainkonsolidierung fehlt")
        payload = self.consolidation_report()
        snapshot_id = new_id("domain152")
        created = now_ts()
        digest = _digest(payload)
        self.db.execute(
            "INSERT INTO consolidation_snapshots_152(snapshot_id,created_at,actor,canonical_ports,available_ports,missing_ports,compatibility_bindings,payload_json,payload_sha256) VALUES(?,?,?,?,?,?,?,?,?)",
            (snapshot_id, created, actor, payload["canonical_ports"], payload["available_ports"], payload["missing_ports"], payload["compatibility_bindings"], dumps(payload), digest),
        )
        self.audit.log("domain_snapshot_152", "architecture", snapshot_id, None, {"sha256": digest, "ports": payload["canonical_ports"]})
        return {**payload, "snapshot_id": snapshot_id, "created_at": created, "payload_sha256": digest}
