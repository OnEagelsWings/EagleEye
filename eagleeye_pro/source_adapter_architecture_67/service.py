from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class SourceAdapterArchitecture67Service:
    """Build 67.0 source adapter architecture.

    Registers adapter specifications only. Execution remains outside this module
    and must be handled by approved provider/capture services with explicit legal
    scope. The contract blocks credentials, private endpoints and bypass modes.
    """
    ALLOWED_CATEGORIES = {"search", "web_capture", "document", "registry", "rdap_dns", "code_hosting", "archive", "manual_import"}
    REQUIRED_GATES = ["legal_scope", "url_policy", "provider_budget", "review_inbox", "audit_event", "redaction_on_export"]
    FORBIDDEN_FEATURES = {"login_bypass", "captcha_bypass", "paywall_bypass", "private_account_access", "credential_use", "live_location", "biometric_identification"}

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()
        self.seed_defaults()

    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS source_adapter_specs_67 (
          adapter_id TEXT PRIMARY KEY, key TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
          category TEXT NOT NULL, execution_mode TEXT NOT NULL, public_only INTEGER NOT NULL,
          gates_json TEXT NOT NULL, inputs_json TEXT NOT NULL, outputs_json TEXT NOT NULL,
          forbidden_features_json TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        """)
        self.db.conn.commit()

    def seed_defaults(self) -> None:
        defaults = [
            {"key": "manual_public_url_capture", "name": "Manual Public URL Capture", "category": "web_capture", "execution_mode": "manual_or_browser_helper", "inputs": ["url", "title", "snapshot_text"], "outputs": ["capture_artifact", "review_item", "evidence_chain_event"]},
            {"key": "public_document_import", "name": "Public Document Import", "category": "document", "execution_mode": "local_file_or_text", "inputs": ["file_path", "source_url", "document_date"], "outputs": ["artifact", "extracted_entities", "review_item"]},
            {"key": "rdap_dns_public_lookup", "name": "RDAP/DNS Public Lookup", "category": "rdap_dns", "execution_mode": "approved_live_provider", "inputs": ["domain"], "outputs": ["technical_identifier", "source_record", "review_item"]},
            {"key": "code_hosting_public_profile", "name": "Public Code Hosting Profile", "category": "code_hosting", "execution_mode": "approved_api_or_manual", "inputs": ["username", "profile_url"], "outputs": ["public_profile_hint", "repo_metadata", "review_item"]},
            {"key": "web_archive_lookup", "name": "Web Archive Lookup", "category": "archive", "execution_mode": "approved_live_provider", "inputs": ["url"], "outputs": ["archive_snapshot", "timestamped_source", "review_item"]},
        ]
        for spec in defaults:
            if not self.db.one("SELECT adapter_id FROM source_adapter_specs_67 WHERE key=?", [spec["key"]]):
                self.register_spec(**spec, persist_audit=False)

    def register_spec(self, key: str, name: str, category: str, execution_mode: str, inputs: List[str] | None = None, outputs: List[str] | None = None, gates: List[str] | None = None, forbidden_features: List[str] | None = None, persist_audit: bool = True) -> Dict[str, Any]:
        validation = self.validate_spec({"key": key, "name": name, "category": category, "execution_mode": execution_mode, "inputs": inputs or [], "outputs": outputs or [], "gates": gates or self.REQUIRED_GATES, "forbidden_features": forbidden_features or []})
        if validation["status"] == "blocked":
            raise ValueError("Adapter spec violates policy: " + "; ".join(validation["problems"]))
        existing = self.db.one("SELECT adapter_id FROM source_adapter_specs_67 WHERE key=?", [key])
        aid = existing["adapter_id"] if existing else new_id("ad67")
        ts = now_ts()
        payload = [aid, key, name, category, execution_mode, 1, dumps(gates or self.REQUIRED_GATES), dumps(inputs or []), dumps(outputs or []), dumps(forbidden_features or []), validation["status"], ts, ts]
        if existing:
            self.db.execute("""UPDATE source_adapter_specs_67 SET name=?, category=?, execution_mode=?, public_only=?, gates_json=?, inputs_json=?, outputs_json=?, forbidden_features_json=?, status=?, updated_at=? WHERE adapter_id=?""", [name, category, execution_mode, 1, dumps(gates or self.REQUIRED_GATES), dumps(inputs or []), dumps(outputs or []), dumps(forbidden_features or []), validation["status"], ts, aid])
        else:
            self.db.execute("""INSERT INTO source_adapter_specs_67(adapter_id,key,name,category,execution_mode,public_only,gates_json,inputs_json,outputs_json,forbidden_features_json,status,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", payload)
        if persist_audit:
            self.audit.log("register", "source_adapter_spec_67", aid, None, {"key": key, "status": validation["status"]})
        return self.get_spec(key)

    def validate_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        problems: List[str] = []
        warnings: List[str] = []
        if spec.get("category") not in self.ALLOWED_CATEGORIES:
            problems.append("unsupported_category")
        forbidden = set(spec.get("forbidden_features") or [])
        if forbidden & self.FORBIDDEN_FEATURES:
            problems.append("declares_forbidden_feature")
        gates = set(spec.get("gates") or [])
        missing = [g for g in self.REQUIRED_GATES if g not in gates]
        if missing:
            warnings.append("missing_recommended_gates:" + ",".join(missing))
        mode = str(spec.get("execution_mode") or "")
        if "bypass" in mode or "credential" in mode or "private" in mode:
            problems.append("unsafe_execution_mode")
        status = "blocked" if problems else "review_required" if warnings else "approved_contract"
        return {"status": status, "problems": problems, "warnings": warnings, "required_gates": self.REQUIRED_GATES}

    def get_spec(self, key: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM source_adapter_specs_67 WHERE key=?", [key])
        if not row:
            raise KeyError(key)
        for field in ["gates_json", "inputs_json", "outputs_json", "forbidden_features_json"]:
            row[field[:-5]] = loads(row.pop(field), [])
        return row

    def list_specs(self) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT key FROM source_adapter_specs_67 ORDER BY category,key")
        return [self.get_spec(r["key"]) for r in rows]
