from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, now_ts
from eagleeye_pro.sources.source_types import SourceDefinition, default_source_definitions


class SourceIntelligenceRegistry:
    """Build 50.0 source catalog for precise, lawful Person/Org/Incident OSINT.

    All search planning must go through this registry. A source without policy metadata
    is not usable by the 46.x pipeline.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS source_intel_catalog (
          source_key TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          category TEXT NOT NULL,
          jurisdiction TEXT DEFAULT 'global',
          access_type TEXT NOT NULL,
          public_status TEXT NOT NULL,
          allowed_for_living_person TEXT NOT NULL,
          allowed_for_historical_research INTEGER DEFAULT 0,
          requires_manual_review INTEGER DEFAULT 1,
          review_rule TEXT DEFAULT 'always',
          claim_strength_default TEXT NOT NULL,
          person_data_risk TEXT DEFAULT 'medium',
          expected_evidence TEXT NOT NULL,
          prohibited_use_json TEXT NOT NULL,
          search_hints_json TEXT NOT NULL,
          notes TEXT DEFAULT '',
          active INTEGER DEFAULT 1,
          seeded_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_source_intel_category ON source_intel_catalog(category, active);
        CREATE INDEX IF NOT EXISTS idx_source_intel_jurisdiction ON source_intel_catalog(jurisdiction, active);
        ''')
        self.db.conn.commit()

    def seed_defaults(self, replace: bool = False) -> Dict[str, Any]:
        inserted = 0
        updated = 0
        for src in default_source_definitions():
            existing = self.get(src.source_key)
            if existing and not replace:
                continue
            data = src.as_dict()
            if existing:
                updated += 1
                self.db.execute('''UPDATE source_intel_catalog SET name=?,category=?,jurisdiction=?,access_type=?,public_status=?,allowed_for_living_person=?,allowed_for_historical_research=?,requires_manual_review=?,review_rule=?,claim_strength_default=?,person_data_risk=?,expected_evidence=?,prohibited_use_json=?,search_hints_json=?,notes=?,active=1,updated_at=? WHERE source_key=?''',
                    [data["name"], data["category"], data["jurisdiction"], data["access_type"], data["public_status"], data["allowed_for_living_person"], int(data["allowed_for_historical_research"]), int(data["requires_manual_review"]), data["review_rule"], data["claim_strength_default"], data["person_data_risk"], data["expected_evidence"], dumps(data["prohibited_use"]), dumps(data["search_hints"]), data.get("notes", ""), now_ts(), data["source_key"]])
            else:
                inserted += 1
                self.db.execute('''INSERT INTO source_intel_catalog(source_key,name,category,jurisdiction,access_type,public_status,allowed_for_living_person,allowed_for_historical_research,requires_manual_review,review_rule,claim_strength_default,person_data_risk,expected_evidence,prohibited_use_json,search_hints_json,notes,active,seeded_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    [data["source_key"], data["name"], data["category"], data["jurisdiction"], data["access_type"], data["public_status"], data["allowed_for_living_person"], int(data["allowed_for_historical_research"]), int(data["requires_manual_review"]), data["review_rule"], data["claim_strength_default"], data["person_data_risk"], data["expected_evidence"], dumps(data["prohibited_use"]), dumps(data["search_hints"]), data.get("notes", ""), 1, now_ts(), now_ts()])
        result = {"inserted": inserted, "updated": updated, "total_active": len(self.list_sources())}
        self.audit.log("seed", "source_intelligence_registry", "build46_defaults", None, result)
        return result

    def get(self, source_key: str) -> Optional[Dict[str, Any]]:
        row = self.db.one("SELECT * FROM source_intel_catalog WHERE source_key=?", [source_key])
        return self._decode(row) if row else None

    def list_sources(self, category: str | None = None, include_inactive: bool = False) -> List[Dict[str, Any]]:
        if category:
            rows = self.db.all("SELECT * FROM source_intel_catalog WHERE category=? AND (? OR active=1) ORDER BY category,source_key", [category, int(include_inactive)])
        else:
            rows = self.db.all("SELECT * FROM source_intel_catalog WHERE (? OR active=1) ORDER BY category,source_key", [int(include_inactive)])
        return [self._decode(r) for r in rows]

    def categories(self) -> List[str]:
        rows = self.db.all("SELECT DISTINCT category FROM source_intel_catalog WHERE active=1 ORDER BY category")
        return [r["category"] for r in rows]

    def _decode(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(row)
        row["prohibited_use"] = loads(row.pop("prohibited_use_json", "[]"), [])
        row["search_hints"] = loads(row.pop("search_hints_json", "[]"), [])
        row["allowed_for_historical_research"] = bool(row.get("allowed_for_historical_research"))
        row["requires_manual_review"] = bool(row.get("requires_manual_review"))
        row["active"] = bool(row.get("active"))
        return row

    def source_policy_summary(self, source_key: str) -> Dict[str, Any]:
        src = self.get(source_key)
        if not src:
            return {"allowed": False, "decision": "block", "reason": "SOURCE_NOT_REGISTERED"}
        if not src.get("active"):
            return {"allowed": False, "decision": "block", "reason": "SOURCE_INACTIVE", "source": src}
        return {
            "allowed": True,
            "decision": "review_required" if src.get("requires_manual_review") else "allow",
            "source_key": source_key,
            "category": src["category"],
            "person_data_risk": src["person_data_risk"],
            "requires_manual_review": src["requires_manual_review"],
            "expected_evidence": src["expected_evidence"],
            "claim_strength_default": src["claim_strength_default"],
            "prohibited_use": src["prohibited_use"],
        }
