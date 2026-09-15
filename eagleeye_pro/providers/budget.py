from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any
import time

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, new_id, now_ts

@dataclass(frozen=True)
class ProviderBudgetProfile:
    provider_key: str
    window_seconds: int
    max_requests: int
    min_interval_seconds: float
    notes: str

DEFAULT_PROVIDER_BUDGETS = {
    "github_users_api": ProviderBudgetProfile("github_users_api", 3600, 30, 1.0, "Conservative local budget below unauthenticated public REST limit."),
    "brave_web_api": ProviderBudgetProfile("brave_web_api", 1, 1, 1.0, "One request per second sliding-window guard."),
    "brave_news_api": ProviderBudgetProfile("brave_news_api", 2, 1, 2.0, "News context is throttled for precise, non-bulk use."),
    "brave_image_api": ProviderBudgetProfile("brave_image_api", 2, 1, 2.0, "Image context only; no biometrics."),
    "wayback_cdx": ProviderBudgetProfile("wayback_cdx", 60, 12, 5.0, "Historical archive context; no bulk crawling."),
    "rdap_domain": ProviderBudgetProfile("rdap_domain", 60, 20, 2.0, "Domain registry context only."),
    "dns_local": ProviderBudgetProfile("dns_local", 60, 60, 0.5, "Local resolver only; no scans."),
    "gitlab_public_api": ProviderBudgetProfile("gitlab_public_api", 3600, 24, 2.0, "Conservative public GitLab user API budget."),
    "crtsh_json": ProviderBudgetProfile("crtsh_json", 60, 10, 5.0, "Certificate Transparency context only."),
}

class ProviderBudgetService:
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS mvfpe_provider_budget_windows (
          window_id TEXT PRIMARY KEY, provider_key TEXT NOT NULL UNIQUE, window_started_epoch REAL NOT NULL,
          used_requests INTEGER DEFAULT 0, last_request_epoch REAL DEFAULT 0, profile_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mvfpe_provider_budget_events (
          event_id TEXT PRIMARY KEY, provider_key TEXT NOT NULL, decision TEXT NOT NULL,
          reason TEXT NOT NULL, created_at TEXT NOT NULL, details_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_mvfpe_provider_budget_events_key ON mvfpe_provider_budget_events(provider_key, created_at);
        ''')
        self.db.conn.commit()

    def _profile(self, provider_key: str) -> ProviderBudgetProfile:
        return DEFAULT_PROVIDER_BUDGETS.get(provider_key, ProviderBudgetProfile(provider_key, 60, 6, 5.0, "Fallback low-throughput public OSINT budget."))

    def check(self, provider_key: str, *, consume: bool = False) -> Dict[str, Any]:
        profile = self._profile(provider_key)
        now = time.time()
        row = self.db.one("SELECT * FROM mvfpe_provider_budget_windows WHERE provider_key=?", [provider_key])
        reset = False
        if not row or now - float(row.get("window_started_epoch") or 0) >= profile.window_seconds:
            reset = True
            row = {"used_requests": 0, "last_request_epoch": 0.0, "window_started_epoch": now}
        used = int(row.get("used_requests") or 0)
        last = float(row.get("last_request_epoch") or 0.0)
        if used >= profile.max_requests:
            decision = {"allowed": False, "reason": "WINDOW_BUDGET_EXHAUSTED", "retry_after_seconds": max(1, int(profile.window_seconds - (now - float(row.get("window_started_epoch") or now)))), "profile": profile.__dict__}
        elif last and now - last < profile.min_interval_seconds:
            decision = {"allowed": False, "reason": "MIN_INTERVAL_NOT_MET", "retry_after_seconds": round(profile.min_interval_seconds - (now - last), 2), "profile": profile.__dict__}
        else:
            decision = {"allowed": True, "reason": "BUDGET_AVAILABLE", "retry_after_seconds": 0, "profile": profile.__dict__}
        if consume and decision["allowed"]:
            used += 1
            payload = dumps(profile.__dict__)
            if reset or not self.db.one("SELECT window_id FROM mvfpe_provider_budget_windows WHERE provider_key=?", [provider_key]):
                self.db.execute("INSERT OR REPLACE INTO mvfpe_provider_budget_windows(window_id,provider_key,window_started_epoch,used_requests,last_request_epoch,profile_json,updated_at) VALUES(?,?,?,?,?,?,?)", [new_id("pbw"), provider_key, now, used, now, payload, now_ts()])
            else:
                self.db.execute("UPDATE mvfpe_provider_budget_windows SET used_requests=?, last_request_epoch=?, profile_json=?, updated_at=? WHERE provider_key=?", [used, now, payload, now_ts(), provider_key])
            self.audit.log("provider_budget_consume", "provider_budget", provider_key, None, decision)
        self.db.execute("INSERT INTO mvfpe_provider_budget_events(event_id,provider_key,decision,reason,created_at,details_json) VALUES(?,?,?,?,?,?)", [new_id("pbe"), provider_key, "allow" if decision["allowed"] else "block", decision["reason"], now_ts(), dumps(decision)])
        return decision
