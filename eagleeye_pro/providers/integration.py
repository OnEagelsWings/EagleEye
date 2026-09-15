from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlparse

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.policy import PolicyGate


@dataclass(frozen=True)
class ProviderCapability:
    key: str
    name: str
    provider_type: str
    mode: str
    requires_api_key: bool
    public_only: bool
    base_url: str
    compliance_tags: List[str]
    reliability: str
    notes: str


CAPABILITIES: List[ProviderCapability] = [
    ProviderCapability("bing_web", "Search: Bing", "search_engine", "manual_url", False, True, "https://www.bing.com/search?q={query}", ["public-web", "manual-review", "no-bypass"], "medium", "Öffnet eine öffentliche Such-URL; keine automatisierte Umgehung."),
    ProviderCapability("duckduckgo_web", "Search: DuckDuckGo", "search_engine", "manual_url", False, True, "https://duckduckgo.com/?q={query}", ["public-web", "manual-review", "no-bypass"], "medium", "Öffnet eine öffentliche Such-URL."),
    ProviderCapability("brave_web", "Search: Brave", "search_engine", "manual_url", False, True, "https://search.brave.com/search?q={query}", ["public-web", "manual-review", "no-bypass"], "medium", "Öffnet eine öffentliche Such-URL."),
    ProviderCapability("google_cse", "Google Programmable Search", "search_api", "api_optional", True, True, "https://www.googleapis.com/customsearch/v1?q={query}", ["public-web", "api-key", "licensed/terms", "human-review"], "medium", "API-fähig über Env Vars; Ergebnisse bleiben Review-Kandidaten."),
    ProviderCapability("brave_api", "Brave Search API", "search_api", "api_optional", True, True, "https://api.search.brave.com/res/v1/web/search?q={query}", ["public-web", "api-key", "licensed/terms", "human-review"], "medium", "API-fähiger Suchprovider; Rate Limits beachten."),
    ProviderCapability("brave_image_api", "Brave Image Search API", "image_api", "api_optional", True, True, "https://api.search.brave.com/res/v1/images/search?q={query}", ["public-image", "api-key", "no-auto-face-id", "human-review"], "medium", "API-fähige Bildsuche; keine automatische biometrische Identifikation."),
    ProviderCapability("brave_news_api", "Brave News Search API", "news_api", "api_optional", True, True, "https://api.search.brave.com/res/v1/news/search?q={query}", ["public-news", "api-key", "freshness-check", "human-review"], "medium_high", "API-fähige News-/Presse-Suche; Quellenkritik und Aktualität prüfen."),
    ProviderCapability("wayback_url", "Wayback Machine", "archive", "manual_url", False, True, "https://web.archive.org/web/*/{query}", ["archive", "historical-context", "public-web"], "medium", "Öffentliche Archive; Kontext- und Aktualitätsprüfung nötig."),
    ProviderCapability("wayback_cdx", "Wayback Machine", "archive_api", "api_public", False, True, "https://web.archive.org/cdx?url={query}&output=json&fl=timestamp,original,statuscode,mimetype,digest&filter=statuscode:200&limit=25", ["archive", "public-api", "rate-limit"], "medium", "Öffentliche CDX-Abfrage; keine Paywall-/Zugriffsumgehung."),
    ProviderCapability("rdap_domain", "RDAP/WHOIS", "domain_infrastructure", "api_public", False, True, "https://rdap.org/domain/{query}", ["domain", "public-registry", "non-intrusive"], "medium", "Nur öffentliche RDAP-Daten; keine Deanonymisierung erzwingen."),
    ProviderCapability("dns_local", "DNS Local Resolver", "domain_infrastructure", "local_lookup", False, True, "dns://{query}", ["domain", "non-intrusive", "metadata"], "medium", "Lokale DNS-Auflösung; keine Scans."),
    ProviderCapability("crtsh", "crt.sh Certificate Transparency", "certificate_transparency", "manual_url", False, True, "https://crt.sh/?q={query}", ["certificate-transparency", "public-web", "domain"], "medium", "Öffentliche Zertifikatstransparenz; Organisations-/Domainkontext."),
    ProviderCapability("crtsh_json", "crt.sh Certificate Transparency JSON", "certificate_transparency", "api_public", False, True, "https://crt.sh/?q={query}&output=json", ["certificate-transparency", "public-api", "domain"], "medium", "Öffentliche JSON-Abfrage bei crt.sh; Domain-/Organisationskontext."),
    ProviderCapability("github_public", "GitHub Public Profiles", "public_profile", "manual_url", False, True, "https://github.com/search?q={query}&type=users", ["public-profile", "technical-footprint", "manual-review"], "medium", "Nur öffentliche Profile/Repos; keine privaten Daten."),
    ProviderCapability("github_users_api", "GitHub Public User Search API", "public_profile_api", "api_public", False, True, "https://api.github.com/search/users?q={query}&per_page=10", ["public-profile", "public-api", "technical-footprint", "human-review"], "medium", "Öffentliche GitHub User Search API; keine privaten Repos oder Auth-Umgehung."),
    ProviderCapability("opencorporates", "OpenCorporates/Firmendaten", "company_registry", "manual_url", False, True, "https://opencorporates.com/companies?q={query}", ["company", "public/licensed", "manual-review"], "medium", "Firmen-/Organisationskontext; Lizenzbedingungen beachten."),
]


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def _domain_from_text(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return v
    if "://" in v:
        return urlparse(v).netloc.split(":")[0]
    v = v.replace("*.", "").strip("/")
    return v.split("/")[0]


class ProviderIntegrationService:
    """Build 22.0 provider integration layer.

    The service intentionally separates provider *preparation* from factual adoption.
    Results created here are connector candidates. They must still pass Review Inbox
    and Evidence Vault workflows before they can be used in reports.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def seed_capabilities(self) -> Dict[str, int]:
        added = 0
        updated = 0
        for cap in CAPABILITIES:
            row = self.db.one("SELECT provider_id FROM provider_registry WHERE name=?", [cap.name])
            if row:
                self.db.execute("""UPDATE provider_registry SET provider_type=?, base_url=?, enabled=1,
                requires_api_key=?, rate_limit_hint=?, public_only=?, compliance_tags_json=?, notes=? WHERE provider_id=?""",
                [cap.provider_type, cap.base_url, int(cap.requires_api_key), "provider_policy", int(cap.public_only), dumps(cap.compliance_tags), cap.notes, row["provider_id"]])
                provider_id = row["provider_id"]
                updated += 1
            else:
                provider_id = new_id("prov")
                self.db.execute("""INSERT INTO provider_registry(provider_id,name,provider_type,base_url,enabled,requires_api_key,rate_limit_hint,public_only,compliance_tags_json,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", [provider_id, cap.name, cap.provider_type, cap.base_url, 1, int(cap.requires_api_key), "provider_policy", int(cap.public_only), dumps(cap.compliance_tags), cap.notes])
                added += 1
            existing = self.db.one("SELECT capability_id FROM provider_capabilities WHERE provider_id=? AND capability_key=?", [provider_id, cap.key])
            payload = [provider_id, cap.key, cap.mode, int(cap.requires_api_key), int(cap.public_only), cap.base_url, dumps(cap.compliance_tags), cap.reliability, cap.notes]
            if existing:
                self.db.execute("""UPDATE provider_capabilities SET mode=?, requires_api_key=?, public_only=?, url_template=?, compliance_tags_json=?, default_reliability=?, notes=? WHERE capability_id=?""",
                [cap.mode, int(cap.requires_api_key), int(cap.public_only), cap.base_url, dumps(cap.compliance_tags), cap.reliability, cap.notes, existing["capability_id"]])
            else:
                self.db.execute("""INSERT INTO provider_capabilities(capability_id,provider_id,capability_key,mode,requires_api_key,public_only,url_template,compliance_tags_json,default_reliability,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", [new_id("capability")] + payload)
        self.audit.log("seed", "provider_capabilities", None, None, {"added": added, "updated": updated})
        return {"added": added, "updated": updated, "capabilities": len(CAPABILITIES)}

    def list_capabilities(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        where = "WHERE pr.enabled=1" if enabled_only else ""
        rows = self.db.all(f"""SELECT pc.*, pr.name AS provider_name, pr.provider_type, pr.enabled
        FROM provider_capabilities pc JOIN provider_registry pr ON pr.provider_id=pc.provider_id
        {where} ORDER BY pr.provider_type, pr.name, pc.capability_key""")
        for r in rows:
            r["compliance_tags_json"] = loads(r.get("compliance_tags_json"), [])
        return rows

    def set_provider_secret_ref(self, provider_name: str, env_var_name: str, notes: str = "") -> Dict[str, Any]:
        provider = self.db.one("SELECT * FROM provider_registry WHERE name=?", [provider_name])
        if not provider:
            raise KeyError("Provider nicht gefunden.")
        value = os.environ.get(env_var_name, "")
        secret_id = new_id("secret")
        self.db.execute("""INSERT INTO provider_secret_refs(secret_id,provider_id,env_var_name,key_last4,configured,created_at,notes)
        VALUES(?,?,?,?,?,?,?)""", [secret_id, provider["provider_id"], env_var_name, value[-4:] if value else "", int(bool(value)), now_ts(), notes])
        self.audit.log("configure", "provider_secret_ref", secret_id, None, {"provider": provider_name, "env_var": env_var_name, "configured": bool(value)})
        return self.db.one("SELECT * FROM provider_secret_refs WHERE secret_id=?", [secret_id])

    def _capability_by_key(self, capability_key: str) -> Dict[str, Any]:
        cap = self.db.one("""SELECT pc.*, pr.name AS provider_name, pr.provider_type, pr.enabled
        FROM provider_capabilities pc JOIN provider_registry pr ON pr.provider_id=pc.provider_id
        WHERE pc.capability_key=?""", [capability_key])
        if not cap:
            raise KeyError(f"Provider capability nicht gefunden: {capability_key}")
        if not cap.get("enabled"):
            raise ValueError("Provider ist deaktiviert.")
        return cap

    def build_provider_url(self, capability_key: str, query: str) -> str:
        cap = self._capability_by_key(capability_key)
        q = (query or "").strip()
        if not q:
            raise ValueError("Query fehlt.")
        if capability_key in {"rdap_domain", "dns_local"}:
            q = _domain_from_text(q)
        policy = PolicyGate.evaluate_query(q)
        if not policy.get("ok"):
            raise ValueError("Provider-Query blockiert: " + str(policy.get("reason")))
        template = cap["url_template"] or ""
        encoded = quote_plus(q)
        if capability_key in {"rdap_domain", "wayback_url", "wayback_cdx", "crtsh"}:
            encoded = q
        return template.replace("{query}", encoded)

    def create_provider_job(self, case_id: str, capability_key: str, query: str, purpose: str, target_id: str = "", notes: str = "") -> Dict[str, Any]:
        cap = self._capability_by_key(capability_key)
        url = self.build_provider_url(capability_key, query)
        rate = self._rate_limit_status(cap["provider_id"])
        if not rate["allowed"]:
            raise ValueError("Provider Rate Limit erreicht; später erneut ausführen oder Limit prüfen.")
        job_id = new_id("pjob")
        ts = now_ts()
        sensitivity = PolicyGate.classify_sensitivity("\n".join([query, purpose, notes]))
        self.db.execute("""INSERT INTO provider_jobs(job_id,case_id,target_id,provider_id,capability_key,query,purpose,request_url,status,sensitivity_json,created_at,updated_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", [job_id, case_id, target_id, cap["provider_id"], capability_key, query, purpose, url, "prepared", dumps(sensitivity), ts, ts, notes])
        self._provider_log(case_id, cap["provider_id"], job_id, "job_prepared", "ok", {"capability_key": capability_key, "query": query, "url": url, "sensitivity": sensitivity})
        self.audit.log("prepare", "provider_job", job_id, case_id, {"provider": cap["provider_name"], "capability": capability_key, "query": query})
        return self.get_job(job_id)

    def mark_job_opened(self, job_id: str) -> Dict[str, Any]:
        job = self.get_job(job_id)
        self.db.execute("UPDATE provider_jobs SET status=?, updated_at=? WHERE job_id=?", ["opened", now_ts(), job_id])
        self._touch_rate_limit(job["provider_id"])
        self._provider_log(job["case_id"], job["provider_id"], job_id, "manual_url_opened", "ok", {"url": job.get("request_url")})
        self.audit.log("open", "provider_job", job_id, job["case_id"], {"url": job.get("request_url")})
        return self.get_job(job_id)

    def run_local_dns_lookup(self, case_id: str, domain: str, purpose: str, target_id: str = "") -> Dict[str, Any]:
        job = self.create_provider_job(case_id, "dns_local", domain, purpose, target_id=target_id, notes="Build 22.0 non-intrusive local DNS lookup")
        host = _domain_from_text(domain)
        results: List[str] = []
        errors: List[str] = []
        try:
            infos = socket.getaddrinfo(host, None)
            for info in infos:
                addr = info[4][0]
                if addr not in results:
                    results.append(addr)
        except Exception as exc:
            errors.append(str(exc))
        status = "completed" if results else "completed_no_result"
        payload = {"domain": host, "addresses": results, "errors": errors, "non_intrusive": True}
        result_id = self._store_provider_result(job["job_id"], case_id, job["provider_id"], "dns_records", payload, source_url="dns://" + host, confidence="candidate", reliability="medium")
        self.db.execute("UPDATE provider_jobs SET status=?, result_count=?, updated_at=? WHERE job_id=?", [status, len(results), now_ts(), job["job_id"]])
        self._touch_rate_limit(job["provider_id"])
        self._provider_log(case_id, job["provider_id"], job["job_id"], "dns_lookup", status, payload)
        return {"job": self.get_job(job["job_id"]), "result_id": result_id, "addresses": results, "errors": errors}

    def import_provider_result(self, case_id: str, job_id: str, title: str, source_url: str, snippet: str, raw_payload: Optional[Dict[str, Any]] = None, confidence: str = "candidate", reliability: str = "medium") -> Dict[str, Any]:
        job = self.get_job(job_id)
        payload = raw_payload or {"title": title, "source_url": source_url, "snippet": snippet, "manual_import": True}
        result_id = self._store_provider_result(job_id, case_id, job["provider_id"], title, payload, source_url=source_url, snippet=snippet, confidence=confidence, reliability=reliability)
        self.db.execute("UPDATE provider_jobs SET status=?, result_count=result_count+1, updated_at=? WHERE job_id=?", ["result_imported", now_ts(), job_id])
        self._provider_log(case_id, job["provider_id"], job_id, "manual_result_imported", "ok", {"result_id": result_id, "source_url": source_url})
        return self.get_result(result_id)

    def create_review_items_from_results(self, case_id: str) -> Dict[str, Any]:
        rows = self.db.all("""SELECT pr.*, pj.query, p.name AS provider_name FROM provider_results pr
        JOIN provider_jobs pj ON pj.job_id=pr.job_id JOIN provider_registry p ON p.provider_id=pr.provider_id
        WHERE pr.case_id=? AND pr.review_item_id=''""", [case_id])
        created = 0
        for r in rows:
            marker = {
                "provider_result_id": r["result_id"],
                "provider": r["provider_name"],
                "reliability": r.get("reliability") or "medium",
                "source_url": r.get("source_url") or "",
                "guardrail": "provider_result_requires_human_review",
            }
            title = r.get("title") or "Provider Result"
            snippet = r.get("snippet") or json.dumps(loads(r.get("raw_payload_json"), {}), ensure_ascii=False)[:600]
            score = {"low": 0.35, "medium": 0.55, "high": 0.72}.get((r.get("reliability") or "medium").lower(), 0.55)
            item_id = new_id("rev")
            ts = now_ts()
            fingerprint = _sha256("|".join([(r.get("source_url") or "").lower().rstrip("/"), title.lower(), snippet[:200].lower()]))
            self.db.execute("""INSERT INTO review_items(item_id,case_id,source_type,provider,title,url,snippet,query,score,status,sensitivity_level,markers_json,normalized_url,fingerprint,quality_score,triage_reason,reviewer,notes,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [item_id, case_id, "provider_result", r["provider_name"], title, r.get("source_url") or "", snippet, r.get("query") or "", score, "new", "normal", dumps(marker), (r.get("source_url") or "").lower().rstrip("/"), fingerprint, score, "provider_result_candidate", "local-analyst", "Build 22.0 Provider Integration Pro: Ergebnis ist Review-Kandidat, kein Beweis.", ts, ts])
            self.db.execute("UPDATE provider_results SET review_item_id=? WHERE result_id=?", [item_id, r["result_id"]])
            created += 1
        self.audit.log("promote", "provider_results_to_review", None, case_id, {"created": created})
        return {"created_review_items": created, "pending_results_before": len(rows)}

    def run_health_checks(self) -> Dict[str, Any]:
        self.seed_capabilities()
        rows = self.db.all("SELECT * FROM provider_registry ORDER BY provider_type,name")
        out = []
        for p in rows:
            checks: List[str] = []
            status = "pass"
            if p.get("public_only") != 1:
                status = "review"; checks.append("provider_not_public_only")
            if p.get("requires_api_key"):
                refs = self.db.all("SELECT * FROM provider_secret_refs WHERE provider_id=? ORDER BY created_at DESC", [p["provider_id"]])
                configured = any(bool(r.get("configured")) for r in refs)
                if not configured:
                    status = "config_required"; checks.append("api_key_env_var_not_configured")
            caps = self.db.all("SELECT * FROM provider_capabilities WHERE provider_id=?", [p["provider_id"]])
            if not caps:
                status = "review"; checks.append("no_capability_registered")
            health_id = new_id("health")
            self.db.execute("""INSERT INTO provider_health_checks(health_id,provider_id,status,checked_at,latency_ms,issues_json,notes)
            VALUES(?,?,?,?,?,?,?)""", [health_id, p["provider_id"], status, now_ts(), 0, dumps(checks), "Offline/config health check; no external requests in selftest."])
            out.append({"provider": p["name"], "status": status, "issues": checks, "capabilities": len(caps)})
        self.audit.log("health_check", "provider_registry", None, None, {"providers": len(out)})
        return {"providers_checked": len(out), "results": out, "gate": "PROVIDER_HEALTH_CHECK_COMPLETE"}

    def provider_dashboard(self, case_id: str = "") -> Dict[str, Any]:
        providers = self.db.all("SELECT * FROM provider_registry")
        caps = self.db.all("SELECT * FROM provider_capabilities")
        jobs = self.db.all("SELECT status, COUNT(*) AS n FROM provider_jobs GROUP BY status")
        results = self.db.one("SELECT COUNT(*) AS n FROM provider_results" + (" WHERE case_id=?" if case_id else ""), [case_id] if case_id else [])
        health = self.db.all("""SELECT p.name, h.status, h.checked_at, h.issues_json FROM provider_health_checks h
        JOIN provider_registry p ON p.provider_id=h.provider_id
        WHERE h.checked_at=(SELECT MAX(h2.checked_at) FROM provider_health_checks h2 WHERE h2.provider_id=h.provider_id)
        ORDER BY p.name""")
        return {
            "providers": len(providers),
            "enabled_providers": sum(1 for p in providers if p.get("enabled")),
            "capabilities": len(caps),
            "jobs_by_status": {j["status"]: j["n"] for j in jobs},
            "results": (results or {}).get("n", 0),
            "latest_health": health,
        }

    def list_jobs(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("""SELECT pj.*, p.name AS provider_name FROM provider_jobs pj
        JOIN provider_registry p ON p.provider_id=pj.provider_id WHERE pj.case_id=? ORDER BY pj.created_at DESC""", [case_id])

    def list_results(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("""SELECT pr.*, p.name AS provider_name FROM provider_results pr
        JOIN provider_registry p ON p.provider_id=pr.provider_id WHERE pr.case_id=? ORDER BY pr.created_at DESC""", [case_id])

    def list_logs(self, case_id: str = "") -> List[Dict[str, Any]]:
        if case_id:
            return self.db.all("""SELECT pl.*, p.name AS provider_name FROM provider_logs pl JOIN provider_registry p ON p.provider_id=pl.provider_id
            WHERE pl.case_id=? ORDER BY pl.created_at DESC LIMIT 250""", [case_id])
        return self.db.all("""SELECT pl.*, p.name AS provider_name FROM provider_logs pl JOIN provider_registry p ON p.provider_id=pl.provider_id
        ORDER BY pl.created_at DESC LIMIT 250""")

    def get_job(self, job_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM provider_jobs WHERE job_id=?", [job_id])
        if not row:
            raise KeyError("Provider Job nicht gefunden.")
        return row

    def get_result(self, result_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM provider_results WHERE result_id=?", [result_id])
        if not row:
            raise KeyError("Provider Result nicht gefunden.")
        return row

    def _store_provider_result(self, job_id: str, case_id: str, provider_id: str, title: str, raw_payload: Dict[str, Any], source_url: str = "", snippet: str = "", confidence: str = "candidate", reliability: str = "medium") -> str:
        result_id = new_id("presult")
        payload_json = json.dumps(raw_payload or {}, ensure_ascii=False, sort_keys=True, default=str)
        raw_hash = _sha256(payload_json)
        self.db.execute("""INSERT INTO provider_results(result_id,job_id,case_id,provider_id,title,source_url,snippet,raw_payload_json,raw_hash,confidence,reliability,review_item_id,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", [result_id, job_id, case_id, provider_id, title, source_url, snippet, payload_json, raw_hash, confidence, reliability, "", now_ts()])
        return result_id

    def _provider_log(self, case_id: str, provider_id: str, job_id: str, event_type: str, status: str, details: Dict[str, Any]) -> None:
        self.db.execute("""INSERT INTO provider_logs(log_id,case_id,provider_id,job_id,event_type,status,details_json,created_at)
        VALUES(?,?,?,?,?,?,?,?)""", [new_id("plog"), case_id, provider_id, job_id, event_type, status, dumps(details), now_ts()])

    def _rate_limit_status(self, provider_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM provider_rate_limits WHERE provider_id=?", [provider_id])
        if not row:
            self.db.execute("""INSERT INTO provider_rate_limits(rate_id,provider_id,window_seconds,max_requests,used_requests,window_started_at,last_request_at,notes)
            VALUES(?,?,?,?,?,?,?,?)""", [new_id("rate"), provider_id, 3600, 120, 0, now_ts(), "", "Default local policy limit; service terms may be stricter."])
            return {"allowed": True, "used": 0, "max": 120}
        # Lightweight policy: reset if the ISO timestamp date is older; enough for local governance.
        try:
            started = time.strptime(row.get("window_started_at") or "1970-01-01T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ")
            age = time.time() - time.mktime(started)
        except Exception:
            age = 999999
        if age > int(row.get("window_seconds") or 3600):
            self.db.execute("UPDATE provider_rate_limits SET used_requests=0, window_started_at=?, last_request_at='' WHERE provider_id=?", [now_ts(), provider_id])
            return {"allowed": True, "used": 0, "max": row.get("max_requests") or 120}
        used = int(row.get("used_requests") or 0)
        mx = int(row.get("max_requests") or 120)
        return {"allowed": used < mx, "used": used, "max": mx}

    def _touch_rate_limit(self, provider_id: str) -> None:
        self._rate_limit_status(provider_id)
        self.db.execute("UPDATE provider_rate_limits SET used_requests=used_requests+1, last_request_at=? WHERE provider_id=?", [now_ts(), provider_id])
