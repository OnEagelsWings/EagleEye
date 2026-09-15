from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.policy import PolicyGate, MAX_MULTI_SEARCH_URLS

MAX_PROVIDER_QUERY_LENGTH = 512
MAX_LIVE_PROVIDER_RESULTS = 25
DEFAULT_TIMEOUT_SECONDS = 10


def _validate_public_http_url(url: str) -> str:
    parsed = urllib.parse.urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("provider endpoint must use public http/https")
    if parsed.username or parsed.password:
        raise ValueError("provider endpoint credentials are forbidden")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain", "0.0.0.0"} or host.endswith((".local", ".lan", ".internal")):
        raise ValueError("private provider endpoint is forbidden")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise ValueError("non-public provider endpoint is forbidden")
    # Resolve immediately before the request to reduce SSRF/DNS-rebinding exposure.
    for info in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM):
        resolved = ipaddress.ip_address(info[4][0])
        if not resolved.is_global:
            raise ValueError("provider endpoint resolved to a non-public address")
    return urllib.parse.urlunparse(parsed)


class _PublicOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, _validate_public_http_url(newurl))


@dataclass(frozen=True)
class RealProviderConnector:
    connector_key: str
    title: str
    family: str
    capability_key: str
    mode: str
    endpoint_template: str
    requires_api_key: bool
    env_var_name: str
    parser_key: str
    reliability: str
    guardrails: List[str]
    notes: str


REAL_CONNECTORS: List[RealProviderConnector] = [
    RealProviderConnector(
        "brave_web_api", "Brave Web Search API", "search_api", "brave_api", "api_json",
        "https://api.search.brave.com/res/v1/web/search?q={query}&count=10", True,
        "BRAVE_SEARCH_API_KEY", "brave_web", "medium_high",
        ["public_web_only", "api_key_env_var_only", "terms_rate_limits", "review_first"],
        "Livefähig mit BRAVE_SEARCH_API_KEY. Ergebnisse bleiben Provider Results/Review-Kandidaten.",
    ),
    RealProviderConnector(
        "brave_image_api", "Brave Image Search API", "image_api", "brave_image_api", "api_json",
        "https://api.search.brave.com/res/v1/images/search?q={query}&count=10", True,
        "BRAVE_SEARCH_API_KEY", "brave_image", "medium",
        ["public_image_context_only", "no_auto_face_id", "api_key_env_var_only", "review_first"],
        "Bild-/Medienkontext; keine automatische biometrische Identifikation.",
    ),
    RealProviderConnector(
        "brave_news_api", "Brave News Search API", "news_api", "brave_news_api", "api_json",
        "https://api.search.brave.com/res/v1/news/search?q={query}&count=10", True,
        "BRAVE_SEARCH_API_KEY", "brave_news", "medium_high",
        ["public_news_only", "check_freshness", "api_key_env_var_only", "review_first"],
        "News-/Pressekontext; Aktualität und Quellenqualität bleiben Review-Aufgabe.",
    ),
    RealProviderConnector(
        "wayback_cdx", "Wayback CDX Public API", "archive_api", "wayback_cdx", "api_json",
        "https://web.archive.org/cdx?url={query}&output=json&fl=timestamp,original,statuscode,mimetype,digest&filter=statuscode:200&limit=25", False,
        "", "wayback_cdx", "medium",
        ["public_archive", "historical_context", "check_date", "review_first"],
        "Öffentliche Archivdaten; Treffer sind historische Kontextspuren.",
    ),
    RealProviderConnector(
        "rdap_domain", "RDAP Domain Lookup", "domain_infrastructure", "rdap_domain", "api_json",
        "https://rdap.org/domain/{query}", False, "", "rdap_domain", "medium",
        ["public_registry", "domain_only", "non_intrusive", "review_first"],
        "Nicht-intrusive öffentliche RDAP-Daten; keine Deanonymisierung erzwingen.",
    ),
    RealProviderConnector(
        "dns_local", "Local DNS Resolver", "domain_infrastructure", "dns_local", "local_lookup",
        "dns://{query}", False, "", "dns_local", "medium",
        ["local_resolver", "non_intrusive", "no_port_scan", "review_first"],
        "Lokale DNS-Auflösung, keine Scans, keine Intrusion.",
    ),
    RealProviderConnector(
        "crtsh_json", "crt.sh Certificate Transparency JSON", "certificate_transparency", "crtsh_json", "api_json",
        "https://crt.sh/?q={query}&output=json", False, "", "crtsh_json", "medium",
        ["public_ct_logs", "domain_context", "non_intrusive", "review_first"],
        "Öffentliche Certificate-Transparency-Spuren; Domain-/Organisationskontext.",
    ),
    RealProviderConnector(
        "github_users_api", "GitHub Public User Search API", "public_profile_api", "github_users_api", "api_json",
        "https://api.github.com/search/users?q={query}&per_page=10", False, "", "github_users", "medium",
        ["public_profiles_only", "no_private_repos", "no_auth_required", "review_first"],
        "Öffentliche GitHub-Profile; keine privaten Repos oder Auth-Umgehung.",
    ),
]


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def _domain_from_text(value: str) -> str:
    v = (value or "").strip()
    if "://" in v:
        v = urllib.parse.urlparse(v).netloc
    v = v.replace("*.", "").strip().strip("/").split("/")[0].split(":")[0]
    return v.lower()


def _safe_short(value: str, limit: int = 600) -> str:
    value = (value or "").replace("\x00", " ").strip()
    return value[:limit]


class RealProviderConnectorService:
    """Build 44.0 – Query Intelligence Pro.

    Provides live-capable but review-first OSINT connectors. Tests and default GUI paths are
    dry-run/offline safe. Real external calls only happen when execute_live=True and required
    API keys/terms are configured through environment variables.
    """

    def __init__(self, db: Database, audit: AuditService, provider_integration=None):
        self.db = db
        self.audit = audit
        self.provider_integration = provider_integration
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS real_provider_connectors (
          connector_id TEXT PRIMARY KEY, connector_key TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
          family TEXT NOT NULL, capability_key TEXT NOT NULL, mode TEXT NOT NULL, endpoint_template TEXT NOT NULL,
          requires_api_key INTEGER DEFAULT 0, env_var_name TEXT DEFAULT '', parser_key TEXT NOT NULL,
          reliability TEXT DEFAULT 'medium', guardrails_json TEXT NOT NULL, active INTEGER DEFAULT 1,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS real_provider_runs (
          run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT DEFAULT '', connector_key TEXT NOT NULL,
          provider_job_id TEXT DEFAULT '', query TEXT NOT NULL, purpose TEXT NOT NULL, request_url TEXT NOT NULL,
          mode TEXT NOT NULL, execute_live INTEGER DEFAULT 0, status TEXT DEFAULT 'prepared', result_count INTEGER DEFAULT 0,
          error_count INTEGER DEFAULT 0, started_at TEXT NOT NULL, finished_at TEXT DEFAULT '', duration_ms INTEGER DEFAULT 0,
          issues_json TEXT NOT NULL, created_by TEXT DEFAULT 'local-analyst', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS real_provider_items (
          item_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, connector_key TEXT NOT NULL,
          provider_result_id TEXT DEFAULT '', title TEXT NOT NULL, source_url TEXT DEFAULT '', snippet TEXT DEFAULT '',
          published_at TEXT DEFAULT '', raw_json TEXT NOT NULL, raw_hash TEXT NOT NULL, reliability TEXT DEFAULT 'medium',
          confidence TEXT DEFAULT 'candidate', review_item_id TEXT DEFAULT '', created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES real_provider_runs(run_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS real_provider_health (
          health_id TEXT PRIMARY KEY, connector_key TEXT NOT NULL, status TEXT NOT NULL, checked_at TEXT NOT NULL,
          configured INTEGER DEFAULT 0, live_capable INTEGER DEFAULT 0, issues_json TEXT NOT NULL, notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS real_provider_normalization_rules (
          rule_id TEXT PRIMARY KEY, parser_key TEXT NOT NULL UNIQUE, title_path TEXT DEFAULT '', url_path TEXT DEFAULT '',
          snippet_path TEXT DEFAULT '', list_path TEXT DEFAULT '', notes TEXT DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_real_provider_runs_case ON real_provider_runs(case_id, connector_key, started_at);
        CREATE INDEX IF NOT EXISTS idx_real_provider_items_case ON real_provider_items(case_id, connector_key, created_at);
        CREATE INDEX IF NOT EXISTS idx_real_provider_health_key ON real_provider_health(connector_key, checked_at);
        ''')
        self.db.conn.commit()

    def seed_defaults(self) -> Dict[str, int]:
        self.ensure_schema()
        added = 0
        updated = 0
        ts = now_ts()
        for c in REAL_CONNECTORS:
            existing = self.db.one("SELECT connector_id FROM real_provider_connectors WHERE connector_key=?", [c.connector_key])
            payload = [c.title, c.family, c.capability_key, c.mode, c.endpoint_template, int(c.requires_api_key), c.env_var_name, c.parser_key, c.reliability, dumps(c.guardrails), 1, ts, c.notes]
            if existing:
                self.db.execute("""UPDATE real_provider_connectors SET title=?, family=?, capability_key=?, mode=?, endpoint_template=?, requires_api_key=?, env_var_name=?, parser_key=?, reliability=?, guardrails_json=?, active=?, updated_at=?, notes=? WHERE connector_id=?""", payload + [existing["connector_id"]])
                updated += 1
            else:
                self.db.execute("""INSERT INTO real_provider_connectors(connector_id,connector_key,title,family,capability_key,mode,endpoint_template,requires_api_key,env_var_name,parser_key,reliability,guardrails_json,active,created_at,updated_at,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [new_id("rpc"), c.connector_key, c.title, c.family, c.capability_key, c.mode, c.endpoint_template, int(c.requires_api_key), c.env_var_name, c.parser_key, c.reliability, dumps(c.guardrails), 1, ts, ts, c.notes])
                added += 1
        for parser_key in sorted({c.parser_key for c in REAL_CONNECTORS}):
            self.db.execute("""INSERT OR IGNORE INTO real_provider_normalization_rules(rule_id,parser_key,notes,created_at) VALUES(?,?,?,?)""", [new_id("rpn"), parser_key, "Build 44.0 parser profile; normalization implemented in code.", ts])
        if self.provider_integration:
            self.provider_integration.seed_capabilities()
        self.audit.log("seed", "real_provider_connectors", None, None, {"added": added, "updated": updated, "connectors": len(REAL_CONNECTORS)})
        return {"added": added, "updated": updated, "connectors": len(REAL_CONNECTORS)}

    def list_connectors(self, active_only: bool = True) -> List[Dict[str, Any]]:
        where = "WHERE active=1" if active_only else ""
        rows = self.db.all(f"SELECT * FROM real_provider_connectors {where} ORDER BY family, title")
        for r in rows:
            r["guardrails"] = loads(r.get("guardrails_json"), [])
            r["configured"] = self._is_configured(r)
            r["live_capable"] = (not r.get("requires_api_key")) or r["configured"]
        return rows

    def health_check(self, execute_live: bool = False) -> Dict[str, Any]:
        self.seed_defaults()
        results = []
        for c in self.list_connectors(active_only=True):
            configured = self._is_configured(c)
            issues = []
            status = "pass"
            if int(c.get("requires_api_key") or 0) and not configured:
                status = "config_required"
                issues.append("api_key_env_var_not_set")
            if execute_live and status == "pass" and c.get("mode") == "api_json":
                # Do not ping arbitrary user queries; health only confirms connector can be prepared.
                issues.append("live_ping_skipped_use_case_run")
            self.db.execute("""INSERT INTO real_provider_health(health_id,connector_key,status,checked_at,configured,live_capable,issues_json,notes) VALUES(?,?,?,?,?,?,?,?)""", [new_id("rph"), c["connector_key"], status, now_ts(), int(configured), int((not c.get("requires_api_key")) or configured), dumps(issues), "Build 44.0 connector health; no default external call."])
            results.append({"connector_key": c["connector_key"], "title": c["title"], "status": status, "configured": configured, "issues": issues})
        return {"connectors_checked": len(results), "results": results, "gate": "REAL_PROVIDER_HEALTH_COMPLETE"}

    def prepare_run(self, case_id: str, connector_key: str, query: str, purpose: str, target_id: str = "", notes: str = "") -> Dict[str, Any]:
        c = self._connector(connector_key)
        q = self._normalize_query_for_connector(c, query)
        self._guard_query(q)
        url = self._build_url(c, q)
        run_id = new_id("rprun")
        ts = now_ts()
        issues = self._preflight_issues(c, execute_live=False)
        status = "config_required" if any(i == "api_key_env_var_not_set" for i in issues) else "prepared"
        provider_job_id = ""
        if self.provider_integration:
            try:
                job = self.provider_integration.create_provider_job(case_id, c["capability_key"], q, purpose, target_id=target_id, notes=f"Build 44.0 Real Provider prepared via {connector_key}: {notes}")
                provider_job_id = job.get("job_id", "")
            except Exception as exc:
                issues.append("provider_job_prepare_failed:" + _safe_short(str(exc), 180))
        self.db.execute("""INSERT INTO real_provider_runs(run_id,case_id,target_id,connector_key,provider_job_id,query,purpose,request_url,mode,execute_live,status,result_count,error_count,started_at,issues_json,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [run_id, case_id, target_id, connector_key, provider_job_id, q, purpose, url, c["mode"], 0, status, 0, len(issues), ts, dumps(issues), notes])
        self.audit.log("prepare", "real_provider_run", run_id, case_id, {"connector": connector_key, "status": status, "issues": issues})
        return self.get_run(run_id)

    def run_connector(self, case_id: str, connector_key: str, query: str, purpose: str, target_id: str = "", execute_live: bool = False, sample_payload: Any = None, notes: str = "") -> Dict[str, Any]:
        c = self._connector(connector_key)
        q = self._normalize_query_for_connector(c, query)
        self._guard_query(q)
        run = self.prepare_run(case_id, connector_key, q, purpose, target_id=target_id, notes=notes)
        t0 = time.perf_counter()
        issues = loads(run.get("issues_json"), []) or []
        status = "prepared"
        raw_payload: Any = sample_payload
        if c["mode"] == "local_lookup":
            raw_payload = self._run_dns_local(q)
            status = "completed"
            execute_live = False
        elif sample_payload is not None:
            status = "completed_sample"
        elif execute_live:
            live_issues = self._preflight_issues(c, execute_live=True)
            issues.extend(live_issues)
            if live_issues:
                status = "blocked_preflight"
            else:
                try:
                    raw_payload = self._http_json(c, self._build_url(c, q))
                    status = "completed"
                except Exception as exc:
                    issues.append("http_error:" + _safe_short(str(exc), 260))
                    status = "failed"
        else:
            status = "dry_run_ready" if not issues else "dry_run_config_required"
        normalized = self._normalize_payload(c["parser_key"], raw_payload, q) if raw_payload is not None else []
        stored = []
        provider_result_ids: List[str] = []
        for item in normalized[:MAX_LIVE_PROVIDER_RESULTS]:
            item_id = new_id("rpitem")
            raw = item.get("raw", item)
            raw_json = dumps(raw)
            raw_hash = _sha256(raw_json)
            title = _safe_short(item.get("title") or c["title"])
            source_url = _safe_short(item.get("url") or run.get("request_url") or "", 1500)
            snippet = _safe_short(item.get("snippet") or "")
            published_at = _safe_short(item.get("published_at") or "", 80)
            provider_result_id = ""
            if self.provider_integration and run.get("provider_job_id"):
                try:
                    pres = self.provider_integration.import_provider_result(case_id, run["provider_job_id"], title, source_url, snippet, raw_payload=raw, confidence="candidate", reliability=c.get("reliability") or "medium")
                    provider_result_id = pres.get("result_id", "")
                    provider_result_ids.append(provider_result_id)
                except Exception as exc:
                    issues.append("provider_result_import_failed:" + _safe_short(str(exc), 180))
            self.db.execute("""INSERT INTO real_provider_items(item_id,run_id,case_id,connector_key,provider_result_id,title,source_url,snippet,published_at,raw_json,raw_hash,reliability,confidence,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [item_id, run["run_id"], case_id, connector_key, provider_result_id, title, source_url, snippet, published_at, raw_json, raw_hash, c.get("reliability") or "medium", "candidate", now_ts()])
            stored.append({"item_id": item_id, "title": title, "url": source_url, "provider_result_id": provider_result_id})
        duration_ms = int((time.perf_counter() - t0) * 1000)
        self.db.execute("""UPDATE real_provider_runs SET execute_live=?, status=?, result_count=?, error_count=?, finished_at=?, duration_ms=?, issues_json=? WHERE run_id=?""", [int(execute_live), status, len(stored), len(issues), now_ts(), duration_ms, dumps(issues), run["run_id"]])
        self.audit.log("run", "real_provider_connector", run["run_id"], case_id, {"connector": connector_key, "status": status, "stored": len(stored), "issues": issues, "live": execute_live})
        return {"run": self.get_run(run["run_id"]), "stored_items": stored, "provider_result_ids": provider_result_ids, "issues": issues, "status": status}

    def results_to_review(self, case_id: str) -> Dict[str, Any]:
        if not self.provider_integration:
            return {"created_review_items": 0, "reason": "provider_integration_unavailable"}
        before = self.db.one("SELECT COUNT(*) AS n FROM provider_results WHERE case_id=? AND review_item_id=''", [case_id]) or {"n": 0}
        res = self.provider_integration.create_review_items_from_results(case_id)
        rows = self.db.all("""SELECT rpi.item_id, pr.review_item_id FROM real_provider_items rpi
        JOIN provider_results pr ON pr.result_id=rpi.provider_result_id
        WHERE rpi.case_id=? AND rpi.review_item_id='' AND pr.review_item_id<>''""", [case_id])
        for row in rows:
            self.db.execute("UPDATE real_provider_items SET review_item_id=? WHERE item_id=?", [row["review_item_id"], row["item_id"]])
        res["pending_provider_results_before"] = before.get("n", 0)
        res["linked_real_provider_items"] = len(rows)
        return res

    def dashboard(self, case_id: str = "") -> Dict[str, Any]:
        connectors = self.list_connectors(active_only=True)
        params = [case_id] if case_id else []
        where = "WHERE case_id=?" if case_id else ""
        runs = self.db.all(f"SELECT * FROM real_provider_runs {where} ORDER BY started_at DESC LIMIT 50", params)
        items = self.db.all(f"SELECT * FROM real_provider_items {where} ORDER BY created_at DESC LIMIT 50", params)
        health = self.db.all("""SELECT * FROM real_provider_health WHERE checked_at IN
        (SELECT MAX(checked_at) FROM real_provider_health GROUP BY connector_key) ORDER BY connector_key""")
        status_counts: Dict[str, int] = {}
        for r in runs:
            status_counts[r.get("status") or "unknown"] = status_counts.get(r.get("status") or "unknown", 0) + 1
        configured = sum(1 for c in connectors if c.get("configured"))
        api_required = sum(1 for c in connectors if int(c.get("requires_api_key") or 0))
        return {
            "connectors": connectors,
            "runs": runs,
            "items": items,
            "health": health,
            "status_counts": status_counts,
            "configured_api_connectors": configured,
            "api_required_connectors": api_required,
            "gate": "REAL_PROVIDER_CONNECTORS_READY",
            "review_first_chain": "Connector → Provider Result → Review Inbox → Evidence Vault → Report",
        }

    def get_run(self, run_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM real_provider_runs WHERE run_id=?", [run_id])
        if not row:
            raise KeyError("Real Provider Run nicht gefunden.")
        return row

    def _connector(self, connector_key: str) -> Dict[str, Any]:
        self.seed_defaults()
        row = self.db.one("SELECT * FROM real_provider_connectors WHERE connector_key=? AND active=1", [connector_key])
        if not row:
            raise KeyError(f"Real Provider Connector nicht gefunden: {connector_key}")
        row["guardrails"] = loads(row.get("guardrails_json"), [])
        return row

    def _is_configured(self, c: Dict[str, Any]) -> bool:
        if not int(c.get("requires_api_key") or 0):
            return True
        env = c.get("env_var_name") or ""
        return bool(env and os.environ.get(env))

    def _preflight_issues(self, c: Dict[str, Any], execute_live: bool) -> List[str]:
        issues: List[str] = []
        if int(c.get("requires_api_key") or 0) and not self._is_configured(c):
            issues.append("api_key_env_var_not_set")
        if execute_live and c.get("mode") == "manual_url":
            issues.append("manual_url_connector_no_live_fetch")
        return issues

    def _normalize_query_for_connector(self, c: Dict[str, Any], query: str) -> str:
        q = (query or "").strip()
        if c.get("parser_key") in {"rdap_domain", "dns_local", "crtsh_json", "wayback_cdx"}:
            maybe_domain = _domain_from_text(q)
            if maybe_domain and "." in maybe_domain and " " not in maybe_domain:
                return maybe_domain
        return q

    def _guard_query(self, query: str) -> None:
        q = (query or "").strip()
        if not q:
            raise ValueError("Query fehlt.")
        if len(q) > MAX_PROVIDER_QUERY_LENGTH:
            raise ValueError("Provider-Query zu lang.")
        policy = PolicyGate.evaluate_query(q)
        if not policy.get("ok"):
            raise ValueError("Provider-Query blockiert: " + str(policy.get("reason")))

    def _build_url(self, c: Dict[str, Any], query: str) -> str:
        q = query
        if c.get("parser_key") in {"rdap_domain", "dns_local"}:
            encoded = urllib.parse.quote(q, safe=".-_")
        elif c.get("parser_key") in {"crtsh_json", "wayback_cdx"} and "." in q and " " not in q:
            encoded = urllib.parse.quote(q, safe="*.-_:/")
        else:
            encoded = urllib.parse.quote_plus(q)
        return (c.get("endpoint_template") or "").replace("{query}", encoded)

    def _http_json(self, c: Dict[str, Any], url: str) -> Any:
        headers = {"User-Agent": "EagleEye-PersonOSINT-Pro/44.0 (+local analyst tool; review-first)"}
        if int(c.get("requires_api_key") or 0):
            api_key = os.environ.get(c.get("env_var_name") or "")
            if not api_key:
                raise RuntimeError("API key env var missing")
            if (c.get("connector_key") or "").startswith("brave_") or (c.get("capability_key") or "").startswith("brave"):
                headers["X-Subscription-Token"] = api_key
        safe_url = _validate_public_http_url(url)
        req = urllib.request.Request(safe_url, headers=headers, method="GET")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(), _PublicOnlyRedirectHandler())
        with opener.open(req, timeout=DEFAULT_TIMEOUT_SECONDS) as resp:
            _validate_public_http_url(resp.geturl())
            data = resp.read(2_000_000)
        return json.loads(data.decode("utf-8", errors="replace"))

    def _run_dns_local(self, domain: str) -> Dict[str, Any]:
        host = _domain_from_text(domain)
        if not host or " " in host or "." not in host:
            return {"domain": host, "addresses": [], "errors": ["invalid_domain_for_dns"]}
        addresses: List[str] = []
        errors: List[str] = []
        try:
            for info in socket.getaddrinfo(host, None):
                addr = info[4][0]
                if addr not in addresses:
                    addresses.append(addr)
        except Exception as exc:
            errors.append(str(exc))
        return {"domain": host, "addresses": addresses, "errors": errors}

    def _normalize_payload(self, parser_key: str, payload: Any, query: str) -> List[Dict[str, Any]]:
        if payload is None:
            return []
        try:
            if parser_key == "brave_web":
                return self._norm_list(((payload or {}).get("web") or {}).get("results") or [], "title", "url", "description", "age")
            if parser_key == "brave_image":
                out = []
                for r in (payload or {}).get("results", []) or []:
                    out.append({"title": r.get("title") or "Brave Image Result", "url": r.get("page_url") or r.get("url") or r.get("source") or "", "snippet": r.get("source") or r.get("description") or "Image context; manual review required.", "published_at": r.get("age") or "", "raw": r})
                return out
            if parser_key == "brave_news":
                return self._norm_list((payload or {}).get("results") or [], "title", "url", "description", "age")
            if parser_key == "github_users":
                out = []
                for r in (payload or {}).get("items", []) or []:
                    out.append({"title": "GitHub: " + (r.get("login") or "public user"), "url": r.get("html_url") or "", "snippet": "Öffentliches GitHub-Profil; Score: " + str(r.get("score", "")), "published_at": "", "raw": r})
                return out
            if parser_key == "wayback_cdx":
                rows = payload or []
                if rows and isinstance(rows[0], list):
                    header = rows[0]
                    out = []
                    for row in rows[1:]:
                        d = dict(zip(header, row))
                        out.append({"title": "Wayback Snapshot " + d.get("timestamp", ""), "url": d.get("original", ""), "snippet": f"status={d.get('statuscode','')} mimetype={d.get('mimetype','')} digest={d.get('digest','')}", "published_at": d.get("timestamp", ""), "raw": d})
                    return out
            if parser_key == "rdap_domain":
                d = payload or {}
                title = "RDAP: " + (d.get("ldhName") or d.get("handle") or query)
                events = d.get("events") or []
                nameservers = ", ".join([ns.get("ldhName", "") for ns in d.get("nameservers", []) if isinstance(ns, dict)])
                return [{"title": title, "url": "https://rdap.org/domain/" + urllib.parse.quote(_domain_from_text(query), safe=".-_"), "snippet": "events=" + str(len(events)) + (" nameservers=" + nameservers if nameservers else ""), "published_at": "", "raw": d}]
            if parser_key == "dns_local":
                d = payload or {}
                addresses = d.get("addresses") or []
                return [{"title": "DNS: " + (d.get("domain") or query), "url": "dns://" + (d.get("domain") or query), "snippet": "addresses=" + ", ".join(addresses) + (" errors=" + "; ".join(d.get("errors") or []) if d.get("errors") else ""), "published_at": "", "raw": d}] if addresses or d.get("errors") else []
            if parser_key == "crtsh_json":
                out = []
                rows = payload if isinstance(payload, list) else []
                seen = set()
                for r in rows[:MAX_LIVE_PROVIDER_RESULTS]:
                    name = (r.get("name_value") or r.get("common_name") or query).split("\n")[0]
                    if name in seen:
                        continue
                    seen.add(name)
                    out.append({"title": "crt.sh: " + name, "url": "https://crt.sh/?id=" + str(r.get("id", "")) if r.get("id") else "https://crt.sh/?q=" + urllib.parse.quote_plus(query), "snippet": f"issuer={r.get('issuer_name','')} not_before={r.get('not_before','')}", "published_at": r.get("not_before") or "", "raw": r})
                return out
        except Exception:
            return []
        if isinstance(payload, dict):
            return [{"title": "Provider Payload", "url": "", "snippet": json.dumps(payload, ensure_ascii=False)[:400], "published_at": "", "raw": payload}]
        return []

    def _norm_list(self, rows: List[Dict[str, Any]], title_key: str, url_key: str, snippet_key: str, date_key: str) -> List[Dict[str, Any]]:
        out = []
        for r in rows[:MAX_LIVE_PROVIDER_RESULTS]:
            out.append({"title": r.get(title_key) or "Provider Result", "url": r.get(url_key) or "", "snippet": r.get(snippet_key) or "", "published_at": r.get(date_key) or "", "raw": r})
        return out
