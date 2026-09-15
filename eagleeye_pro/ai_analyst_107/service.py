from __future__ import annotations

import html
import json
import os
import re
import socket
import ipaddress
import hashlib
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

PUBLIC_SCHEMES = {"http", "https"}
BLOCKED_QUERY_TERMS = re.compile(
    r"\b(password|passwort|login|credential|zugangsdaten|private account|privates konto|"
    r"captcha|paywall|leak database|stolen data|gestohlene daten|home address|wohnadresse|"
    r"social security|steuer-id|bank account|kontonummer)\b",
    re.I,
)


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def _is_loopback_host(hostname: str) -> bool:
    host = (hostname or "").strip().strip("[]").casefold()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _validate_local_service_url(value: str, *, field: str) -> str:
    parsed = urlparse((value or "").strip())
    if parsed.scheme != "http" or not parsed.hostname or not _is_loopback_host(parsed.hostname):
        raise ValueError(f"{field} muss eine lokale HTTP-Loopback-Adresse sein")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError(f"Ungültige URL für {field}")
    return value.rstrip("/")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError(f"Unerwarteter Redirect ({code}) zu {newurl}")


def _http_json(url: str, *, method: str = "GET", headers: Dict[str, str] | None = None,
               payload: Dict[str, Any] | None = None, timeout: int = 25,
               max_bytes: int = 4 * 1024 * 1024) -> Dict[str, Any]:
    data = None
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept": "application/json", "DNT": "1", "Sec-GPC": "1",
    }
    hdrs.update(headers or {})
    hdrs.pop("Referer", None)
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    request = Request(url, data=data, headers=hdrs, method=method)
    parsed = urlparse(url)
    proxy_url = os.environ.get("EAGLEEYE_OUTBOUND_PROXY", "").strip()
    if proxy_url and not _is_loopback_host(parsed.hostname or ""):
        proxy_handler = ProxyHandler({"http": proxy_url, "https": proxy_url})
    else:
        # Disable implicit OS/environment proxy discovery. Build 124 uses only the
        # explicitly reviewed proxy from Investigator Protection settings.
        proxy_handler = ProxyHandler()
    opener = build_opener(proxy_handler, _NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            content_type = (response.headers.get("Content-Type") or "").casefold()
            if "json" not in content_type:
                raise RuntimeError(f"Unerwarteter Content-Type: {content_type or 'unbekannt'}")
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise RuntimeError("Provider-Antwort überschreitet das Größenlimit")
            decoded = raw.decode("utf-8", errors="strict")
            result = json.loads(decoded)
            if not isinstance(result, dict):
                raise RuntimeError("Provider-Antwort ist kein JSON-Objekt")
            return result
    except HTTPError as exc:
        body = exc.read(2000).decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Provider-Dienst nicht erreichbar. Prüfe Dienststart und konfigurierte URL oder nutze Browser-Queue. Technisch: {exc.reason}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Ungültige JSON-Antwort des Providers") from exc


@dataclass(frozen=True)
class SearchConfig:
    ollama_url: str
    ollama_model: str
    search_provider: str
    searxng_url: str
    brave_api_key: str
    ollama_api_key: str
    country: str
    language: str


class AIAnalyst107Service:
    """Controlled AI analyst and approval-gated public web search.

    The AI may generate queries and rank public results, but a search can run only with a
    one-time lead-investigator authorization bound to one case and one target.
    """

    def __init__(self, db: Database, audit: AuditService, *, targets: Any, secret_resolver: Callable[[str], str] | None = None):
        self.db = db
        self.audit = audit
        self.targets = targets
        self.secret_resolver = secret_resolver
        self.ensure_schema()

    def _provider_secret(self, name: str, env_name: str) -> str:
        if self.secret_resolver is not None:
            try:
                value = self.secret_resolver(name)
            except Exception:
                value = ""
            if value:
                return value
        # Compatibility for direct legacy construction. The canonical Build 124
        # AppContext resolves provider keys from the encrypted vault and does not
        # place them in the process environment.
        return os.environ.get(env_name, "")

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS ai_settings_107(
          setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ai_authorizations_107(
          authorization_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
          approved_by TEXT NOT NULL, purpose TEXT NOT NULL, provider TEXT NOT NULL,
          max_queries INTEGER NOT NULL, max_results_per_query INTEGER NOT NULL,
          status TEXT NOT NULL, expires_at INTEGER NOT NULL, created_at TEXT NOT NULL,
          consumed_at TEXT DEFAULT '', query_plan_json TEXT DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS ai_search_runs_107(
          run_id TEXT PRIMARY KEY, authorization_id TEXT NOT NULL, case_id TEXT NOT NULL,
          target_id TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
          status TEXT NOT NULL, query_count INTEGER NOT NULL DEFAULT 0,
          result_count INTEGER NOT NULL DEFAULT 0, error TEXT DEFAULT '',
          created_at TEXT NOT NULL, completed_at TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS ai_search_results_107(
          result_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL,
          target_id TEXT NOT NULL, query TEXT NOT NULL, provider TEXT NOT NULL,
          title TEXT NOT NULL, url TEXT NOT NULL, snippet TEXT DEFAULT '',
          source_engine TEXT DEFAULT '', published_at TEXT DEFAULT '',
          relevance INTEGER NOT NULL DEFAULT 0, rationale TEXT DEFAULT '',
          review_status TEXT NOT NULL DEFAULT 'candidate', created_at TEXT NOT NULL,
          UNIQUE(run_id, url)
        );
        CREATE INDEX IF NOT EXISTS idx_ai107_auth_case ON ai_authorizations_107(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_ai107_runs_case ON ai_search_runs_107(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_ai107_results_run ON ai_search_results_107(run_id, relevance DESC);
        ''')
        # Build 107.1 never persists provider secrets. Remove any plaintext values left by 107.0.
        self.db.execute("DELETE FROM ai_settings_107 WHERE setting_key IN ('brave_api_key','ollama_api_key')")
        # Build 123 migration: older workspaces silently defaulted to a local SearXNG
        # endpoint and failed with WinError 10061 on normal Windows installations.
        migrated = self.db.one("SELECT setting_value FROM ai_settings_107 WHERE setting_key='provider_default_migrated_123'")
        if not migrated:
            selected = self.db.one("SELECT setting_value FROM ai_settings_107 WHERE setting_key='search_provider'")
            if not selected or selected.get("setting_value") == "searxng":
                self.db.execute(
                    "INSERT INTO ai_settings_107(setting_key,setting_value,updated_at) VALUES('search_provider','browser_queue',?) "
                    "ON CONFLICT(setting_key) DO UPDATE SET setting_value='browser_queue',updated_at=excluded.updated_at",
                    [now_ts()],
                )
            self.db.execute(
                "INSERT INTO ai_settings_107(setting_key,setting_value,updated_at) VALUES('provider_default_migrated_123','1',?)",
                [now_ts()],
            )
        self.db.conn.commit()

    def get_config(self) -> SearchConfig:
        rows = self.db.all("SELECT setting_key,setting_value FROM ai_settings_107")
        stored = {r["setting_key"]: r["setting_value"] for r in rows}
        ollama_url = _validate_local_service_url(stored.get("ollama_url", "http://127.0.0.1:11434"), field="Ollama URL")
        searxng_url = _validate_local_service_url(stored.get("searxng_url", "http://127.0.0.1:8080"), field="SearXNG URL")
        return SearchConfig(
            ollama_url=ollama_url,
            ollama_model=stored.get("ollama_model", ""),
            search_provider=stored.get("search_provider", "browser_queue"),
            searxng_url=searxng_url,
            brave_api_key=self._provider_secret("brave_api_key", "EAGLEEYE_BRAVE_API_KEY"),
            ollama_api_key=self._provider_secret("ollama_api_key", "OLLAMA_API_KEY"),
            country=stored.get("country", "DE").upper(),
            language=stored.get("language", "de"),
        )

    def save_config(self, **values: str) -> Dict[str, Any]:
        allowed = {"ollama_url", "ollama_model", "search_provider", "searxng_url", "country", "language"}
        for key, value in values.items():
            if key not in allowed:
                continue
            val = (value or "").strip()
            if key == "ollama_url" and val:
                val = _validate_local_service_url(val, field="Ollama URL")
            if key == "searxng_url" and val:
                val = _validate_local_service_url(val, field="SearXNG URL")
            if key == "search_provider" and val not in {"browser_queue", "searxng", "brave", "ollama_web"}:
                raise ValueError("Provider muss browser_queue, searxng, brave oder ollama_web sein")
            self.db.execute(
                "INSERT INTO ai_settings_107(setting_key,setting_value,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value,updated_at=excluded.updated_at",
                [key, val, now_ts()],
            )
        self.audit.log("configure", "ai_analyst_107", "settings", None, {"keys": sorted(set(values) & allowed)})
        cfg = self.get_config()
        return {**cfg.__dict__, "brave_api_key": "configured" if cfg.brave_api_key else "", "ollama_api_key": "configured" if cfg.ollama_api_key else ""}

    def ollama_status(self) -> Dict[str, Any]:
        cfg = self.get_config()
        try:
            payload = _http_json(cfg.ollama_url + "/api/tags", timeout=4)
            models = [m.get("name") or m.get("model") for m in payload.get("models", [])]
            return {"connected": True, "url": cfg.ollama_url, "models": [m for m in models if m]}
        except Exception as exc:
            return {"connected": False, "url": cfg.ollama_url, "models": [], "error": str(exc)}

    def provider_status(self, provider: str | None = None) -> Dict[str, Any]:
        cfg = self.get_config()
        selected = (provider or cfg.search_provider or "browser_queue").strip()
        if selected == "browser_queue":
            return {
                "provider": "browser_queue", "ready": True,
                "detail": "Serverloser Browsermodus: personalisierte Suchaufgaben werden lokal erzeugt und im Recherche-Tab geöffnet.",
                "requires_network_service": False,
            }
        if selected == "brave":
            ready = bool(cfg.brave_api_key)
            return {"provider": "brave", "ready": ready, "detail": "API-Key konfiguriert" if ready else "EAGLEEYE_BRAVE_API_KEY fehlt", "requires_network_service": True}
        if selected == "ollama_web":
            ready = bool(cfg.ollama_api_key)
            return {"provider": "ollama_web", "ready": ready, "detail": "Ollama API-Key konfiguriert" if ready else "OLLAMA_API_KEY fehlt", "requires_network_service": True}
        if selected != "searxng":
            return {"provider": selected, "ready": False, "detail": "Unbekannter Suchprovider", "requires_network_service": True}
        try:
            url = cfg.searxng_url + "/search?" + urlencode({"q": "EagleEye connectivity test", "format": "json", "categories": "general"})
            payload = _http_json(url, timeout=4)
            return {"provider": "searxng", "ready": isinstance(payload.get("results", []), list), "detail": cfg.searxng_url, "requires_network_service": True}
        except Exception as exc:
            return {
                "provider": "searxng", "ready": False,
                "detail": f"SearXNG ist unter {cfg.searxng_url} nicht erreichbar. Starte den Dienst oder wähle Browser-Queue. Technisch: {exc}",
                "requires_network_service": True,
            }

    def _target_anchors(self, target: Dict[str, Any]) -> List[str]:
        anchors: List[str] = []
        for value in [target.get("name")]:
            if value and len(str(value).strip()) >= 3:
                anchors.append(str(value).strip())
        for key in ["aliases_json", "usernames_json", "emails_json", "domains_json"]:
            for value in target.get(key, []) or []:
                value = str(value).strip()
                if len(value) >= 3:
                    anchors.append(value)
        # Preserve order, remove duplicates.
        return list(dict.fromkeys(anchors))

    def authorize_search(self, *, case_id: str, target_id: str, approved_by: str, purpose: str,
                         provider: str, max_queries: int, max_results_per_query: int,
                         confirmation: str) -> Dict[str, Any]:
        target = self.targets.get_target(target_id)
        if target.get("case_id") != case_id:
            raise ValueError("Zielperson gehört nicht zum aktiven Fall")
        if confirmation.strip().upper() != "SUCHE FREIGEBEN":
            raise ValueError("Freigabephrase fehlt: SUCHE FREIGEBEN")
        if not approved_by.strip() or not purpose.strip():
            raise ValueError("Leitender Ermittler und Zweck sind erforderlich")
        provider = provider or self.get_config().search_provider
        if provider not in {"browser_queue", "searxng", "brave", "ollama_web"}:
            raise ValueError("Nicht unterstützter Suchprovider")
        max_queries = max(1, min(int(max_queries), 12))
        max_results_per_query = max(1, min(int(max_results_per_query), 20))
        auth_id = new_id("aiauth107")
        expires = int(time.time()) + 15 * 60
        self.db.execute(
            "INSERT INTO ai_authorizations_107(authorization_id,case_id,target_id,approved_by,purpose,provider,max_queries,max_results_per_query,status,expires_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            [auth_id, case_id, target_id, approved_by.strip(), purpose.strip(), provider, max_queries, max_results_per_query, "approved_once", expires, now_ts()],
        )
        self.audit.log("approve", "ai_web_search_107", auth_id, case_id, {
            "target_id": target_id, "provider": provider, "max_queries": max_queries,
            "max_results_per_query": max_results_per_query, "expires_at": expires,
        })
        return {"authorization_id": auth_id, "status": "approved_once", "expires_at": expires}

    def _fallback_queries(self, target: Dict[str, Any], limit: int) -> List[Dict[str, str]]:
        name = (target.get("name") or "").strip()
        locations = target.get("locations_json", []) or []
        companies = target.get("companies_json", []) or []
        usernames = target.get("usernames_json", []) or []
        emails = target.get("emails_json", []) or []
        domains = target.get("domains_json", []) or []
        candidates: List[Dict[str, str]] = []
        if name:
            candidates.extend([
                {"query": f'"{name}"', "objective": "Identitätsanker und allgemeine öffentliche Erwähnungen"},
                {"query": f'"{name}" filetype:pdf', "objective": "Öffentliche Dokumente"},
                {"query": f'"{name}" (interview OR presse OR profil)', "objective": "Presse und Profile"},
            ])
        for value in locations[:2]:
            candidates.append({"query": f'"{name}" "{value}"', "objective": "Ortsbezogene Disambiguierung"})
        for value in companies[:2]:
            candidates.append({"query": f'"{name}" "{value}"', "objective": "Beruflicher Kontext"})
        for value in usernames[:3]:
            candidates.append({"query": f'"{value}" "{name}"', "objective": "Username-Korrelation"})
        for value in emails[:2]:
            candidates.append({"query": f'"{value}"', "objective": "Öffentliche Erwähnungen der bestätigten E-Mail-Adresse"})
        for value in domains[:2]:
            candidates.append({"query": f'site:{value} "{name}"', "objective": "Bestätigte Domain prüfen"})
        return candidates[:limit]

    def _ollama_queries(self, target: Dict[str, Any], limit: int) -> List[Dict[str, str]]:
        cfg = self.get_config()
        if not cfg.ollama_model:
            return self._fallback_queries(target, limit)
        allowed_profile = {
            "name": target.get("name"), "aliases": target.get("aliases_json", []),
            "usernames": target.get("usernames_json", []), "emails": target.get("emails_json", []),
            "locations": target.get("locations_json", []), "companies": target.get("companies_json", []),
            "domains": target.get("domains_json", []),
        }
        schema = {
            "type": "object", "properties": {"queries": {"type": "array", "maxItems": limit,
                "items": {"type": "object", "properties": {
                    "query": {"type": "string"}, "objective": {"type": "string"}},
                    "required": ["query", "objective"]}}}, "required": ["queries"]
        }
        prompt = (
            "Erzeuge effiziente Suchmaschinenabfragen ausschließlich zur angegebenen Zielperson. "
            "Jede Query muss mindestens einen exakt vorhandenen Identitätsanker (Name, Alias, Username, E-Mail oder Domain) enthalten. "
            "Nutze Orte und Firmen nur zusammen mit einem Identitätsanker. Keine Suche nach Privatadressen, Passwörtern, Zugangsdaten, "
            "privaten Konten, Leaks, Familienangehörigen oder anderen Personen. Keine Identitätsbehauptungen. "
            f"Maximal {limit} Queries. Zielprofil: {json.dumps(allowed_profile, ensure_ascii=False)}"
        )
        try:
            payload = _http_json(cfg.ollama_url + "/api/chat", method="POST", payload={
                "model": cfg.ollama_model, "stream": False, "format": schema,
                "messages": [{"role": "system", "content": "Du bist ein vorsichtiger OSINT-Abfrageplaner für öffentliche Quellen."},
                             {"role": "user", "content": prompt}],
                "options": {"temperature": 0.1},
            }, timeout=30)
            content = ((payload.get("message") or {}).get("content") or "{}").strip()
            parsed = json.loads(content)
            return list(parsed.get("queries") or [])[:limit]
        except Exception:
            # Query planning must remain usable when Ollama is not installed or not running.
            return self._fallback_queries(target, limit)

    def _validate_queries(self, target: Dict[str, Any], queries: List[Dict[str, str]], limit: int) -> List[Dict[str, str]]:
        anchors = self._target_anchors(target)
        valid: List[Dict[str, str]] = []
        for item in queries:
            query = " ".join(str(item.get("query") or "").split())[:400]
            objective = " ".join(str(item.get("objective") or "").split())[:300]
            if not query or BLOCKED_QUERY_TERMS.search(query):
                continue
            lowered = query.casefold()
            if not any(anchor.casefold() in lowered for anchor in anchors):
                continue
            if any(existing["query"].casefold() == query.casefold() for existing in valid):
                continue
            valid.append({"query": query, "objective": objective or "Öffentliche Recherche zur Zielperson"})
            if len(valid) >= limit:
                break
        if not valid:
            valid = self._fallback_queries(target, limit)
        return valid[:limit]

    def _search_searxng(self, query: str, count: int) -> List[Dict[str, Any]]:
        cfg = self.get_config()
        url = cfg.searxng_url + "/search?" + urlencode({
            "q": query, "format": "json", "categories": "general", "language": cfg.language,
            "safesearch": "1",
        })
        payload = _http_json(url, timeout=30)
        output = []
        for item in payload.get("results", [])[:count]:
            output.append({
                "title": item.get("title") or "Ohne Titel", "url": item.get("url") or "",
                "snippet": item.get("content") or "", "source_engine": ", ".join(item.get("engines") or []) if isinstance(item.get("engines"), list) else (item.get("engine") or "searxng"),
                "published_at": item.get("publishedDate") or "",
            })
        return output

    def _search_ollama_web(self, query: str, count: int) -> List[Dict[str, Any]]:
        cfg = self.get_config()
        if not cfg.ollama_api_key:
            raise RuntimeError("OLLAMA_API_KEY fehlt")
        payload = _http_json("https://ollama.com/api/web_search", method="POST", headers={"Authorization": f"Bearer {cfg.ollama_api_key}"}, payload={"query": query, "max_results": min(count, 10)}, timeout=30)
        output = []
        for item in payload.get("results", [])[:count]:
            output.append({"title": item.get("title") or "Ohne Titel", "url": item.get("url") or "", "snippet": item.get("content") or "", "source_engine": "ollama_web", "published_at": ""})
        return output

    def _search_brave(self, query: str, count: int) -> List[Dict[str, Any]]:
        cfg = self.get_config()
        if not cfg.brave_api_key:
            raise RuntimeError("Brave Search API-Key fehlt")
        url = "https://api.search.brave.com/res/v1/web/search?" + urlencode({
            "q": query, "count": min(count, 20), "country": cfg.country,
            "search_lang": cfg.language, "safesearch": "moderate",
        })
        payload = _http_json(url, headers={"X-Subscription-Token": cfg.brave_api_key, "Accept": "application/json"}, timeout=30)
        output = []
        for item in ((payload.get("web") or {}).get("results") or [])[:count]:
            output.append({
                "title": item.get("title") or "Ohne Titel", "url": item.get("url") or "",
                "snippet": item.get("description") or "", "source_engine": "brave",
                "published_at": item.get("page_age") or item.get("age") or "",
            })
        return output

    def _rank(self, target: Dict[str, Any], result: Dict[str, Any]) -> tuple[int, str]:
        haystack = " ".join([result.get("title", ""), result.get("snippet", ""), result.get("url", "")]).casefold()
        matches = [a for a in self._target_anchors(target) if a.casefold() in haystack]
        score = min(100, 20 + 20 * len(matches)) if matches else 10
        return score, ("Treffer enthält bestätigte Anker: " + ", ".join(matches[:4])) if matches else "Nur schwacher Textabgleich; manuelle Prüfung erforderlich"

    def execute_authorized_search(self, authorization_id: str) -> Dict[str, Any]:
        auth = self.db.one("SELECT * FROM ai_authorizations_107 WHERE authorization_id=?", [authorization_id])
        if not auth:
            raise KeyError("Freigabeticket nicht gefunden")
        if auth.get("status") != "approved_once":
            raise ValueError("Freigabeticket wurde bereits verbraucht oder widerrufen")
        if int(auth.get("expires_at") or 0) < int(time.time()):
            self.db.execute("UPDATE ai_authorizations_107 SET status='expired' WHERE authorization_id=?", [authorization_id])
            raise ValueError("Freigabeticket ist abgelaufen")
        target = self.targets.get_target(auth["target_id"])
        if target.get("case_id") != auth.get("case_id"):
            raise ValueError("Fall-/Zielbindung verletzt")

        # External providers are checked before the one-time authorization is consumed.
        # A missing optional local service must not destroy the user's ticket.
        provider = str(auth.get("provider") or self.get_config().search_provider)
        status = self.provider_status(provider)
        if not status.get("ready"):
            raise RuntimeError(str(status.get("detail") or "Suchprovider ist nicht bereit"))

        # Atomic single-use transition. Concurrent requests cannot consume the same ticket twice.
        cursor = self.db.execute(
            "UPDATE ai_authorizations_107 SET status='consumed',consumed_at=? "
            "WHERE authorization_id=? AND status='approved_once' AND expires_at>=?",
            [now_ts(), authorization_id, int(time.time())],
        )
        if getattr(cursor, "rowcount", 0) != 1:
            raise ValueError("Freigabeticket wurde parallel verbraucht oder ist abgelaufen")
        cfg = self.get_config()
        run_id = new_id("airun107")
        self.db.execute(
            "INSERT INTO ai_search_runs_107(run_id,authorization_id,case_id,target_id,provider,model,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
            [run_id, authorization_id, auth["case_id"], auth["target_id"], auth["provider"], cfg.ollama_model or "deterministic_fallback", "running", now_ts()],
        )
        try:
            raw_queries = self._ollama_queries(target, int(auth["max_queries"]))
            queries = self._validate_queries(target, raw_queries, int(auth["max_queries"]))
            self.db.execute("UPDATE ai_authorizations_107 SET query_plan_json=? WHERE authorization_id=?", [dumps(queries), authorization_id])
            if auth["provider"] == "browser_queue":
                self.db.execute(
                    "UPDATE ai_search_runs_107 SET status='queued_for_browser',query_count=?,result_count=0,completed_at=? WHERE run_id=?",
                    [len(queries), now_ts(), run_id],
                )
                self.audit.log("queue", "ai_web_search_107", run_id, auth["case_id"], {
                    "authorization_id": authorization_id, "target_id": auth["target_id"], "queries": len(queries),
                    "mode": "browser_queue", "network_called": False,
                })
                return {"run_id": run_id, "queries": queries, "result_count": 0, "status": "queued_for_browser", "mode": "browser_queue"}
            total = 0
            completed_queries = 0
            for plan in queries:
                if auth["provider"] == "brave":
                    found = self._search_brave(plan["query"], int(auth["max_results_per_query"]))
                elif auth["provider"] == "ollama_web":
                    found = self._search_ollama_web(plan["query"], int(auth["max_results_per_query"]))
                else:
                    found = self._search_searxng(plan["query"], int(auth["max_results_per_query"]))
                completed_queries += 1
                for item in found:
                    parsed = urlparse(item.get("url") or "")
                    if parsed.scheme not in PUBLIC_SCHEMES or not parsed.hostname or parsed.username or parsed.password:
                        continue
                    if _is_loopback_host(parsed.hostname):
                        continue
                    relevance, rationale = self._rank(target, item)
                    try:
                        self.db.execute(
                            "INSERT INTO ai_search_results_107(result_id,run_id,case_id,target_id,query,provider,title,url,snippet,source_engine,published_at,relevance,rationale,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            [new_id("aires107"), run_id, auth["case_id"], auth["target_id"], plan["query"], auth["provider"], item["title"][:500], item["url"][:2000], item["snippet"][:4000], item["source_engine"][:200], str(item["published_at"])[:100], relevance, rationale, now_ts()],
                        )
                        total += 1
                    except Exception as exc:
                        if "UNIQUE constraint" not in str(exc):
                            raise
            self.db.execute("UPDATE ai_search_runs_107 SET status='completed',query_count=?,result_count=?,completed_at=? WHERE run_id=?", [len(queries), total, now_ts(), run_id])
            self.audit.log("execute", "ai_web_search_107", run_id, auth["case_id"], {"authorization_id": authorization_id, "target_id": auth["target_id"], "queries": len(queries), "results": total})
            return {"run_id": run_id, "queries": queries, "result_count": total, "status": "completed"}
        except Exception as exc:
            self.db.execute("UPDATE ai_search_runs_107 SET status='failed',error=?,completed_at=? WHERE run_id=?", [str(exc)[:2000], now_ts(), run_id])
            # If no provider query completed, the failure did not produce a partial search.
            # Restore the one-time authorization so a corrected provider configuration can retry.
            if auth.get("provider") != "browser_queue" and int(locals().get("completed_queries", 0)) == 0:
                self.db.execute(
                    "UPDATE ai_authorizations_107 SET status='approved_once',consumed_at='' WHERE authorization_id=? AND status='consumed'",
                    [authorization_id],
                )
            self.audit.log("fail", "ai_web_search_107", run_id, auth["case_id"], {"error": str(exc), "authorization_id": authorization_id, "authorization_restored": int(locals().get("completed_queries", 0)) == 0})
            raise

    def list_authorizations(self, case_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM ai_authorizations_107 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", [case_id, int(limit)])
        for row in rows:
            row["query_plan"] = loads(row.pop("query_plan_json", "[]"), [])
        return rows

    def list_runs(self, case_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM ai_search_runs_107 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", [case_id, int(limit)])

    def list_results(self, case_id: str, limit: int = 300) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM ai_search_results_107 WHERE case_id=? ORDER BY relevance DESC,created_at DESC LIMIT ?", [case_id, int(limit)])


def render_ai_analyst_107(ctx: Any, case_id: str, csrf: str, token: str) -> str:
    svc: AIAnalyst107Service = ctx.ai_analyst_107
    cfg = svc.get_config()
    ollama = svc.ollama_status()
    provider = svc.provider_status()
    targets = ctx.targets.list_targets(case_id)
    auths = svc.list_authorizations(case_id)
    runs = svc.list_runs(case_id)
    results = svc.list_results(case_id)
    model_opts = "".join(f'<option value="{_esc(m)}" {"selected" if m == cfg.ollama_model else ""}>{_esc(m)}</option>' for m in ollama.get("models", []))
    if not model_opts:
        model_opts = f'<option value="{_esc(cfg.ollama_model)}">{_esc(cfg.ollama_model or "Kein Modell erkannt")}</option>'
    target_opts = "".join(f'<option value="{_esc(t.get("target_id"))}">{_esc(t.get("name"))}</option>' for t in targets) or '<option value="">Zuerst Zielperson anlegen</option>'
    ready_auths = [a for a in auths if a.get("status") == "approved_once" and int(a.get("expires_at") or 0) >= int(time.time())]
    auth_opts = "".join(f'<option value="{_esc(a["authorization_id"])}">{_esc(a["approved_by"])} · {_esc(a["provider"])} · {_esc(a["authorization_id"])}</option>' for a in ready_auths) or '<option value="">Keine aktive Einmalfreigabe</option>'
    arows = "".join(f'<tr><td>{_esc(a["created_at"])}</td><td>{_esc(a["approved_by"])}</td><td>{_esc(a["provider"])}</td><td>{_esc(a["status"])}</td><td>{_esc(a["max_queries"])} × {_esc(a["max_results_per_query"])}</td><td><code>{_esc(a["authorization_id"])}</code></td></tr>' for a in auths)
    runrows = "".join(f'<tr><td>{_esc(r["created_at"])}</td><td>{_esc(r["provider"])}</td><td>{_esc(r["model"])}</td><td>{_esc(r["status"])}</td><td>{_esc(r["query_count"])}</td><td>{_esc(r["result_count"])}</td><td>{_esc(r["error"])}</td></tr>' for r in runs)
    resultrows = "".join(
        f'<tr><td>{_esc(r["relevance"])}</td><td><a target="_blank" rel="noreferrer" href="{_esc(r["url"])}">{_esc(r["title"])}</a><div class="muted">{_esc(r["snippet"][:500])}</div></td><td>{_esc(r["query"])}</td><td>{_esc(r["source_engine"])}</td><td>{_esc(r["rationale"])}</td></tr>'
        for r in results
    )
    return f'''<h2>AI Analyst 107</h2>
<div class="callout"><b>Kontrollmodus:</b> Die KI darf nur die aktive Zielperson recherchieren. Automatische Websuche benötigt für jeden Lauf eine neue Einmalfreigabe des leitenden Ermittlers. Das Ticket ist 15 Minuten gültig. Externe Provider werden vorab geprüft; bei Nichterreichbarkeit bleibt die Freigabe unverbraucht. Browser-Queue benötigt keinen lokalen Zusatzdienst.</div>
<h3>1. Ollama und Suchprovider</h3>
<p>Ollama: <b>{"verbunden" if ollama.get("connected") else "nicht verbunden"}</b> · {_esc(ollama.get("url"))}<br>Suchprovider: <b>{_esc(provider.get("provider"))}</b> · {"bereit" if provider.get("ready") else "nicht bereit"} · {_esc(provider.get("detail"))}</p>
<form method="post" action="/ai107/config?token={_esc(token)}"><input type="hidden" name="csrf" value="{_esc(csrf)}">
<label>Ollama URL<input name="ollama_url" value="{_esc(cfg.ollama_url)}"></label>
<label>Ollama-Modell<select name="ollama_model">{model_opts}</select></label>
<label>Suchprovider<select name="search_provider"><option value="browser_queue" {"selected" if cfg.search_provider == "browser_queue" else ""}>Browser-Queue (empfohlen, kein Zusatzdienst)</option><option value="searxng" {"selected" if cfg.search_provider == "searxng" else ""}>SearXNG (lokaler Dienst erforderlich)</option><option value="brave" {"selected" if cfg.search_provider == "brave" else ""}>Brave Search API</option><option value="ollama_web" {"selected" if cfg.search_provider == "ollama_web" else ""}>Ollama Web Search API</option></select></label>
<label>SearXNG URL<input name="searxng_url" value="{_esc(cfg.searxng_url)}"></label>
<div class="callout"><b>API-Schlüssel:</b> werden aus Sicherheitsgründen nicht in SQLite gespeichert. Setze <code>EAGLEEYE_BRAVE_API_KEY</code> beziehungsweise <code>OLLAMA_API_KEY</code> als Windows-Umgebungsvariable.</div>
<label>Land<input name="country" value="{_esc(cfg.country)}"></label><label>Sprache<input name="language" value="{_esc(cfg.language)}"></label><button>Konfiguration speichern</button></form>
<h3>2. Einmalfreigabe durch leitenden Ermittler</h3>
<form method="post" action="/ai107/authorize?token={_esc(token)}"><input type="hidden" name="csrf" value="{_esc(csrf)}"><input type="hidden" name="case_id" value="{_esc(case_id)}">
<label>Zielperson<select name="target_id" required>{target_opts}</select></label><label>Leitender Ermittler<input name="approved_by" required></label>
<label>Dokumentierter Recherchezweck<textarea name="purpose" rows="3" required></textarea></label>
<label>Provider<select name="provider"><option value="{_esc(cfg.search_provider)}">{_esc(cfg.search_provider)}</option><option value="browser_queue">browser_queue</option><option value="searxng">searxng</option><option value="brave">brave</option><option value="ollama_web">ollama_web</option></select></label>
<label>Maximale Queries<input type="number" min="1" max="12" name="max_queries" value="6"></label><label>Treffer je Query<input type="number" min="1" max="20" name="max_results_per_query" value="10"></label>
<label>Freigabephrase<input name="confirmation" placeholder="SUCHE FREIGEBEN" required></label><button>Einmalige Suche freigeben</button></form>
<h3>3. Freigegebene Suche ausführen</h3>
<form method="post" action="/ai107/search?token={_esc(token)}"><input type="hidden" name="csrf" value="{_esc(csrf)}"><label>Freigabeticket<select name="authorization_id" required>{auth_opts}</select></label><button>KI-Websuche jetzt ausführen</button></form>
<h3>Freigaben</h3><table><tr><th>Zeit</th><th>Freigegeben durch</th><th>Provider</th><th>Status</th><th>Limit</th><th>ID</th></tr>{arows or '<tr><td colspan="6">Keine Freigaben.</td></tr>'}</table>
<h3>Suchläufe</h3><table><tr><th>Zeit</th><th>Provider</th><th>Modell</th><th>Status</th><th>Queries</th><th>Treffer</th><th>Fehler</th></tr>{runrows or '<tr><td colspan="7">Keine Läufe.</td></tr>'}</table>
<h3>Automatisch gefundene Recherchekandidaten</h3><p class="muted">Relevanz ist nur eine Priorisierungshilfe. Jeder Treffer bleibt Kandidat und muss manuell geprüft werden.</p><table><tr><th>Score</th><th>Treffer</th><th>Query</th><th>Quelle</th><th>Begründung</th></tr>{resultrows or '<tr><td colspan="5">Noch keine Ergebnisse.</td></tr>'}</table>'''
