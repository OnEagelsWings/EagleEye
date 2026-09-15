from __future__ import annotations
from typing import Any
from eagleeye_pro.version import BUILD, SCHEMA_VERSION

class Build2601CompatibilityService:
    BUILD = "260.1"
    def __init__(self, db: Any, *, parent: Any) -> None:
        self.db = db
        self.parent = parent

    def capabilities(self) -> dict[str, str]:
        rows = self.db.all("SELECT capability_key,introduced_build FROM capability_manifest_2601 WHERE status='active' ORDER BY capability_key")
        return {row["capability_key"]: row["introduced_build"] for row in rows}

    def has_capability(self, key: str, minimum_introduced_build: str | None = None) -> bool:
        row = self.db.one("SELECT introduced_build,status FROM capability_manifest_2601 WHERE capability_key=?", (key,))
        if not row or row["status"] != "active":
            return False
        if minimum_introduced_build is None:
            return True
        def parts(value: str) -> tuple[int, ...]:
            return tuple(int(x) for x in str(value).split("."))
        return parts(row["introduced_build"]) >= parts(minimum_introduced_build)

    def compatibility_report(self) -> dict[str, Any]:
        integrity = self.db.one("PRAGMA integrity_check")
        value = next(iter(integrity.values())) if integrity else "unknown"
        caps = self.capabilities()
        return {
            "build": BUILD,
            "schema_version": SCHEMA_VERSION,
            "sqlite_integrity": value,
            "capability_count": len(caps),
            "capabilities": caps,
            "historical_feature_contracts": True,
            "historical_schema_labels_required_for_current_runtime": False,
            "migration_tests_keep_explicit_versions": True,
            "automatic_external_action": False,
        }
