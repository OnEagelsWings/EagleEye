from __future__ import annotations

import hashlib
import html as htmlmod
import json
import re
import socket
import ssl
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

POLICY_VERSION = "phase15.governed-crawler.v2"
USER_AGENT = "EagleEye-GovernedCrawler/350.0 (+local-review-first)"
VALID_ONION = re.compile(r"^[a-z2-7]{56}\.onion$", re.I)
READ_ONLY_METHODS = {"GET", "HEAD"}
TEXT_TYPES = ("text/", "application/json", "application/xml", "application/xhtml+xml")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean_url(url: str) -> str:
    parsed = urlsplit(str(url).strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("only absolute http/https URLs are supported")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("userinfo in URL is forbidden")
    host = parsed.hostname.lower().rstrip(".")
    port = parsed.port
    if port not in (None, 80, 443):
        raise ValueError("non-standard ports are not allowed in Build 349")
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, ""))


@dataclass(frozen=True)
class FetchResponse:
    url: str
    status: int
    headers: Mapping[str, str]
    body: bytes
    elapsed_ms: int = 0


class CrawlTransport(Protocol):
    transport_kind: str
    externally_configured: bool

    def fetch(self, url: str, *, method: str = "GET", headers: Mapping[str, str] | None = None, timeout_seconds: int = 20, max_bytes: int = 2_000_000) -> FetchResponse: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # pragma: no cover - urllib callback
        return None


class UrllibReadOnlyTransport:
    """Explicit, read-only clearnet transport.

    It never uses environment proxy settings. A proxy must be passed explicitly. It
    deliberately refuses .onion so an onion hostname cannot leak to local DNS.
    """

    transport_kind = "clearnet_urllib_explicit_v1"
    externally_configured = True

    def __init__(self, *, proxy_url: str | None = None, ca_file: str | None = None, user_agent: str | None = None) -> None:
        self.proxy_url = str(proxy_url or "").strip()
        self.user_agent = str(user_agent or USER_AGENT).strip()[:300] or USER_AGENT
        proxy_map = {"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else {}
        self._ssl = ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()
        self._opener = build_opener(ProxyHandler(proxy_map), HTTPSHandler(context=self._ssl), _NoRedirect())

    def fetch(self, url: str, *, method: str = "GET", headers: Mapping[str, str] | None = None, timeout_seconds: int = 20, max_bytes: int = 2_000_000) -> FetchResponse:
        target = _clean_url(url)
        host = (urlsplit(target).hostname or "").lower()
        if VALID_ONION.fullmatch(host):
            raise PermissionError("built-in clearnet transport refuses onion hosts; use an approved Tor gateway transport")
        method_u = method.upper()
        if method_u not in READ_ONLY_METHODS:
            raise PermissionError("crawler transport is read-only")
        request_headers = {"User-Agent": self.user_agent, "Accept": "text/html,text/plain,application/json,application/xml;q=0.9,*/*;q=0.5"}
        request_headers.update({str(k): str(v) for k, v in (headers or {}).items()})
        started = time.monotonic()
        req = Request(target, method=method_u, headers=request_headers)
        try:
            response = self._opener.open(req, timeout=max(1, min(int(timeout_seconds), 60)))
        except HTTPError as exc:
            response = exc
        with response:
            body = response.read(max(1, int(max_bytes)) + 1) if method_u == "GET" else b""
            if len(body) > int(max_bytes):
                raise ValueError("response exceeds configured max_bytes")
            hdrs = {str(k).lower(): str(v) for k, v in response.headers.items()}
            return FetchResponse(url=target, status=int(getattr(response, "status", getattr(response, "code", 200))), headers=hdrs, body=body, elapsed_ms=int((time.monotonic() - started) * 1000))


class StaticTransport:
    """Deterministic transport for replay/contract tests; never opens a network connection."""

    transport_kind = "static_replay_v1"
    externally_configured = False

    def __init__(self, responses: Mapping[str, FetchResponse | tuple[int, Mapping[str, str], bytes]]) -> None:
        self.responses: dict[str, FetchResponse] = {}
        for url, value in responses.items():
            clean = _clean_url(url)
            if isinstance(value, FetchResponse):
                self.responses[clean] = value
            else:
                status, headers, body = value
                self.responses[clean] = FetchResponse(clean, int(status), dict(headers), bytes(body), 1)
        self.calls: list[str] = []
        self.request_log: list[dict[str, Any]] = []
        self.user_agent = USER_AGENT

    def fetch(self, url: str, *, method: str = "GET", headers: Mapping[str, str] | None = None, timeout_seconds: int = 20, max_bytes: int = 2_000_000) -> FetchResponse:
        if method.upper() not in READ_ONLY_METHODS:
            raise PermissionError("crawler transport is read-only")
        clean = _clean_url(url)
        self.calls.append(clean)
        self.request_log.append({"url": clean, "method": method.upper(), "headers": {str(k): str(v) for k, v in (headers or {}).items()}})
        if clean not in self.responses:
            raise KeyError(f"no replay response for {clean}")
        response = self.responses[clean]
        if len(response.body) > int(max_bytes):
            raise ValueError("response exceeds configured max_bytes")
        return response


class _HTMLSignals(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._in_title = False
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
        if t == "title": self._in_title = True
        if t in {"script", "style", "noscript"}: self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "title": self._in_title = False
        if t in {"script", "style", "noscript"} and self._skip: self._skip -= 1

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text or self._skip: return
        if self._in_title: self.title_parts.append(text)
        self.text_parts.append(text)


class RobotsRules:
    """Small RFC-9309-style robots matcher used by the governed crawler.

    Build 397 fixes two readiness defects from the weekly qualification report:
    wildcard/end-anchor rules and groups containing multiple User-agent lines.
    Rule precedence uses the longest matching octet pattern; Allow wins ties.
    """

    def __init__(self, text: str, *, deny_all: bool = False, failure_reason: str = "") -> None:
        self.failure_reason = str(failure_reason or "")[:500]
        self._deny_all = bool(deny_all)
        self.rules: list[tuple[str, str, int]] = []
        if self._deny_all:
            self.rules.append(("disallow", "/", 1))
            return

        product = USER_AGENT.split("/", 1)[0].casefold()
        full_ua = USER_AGENT.casefold()
        groups: list[tuple[list[str], list[tuple[str, str]]]] = []
        agents: list[str] = []
        rules: list[tuple[str, str]] = []
        rules_started = False

        def flush() -> None:
            nonlocal agents, rules, rules_started
            if agents:
                groups.append((agents, rules))
            agents, rules, rules_started = [], [], False

        for raw in str(text or "").splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = [x.strip() for x in line.split(":", 1)]
            low = key.casefold()
            if low == "user-agent":
                if rules_started:
                    flush()
                if value:
                    agents.append(value.casefold())
            elif low in {"allow", "disallow"}:
                if not agents:
                    continue
                rules_started = True
                # Empty Disallow means allow all and therefore contributes no rule.
                if value or low == "allow":
                    rules.append((low, value))
        flush()

        def agent_score(agent: str) -> int:
            if agent == "*":
                return 1
            # Product token matching is case-insensitive.  Accept the exact product
            # token and full configured UA, plus an explicit product-prefix form.
            if agent in {product, full_ua}:
                return 10000 + len(agent)
            if product.startswith(agent) or agent.startswith(product):
                return 5000 + min(len(agent), len(product))
            return 0

        scored = [(max((agent_score(a) for a in uas), default=0), rs) for uas, rs in groups]
        best = max((score for score, _ in scored), default=0)
        selected = [rs for score, rs in scored if score == best and score > 0]
        for rs in selected:
            for kind, pattern in rs:
                specificity = len(pattern.replace("*", "").rstrip("$"))
                self.rules.append((kind, pattern, specificity))

    @classmethod
    def fail_closed(cls, reason: str) -> "RobotsRules":
        return cls("", deny_all=True, failure_reason=reason)

    @staticmethod
    def _matches(pattern: str, target: str) -> bool:
        if pattern == "":
            return False
        anchored = pattern.endswith("$")
        core = pattern[:-1] if anchored else pattern
        expr = "^" + re.escape(core).replace(r"\*", ".*")
        if anchored:
            expr += "$"
        return re.search(expr, target) is not None

    @property
    def fail_closed_state(self) -> bool:
        return self._deny_all

    def allowed(self, path: str) -> bool:
        target = path or "/"
        matched: list[tuple[int, int, str]] = []
        for kind, pattern, specificity in self.rules:
            if self._matches(pattern, target):
                # allow wins equal-specificity ties
                matched.append((specificity, 1 if kind == "allow" else 0, kind))
        if not matched:
            return not self._deny_all
        _, _, kind = max(matched)
        return kind == "allow"


class GovernedCrawler:
    """Bounded crawler worker behind Search Capsule + OPSEC v2 + Job Engine.

    Network transport is injected. This class never changes proxy/Tor/firewall/OS
    configuration, never submits forms, and never sends credentials.
    """

    def __init__(self, db: Any, *, build348: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.build348 = build348
        self.actor = actor

    def _source(self, source_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT s.*,p.* FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE s.source_id=?", (source_id,))
        if not row: raise KeyError(source_id)
        for key in ("seed_urls_json", "allowed_hosts_json"):
            row[key[:-5]] = json.loads(row[key])
        return row

    def register_source(self, *, display_name: str, seed_urls: Sequence[str], terms_ref: str, jurisdiction: str = "Global", source_class: str = "public_web", max_depth: int = 1, max_pages: int = 20, requests_per_minute: int = 10, max_response_bytes: int = 2_000_000, parser_version: str = "html-text-links-v1") -> dict[str, Any]:
        seeds = list(dict.fromkeys(_clean_url(u) for u in seed_urls))
        if not seeds: raise ValueError("at least one seed URL required")
        hosts = sorted({(urlsplit(u).hostname or "").lower() for u in seeds})
        onion = any(VALID_ONION.fullmatch(h) for h in hosts)
        if onion and not all(VALID_ONION.fullmatch(h) for h in hosts):
            raise ValueError("clearnet and onion seeds cannot share one source policy")
        if onion and len(hosts) != 1:
            raise ValueError("Build 349 requires one reviewed onion host per source policy")
        if not str(terms_ref).strip():
            raise ValueError("terms_ref/license snapshot reference required")
        source_kind = "darknet_onion" if onion else "crawler_web"
        locator = hosts[0] if len(hosts) == 1 else "crawler:" + _sha(hosts)[:24]
        existing = self.db.one("SELECT source_id FROM phase15_sources WHERE source_kind=? AND locator=?", (source_kind, locator))
        if existing: return self._source(existing["source_id"])
        source_id = "src349_" + uuid.uuid4().hex[:20]
        now = _now()
        source_body = {
            "source_id": source_id, "source_kind": source_kind, "locator": locator,
            "display_name": str(display_name)[:240], "source_class": str(source_class)[:120],
            "jurisdiction": str(jurisdiction)[:80], "allowed_use": "public_or_authorized_read_only",
            "review_status": "pending_review", "risk_class": "high" if onion else "standard",
            "provenance_json": _canon({"terms_ref": terms_ref, "registered_by": self.actor, "crawler_policy": POLICY_VERSION}),
            "created_by": self.actor, "created_at": now, "updated_at": now,
        }
        self.db.execute("INSERT INTO phase15_sources(source_id,source_kind,locator,display_name,source_class,jurisdiction,allowed_use,review_status,risk_class,provenance_json,created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*source_body.values(), _sha(source_body)))
        policy = {
            "source_id": source_id, "seed_urls_json": _canon(seeds), "allowed_hosts_json": _canon(hosts),
            "terms_ref": str(terms_ref)[:1000], "robots_mode": "respect_required", "auth_type": "none",
            "max_depth": max(0, min(int(max_depth), 3)), "max_pages": max(1, min(int(max_pages), 100)),
            "requests_per_minute": max(1, min(int(requests_per_minute), 60)),
            "max_response_bytes": max(16_384, min(int(max_response_bytes), 10_000_000)),
            "parser_version": str(parser_version)[:120], "enabled": 0, "source_health": "not_run",
            "created_at": now, "updated_at": now,
        }
        self.db.execute("INSERT INTO phase15_crawler_policies(source_id,seed_urls_json,allowed_hosts_json,terms_ref,robots_mode,auth_type,max_depth,max_pages,requests_per_minute,max_response_bytes,parser_version,enabled,source_health,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*policy.values(), _sha(policy)))
        return self._source(source_id)

    def review_source(self, source_id: str, *, decision: str, rationale: str, reviewer: str) -> dict[str, Any]:
        source = self._source(source_id)
        if source["review_status"] != "pending_review": raise PermissionError("source review is append-once in Build 349")
        if decision not in {"approve_read_only", "reject"}: raise ValueError("invalid source decision")
        if not rationale.strip() or not reviewer.strip(): raise ValueError("rationale and reviewer required")
        now = _now(); status = "approved_read_only" if decision == "approve_read_only" else "rejected"
        event = {"event_id":"srev349_"+uuid.uuid4().hex[:20],"source_id":source_id,"decision":decision,"rationale":rationale[:4000],"reviewer":reviewer[:160],"created_at":now}
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO phase15_source_review_events(event_id,source_id,decision,rationale,reviewer,created_at,record_hash) VALUES(?,?,?,?,?,?,?)", (*event.values(), _sha(event)))
            self.db.execute("UPDATE phase15_sources SET review_status=?,updated_at=? WHERE source_id=?", (status, now, source_id))
            self.db.execute("UPDATE phase15_crawler_policies SET enabled=?,updated_at=? WHERE source_id=?", (1 if status == "approved_read_only" else 0, now, source_id))
        return self._source(source_id)

    def enqueue_crawl(self, *, case_id: str, source_id: str) -> dict[str, Any]:
        source = self._source(source_id)
        if source["review_status"] != "approved_read_only" or int(source["enabled"]) != 1:
            raise PermissionError("human-reviewed approved source required")
        if source["auth_type"] != "none": raise PermissionError("Build 349 crawler does not support authenticated crawling")
        hosts = source["allowed_hosts"]
        if source["source_kind"] == "darknet_onion":
            research = self.build348.create_darknet_research(case_id=case_id, query=f"governed crawl: {source['display_name']}", source_ids=[source_id], human_approved=True, max_requests=int(source["max_pages"]) + 3)
            search_run_id = research["capsule"]["search_run_id"]
        else:
            capsule = self.build348.create_clearnet_capsule(case_id=case_id, egress_hosts=hosts, max_requests=int(source["max_pages"]) + 3)
            search_run_id = capsule["search_run_id"]
        crawl_run_id = "crawl349_" + uuid.uuid4().hex[:20]
        now = _now()
        run = {"crawl_run_id":crawl_run_id,"case_id":case_id,"source_id":source_id,"search_run_id":search_run_id,"status":"queued","pages_fetched":0,"pages_stored":0,"bytes_fetched":0,"started_at":None,"completed_at":None,"created_at":now,"summary_json":"{}"}
        self.db.execute("INSERT INTO phase15_crawl_runs(crawl_run_id,case_id,source_id,search_run_id,status,pages_fetched,pages_stored,bytes_fetched,started_at,completed_at,created_at,summary_json,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (*run.values(), _sha(run)))
        job = self.build348.enqueue_job(job_type="governed_crawl_v1", case_id=case_id, search_run_id=search_run_id, idempotency_key=f"crawl349:{crawl_run_id}", payload={"crawl_run_id":crawl_run_id,"source_id":source_id,"network_execution_by_build349_worker":True,"read_only":True}, max_attempts=3, priority=80, resource_budget={"max_runtime_seconds":900,"max_memory_mb":512,"max_output_bytes":int(source["max_pages"])*int(source["max_response_bytes"])}, rate_budget={"max_requests":int(source["max_pages"])+3,"requests_per_minute":int(source["requests_per_minute"])})
        return {"crawl_run_id":crawl_run_id,"search_run_id":search_run_id,"job":job,"source":source}

    def _resolve_public(self, host: str, resolver: Callable[[str], Sequence[str]] | None) -> list[str]:
        if resolver is not None: return [str(v) for v in resolver(host)]
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return sorted({str(item[4][0]) for item in infos})

    def _preflight(self, *, source: dict[str, Any], search_run_id: str, url: str, resolver: Callable[[str], Sequence[str]] | None, redirect_from: str | None = None) -> dict[str, Any]:
        clean = _clean_url(url); host=(urlsplit(clean).hostname or "").lower()
        if host not in set(source["allowed_hosts"]): raise PermissionError("crawler target escaped source allowlist")
        if source["source_kind"] == "darknet_onion":
            ips: list[str] = []
        else:
            ips = self._resolve_public(host, resolver)
        decision = self.build348.preflight_request(search_run_id, url=clean, source_id=source["source_id"] if source["source_kind"]=="darknet_onion" else None, resolved_ips=ips, browser_webrtc_disabled=True, dns_via_approved_profile=True, redirect_chain=[redirect_from] if redirect_from else None, expected_response_bytes=int(source["max_response_bytes"]))
        if decision.get("final_disposition", decision.get("disposition")) != "allow_for_gateway":
            raise PermissionError("OPSEC preflight blocked crawler request")
        return decision

    def _record_fetch(self, *, crawl_run_id: str, url: str, response: FetchResponse | None, disposition: str, reason: str = "", object_id: str = "", depth: int = 0) -> None:
        created=_now(); body_bytes=response.body if response else b""; headers=dict(response.headers) if response else {}
        row={"fetch_id":"fetch349_"+uuid.uuid4().hex[:20],"crawl_run_id":crawl_run_id,"url":url,"depth":int(depth),"status_code":int(response.status if response else 0),"content_type":str(headers.get("content-type", ""))[:200],"content_sha256":_sha(body_bytes) if response else "","size_bytes":len(body_bytes),"elapsed_ms":int(response.elapsed_ms if response else 0),"disposition":disposition,"reason":reason[:1000],"object_id":object_id,"created_at":created}
        self.db.execute("INSERT INTO phase15_crawl_fetches(fetch_id,crawl_run_id,url,depth,status_code,content_type,content_sha256,size_bytes,elapsed_ms,disposition,reason,object_id,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*row.values(), _sha(row)))

    def _fetch_one(self, *, source: dict[str, Any], crawl_run_id: str, search_run_id: str, job_id: str, worker_id: str, url: str, depth: int, transport: CrawlTransport, resolver: Callable[[str], Sequence[str]] | None, redirect_from: str | None = None) -> FetchResponse:
        self._preflight(source=source, search_run_id=search_run_id, url=url, resolver=resolver, redirect_from=redirect_from)
        self.build348.consume_job_request_budget(job_id, worker_id=worker_id, units=1)
        response = transport.fetch(url, method="GET", headers={"User-Agent": USER_AGENT}, timeout_seconds=20, max_bytes=int(source["max_response_bytes"]))
        return response

    def _robots_for(self, *, source: dict[str, Any], crawl_run_id: str, search_run_id: str, job_id: str, worker_id: str, seed_url: str, transport: CrawlTransport, resolver: Callable[[str], Sequence[str]] | None) -> RobotsRules:
        p=urlsplit(seed_url); robots=urlunsplit((p.scheme,p.netloc,"/robots.txt","",""))
        try:
            response=self._fetch_one(source=source,crawl_run_id=crawl_run_id,search_run_id=search_run_id,job_id=job_id,worker_id=worker_id,url=robots,depth=0,transport=transport,resolver=resolver)
        except KeyError as exc:
            # A missing replay entry is not evidence that robots.txt is absent.
            return RobotsRules.fail_closed(f"robots_fetch_unavailable:{type(exc).__name__}")
        if response.status in {404, 410}:
            self._record_fetch(crawl_run_id=crawl_run_id,url=robots,response=response,disposition="robots_absent",reason=f"http_{response.status}",depth=0)
            return RobotsRules("")
        if not (200 <= int(response.status) < 300):
            self._record_fetch(crawl_run_id=crawl_run_id,url=robots,response=response,disposition="robots_fail_closed",reason=f"http_{response.status}",depth=0)
            return RobotsRules.fail_closed(f"robots_http_{response.status}")
        text=response.body.decode("utf-8",errors="replace")[:500000]
        self._record_fetch(crawl_run_id=crawl_run_id,url=robots,response=response,disposition="robots_checked",depth=0)
        return RobotsRules(text)

    def execute_claimed_job(self, *, job_id: str, worker_id: str, transport: CrawlTransport, resolver: Callable[[str], Sequence[str]] | None = None) -> dict[str, Any]:
        job=self.build348.jobs.get(job_id) if hasattr(self.build348,"jobs") else None
        if job is None: job=self.db.one("SELECT * FROM phase15_jobs WHERE job_id=?", (job_id,))
        if not job or job["status"]!="running" or job["lease_owner"]!=worker_id: raise PermissionError("active crawler worker lease required")
        if job["job_type"]!="governed_crawl_v1": raise ValueError("not a governed crawl job")
        payload=json.loads(job["payload_json"]); crawl_run_id=payload["crawl_run_id"]; source=self._source(payload["source_id"])
        run=self.db.one("SELECT * FROM phase15_crawl_runs WHERE crawl_run_id=?", (crawl_run_id,)); search_run_id=run["search_run_id"]
        if source["source_kind"]=="darknet_onion" and not str(transport.transport_kind).startswith("tor_") and transport.transport_kind!="static_replay_v1":
            raise PermissionError("darknet crawl requires approved Tor gateway transport")
        now=_now(); self.db.execute("UPDATE phase15_crawl_runs SET status='running',started_at=COALESCE(started_at,?) WHERE crawl_run_id=?", (now,crawl_run_id))
        robots_by_host: dict[str,RobotsRules]={}; queue=[(u,0) for u in source["seed_urls"]]; seen:set[str]=set(); stored=0; fetched=0; total_bytes=0; errors=0
        try:
            while queue and fetched < int(source["max_pages"]):
                url,depth=queue.pop(0); url=_clean_url(url)
                if url in seen: continue
                seen.add(url); parsed=urlsplit(url); host=(parsed.hostname or "").lower()
                if host not in set(source["allowed_hosts"]): continue
                if host not in robots_by_host:
                    robots_by_host[host]=self._robots_for(source=source,crawl_run_id=crawl_run_id,search_run_id=search_run_id,job_id=job_id,worker_id=worker_id,seed_url=url,transport=transport,resolver=resolver)
                robots_target=(parsed.path or "/") + (("?" + parsed.query) if parsed.query else "")
                if not robots_by_host[host].allowed(robots_target):
                    self._record_fetch(crawl_run_id=crawl_run_id,url=url,response=None,disposition="robots_block",reason="disallowed_by_robots",depth=depth); continue
                try:
                    response=self._fetch_one(source=source,crawl_run_id=crawl_run_id,search_run_id=search_run_id,job_id=job_id,worker_id=worker_id,url=url,depth=depth,transport=transport,resolver=resolver)
                except Exception as exc:
                    errors+=1; self._record_fetch(crawl_run_id=crawl_run_id,url=url,response=None,disposition="fetch_error",reason=f"{type(exc).__name__}:{exc}",depth=depth); continue
                fetched+=1; total_bytes+=len(response.body)
                if response.status in {301,302,303,307,308}:
                    location=response.headers.get("location","")
                    if location:
                        nxt=_clean_url(urljoin(url,location)); nh=(urlsplit(nxt).hostname or "").lower()
                        if nh in set(source["allowed_hosts"]): queue.insert(0,(nxt,depth))
                        else: self._record_fetch(crawl_run_id=crawl_run_id,url=url,response=response,disposition="redirect_block",reason="redirect_outside_allowlist",depth=depth)
                    continue
                ctype=str(response.headers.get("content-type","application/octet-stream")).split(";",1)[0].strip().lower()
                text=""
                if ctype.startswith(TEXT_TYPES) or not ctype:
                    text=response.body.decode("utf-8",errors="replace")
                inspection=self.build348.build347.inspect_content(search_run_id,content_text=text[:500000],content_type=ctype or "application/octet-stream",source_url=url,declared_download=False,attachment_name="")
                security_state="quarantined" if inspection["disposition"]=="quarantine" or source["source_kind"]=="darknet_onion" else "review_pending"
                obj=self.build348.ingest_artifact(case_id=run["case_id"],content=response.body,media_type=ctype or "application/octet-stream",search_run_id=search_run_id,source_id=source["source_id"],security_state=security_state,provenance={"crawler_policy":POLICY_VERSION,"crawl_run_id":crawl_run_id,"url":url,"status":response.status,"headers_sha256":_sha(dict(response.headers)),"parser_version":source["parser_version"],"transport_kind":transport.transport_kind})
                stored+=1; self._record_fetch(crawl_run_id=crawl_run_id,url=url,response=response,disposition="stored_quarantine" if obj["quarantined"] else "stored_review_pending",object_id=obj["object_id"],depth=depth)
                if text and depth < int(source["max_depth"]) and ctype in {"text/html","application/xhtml+xml"}:
                    parser=_HTMLSignals(); parser.feed(text[:2_000_000])
                    for href in parser.links[:1000]:
                        try: nxt=_clean_url(urljoin(url,htmlmod.unescape(href)))
                        except Exception: continue
                        if (urlsplit(nxt).hostname or "").lower() in set(source["allowed_hosts"]) and nxt not in seen: queue.append((nxt,depth+1))
                self.build348.checkpoint_job(job_id,{"crawl_run_id":crawl_run_id,"seen":len(seen),"pages_fetched":fetched,"pages_stored":stored,"bytes_fetched":total_bytes,"queue":len(queue)},worker_id=worker_id)
            summary={"pages_fetched":fetched,"pages_stored":stored,"bytes_fetched":total_bytes,"errors":errors,"seen_urls":len(seen),"remaining_queue":len(queue),"bounded":True,"transport_kind":transport.transport_kind,"external_transport":bool(transport.externally_configured)}
            self.db.execute("UPDATE phase15_crawl_runs SET status='succeeded',pages_fetched=?,pages_stored=?,bytes_fetched=?,completed_at=?,summary_json=? WHERE crawl_run_id=?", (fetched,stored,total_bytes,_now(),_canon(summary),crawl_run_id))
            self.db.execute("UPDATE phase15_crawler_policies SET source_health=?,updated_at=? WHERE source_id=?", ("healthy" if errors==0 else "degraded",_now(),source["source_id"]))
            return self.build348.complete_job(job_id,summary,worker_id=worker_id)
        except Exception as exc:
            self.db.execute("UPDATE phase15_crawl_runs SET status='failed',completed_at=?,summary_json=? WHERE crawl_run_id=?", (_now(),_canon({"error":f"{type(exc).__name__}:{exc}","pages_fetched":fetched,"pages_stored":stored}),crawl_run_id))
            return self.build348.fail_job(job_id,f"{type(exc).__name__}:{exc}",worker_id=worker_id,retry_delay_seconds=30)

    def run_next(self, *, worker_id: str, transport: CrawlTransport, resolver: Callable[[str], Sequence[str]] | None = None) -> dict[str, Any] | None:
        job=self.build348.claim_job(worker_id=worker_id,lease_seconds=300)
        if not job: return None
        if job["job_type"]!="governed_crawl_v1":
            self.build348.fail_job(job["job_id"],"worker only accepts governed_crawl_v1",worker_id=worker_id,retry_delay_seconds=0)
            return None
        return self.execute_claimed_job(job_id=job["job_id"],worker_id=worker_id,transport=transport,resolver=resolver)

    def runs(self, *, case_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        n=max(1,min(int(limit),500))
        if case_id: return self.db.all("SELECT * FROM phase15_crawl_runs WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id,n))
        return self.db.all("SELECT * FROM phase15_crawl_runs ORDER BY created_at DESC LIMIT ?", (n,))

    def fetches(self, crawl_run_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM phase15_crawl_fetches WHERE crawl_run_id=? ORDER BY created_at ASC LIMIT ?", (crawl_run_id,max(1,min(int(limit),2000))))

    def status(self) -> dict[str, Any]:
        r=self.db.one("SELECT COUNT(*) c,COALESCE(SUM(pages_fetched),0) f,COALESCE(SUM(pages_stored),0) s,COALESCE(SUM(bytes_fetched),0) b FROM phase15_crawl_runs") or {"c":0,"f":0,"s":0,"b":0}
        return {"policy":POLICY_VERSION,"runs":int(r["c"]),"pages_fetched":int(r["f"]),"pages_stored":int(r["s"]),"bytes_fetched":int(r["b"]),"built_in_clearnet_transport":True,"built_in_onion_transport":False,"direct_onion_dns_forbidden":True,"forms_or_writes_supported":False,"credentials_supported":False}
