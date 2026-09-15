from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.search_chain.service import SearchFundChainService


def _as_json_list(value: Any) -> str:
    if value is None:
        return dumps([])
    if isinstance(value, list):
        return dumps([str(v).strip() for v in value if str(v).strip()])
    if isinstance(value, tuple):
        return dumps([str(v).strip() for v in value if str(v).strip()])
    return dumps([v.strip() for v in str(value).replace(";", ",").split(",") if v.strip()])


class CaseCockpit54Service:
    """One-screen case cockpit: case + entity + seed information + chain metrics."""

    def __init__(self, db: Database, audit: AuditService, search_chain: SearchFundChainService, search_expander=None, target_service=None):
        self.db = db
        self.audit = audit
        self.search_chain = search_chain
        self.search_expander = search_expander
        # Build 54.3: compatibility bridge. One-Page Intake is the single source
        # of truth; older Query Factory / Query Intelligence modules still read
        # the legacy targets table. The bridge mirrors entities into targets so
        # the user does not have to enter the same name/fall twice.
        self.target_service = target_service
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS investigation_entities_54 (
          entity_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_type TEXT NOT NULL,
          display_name TEXT NOT NULL,
          known_names_json TEXT NOT NULL,
          aliases_json TEXT NOT NULL,
          dates_json TEXT NOT NULL,
          places_json TEXT NOT NULL,
          organizations_json TEXT NOT NULL,
          roles_json TEXT NOT NULL,
          identifiers_json TEXT NOT NULL,
          public_links_json TEXT NOT NULL,
          notes TEXT DEFAULT '',
          status TEXT DEFAULT 'active',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_entities54_case ON investigation_entities_54(case_id, entity_type, display_name);
        ''')
        self.db.conn.commit()

    def create_entity(self, case_id: str, entity_type: str, display_name: str, **kwargs: Any) -> Dict[str, Any]:
        entity_type = (entity_type or "person").lower().strip()
        if entity_type not in {"person", "organization", "incident"}:
            raise ValueError("entity_type must be person, organization or incident")
        if not display_name.strip():
            raise ValueError("display_name is required")
        entity_id = new_id("entity54")
        now = now_ts()
        fields = {
            "known_names_json": _as_json_list(kwargs.get("known_names") or display_name),
            "aliases_json": _as_json_list(kwargs.get("aliases")),
            "dates_json": _as_json_list(kwargs.get("dates")),
            "places_json": _as_json_list(kwargs.get("places") or kwargs.get("locations")),
            "organizations_json": _as_json_list(kwargs.get("organizations") or kwargs.get("companies")),
            "roles_json": _as_json_list(kwargs.get("roles")),
            "identifiers_json": _as_json_list(kwargs.get("identifiers")),
            "public_links_json": _as_json_list(kwargs.get("public_links") or kwargs.get("links")),
        }
        self.db.execute('''INSERT INTO investigation_entities_54(entity_id,case_id,entity_type,display_name,known_names_json,aliases_json,dates_json,places_json,organizations_json,roles_json,identifiers_json,public_links_json,notes,status,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [entity_id, case_id, entity_type, display_name.strip(), fields["known_names_json"], fields["aliases_json"], fields["dates_json"], fields["places_json"], fields["organizations_json"], fields["roles_json"], fields["identifiers_json"], fields["public_links_json"], kwargs.get("notes", ""), "active", now, now])
        entity = self.get_entity(entity_id)
        seed = self.search_chain.seed_from_entity(case_id, entity)
        legacy_target_id = self._ensure_legacy_target(entity)
        self.audit.log("create", "investigation_entity_54", entity_id, case_id, {"entity_type": entity_type, "seed_node": seed["root_node"]["node_id"], "legacy_target_id": legacy_target_id})
        entity["seed_chain"] = seed
        entity["legacy_target_id"] = legacy_target_id
        return entity

    def update_entity(self, entity_id: str, **updates: Any) -> Dict[str, Any]:
        entity = self.get_entity(entity_id)
        scalar = {}
        if "display_name" in updates and str(updates["display_name"]).strip():
            scalar["display_name"] = str(updates["display_name"]).strip()
        if "notes" in updates:
            scalar["notes"] = str(updates["notes"])
        for logical, column in [("known_names", "known_names_json"), ("aliases", "aliases_json"), ("dates", "dates_json"), ("places", "places_json"), ("organizations", "organizations_json"), ("roles", "roles_json"), ("identifiers", "identifiers_json"), ("public_links", "public_links_json")]:
            if logical in updates:
                scalar[column] = _as_json_list(updates.get(logical))
        if scalar:
            parts = ",".join([f"{k}=?" for k in scalar]) + ",updated_at=?"
            self.db.execute(f"UPDATE investigation_entities_54 SET {parts} WHERE entity_id=?", [*scalar.values(), now_ts(), entity_id])
        self.audit.log("update", "investigation_entity_54", entity_id, entity["case_id"], {"fields": sorted(scalar)})
        return self.get_entity(entity_id)

    def generate_search_parameters(self, entity_id: str) -> Dict[str, Any]:
        entity = self.get_entity(entity_id)
        # 1) chain-first visible queries
        root = self._root_node(entity["case_id"], entity_id)
        chain_queries = self.search_chain.generate_queries_from_node(root["node_id"], engine="google") if root else {"created_queries": [], "count": 0}
        # 2) full source-aware Build-46 expander, if present
        expander_plan = None
        if self.search_expander:
            seed = self._seed_for_expander(entity)
            mode = "organization" if entity["entity_type"] == "organization" else ("incident" if entity["entity_type"] == "incident" else "person")
            expander_plan = self.search_expander.create_plan(entity["case_id"], mode, seed, target_id=entity_id, notes="Build 54 cockpit-generated plan")
        self.audit.log("generate", "cockpit_search_parameters_54", entity_id, entity["case_id"], {"chain_queries": chain_queries.get("count", 0), "expander_plan": expander_plan.get("plan_id") if expander_plan else ""})
        return {"entity": entity, "chain_queries": chain_queries, "expander_plan": expander_plan}


    def _ensure_legacy_target(self, entity: Dict[str, Any]) -> str:
        """Mirror one-page entities into the legacy target table.

        This removes the previous duplication where the user had to create a
        person/anchor once in the new intake and a second time in older search
        modules before searches could start. Existing matching targets are
        reused.
        """
        if not self.target_service:
            return ""
        case_id = entity.get("case_id", "")
        name = entity.get("display_name", "").strip()
        if not case_id or not name:
            return ""
        existing = self.db.one("SELECT target_id FROM targets WHERE case_id=? AND lower(name)=lower(?) ORDER BY created_at LIMIT 1", [case_id, name])
        if existing:
            return existing["target_id"]
        aliases = ", ".join((entity.get("aliases") or []) + [n for n in (entity.get("known_names") or []) if n != name])
        locations = ", ".join(entity.get("places") or [])
        companies = ", ".join(entity.get("organizations") or [])
        domains = ", ".join([x for x in (entity.get("identifiers") or []) + (entity.get("public_links") or []) if "." in x or x.startswith("http")])
        notes = "Auto-created from One-Page Intake entity. " + (entity.get("notes") or "")
        try:
            created = self.target_service.create_target(case_id, name, aliases=aliases, locations=locations, companies=companies, domains=domains, notes=notes)
            return created.get("target_id", "")
        except Exception as exc:  # keep intake usable even if legacy bridge fails
            self.audit.log("warning", "legacy_target_bridge", entity.get("entity_id", ""), case_id, {"error": str(exc)})
            return ""

    def dashboard(self, case_id: str) -> Dict[str, Any]:
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id]) or {}
        entities = self.list_entities(case_id)
        chain = self.search_chain.build_chain(case_id)
        plans = self.db.all("SELECT plan_id,mode,parameter_count,status,generated_at FROM search_plans_46 WHERE case_id=? ORDER BY generated_at DESC", [case_id]) if self._table_exists("search_plans_46") else []
        artifacts = self.db.all("SELECT artifact_id,title,review_status,sha256,source_url FROM evidence_vault_artifacts_50 WHERE case_id=? ORDER BY created_at DESC LIMIT 25", [case_id]) if self._table_exists("evidence_vault_artifacts_50") else []
        profiles = self.db.all("SELECT profile_id,profile_type,content_hash,created_at FROM spearhead_profiles_50 WHERE case_id=? ORDER BY created_at DESC LIMIT 10", [case_id]) if self._table_exists("spearhead_profiles_50") else []
        return {"build": "55.3", "case": case, "entities": entities, "search_plans": plans, "chain_metrics": chain["metrics"], "recent_chain_nodes": chain["nodes"][-20:], "evidence_artifacts": artifacts, "profiles": profiles, "cockpit_sections": ["case", "entities", "seed_info", "search_parameters", "search_queries", "findings", "search_fund_chain", "profile_preview"]}

    def list_entities(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM investigation_entities_54 WHERE case_id=? ORDER BY created_at", [case_id])
        return [self._decode(r) for r in rows]

    def get_entity(self, entity_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_entities_54 WHERE entity_id=?", [entity_id])
        if not row:
            raise KeyError(entity_id)
        return self._decode(row)

    def _decode(self, row: Dict[str, Any]) -> Dict[str, Any]:
        for col in ["known_names_json", "aliases_json", "dates_json", "places_json", "organizations_json", "roles_json", "identifiers_json", "public_links_json"]:
            row[col.replace("_json", "")] = loads(row.pop(col, "[]"), [])
        return row

    def _root_node(self, case_id: str, entity_id: str) -> Dict[str, Any] | None:
        row = self.db.one("SELECT node_id FROM search_chain_nodes_54 WHERE case_id=? AND entity_id=? AND node_type='seed_info' AND parent_node_id='' ORDER BY created_at LIMIT 1", [case_id, entity_id])
        return self.search_chain.get_node(row["node_id"]) if row else None

    def _seed_for_expander(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": entity["display_name"],
            "aliases": entity.get("aliases", []),
            "places": entity.get("places", []),
            "organizations": entity.get("organizations", []),
            "dates": entity.get("dates", []),
            "keywords": entity.get("roles", []) + entity.get("identifiers", []),
        }

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]))
