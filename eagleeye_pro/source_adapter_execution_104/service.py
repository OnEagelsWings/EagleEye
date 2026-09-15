from __future__ import annotations

import hashlib
import json
import re
import socket
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.url_policy import URLPolicy


@dataclass(frozen=True)
class AdapterSpec104:
    adapter_id: str
    name: str
    category: str
    input_type: str
    provider_key: str
    source_type: str
    capabilities: tuple[str, ...]
    public_only: bool = True
    authentication_required: bool = False
    execution_mode: str = "live_public_lookup"
    rate_note: str = "Conservative local rate limit."
    legal_note: str = "Only public-source use within an approved case scope."


class _SafeRedirect104(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        decision = URLPolicy.normalize_public_url(newurl)
        if not decision.get("ok") or urlparse(newurl).scheme.lower() != "https":
            raise HTTPError(newurl, code, "Unsafe redirect blocked", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class SafeHTTPTransport104:
    """Small HTTPS-only public lookup transport with bounded response bodies."""

    USER_AGENT = "EagleEye-PersonOSINT-Pro/104.0 public-only-review-first"

    def __init__(self, *, timeout_seconds: float = 12.0, max_bytes: int = 5 * 1024 * 1024):
        self.timeout_seconds = float(timeout_seconds)
        self.max_bytes = int(max_bytes)
        self.opener = build_opener(ProxyHandler(), HTTPSHandler(), _SafeRedirect104())

    def fetch(self, url: str, headers: Dict[str, str] | None = None) -> Dict[str, Any]:
        decision = URLPolicy.normalize_public_url(url)
        if not decision.get("ok"):
            raise ValueError(decision.get("blocked_reason") or "URL blocked")
        if urlparse(url).scheme.lower() != "https":
            raise ValueError("Build 104 live adapters require HTTPS.")
        request_headers = {"User-Agent": self.USER_AGENT, "Accept": "application/json"}
        request_headers.update(headers or {})
        req = Request(url, headers=request_headers, method="GET")
        started = time.monotonic()
        try:
            with self.opener.open(req, timeout=self.timeout_seconds) as response:
                body = response.read(self.max_bytes + 1)
                if len(body) > self.max_bytes:
                    raise ValueError("Provider response exceeds the configured size limit.")
                final_url = response.geturl()
                final_decision = URLPolicy.normalize_public_url(final_url)
                if not final_decision.get("ok") or urlparse(final_url).scheme.lower() != "https":
                    raise ValueError("Provider redirected to a blocked destination.")
                safe_headers = {
                    k.lower(): v
                    for k, v in response.headers.items()
                    if k.lower() in {"content-type", "content-length", "etag", "last-modified", "date", "cache-control"}
                }
                return {
                    "status_code": int(getattr(response, "status", 200)),
                    "requested_url": url,
                    "final_url": final_url,
                    "headers": safe_headers,
                    "body": body,
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                }
        except HTTPError as exc:
            body = exc.read(self.max_bytes) if hasattr(exc, "read") else b""
            raise RuntimeError(f"HTTP {exc.code} from public provider: {body[:300].decode('utf-8', errors='replace')}") from exc
        except (URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"Public provider request failed: {exc}") from exc


class SourceAdapterExecution104Service:
    """Build 104.0 controlled execution layer for a small set of public adapters.

    Every successful execution stores the exact response bundle, hashes it, creates one
    canonical candidate finding/evidence object, rates the source and adds only candidate
    graph relations. It never creates a verified person claim.
    """

    BUILD = "104.0"
    DOMAIN_RE = re.compile(r"(?=^.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.I)
    USER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,37}[A-Za-z0-9])?$")
    DNS_TYPES = ("A", "AAAA", "MX", "NS")
    FIXED_PROVIDER_HOSTS = {
        "dns_local": {"cloudflare-dns.com"},
        "wayback_cdx": {"web.archive.org"},
        "github_users_api": {"api.github.com"},
        "gitlab_public_api": {"gitlab.com"},
    }
    SPECS: Dict[str, AdapterSpec104] = {
        "rdap_domain_104": AdapterSpec104(
            "rdap_domain_104", "RDAP Domain Lookup", "domain_intelligence", "domain", "rdap_domain",
            "official_register", ("domain_record", "nameserver_candidates", "organization_candidates"),
            rate_note="Maximum 20 requests/minute with a two-second local interval.",
        ),
        "dns_doh_104": AdapterSpec104(
            "dns_doh_104", "DNS over HTTPS", "domain_intelligence", "domain", "dns_local",
            "primary_source", ("A", "AAAA", "MX", "NS"),
            rate_note="Each DNS record type consumes one conservative local budget unit.",
        ),
        "wayback_cdx_104": AdapterSpec104(
            "wayback_cdx_104", "Web Archive CDX", "archive", "url", "wayback_cdx",
            "archive", ("historical_snapshots", "timestamps", "content_digests"),
            rate_note="Small result limits only; no bulk crawling.",
        ),
        "github_public_profile_104": AdapterSpec104(
            "github_public_profile_104", "GitHub Public Profile", "public_code_profile", "username", "github_users_api",
            "public_profile", ("public_profile", "public_metadata", "public_organization_candidate"),
            rate_note="Unauthenticated public API, conservatively limited below provider thresholds.",
        ),
        "gitlab_public_profile_104": AdapterSpec104(
            "gitlab_public_profile_104", "GitLab Public Profile", "public_code_profile", "username", "gitlab_public_api",
            "public_profile", ("public_profile", "public_metadata"),
            rate_note="Public API only; exact username lookup and no private projects.",
        ),
    }

    def __init__(
        self,
        db: Database,
        audit: AuditService,
        artifact_dir: str | Path,
        *,
        legal: Any,
        provider_budget: Any,
        platform: Any,
        graph: Any,
        source_reliability: Any,
        transport: Any | None = None,
    ):
        self.db = db
        self.audit = audit
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.legal = legal
        self.budget = provider_budget
        self.platform = platform
        self.graph = graph
        self.reliability = source_reliability
        self.transport = transport or SafeHTTPTransport104()
        self.ensure_schema()
        self.apply_migration()
        self.seed_registry()

    def ensure_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_adapter_registry_104(
              adapter_id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
              input_type TEXT NOT NULL, provider_key TEXT NOT NULL, source_type TEXT NOT NULL,
              capabilities_json TEXT NOT NULL, public_only INTEGER NOT NULL,
              authentication_required INTEGER NOT NULL, execution_mode TEXT NOT NULL,
              rate_note TEXT NOT NULL, legal_note TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_adapter_executions_104(
              execution_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, adapter_id TEXT NOT NULL,
              normalized_input TEXT NOT NULL, options_json TEXT NOT NULL, status TEXT NOT NULL,
              provider_key TEXT NOT NULL, request_count INTEGER NOT NULL DEFAULT 0,
              requested_urls_json TEXT NOT NULL, response_sha256 TEXT DEFAULT '', response_bytes INTEGER DEFAULT 0,
              raw_bundle_path TEXT DEFAULT '', capture_id TEXT DEFAULT '', finding_id TEXT DEFAULT '',
              evidence_id TEXT DEFAULT '', source_rating_id TEXT DEFAULT '', graph_refs_json TEXT NOT NULL,
              warnings_json TEXT NOT NULL, error_text TEXT DEFAULT '', started_at TEXT NOT NULL,
              completed_at TEXT DEFAULT '', actor TEXT DEFAULT 'local-analyst',
              FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_adapter_exec_case_104
              ON source_adapter_executions_104(case_id, started_at);
            CREATE TABLE IF NOT EXISTS source_adapter_http_events_104(
              http_event_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL, request_index INTEGER NOT NULL,
              requested_url TEXT NOT NULL, final_url TEXT NOT NULL, status_code INTEGER NOT NULL,
              response_sha256 TEXT NOT NULL, response_bytes INTEGER NOT NULL,
              headers_json TEXT NOT NULL, elapsed_ms INTEGER NOT NULL, created_at TEXT NOT NULL,
              FOREIGN KEY(execution_id) REFERENCES source_adapter_executions_104(execution_id) ON DELETE CASCADE
            );
            """
        )
        self.db.conn.commit()

    def apply_migration(self) -> Dict[str, Any]:
        migration_id = "104.0-controlled-source-adapters-v1"
        row = self.db.one("SELECT migration_id FROM schema_migrations_103_1 WHERE migration_id=?", [migration_id])
        if row:
            # A historical migration must never downgrade global runtime metadata.
            return {"status": "already_applied", "version": self.BUILD, "migration_id": migration_id}
        checksum = hashlib.sha256(migration_id.encode("utf-8")).hexdigest()
        with self.db.conn:
            self.db.conn.execute(
                "INSERT INTO schema_migrations_103_1(migration_id,version,description,checksum,applied_at) VALUES(?,?,?,?,?)",
                [migration_id, self.BUILD, "Controlled public source adapter execution layer", checksum, now_ts()],
            )
            # The migration version is recorded in schema_migrations_103_1. Global
            # schema/build metadata remains owned by the current Database bootstrap.
        self.audit.log("migrate", "schema", migration_id, None, {"version": self.BUILD, "checksum": checksum})
        return {"status": "applied", "version": self.BUILD, "migration_id": migration_id}

    def seed_registry(self) -> None:
        for spec in self.SPECS.values():
            self.db.execute(
                """INSERT OR REPLACE INTO source_adapter_registry_104(
                adapter_id,name,category,input_type,provider_key,source_type,capabilities_json,public_only,
                authentication_required,execution_mode,rate_note,legal_note,enabled,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    spec.adapter_id, spec.name, spec.category, spec.input_type, spec.provider_key,
                    spec.source_type, dumps(list(spec.capabilities)), int(spec.public_only),
                    int(spec.authentication_required), spec.execution_mode, spec.rate_note,
                    spec.legal_note, 1, now_ts(),
                ],
            )

    def list_adapters(self) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM source_adapter_registry_104 ORDER BY category,name")
        for row in rows:
            row["capabilities"] = loads(row.pop("capabilities_json", "[]"), [])
            row["public_only"] = bool(row["public_only"])
            row["authentication_required"] = bool(row["authentication_required"])
            row["enabled"] = bool(row["enabled"])
            budget = self.budget.check(row["provider_key"], consume=False)
            row["budget"] = budget
        return rows

    def readiness(self, case_id: str = "") -> Dict[str, Any]:
        case_id = self.platform.resolve_case_id(case_id)
        legal = self.legal.evaluate_case(case_id)
        adapters = self.list_adapters()
        return {
            "build": self.BUILD,
            "case_id": case_id,
            "legal_gate": legal,
            "adapter_count": len(adapters),
            "enabled_adapter_count": sum(1 for a in adapters if a["enabled"]),
            "live_execution_ready": bool(legal.get("ok") and adapters),
            "principles": ["public_only", "explicit_confirmation", "candidate_not_claim", "raw_response_hashed", "rate_limited", "audit_logged"],
        }

    def execute(
        self,
        case_id: str,
        adapter_id: str,
        input_value: str,
        *,
        options: Dict[str, Any] | None = None,
        explicit_live_confirmation: bool = False,
        actor: str = "local-analyst",
    ) -> Dict[str, Any]:
        case_id = self.platform.resolve_case_id(case_id)
        spec = self.SPECS.get(adapter_id)
        if not spec:
            raise ValueError(f"Unsupported Build-104 adapter: {adapter_id}")
        if not explicit_live_confirmation:
            raise PermissionError("Explicit live-provider confirmation is required.")
        legal = self.legal.evaluate_case(case_id)
        if not legal.get("ok"):
            raise PermissionError("Approved legal scope is required before live public adapter execution: " + "; ".join(legal.get("issues") or []))
        normalized = self._normalize_input(spec, input_value)
        safe_options = self._normalize_options(spec, options or {})
        execution_id = new_id("ad104")
        started = now_ts()
        self.db.execute(
            """INSERT INTO source_adapter_executions_104(
            execution_id,case_id,adapter_id,normalized_input,options_json,status,provider_key,request_count,
            requested_urls_json,response_sha256,response_bytes,raw_bundle_path,capture_id,finding_id,evidence_id,
            source_rating_id,graph_refs_json,warnings_json,error_text,started_at,completed_at,actor)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [execution_id, case_id, adapter_id, normalized, dumps(safe_options), "running", spec.provider_key, 0,
             dumps([]), "", 0, "", "", "", "", "", dumps({}), dumps([]), "", started, "", actor],
        )
        self.audit.log("start", "source_adapter_execution_104", execution_id, case_id, {"adapter_id": adapter_id, "input_type": spec.input_type, "input": normalized})
        try:
            bundle = self._run_adapter(execution_id, spec, normalized, safe_options)
            raw_bytes = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            edir = self.artifact_dir / case_id / execution_id
            edir.mkdir(parents=True, exist_ok=False)
            raw_path = edir / "response_bundle.json"
            raw_path.write_bytes(raw_bytes)
            response_sha = hashlib.sha256(raw_bytes).hexdigest()
            requested_urls = [r["requested_url"] for r in bundle["responses"]]
            canonical_source_url = bundle.get("source_url") or requested_urls[0]
            capture = self.platform.include_finding(
                case_id=case_id,
                url=canonical_source_url,
                text=raw_bytes.decode("utf-8"),
                title=bundle.get("title") or f"{spec.name}: {normalized}",
                source_label=adapter_id,
                notes="Controlled live public adapter result; raw response bundle hashed; candidate only.",
                input_kind="source_adapter",
                run_security=True,
                run_ai_triage=True,
                metadata={
                    "build": self.BUILD,
                    "adapter_id": adapter_id,
                    "adapter_execution_id": execution_id,
                    "source_type": spec.source_type,
                    "provider_key": spec.provider_key,
                    "raw_bundle_path": str(raw_path),
                    "raw_bundle_sha256": response_sha,
                    "request_count": len(bundle["responses"]),
                },
            )
            graph_refs = self._graph_candidates(case_id, execution_id, spec, normalized, bundle, capture)
            completed = now_ts()
            self.db.execute(
                """UPDATE source_adapter_executions_104 SET status='succeeded',request_count=?,requested_urls_json=?,
                response_sha256=?,response_bytes=?,raw_bundle_path=?,capture_id=?,finding_id=?,evidence_id=?,source_rating_id=?,
                graph_refs_json=?,warnings_json=?,completed_at=? WHERE execution_id=?""",
                [len(bundle["responses"]), dumps(requested_urls), response_sha, len(raw_bytes), str(raw_path),
                 capture.get("capture_id", ""), capture.get("finding_id", ""), capture.get("evidence_id", ""),
                 capture.get("source_rating_id", ""), dumps(graph_refs), dumps(bundle.get("warnings", [])), completed, execution_id],
            )
            self.audit.log("complete", "source_adapter_execution_104", execution_id, case_id, {
                "adapter_id": adapter_id, "status": "succeeded", "response_sha256": response_sha,
                "capture_id": capture.get("capture_id", ""), "finding_id": capture.get("finding_id", ""),
                "candidate_not_claim": True,
            })
            return self.get_execution(execution_id)
        except Exception as exc:
            self.db.execute(
                "UPDATE source_adapter_executions_104 SET status='failed',error_text=?,completed_at=? WHERE execution_id=?",
                [str(exc)[:4000], now_ts(), execution_id],
            )
            self.audit.log("fail", "source_adapter_execution_104", execution_id, case_id, {"adapter_id": adapter_id, "error": str(exc)[:1000]})
            return self.get_execution(execution_id)

    def get_execution(self, execution_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM source_adapter_executions_104 WHERE execution_id=?", [execution_id])
        if not row:
            raise KeyError(execution_id)
        row["options"] = loads(row.pop("options_json", "{}"), {})
        row["requested_urls"] = loads(row.pop("requested_urls_json", "[]"), [])
        row["graph_refs"] = loads(row.pop("graph_refs_json", "{}"), {})
        row["warnings"] = loads(row.pop("warnings_json", "[]"), [])
        row["candidate_not_claim"] = True
        row["http_events"] = self.db.all(
            "SELECT * FROM source_adapter_http_events_104 WHERE execution_id=? ORDER BY request_index", [execution_id]
        )
        for event in row["http_events"]:
            event["headers"] = loads(event.pop("headers_json", "{}"), {})
        return row

    def list_executions(self, case_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        case_id = self.platform.resolve_case_id(case_id)
        rows = self.db.all(
            "SELECT execution_id FROM source_adapter_executions_104 WHERE case_id=? ORDER BY started_at DESC LIMIT ?",
            [case_id, int(limit)],
        )
        return [self.get_execution(r["execution_id"]) for r in rows]

    def verify_execution(self, execution_id: str) -> Dict[str, Any]:
        row = self.get_execution(execution_id)
        path = Path(row.get("raw_bundle_path") or "")
        actual = self._sha_file(path) if path.is_file() else ""
        capture_verification = {}
        if row.get("capture_id"):
            try:
                capture_verification = self.platform.verify_capture(row["capture_id"])
            except Exception as exc:
                capture_verification = {"valid": False, "error": str(exc)}
        valid = bool(path.is_file() and actual == row.get("response_sha256") and capture_verification.get("valid"))
        return {
            "execution_id": execution_id,
            "valid": valid,
            "raw_bundle_exists": path.is_file(),
            "stored_sha256": row.get("response_sha256", ""),
            "actual_sha256": actual,
            "capture_verification": capture_verification,
        }

    # ----- provider execution -----
    def _run_adapter(self, execution_id: str, spec: AdapterSpec104, value: str, options: Dict[str, Any]) -> Dict[str, Any]:
        if spec.adapter_id == "rdap_domain_104":
            url = f"https://rdap.org/domain/{quote(value, safe='.-')}"
            responses = [self._fetch_json(execution_id, spec.provider_key, url, 0)]
            data = responses[0]["json"]
            return {"adapter_id": spec.adapter_id, "input": value, "title": f"RDAP domain record: {value}", "source_url": responses[0]["final_url"], "responses": responses, "summary": self._rdap_summary(data), "warnings": []}
        if spec.adapter_id == "dns_doh_104":
            record_types = options.get("record_types") or list(self.DNS_TYPES)
            responses = []
            for index, record_type in enumerate(record_types):
                url = "https://cloudflare-dns.com/dns-query?" + urlencode({"name": value, "type": record_type})
                responses.append(self._fetch_json(execution_id, spec.provider_key, url, index, headers={"Accept": "application/dns-json"}, label=record_type))
            return {"adapter_id": spec.adapter_id, "input": value, "title": f"DNS public records: {value}", "source_url": responses[0]["final_url"], "responses": responses, "summary": self._dns_summary(responses), "warnings": []}
        if spec.adapter_id == "wayback_cdx_104":
            limit = int(options.get("limit", 10))
            params = [("url", value), ("output", "json"), ("fl", "timestamp,original,statuscode,mimetype,digest"), ("filter", "statuscode:200"), ("collapse", "digest"), ("limit", str(limit))]
            url = "https://web.archive.org/cdx/search/cdx?" + urlencode(params)
            responses = [self._fetch_json(execution_id, spec.provider_key, url, 0)]
            return {"adapter_id": spec.adapter_id, "input": value, "title": f"Web Archive snapshots: {value}", "source_url": responses[0]["final_url"], "responses": responses, "summary": self._wayback_summary(responses[0]["json"]), "warnings": []}
        if spec.adapter_id == "github_public_profile_104":
            url = f"https://api.github.com/users/{quote(value, safe='-._')}"
            responses = [self._fetch_json(execution_id, spec.provider_key, url, 0, headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10"})]
            return {"adapter_id": spec.adapter_id, "input": value, "title": f"GitHub public profile: {value}", "source_url": responses[0]["final_url"], "responses": responses, "summary": self._profile_summary(responses[0]["json"], "github"), "warnings": ["Username equality is not identity proof."]}
        if spec.adapter_id == "gitlab_public_profile_104":
            url = "https://gitlab.com/api/v4/users?" + urlencode({"username": value})
            responses = [self._fetch_json(execution_id, spec.provider_key, url, 0)]
            payload = responses[0]["json"]
            profile = {}
            if isinstance(payload, list):
                profile = next((item for item in payload if str(item.get("username") or "").casefold() == value.casefold()), {})
            warnings = ["Username equality is not identity proof."]
            if not profile:
                warnings.append("No exact public GitLab username match was returned.")
            return {"adapter_id": spec.adapter_id, "input": value, "title": f"GitLab public profile: {value}", "source_url": responses[0]["final_url"], "responses": responses, "summary": self._profile_summary(profile, "gitlab"), "warnings": warnings}
        raise ValueError(spec.adapter_id)

    def _fetch_json(self, execution_id: str, provider_key: str, url: str, index: int, *, headers: Dict[str, str] | None = None, label: str = "") -> Dict[str, Any]:
        budget = self.budget.check(provider_key, consume=True)
        if not budget.get("allowed") and budget.get("reason") == "MIN_INTERVAL_NOT_MET":
            delay = max(0.0, min(5.0, float(budget.get("retry_after_seconds") or 0)))
            if delay:
                time.sleep(delay)
            budget = self.budget.check(provider_key, consume=True)
        if not budget.get("allowed"):
            raise RuntimeError(f"Provider budget blocked request: {budget.get('reason')} retry_after={budget.get('retry_after_seconds')}")
        result = self.transport.fetch(url, headers=headers)
        final_host = (urlparse(result.get("final_url") or "").hostname or "").lower().rstrip(".")
        allowed_hosts = self.FIXED_PROVIDER_HOSTS.get(provider_key)
        if allowed_hosts and final_host not in allowed_hosts:
            raise RuntimeError(f"Provider redirect host blocked: {final_host or 'missing'}")
        body = result["body"]
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Provider returned non-JSON content.") from exc
        digest = hashlib.sha256(body).hexdigest()
        event_id = new_id("http104")
        self.db.execute(
            """INSERT INTO source_adapter_http_events_104(http_event_id,execution_id,request_index,requested_url,final_url,status_code,
            response_sha256,response_bytes,headers_json,elapsed_ms,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            [event_id, execution_id, index, result["requested_url"], result["final_url"], int(result["status_code"]), digest, len(body), dumps(result.get("headers", {})), int(result.get("elapsed_ms", 0)), now_ts()],
        )
        return {
            "request_index": index,
            "label": label,
            "requested_url": result["requested_url"],
            "final_url": result["final_url"],
            "status_code": int(result["status_code"]),
            "headers": result.get("headers", {}),
            "body_sha256": digest,
            "body_bytes": len(body),
            "raw_text": body.decode("utf-8"),
            "json": parsed,
            "elapsed_ms": int(result.get("elapsed_ms", 0)),
        }

    # ----- normalization -----
    def _normalize_input(self, spec: AdapterSpec104, value: str) -> str:
        raw = (value or "").strip()
        if spec.input_type == "domain":
            host = raw.lower().rstrip(".")
            if "://" in host:
                host = (urlparse(host).hostname or "").lower().rstrip(".")
            try:
                host = host.encode("idna").decode("ascii")
            except UnicodeError as exc:
                raise ValueError("Invalid internationalized domain name.") from exc
            if not self.DOMAIN_RE.fullmatch(host):
                raise ValueError("A valid public domain name is required.")
            decision = URLPolicy.normalize_public_url("https://" + host + "/")
            if not decision.get("ok"):
                raise ValueError(decision.get("blocked_reason") or "Domain blocked")
            return host
        if spec.input_type == "username":
            if not self.USER_RE.fullmatch(raw):
                raise ValueError("Invalid public profile username.")
            return raw
        if spec.input_type == "url":
            decision = URLPolicy.normalize_public_url(raw)
            if not decision.get("ok"):
                raise ValueError(decision.get("blocked_reason") or "URL blocked")
            return decision.get("canonical_url") or decision.get("normalized_url") or raw
        raise ValueError("Unsupported adapter input type.")

    def _normalize_options(self, spec: AdapterSpec104, options: Dict[str, Any]) -> Dict[str, Any]:
        if spec.adapter_id == "dns_doh_104":
            raw = options.get("record_types") or self.DNS_TYPES
            if isinstance(raw, str):
                raw = [v.strip().upper() for v in raw.split(",") if v.strip()]
            types = []
            for value in raw:
                value = str(value).upper()
                if value not in self.DNS_TYPES:
                    raise ValueError(f"Unsupported DNS record type: {value}")
                if value not in types:
                    types.append(value)
            return {"record_types": types or list(self.DNS_TYPES)}
        if spec.adapter_id == "wayback_cdx_104":
            return {"limit": max(1, min(25, int(options.get("limit", 10))))}
        return {}

    # ----- graph candidate generation -----
    def _graph_candidates(self, case_id: str, execution_id: str, spec: AdapterSpec104, value: str, bundle: Dict[str, Any], capture: Dict[str, Any]) -> Dict[str, Any]:
        source = self._upsert_node(case_id, "source", spec.name, bundle.get("source_url", ""), 70, execution_id, {"adapter_id": spec.adapter_id, "candidate_not_claim": True})
        refs: Dict[str, Any] = {"source_node_id": source["node_id"], "nodes": [], "edges": []}
        evidence_ref = capture.get("evidence_id", "")
        if spec.adapter_id in {"rdap_domain_104", "dns_doh_104"}:
            root = self._upsert_node(case_id, "domain", value, value, 65, execution_id, {"adapter_id": spec.adapter_id})
            refs["nodes"].append(root["node_id"])
            refs["edges"].append(self._upsert_edge(case_id, source["node_id"], root["node_id"], "mentions", 65, evidence_ref, {"adapter_id": spec.adapter_id})["edge_id"])
            summary = bundle.get("summary") or {}
            for ip in summary.get("ip_addresses", []):
                node = self._upsert_node(case_id, "ip_address", ip, ip, 55, execution_id, {"candidate_not_claim": True})
                refs["nodes"].append(node["node_id"]); refs["edges"].append(self._upsert_edge(case_id, root["node_id"], node["node_id"], "resolves_to", 55, evidence_ref, {})["edge_id"])
            for host in summary.get("nameservers", []) + summary.get("mail_exchangers", []):
                node = self._upsert_node(case_id, "domain", host, host, 55, execution_id, {"candidate_not_claim": True})
                refs["nodes"].append(node["node_id"]); refs["edges"].append(self._upsert_edge(case_id, root["node_id"], node["node_id"], "associated_with", 45, evidence_ref, {"candidate_not_claim": True})["edge_id"])
            for org in summary.get("organizations", []):
                node = self._upsert_node(case_id, "organization", org, org, 45, execution_id, {"candidate_not_claim": True})
                refs["nodes"].append(node["node_id"]); refs["edges"].append(self._upsert_edge(case_id, root["node_id"], node["node_id"], "registered_to_candidate", 40, evidence_ref, {"candidate_not_claim": True})["edge_id"])
        elif spec.adapter_id == "wayback_cdx_104":
            root = self._upsert_node(case_id, "url", value, value, 65, execution_id, {})
            refs["nodes"].append(root["node_id"])
            refs["edges"].append(self._upsert_edge(case_id, source["node_id"], root["node_id"], "mentions", 65, evidence_ref, {})["edge_id"])
            for snapshot in (bundle.get("summary") or {}).get("snapshots", [])[:25]:
                label = snapshot.get("timestamp", "archive")
                node = self._upsert_node(case_id, "archive_snapshot", label, snapshot.get("archive_url", ""), 55, execution_id, snapshot)
                refs["nodes"].append(node["node_id"]); refs["edges"].append(self._upsert_edge(case_id, root["node_id"], node["node_id"], "archived_as", 55, evidence_ref, {})["edge_id"])
        else:
            profile = bundle.get("summary") or {}
            username = self._upsert_node(case_id, "username", value, value, 55, execution_id, {"platform": profile.get("platform", ""), "candidate_not_claim": True})
            refs["nodes"].append(username["node_id"])
            refs["edges"].append(self._upsert_edge(case_id, source["node_id"], username["node_id"], "mentions", 55, evidence_ref, {})["edge_id"])
            profile_url = profile.get("profile_url") or bundle.get("source_url", "")
            if profile_url:
                node = self._upsert_node(case_id, "url", profile_url, profile_url, 60, execution_id, {})
                refs["nodes"].append(node["node_id"]); refs["edges"].append(self._upsert_edge(case_id, username["node_id"], node["node_id"], "profile_on", 55, evidence_ref, {"candidate_not_claim": True})["edge_id"])
            company = profile.get("company") or ""
            if company:
                node = self._upsert_node(case_id, "organization", company, company, 40, execution_id, {"candidate_not_claim": True})
                refs["nodes"].append(node["node_id"]); refs["edges"].append(self._upsert_edge(case_id, username["node_id"], node["node_id"], "associated_with", 35, evidence_ref, {"candidate_not_claim": True})["edge_id"])
            location = profile.get("location") or ""
            if location:
                node = self._upsert_node(case_id, "location", location, location, 35, execution_id, {"candidate_not_claim": True})
                refs["nodes"].append(node["node_id"]); refs["edges"].append(self._upsert_edge(case_id, username["node_id"], node["node_id"], "associated_with", 30, evidence_ref, {"candidate_not_claim": True})["edge_id"])
        return refs

    def _upsert_node(self, case_id: str, node_type: str, label: str, value: str, confidence: int, source_ref: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        row = self.db.one("SELECT node_id FROM investigation_graph_nodes_68 WHERE case_id=? AND node_type=? AND label=? AND value=? LIMIT 1", [case_id, node_type, label, value])
        if row:
            return self.graph.get_node(row["node_id"])
        return self.graph.add_node(case_id, node_type, label, value=value, confidence=confidence, source_ref=source_ref, metadata={"build": self.BUILD, **metadata})

    def _upsert_edge(self, case_id: str, source: str, target: str, edge_type: str, confidence: int, evidence_ref: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        row = self.db.one("SELECT edge_id FROM investigation_graph_edges_68 WHERE case_id=? AND source_node_id=? AND target_node_id=? AND edge_type=? LIMIT 1", [case_id, source, target, edge_type])
        if row:
            return self.graph.get_edge(row["edge_id"])
        return self.graph.add_edge(case_id, source, target, edge_type, confidence=confidence, review_status="candidate", evidence_ref=evidence_ref, metadata={"build": self.BUILD, "candidate_not_claim": True, **metadata})

    # ----- response summaries (minimized; no private-address extraction) -----
    def _rdap_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        nameservers = sorted({str(n.get("ldhName") or "").lower().rstrip(".") for n in data.get("nameservers", []) if n.get("ldhName")})
        organizations: List[str] = []
        for entity in data.get("entities", []) or []:
            roles = {str(r).lower() for r in entity.get("roles", [])}
            if not roles.intersection({"registrant", "registrar", "technical", "administrative"}):
                continue
            vcard = entity.get("vcardArray") or []
            rows = vcard[1] if len(vcard) > 1 and isinstance(vcard[1], list) else []
            for item in rows:
                if isinstance(item, list) and len(item) >= 4 and item[0] == "org":
                    value = item[3]
                    if isinstance(value, list): value = " ".join(str(v) for v in value)
                    value = str(value).strip()
                    if value and value not in organizations: organizations.append(value[:240])
        return {
            "domain": data.get("ldhName") or data.get("unicodeName") or "",
            "handle": data.get("handle") or "",
            "status": list(data.get("status") or []),
            "nameservers": nameservers,
            "organizations": organizations,
            "events": [{"action": e.get("eventAction"), "date": e.get("eventDate")} for e in data.get("events", []) if e.get("eventAction")],
            "ip_addresses": [], "mail_exchangers": [],
        }

    def _dns_summary(self, responses: List[Dict[str, Any]]) -> Dict[str, Any]:
        ips: set[str] = set(); nameservers: set[str] = set(); mx: set[str] = set(); records: List[Dict[str, Any]] = []
        for response in responses:
            rtype = response.get("label")
            for answer in (response.get("json") or {}).get("Answer", []) or []:
                data = str(answer.get("data") or "").strip()
                records.append({"type": rtype, "name": answer.get("name", ""), "ttl": answer.get("TTL"), "data": data})
                if rtype in {"A", "AAAA"} and data: ips.add(data)
                elif rtype == "NS" and data: nameservers.add(data.rstrip("."))
                elif rtype == "MX" and data:
                    parts = data.split(maxsplit=1); mx.add((parts[-1] if parts else data).rstrip("."))
        return {"records": records, "ip_addresses": sorted(ips), "nameservers": sorted(nameservers), "mail_exchangers": sorted(mx), "organizations": []}

    def _wayback_summary(self, payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, list) or not payload:
            return {"snapshots": []}
        header = payload[0] if isinstance(payload[0], list) else []
        snapshots = []
        for row in payload[1:26]:
            if not isinstance(row, list): continue
            item = dict(zip(header, row))
            timestamp = str(item.get("timestamp") or "")
            original = str(item.get("original") or "")
            item["archive_url"] = f"https://web.archive.org/web/{timestamp}/{original}" if timestamp and original else ""
            snapshots.append(item)
        return {"snapshots": snapshots, "snapshot_count": len(snapshots)}

    def _profile_summary(self, data: Dict[str, Any], platform: str) -> Dict[str, Any]:
        return {
            "platform": platform,
            "username": data.get("login") or data.get("username") or "",
            "display_name": data.get("name") or "",
            "profile_url": data.get("html_url") or data.get("web_url") or "",
            "company": data.get("company") or data.get("organization") or "",
            "location": data.get("location") or "",
            "public_email": data.get("email") or data.get("public_email") or "",
            "website": data.get("blog") or data.get("website_url") or "",
            "created_at": data.get("created_at") or "",
            "public_repositories": data.get("public_repos") if "public_repos" in data else None,
            "bio": data.get("bio") or "",
        }

    @staticmethod
    def _sha_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
