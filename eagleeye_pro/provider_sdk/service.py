from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


@dataclass(frozen=True)
class ProviderProfile:
    connector_key: str
    display_name: str
    source_category: str
    public_only: bool
    supports_live_run: bool
    requires_api_key: bool
    max_per_hour: int
    terms_summary: str
    output_stage: str = "review_inbox_only"


DEFAULT_PROVIDER_PROFILES = [
    ProviderProfile("manual_public_url", "Manual Public URL", "public_pdf", True, False, False, 999, "Manual capture only; analyst verifies public access."),
    ProviderProfile("brave_search", "Brave Search API", "search_engine", True, True, True, 60, "Use official API, respect rate limits and 429 responses."),
    ProviderProfile("github_public", "GitHub Public API", "public_profile", True, True, False, 60, "Public REST API only; no private repos or credentialed bypass."),
    ProviderProfile("wayback_cdx", "Internet Archive CDX", "web_archive", True, True, False, 120, "Historical public snapshots; preserve timestamp context."),
    ProviderProfile("rdap_domain", "RDAP Domain", "infrastructure", True, True, False, 120, "Public registration data only; respect redactions/privacy proxies."),
    ProviderProfile("dns_local", "DNS Local Resolver", "infrastructure", True, True, False, 240, "Non-intrusive DNS lookups only."),
    ProviderProfile("crtsh", "crt.sh", "certificate_transparency", True, True, False, 120, "Public CT logs only; no active probing."),
]


class ProviderSDKService:
    """Build 50 provider SDK registry and safe preparation layer."""

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS provider_sdk_profiles_50 (
          connector_key TEXT PRIMARY KEY,
          display_name TEXT NOT NULL,
          source_category TEXT NOT NULL,
          public_only INTEGER DEFAULT 1,
          supports_live_run INTEGER DEFAULT 0,
          requires_api_key INTEGER DEFAULT 0,
          max_per_hour INTEGER DEFAULT 60,
          terms_summary TEXT NOT NULL,
          output_stage TEXT DEFAULT 'review_inbox_only',
          seeded_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS provider_prepared_runs_50 (
          prepared_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          connector_key TEXT NOT NULL,
          query TEXT NOT NULL,
          purpose TEXT NOT NULL,
          execute_live_requested INTEGER DEFAULT 0,
          decision TEXT NOT NULL,
          decision_reason TEXT NOT NULL,
          source_category TEXT NOT NULL,
          output_stage TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        ''')
        self.db.conn.commit()

    def seed_defaults(self) -> Dict[str, int]:
        created = 0
        for p in DEFAULT_PROVIDER_PROFILES:
            if not self.db.one("SELECT connector_key FROM provider_sdk_profiles_50 WHERE connector_key=?", [p.connector_key]):
                self.db.execute('''INSERT INTO provider_sdk_profiles_50(connector_key,display_name,source_category,public_only,supports_live_run,requires_api_key,max_per_hour,terms_summary,output_stage,seeded_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)''', [p.connector_key, p.display_name, p.source_category, int(p.public_only), int(p.supports_live_run), int(p.requires_api_key), p.max_per_hour, p.terms_summary, p.output_stage, now_ts(), now_ts()])
                created += 1
        self.audit.log("seed", "provider_sdk_profiles_50", "defaults", None, {"created": created})
        return {"created": created, "total": len(self.list_profiles())}

    def list_profiles(self) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM provider_sdk_profiles_50 ORDER BY source_category, connector_key")

    def get(self, connector_key: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM provider_sdk_profiles_50 WHERE connector_key=?", [connector_key])
        if not row:
            raise KeyError(connector_key)
        return row

    def prepare(self, case_id: str, connector_key: str, query: str, purpose: str, execute_live_requested: bool = False) -> Dict[str, Any]:
        profile = self.get(connector_key)
        decision = "allow"
        reason = "Prepared public-only run; results must enter review inbox."
        if execute_live_requested and not profile["supports_live_run"]:
            decision, reason = "block", "Connector does not support live runs."
        if not profile["public_only"]:
            decision, reason = "block", "Non-public provider profiles are not allowed."
        prepared_id = new_id("prun50")
        self.db.execute('''INSERT INTO provider_prepared_runs_50(prepared_id,case_id,connector_key,query,purpose,execute_live_requested,decision,decision_reason,source_category,output_stage,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''', [prepared_id, case_id, connector_key, query, purpose, int(execute_live_requested), decision, reason, profile["source_category"], profile["output_stage"], now_ts()])
        self.audit.log("prepare", "provider_prepared_run_50", prepared_id, case_id, {"connector_key": connector_key, "decision": decision})
        return {"prepared_id": prepared_id, "decision": decision, "decision_reason": reason, "provider": profile, "output_stage": profile["output_stage"]}
