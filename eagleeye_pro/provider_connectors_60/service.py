from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import quote_plus, urlparse
import hashlib

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.categorized_search.service import TEN_SEARCH_ENGINES


CONNECTOR_PROFILES_60: List[Dict[str, Any]] = [
    {
        "provider_key": "manual_serp_capture",
        "label": "Manual SERP Capture",
        "provider_type": "browser_capture",
        "public_only": True,
        "requires_api_key": False,
        "supports_live_run": False,
        "rate_limit": {"mode": "user_driven", "max_per_hour": 0},
        "terms": "User copies visible public search results into EagleEye; no scraping or bypass.",
        "strength": "high_control",
    },
    {
        "provider_key": "browser_result_helper",
        "label": "Browser Result Helper",
        "provider_type": "local_helper",
        "public_only": True,
        "requires_api_key": False,
        "supports_live_run": False,
        "rate_limit": {"mode": "user_confirmed", "max_per_hour": 0},
        "terms": "One-click or paste-based local capture of user-visible public results only.",
        "strength": "fast_capture",
    },
    {
        "provider_key": "brave_search_api",
        "label": "Brave Search API",
        "provider_type": "search_api",
        "public_only": True,
        "requires_api_key": True,
        "supports_live_run": True,
        "rate_limit": {"mode": "provider_budget", "max_per_second": 1, "honor_429": True},
        "terms": "Provider API only; honor rate-limit headers and API terms.",
        "strength": "independent_index",
    },
    {
        "provider_key": "bing_web_search_api",
        "label": "Bing Web Search API",
        "provider_type": "search_api",
        "public_only": True,
        "requires_api_key": True,
        "supports_live_run": True,
        "rate_limit": {"mode": "provider_budget", "honor_429": True},
        "terms": "Official API only; no result scraping or automated browser abuse.",
        "strength": "broad_index",
    },
    {
        "provider_key": "google_programmable_search",
        "label": "Google Programmable Search",
        "provider_type": "search_api",
        "public_only": True,
        "requires_api_key": True,
        "supports_live_run": True,
        "rate_limit": {"mode": "provider_budget", "quota_required": True},
        "terms": "Programmable Search API where available; no bypass or raw SERP scraping.",
        "strength": "high_precision_if_configured",
    },
    {
        "provider_key": "wayback_cdx_public",
        "label": "Wayback CDX Public",
        "provider_type": "archive_api",
        "public_only": True,
        "requires_api_key": False,
        "supports_live_run": True,
        "rate_limit": {"mode": "polite", "cache_required": True},
        "terms": "Public archive metadata, polite rates, cache repeated requests.",
        "strength": "historical_context",
    },
    {
        "provider_key": "rdap_public",
        "label": "RDAP Public Lookup",
        "provider_type": "domain_infrastructure",
        "public_only": True,
        "requires_api_key": False,
        "supports_live_run": True,
        "rate_limit": {"mode": "polite", "cache_required": True},
        "terms": "Public RDAP only; do not infer private identity without corroboration.",
        "strength": "domain_registration_context",
    },
    {
        "provider_key": "crtsh_public",
        "label": "crt.sh Public Certificate Search",
        "provider_type": "domain_infrastructure",
        "public_only": True,
        "requires_api_key": False,
        "supports_live_run": True,
        "rate_limit": {"mode": "polite", "cache_required": True},
        "terms": "Public CT data; infrastructure clue, not personal attribution proof.",
        "strength": "certificate_context",
    },
]


def _sha(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(str(part or "").encode("utf-8", errors="ignore")); h.update(b"\0")
    return h.hexdigest()


def _domain(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower().replace("www.", "")
    except Exception:
        return ""


class ProviderConnectorSDK60Service:
    """Build 60.0 provider connector SDK.

    The SDK defines provider contracts and preflight/normalization primitives for
    professional OSINT feeds. It remains public-only and blocks any connector
    profile that would require credential bypass, CAPTCHA bypass or hidden access.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()
        self.seed_defaults()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS provider_connectors_60 (
          provider_key TEXT PRIMARY KEY,
          label TEXT NOT NULL,
          provider_type TEXT NOT NULL,
          public_only INTEGER DEFAULT 1,
          requires_api_key INTEGER DEFAULT 0,
          supports_live_run INTEGER DEFAULT 0,
          rate_limit_json TEXT NOT NULL,
          terms_profile TEXT NOT NULL,
          strength TEXT DEFAULT '',
          active INTEGER DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS provider_preflights_60 (
          preflight_id TEXT PRIMARY KEY,
          case_id TEXT DEFAULT '',
          entity_id TEXT DEFAULT '',
          provider_key TEXT NOT NULL,
          query TEXT NOT NULL,
          category_key TEXT DEFAULT '',
          decision TEXT NOT NULL,
          reason TEXT NOT NULL,
          budget_json TEXT NOT NULL,
          prepared_links_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS provider_normalized_results_60 (
          normalized_id TEXT PRIMARY KEY,
          provider_key TEXT NOT NULL,
          case_id TEXT DEFAULT '',
          entity_id TEXT DEFAULT '',
          title TEXT NOT NULL,
          url TEXT NOT NULL,
          canonical_url TEXT NOT NULL,
          domain TEXT DEFAULT '',
          snippet TEXT DEFAULT '',
          source_type TEXT DEFAULT 'public_web',
          confidence_hint TEXT DEFAULT 'candidate',
          raw_hash TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(provider_key, canonical_url, raw_hash)
        );
        ''')
        self.db.conn.commit()

    def seed_defaults(self) -> None:
        now = now_ts()
        for profile in CONNECTOR_PROFILES_60:
            self.db.execute('''INSERT OR IGNORE INTO provider_connectors_60(provider_key,label,provider_type,public_only,requires_api_key,supports_live_run,rate_limit_json,terms_profile,strength,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)''', [
                profile["provider_key"], profile["label"], profile["provider_type"], 1 if profile["public_only"] else 0,
                1 if profile["requires_api_key"] else 0, 1 if profile["supports_live_run"] else 0,
                dumps(profile["rate_limit"]), profile["terms"], profile["strength"], now, now,
            ])

    def list_connectors(self, *, active_only: bool = True) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM provider_connectors_60"
        params: List[Any] = []
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY provider_type, label"
        rows = self.db.all(sql, params)
        for row in rows:
            row["rate_limit"] = loads(row.pop("rate_limit_json", "{}"), {})
            row["public_only"] = bool(row.get("public_only"))
            row["requires_api_key"] = bool(row.get("requires_api_key"))
            row["supports_live_run"] = bool(row.get("supports_live_run"))
            row["active"] = bool(row.get("active"))
        return rows

    def get_connector(self, provider_key: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM provider_connectors_60 WHERE provider_key=?", [provider_key])
        if not row:
            raise KeyError(provider_key)
        row["rate_limit"] = loads(row.pop("rate_limit_json", "{}"), {})
        row["public_only"] = bool(row.get("public_only"))
        row["requires_api_key"] = bool(row.get("requires_api_key"))
        row["supports_live_run"] = bool(row.get("supports_live_run"))
        return row

    def preflight_query(self, provider_key: str, query: str, *, case_id: str = "", entity_id: str = "", category_key: str = "", allow_live: bool = False) -> Dict[str, Any]:
        connector = self.get_connector(provider_key)
        q = str(query or "").strip()
        if not q:
            raise ValueError("query is required")
        decision = "allow_prepare"
        reasons: List[str] = []
        if not connector["public_only"]:
            decision = "block"; reasons.append("connector_not_public_only")
        if connector["requires_api_key"] and not allow_live:
            decision = "manual_or_config_required"; reasons.append("api_key_required_live_run_disabled")
        if connector["provider_type"] in {"search_api", "archive_api", "domain_infrastructure"} and allow_live and connector["requires_api_key"]:
            reasons.append("provider_budget_and_api_terms_required")
        if not reasons:
            reasons.append("public_only_preflight_ok")
        prepared_links = self._prepared_links(connector, q)
        preflight_id = new_id("pf60")
        self.db.execute('''INSERT INTO provider_preflights_60(preflight_id,case_id,entity_id,provider_key,query,category_key,decision,reason,budget_json,prepared_links_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''', [preflight_id, case_id, entity_id, provider_key, q, category_key, decision, ",".join(reasons), dumps(connector.get("rate_limit", {})), dumps(prepared_links), now_ts()])
        self.audit.log("preflight", "provider_connector_60", preflight_id, case_id or None, {"provider_key": provider_key, "decision": decision})
        return {"preflight_id": preflight_id, "provider": connector, "query": q, "decision": decision, "reasons": reasons, "prepared_links": prepared_links}

    def _prepared_links(self, connector: Dict[str, Any], query: str) -> List[Dict[str, str]]:
        key = connector.get("provider_key", "")
        q = quote_plus(query)
        if key in {"manual_serp_capture", "browser_result_helper"}:
            return [{"engine": e.key, "label": e.label, "url": e.url(query)} for e in TEN_SEARCH_ENGINES]
        if key == "wayback_cdx_public":
            return [{"engine": "wayback_cdx", "label": "Wayback CDX", "url": f"https://web.archive.org/cdx?url={q}&output=json"}]
        if key == "rdap_public":
            return [{"engine": "rdap", "label": "RDAP Bootstrap", "url": f"https://rdap.org/domain/{q}"}]
        if key == "crtsh_public":
            return [{"engine": "crtsh", "label": "crt.sh", "url": f"https://crt.sh/?q={q}"}]
        return [{"engine": key, "label": connector.get("label", key), "url": "api_config_required"}]

    def normalize_results(self, provider_key: str, results: List[Dict[str, Any]], *, case_id: str = "", entity_id: str = "") -> Dict[str, Any]:
        normalized: List[Dict[str, Any]] = []
        for item in results:
            title = str(item.get("title") or item.get("name") or "").strip()
            url = str(item.get("url") or item.get("link") or "").strip()
            snippet = str(item.get("snippet") or item.get("description") or "").strip()
            if not title or not url:
                continue
            canonical = self._canonical_url(url)
            raw_hash = _sha(title, canonical, snippet)
            nid = new_id("norm60")
            try:
                self.db.execute('''INSERT INTO provider_normalized_results_60(normalized_id,provider_key,case_id,entity_id,title,url,canonical_url,domain,snippet,source_type,confidence_hint,raw_hash,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', [nid, provider_key, case_id, entity_id, title, url, canonical, _domain(canonical), snippet, self._source_type_from_url(canonical), "candidate", raw_hash, now_ts()])
            except Exception:
                existing = self.db.one("SELECT * FROM provider_normalized_results_60 WHERE provider_key=? AND canonical_url=? AND raw_hash=?", [provider_key, canonical, raw_hash])
                if existing:
                    nid = existing["normalized_id"]
            normalized.append({"normalized_id": nid, "provider_key": provider_key, "title": title, "url": url, "canonical_url": canonical, "domain": _domain(canonical), "snippet": snippet, "source_type": self._source_type_from_url(canonical), "raw_hash": raw_hash})
        self.audit.log("normalize", "provider_results_60", provider_key, case_id or None, {"count": len(normalized)})
        return {"count": len(normalized), "results": normalized}

    def _canonical_url(self, url: str) -> str:
        parsed = urlparse(url.strip())
        if not parsed.scheme or not parsed.netloc:
            return url.strip()
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower().replace('www.', '')}{parsed.path}".rstrip("/")

    def _source_type_from_url(self, url: str) -> str:
        d = _domain(url)
        path = urlparse(url).path.lower()
        if path.endswith(".pdf"):
            return "public_pdf"
        if any(token in d for token in ["gericht", "justiz", "court"]):
            return "court_or_justice"
        if any(token in d for token in ["register", "bundesanzeiger", "unternehmensregister"]):
            return "registry"
        if any(token in d for token in ["archive", "archiv", "zeitung", "news"]):
            return "archive_or_press"
        return "public_web"
