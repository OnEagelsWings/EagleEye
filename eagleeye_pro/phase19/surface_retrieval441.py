from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit
import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import threading
import time

from eagleeye.crawler.engine import FetchResponse, RobotsRules, USER_AGENT

BUILD = "441.0"
POLICY_ID = "phase19.controlled-surface-retrieval.v441"
CONFIRM = "SURFACE441_LIVE"
SAFE_MEDIA = {
    "text/plain",
    "text/html",
    "text/xml",
    "application/json",
    "application/xml",
    "application/xhtml+xml",
    "application/rss+xml",
    "application/atom+xml",
    "application/pdf",
}
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 3
MAX_BYTES_HARD = 2_000_000
MAX_TIMEOUT_HARD = 30
ROBOTS_MAX_BYTES = 200_000


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value):
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode()
    return hashlib.sha256(raw).hexdigest()


def _clean_url(value):
    parsed = urlsplit(str(value or "").strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("absolute public http(s) URL required")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("userinfo/credentials in URL are forbidden")
    host = parsed.hostname.casefold().rstrip(".")
    if host.endswith(".onion") or host in {"localhost", "localhost.localdomain"}:
        raise ValueError("surface retrieval requires a public non-onion host")
    if parsed.port not in {None, 80, 443}:
        raise ValueError("non-standard target ports are forbidden")
    port = parsed.port
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, ""))


def _media_type(headers):
    value = str(dict(headers or {}).get("content-type", "") or "")
    return value.split(";", 1)[0].strip().casefold() or "application/octet-stream"


def _retry_after(headers):
    raw = str(dict(headers or {}).get("retry-after", "") or "").strip()
    if raw.isdigit():
        return min(int(raw), 86400)
    return None


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, connect_host, *, server_hostname, port=443, timeout=20, context=None):
        super().__init__(connect_host, port=port, timeout=timeout, context=context)
        self._ee_server_hostname = server_hostname

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), self.timeout, self.source_address)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self._ee_server_hostname)


class PinnedSurfaceTransport441:
    """Read-only clearnet transport pinned to a prevalidated public IP.

    No environment proxy, cookies, credentials or write methods are supported.
    DNS is resolved by the caller before transport invocation; the transport connects
    directly to one validated IP while preserving TLS SNI/certificate validation for
    the reviewed hostname.
    """

    transport_kind = "surface441_pinned_stdlib_v1"
    externally_configured = True
    requires_resolved_ips = True

    def __init__(self, *, ca_file=None, user_agent=None):
        self.user_agent = str(user_agent or USER_AGENT).strip()[:300] or USER_AGENT
        self._ssl = ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()

    def fetch(
        self,
        url,
        *,
        resolved_ips,
        method="GET",
        headers=None,
        timeout_seconds=20,
        max_bytes=1_000_000,
    ):
        target = _clean_url(url)
        parsed = urlsplit(target)
        method = str(method or "").upper()
        if method != "GET":
            raise PermissionError("Build 441 surface transport is GET-only")
        timeout = max(1, min(int(timeout_seconds), MAX_TIMEOUT_HARD))
        limit = max(1, min(int(max_bytes), MAX_BYTES_HARD))
        host = parsed.hostname.casefold()
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        request_target = (parsed.path or "/") + (("?" + parsed.query) if parsed.query else "")
        host_header = host
        if parsed.port is not None:
            host_header = f"{host}:{parsed.port}"

        safe_headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,text/plain,application/json,application/xml,application/rss+xml,application/atom+xml,application/pdf;q=0.8,*/*;q=0.2",
            "Accept-Encoding": "identity",
            "Connection": "close",
        }
        forbidden = {
            "authorization",
            "proxy-authorization",
            "cookie",
            "set-cookie",
            "host",
            "origin",
            "referer",
        }
        for key, value in dict(headers or {}).items():
            if str(key).casefold() in forbidden:
                raise PermissionError("credential/session/request-origin headers are forbidden")
            safe_headers[str(key)] = str(value)

        last_error = None
        started = time.monotonic()
        for address in list(resolved_ips or []):
            conn = None
            try:
                if parsed.scheme == "https":
                    conn = _PinnedHTTPSConnection(
                        address,
                        server_hostname=host,
                        port=port,
                        timeout=timeout,
                        context=self._ssl,
                    )
                else:
                    conn = http.client.HTTPConnection(address, port=port, timeout=timeout)

                conn.putrequest("GET", request_target, skip_host=True, skip_accept_encoding=True)
                conn.putheader("Host", host_header)
                for key, value in safe_headers.items():
                    conn.putheader(key, value)
                conn.endheaders()
                response = conn.getresponse()
                body = response.read(limit + 1)
                if len(body) > limit:
                    raise ValueError("response exceeds configured max_bytes")
                response_headers = {str(k).casefold(): str(v) for k, v in response.getheaders()}
                return FetchResponse(
                    target,
                    int(response.status),
                    response_headers,
                    bytes(body),
                    int((time.monotonic() - started) * 1000),
                )
            except Exception as exc:
                last_error = exc
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
        if last_error is not None:
            raise last_error
        raise RuntimeError("no validated public IP available for retrieval")


class ControlledSurfaceRetrieval441:
    """Phase-19 single-task public-surface executor.

    This adapter closes the Build-425 execution gap without creating a general
    browser. It executes one reviewed crawl task at a time, respects robots.txt,
    follows only same-host redirects, pins DNS to validated globally-routable IPs,
    and writes results through Build 425 -> 422/423 provenance intake.
    """

    def __init__(
        self,
        db,
        audit,
        *,
        registry421,
        crawler425,
        health424,
        governance,
        loop439,
        actor="local-analyst",
    ):
        self.db = db
        self.audit = audit
        self.registry421 = registry421
        self.crawler425 = crawler425
        self.health424 = health424
        self.governance = governance
        self.loop439 = loop439
        self.actor = actor
        self._live_lock = threading.Lock()
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS surface_retrieval_run_441(
            run_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            case_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            state TEXT NOT NULL,
            execution_mode TEXT NOT NULL,
            authorization_mode TEXT NOT NULL,
            final_url TEXT NOT NULL,
            http_status INTEGER NOT NULL,
            media_type TEXT NOT NULL,
            bytes_count INTEGER NOT NULL,
            response_sha256 TEXT NOT NULL,
            event_id TEXT NOT NULL,
            content_id TEXT NOT NULL,
            redirect_chain_json TEXT NOT NULL,
            resolved_hosts_json TEXT NOT NULL,
            error_class TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_surface441_case
            ON surface_retrieval_run_441(case_id,created_at);
            CREATE INDEX IF NOT EXISTS idx_surface441_task
            ON surface_retrieval_run_441(task_id,created_at);
            """
        )
        self.db.conn.commit()

    def _rh(self, row):
        return _hash({k: row[k] for k in row if k != "record_hash"})

    def _identity(self, identity):
        if not isinstance(identity, dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("canonical active identity required")
        try:
            user = self.governance.identity.public_user(str(identity["username"]))
        except (KeyError, ValueError):
            raise PermissionError("canonical active identity required")
        if not user.get("active") or str(user.get("user_id")) != str(identity.get("user_id")):
            raise PermissionError("canonical active identity required")
        return {**user, "session_id": str(identity.get("session_id") or "surface441")}

    def _authorize(self, identity, task):
        ident = self._identity(identity)
        self.governance.authorize(
            ident,
            case_id=str(task["case_id"]),
            capability="crawler.run",
            object_type="surface_retrieval_441",
            object_id=str(task["task_id"]),
        )
        return ident

    def _task(self, task_id):
        task = dict(self.crawler425.get(str(task_id)))
        task["scope"] = json.loads(task.get("scope_json") or "{}")
        task["budget"] = json.loads(task.get("budget_json") or "{}")
        return task

    def _source_and_target(self, task, *, live=False):
        source = self.registry421.get(task["source_id"])
        if int(source.get("enabled", 0)) != 1:
            raise PermissionError("source is disabled")
        if source.get("source_type") == "tor_onion" or source.get("access_mode") == "tor_public":
            raise PermissionError("onion sources require the isolated Tor worker")
        if source.get("access_mode") != "public":
            raise PermissionError("Build 441 executes only unauthenticated public sources")
        if live and bool((source.get("coverage") or {}).get("fixture_only")):
            raise PermissionError("synthetic fixture sources cannot be used for live retrieval")

        target = _clean_url(task["target"])
        target_host = urlsplit(target).hostname.casefold()
        base = _clean_url(source["base_url"]) if source.get("base_url") else ""
        if not base:
            raise PermissionError("registered source requires a reviewed base_url")
        base_host = urlsplit(base).hostname.casefold()
        if target_host != base_host:
            raise PermissionError("task target must remain on the exact registered source host")

        allowed = {
            str(x).casefold().rstrip(".")
            for x in (task.get("scope") or {}).get("allowed_hosts", [])
            if str(x).strip()
        }
        if not allowed:
            allowed = {target_host}
        if target_host not in allowed:
            raise PermissionError("task target escaped the approved task host scope")
        return source, target, target_host

    def _resolve_public(self, host, resolver=None):
        if resolver is None:
            infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            values = sorted({str(item[4][0]) for item in infos})
        else:
            values = sorted({str(x) for x in resolver(host)})
        if not values:
            raise PermissionError("target hostname did not resolve")
        parsed = []
        for value in values:
            try:
                address = ipaddress.ip_address(value)
            except ValueError as exc:
                raise PermissionError("resolver returned a non-IP address") from exc
            if not address.is_global:
                raise PermissionError("target resolved to a non-public IP address")
            parsed.append(str(address))
        return parsed

    def _budget(self, task):
        raw = task.get("budget") or {}
        max_bytes = int(raw.get("max_bytes") or 1_000_000)
        max_seconds = int(raw.get("max_seconds") or 20)
        max_pages = int(raw.get("max_pages") or 1)
        if max_pages != 1:
            raise PermissionError("Build 441 executes one-page Phase-19 tasks only")
        if not 1 <= max_bytes <= MAX_BYTES_HARD:
            raise PermissionError("task max_bytes exceeds Build-441 hard limit")
        if not 1 <= max_seconds <= MAX_TIMEOUT_HARD:
            raise PermissionError("task max_seconds exceeds Build-441 hard limit")
        return {"max_pages": 1, "max_bytes": max_bytes, "max_seconds": max_seconds}

    def _transport_fetch(self, transport, url, *, ips, timeout, max_bytes):
        kwargs = {
            "method": "GET",
            "headers": {"User-Agent": USER_AGENT},
            "timeout_seconds": timeout,
            "max_bytes": max_bytes,
        }
        if bool(getattr(transport, "requires_resolved_ips", False)):
            kwargs["resolved_ips"] = ips
        return transport.fetch(url, **kwargs)

    def _preflight_url(self, url, *, expected_host, resolver):
        clean = _clean_url(url)
        host = urlsplit(clean).hostname.casefold()
        if host != expected_host:
            raise PermissionError("redirect escaped the approved exact host")
        ips = self._resolve_public(host, resolver)
        return clean, ips

    def _robots(self, *, transport, target, expected_host, resolver, timeout):
        parsed = urlsplit(target)
        robots_url = urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
        current = robots_url
        chain = []
        for _ in range(MAX_REDIRECTS + 1):
            current, ips = self._preflight_url(current, expected_host=expected_host, resolver=resolver)
            response = self._transport_fetch(
                transport,
                current,
                ips=ips,
                timeout=timeout,
                max_bytes=ROBOTS_MAX_BYTES,
            )
            chain.append(current)
            if int(response.status) in REDIRECT_STATUSES:
                location = str(response.headers.get("location", "") or "").strip()
                if not location:
                    return RobotsRules.fail_closed("robots_redirect_without_location"), chain
                current = urljoin(current, location)
                continue
            if int(response.status) in {404, 410}:
                return RobotsRules(""), chain
            if not 200 <= int(response.status) < 300:
                return RobotsRules.fail_closed(f"robots_http_{int(response.status)}"), chain
            media = _media_type(response.headers)
            if media not in {"text/plain", "text/html"}:
                return RobotsRules.fail_closed("robots_unsafe_media_type"), chain
            text = bytes(response.body or b"").decode("utf-8", errors="replace")[:ROBOTS_MAX_BYTES]
            return RobotsRules(text), chain
        return RobotsRules.fail_closed("robots_redirect_limit"), chain

    def _fetch_target(
        self,
        *,
        transport,
        target,
        expected_host,
        resolver,
        timeout,
        max_bytes,
        robots,
    ):
        current = target
        chain = []
        resolution_log = {}
        for _ in range(MAX_REDIRECTS + 1):
            clean, ips = self._preflight_url(current, expected_host=expected_host, resolver=resolver)
            path = urlsplit(clean).path or "/"
            query = urlsplit(clean).query
            robots_target = path + (("?" + query) if query else "")
            if not robots.allowed(robots_target):
                return {
                    "blocked": True,
                    "reason": "disallowed_by_robots",
                    "final_url": clean,
                    "redirect_chain": chain + [clean],
                    "resolution_log": resolution_log,
                    "response": None,
                }
            resolution_log[clean] = ips
            response = self._transport_fetch(
                transport,
                clean,
                ips=ips,
                timeout=timeout,
                max_bytes=max_bytes,
            )
            chain.append(clean)
            if int(response.status) in REDIRECT_STATUSES:
                location = str(response.headers.get("location", "") or "").strip()
                if not location:
                    return {
                        "blocked": True,
                        "reason": "redirect_without_location",
                        "final_url": clean,
                        "redirect_chain": chain,
                        "resolution_log": resolution_log,
                        "response": response,
                    }
                current = urljoin(clean, location)
                continue
            return {
                "blocked": False,
                "reason": "",
                "final_url": clean,
                "redirect_chain": chain,
                "resolution_log": resolution_log,
                "response": response,
            }
        return {
            "blocked": True,
            "reason": "redirect_limit_exceeded",
            "final_url": chain[-1] if chain else target,
            "redirect_chain": chain,
            "resolution_log": resolution_log,
            "response": None,
        }

    def _record_run(
        self,
        *,
        task,
        identity,
        state,
        execution_mode,
        authorization_mode,
        final_url="",
        http_status=0,
        media_type="",
        bytes_count=0,
        response_sha256="",
        event_id="",
        content_id="",
        redirect_chain=None,
        resolved_hosts=None,
        error_class="",
    ):
        import secrets

        row = {
            "run_id": "surf441_" + secrets.token_hex(10),
            "task_id": task["task_id"],
            "case_id": task["case_id"],
            "source_id": task["source_id"],
            "state": state,
            "execution_mode": execution_mode,
            "authorization_mode": authorization_mode,
            "final_url": str(final_url or ""),
            "http_status": int(http_status or 0),
            "media_type": str(media_type or ""),
            "bytes_count": int(bytes_count or 0),
            "response_sha256": str(response_sha256 or ""),
            "event_id": str(event_id or ""),
            "content_id": str(content_id or ""),
            "redirect_chain_json": _canon(redirect_chain or []),
            "resolved_hosts_json": _canon(resolved_hosts or {}),
            "error_class": str(error_class or "")[:300],
            "created_by": str(identity["username"]),
            "created_at": _now(),
            "completed_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO surface_retrieval_run_441 VALUES("
            + ",".join("?" for _ in row)
            + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "surface_retrieval_run_441",
            "surface_retrieval_run_441",
            row["run_id"],
            task["case_id"],
            {
                "task_id": task["task_id"],
                "state": state,
                "execution_mode": execution_mode,
                "authorization_mode": authorization_mode,
                "network_execution": execution_mode == "live_pinned_public_get",
            },
        )
        return self.run(row["run_id"])

    def _accept_terminal(
        self,
        *,
        ident,
        task,
        status,
        response=None,
        provenance=None,
        usage=None,
        content=None,
        media_type="application/octet-stream",
    ):
        return self.crawler425.accept_retrieval(
            identity=ident,
            task_id=task["task_id"],
            status=status,
            content=content,
            media_type=media_type,
            provenance=provenance or {},
            usage=usage or {},
        )

    def _execute(
        self,
        *,
        identity,
        task_id,
        transport,
        resolver=None,
        execution_mode,
        authorization_mode,
        live=False,
    ):
        task = self._task(task_id)
        ident = self._authorize(identity, task)
        if task["state"] != "planned":
            raise ValueError("surface crawl task must be in planned state")
        source, target, host = self._source_and_target(task, live=live)
        budget = self._budget(task)

        advice = self.health424.acquisition_advice(task["source_id"])
        if advice["decision"] in {"avoid", "defer"}:
            raise PermissionError("source health currently blocks live execution")

        try:
            robots, robots_chain = self._robots(
                transport=transport,
                target=target,
                expected_host=host,
                resolver=resolver,
                timeout=min(10, budget["max_seconds"]),
            )
            if robots.fail_closed_state:
                accepted = self._accept_terminal(
                    ident=ident,
                    task=task,
                    status="blocked",
                    provenance={
                        "build": BUILD,
                        "reason": "robots_fail_closed",
                        "robots_failure_reason": robots.failure_reason,
                        "robots_chain": robots_chain,
                        "execution_mode": execution_mode,
                    },
                    usage={
                        "robots_respected": True,
                        "fail_closed": True,
                        "no_auth": True,
                        "no_cookies": True,
                        "no_forms": True,
                        "no_writes": True,
                        "no_js": True,
                    },
                )
                return {
                    "run": self._record_run(
                        task=task,
                        identity=ident,
                        state="blocked",
                        execution_mode=execution_mode,
                        authorization_mode=authorization_mode,
                        final_url=target,
                        event_id=accepted["event_id"],
                        error_class="robots_fail_closed",
                    ),
                    "accepted": accepted,
                }

            outcome = self._fetch_target(
                transport=transport,
                target=target,
                expected_host=host,
                resolver=resolver,
                timeout=budget["max_seconds"],
                max_bytes=budget["max_bytes"],
                robots=robots,
            )

            if outcome["blocked"]:
                accepted = self._accept_terminal(
                    ident=ident,
                    task=task,
                    status="blocked",
                    response=outcome.get("response"),
                    provenance={
                        "build": BUILD,
                        "reason": outcome["reason"],
                        "final_url": outcome["final_url"],
                        "redirect_chain": outcome["redirect_chain"],
                        "dns_public_validated": True,
                        "execution_mode": execution_mode,
                    },
                    usage={
                        "robots_respected": True,
                        "same_host_redirects_only": True,
                        "budget_enforced": True,
                        "no_auth": True,
                        "no_cookies": True,
                        "no_forms": True,
                        "no_writes": True,
                        "no_js": True,
                    },
                )
                return {
                    "run": self._record_run(
                        task=task,
                        identity=ident,
                        state="blocked",
                        execution_mode=execution_mode,
                        authorization_mode=authorization_mode,
                        final_url=outcome["final_url"],
                        http_status=int(getattr(outcome.get("response"), "status", 0) or 0),
                        event_id=accepted["event_id"],
                        redirect_chain=outcome["redirect_chain"],
                        resolved_hosts=outcome["resolution_log"],
                        error_class=outcome["reason"],
                    ),
                    "accepted": accepted,
                }

            response = outcome["response"]
            status = int(response.status)
            body = bytes(response.body or b"")
            media = _media_type(response.headers)
            digest = _hash(body) if body else ""

            if len(body) > budget["max_bytes"]:
                raise ValueError("response exceeds configured max_bytes")

            if status < 200 or status >= 300:
                state = "rate_limited" if status == 429 else ("unavailable" if status >= 500 else "degraded")
                self.health424.record(
                    identity=ident,
                    source_id=task["source_id"],
                    state=state,
                    http_status=status,
                    latency_ms=int(response.elapsed_ms or 0),
                    retry_after_seconds=_retry_after(response.headers),
                    error_class=f"http_{status}",
                    metadata={"build": BUILD, "task_id": task["task_id"]},
                )
                accepted = self._accept_terminal(
                    ident=ident,
                    task=task,
                    status="failed",
                    provenance={
                        "build": BUILD,
                        "http_status": status,
                        "final_url": outcome["final_url"],
                        "redirect_chain": outcome["redirect_chain"],
                        "execution_mode": execution_mode,
                    },
                    usage={
                        "robots_respected": True,
                        "same_host_redirects_only": True,
                        "no_auth": True,
                        "no_cookies": True,
                        "no_forms": True,
                        "no_writes": True,
                        "no_js": True,
                    },
                )
                return {
                    "run": self._record_run(
                        task=task,
                        identity=ident,
                        state="failed",
                        execution_mode=execution_mode,
                        authorization_mode=authorization_mode,
                        final_url=outcome["final_url"],
                        http_status=status,
                        media_type=media,
                        bytes_count=len(body),
                        response_sha256=digest,
                        event_id=accepted["event_id"],
                        redirect_chain=outcome["redirect_chain"],
                        resolved_hosts=outcome["resolution_log"],
                        error_class=f"http_{status}",
                    ),
                    "accepted": accepted,
                }

            if media not in SAFE_MEDIA:
                accepted = self._accept_terminal(
                    ident=ident,
                    task=task,
                    status="blocked",
                    provenance={
                        "build": BUILD,
                        "reason": "unsafe_media_type",
                        "http_status": status,
                        "final_url": outcome["final_url"],
                        "media_type": media,
                        "execution_mode": execution_mode,
                    },
                    usage={
                        "downloads_blocked": True,
                        "robots_respected": True,
                        "no_auth": True,
                        "no_cookies": True,
                        "no_forms": True,
                        "no_writes": True,
                        "no_js": True,
                    },
                )
                return {
                    "run": self._record_run(
                        task=task,
                        identity=ident,
                        state="blocked",
                        execution_mode=execution_mode,
                        authorization_mode=authorization_mode,
                        final_url=outcome["final_url"],
                        http_status=status,
                        media_type=media,
                        bytes_count=len(body),
                        response_sha256=digest,
                        event_id=accepted["event_id"],
                        redirect_chain=outcome["redirect_chain"],
                        resolved_hosts=outcome["resolution_log"],
                        error_class="unsafe_media_type",
                    ),
                    "accepted": accepted,
                }

            accepted = self._accept_terminal(
                ident=ident,
                task=task,
                status="retrieved",
                content=body,
                media_type=media,
                provenance={
                    "build": BUILD,
                    "http_status": status,
                    "final_url": outcome["final_url"],
                    "redirect_chain": outcome["redirect_chain"],
                    "resolved_host_fingerprint": _hash(outcome["resolution_log"]),
                    "dns_public_validated": True,
                    "tls_validation": urlsplit(outcome["final_url"]).scheme == "https",
                    "execution_mode": execution_mode,
                    "transport_kind": str(getattr(transport, "transport_kind", type(transport).__name__)),
                },
                usage={
                    "public_only": True,
                    "robots_respected": True,
                    "same_host_redirects_only": True,
                    "dns_ip_pinned": bool(getattr(transport, "requires_resolved_ips", False)),
                    "budget_enforced": True,
                    "no_auth": True,
                    "no_cookies": True,
                    "no_forms": True,
                    "no_writes": True,
                    "no_js": True,
                    "no_scope_expansion": True,
                },
            )
            self.health424.record(
                identity=ident,
                source_id=task["source_id"],
                state="healthy",
                http_status=status,
                latency_ms=int(response.elapsed_ms or 0),
                freshness_at=_now(),
                metadata={"build": BUILD, "task_id": task["task_id"]},
            )
            content_id = ""
            if accepted.get("content"):
                content_id = accepted["content"].get("content_id", "")
            run = self._record_run(
                task=task,
                identity=ident,
                state="completed",
                execution_mode=execution_mode,
                authorization_mode=authorization_mode,
                final_url=outcome["final_url"],
                http_status=status,
                media_type=media,
                bytes_count=len(body),
                response_sha256=digest,
                event_id=accepted["event_id"],
                content_id=content_id,
                redirect_chain=outcome["redirect_chain"],
                resolved_hosts=outcome["resolution_log"],
            )
            return {"run": run, "accepted": accepted}
        except Exception as exc:
            current = self._task(task_id)
            if current["state"] in {"planned", "deferred"}:
                try:
                    accepted = self._accept_terminal(
                        ident=ident,
                        task=current,
                        status="failed",
                        provenance={
                            "build": BUILD,
                            "error_class": type(exc).__name__,
                            "execution_mode": execution_mode,
                        },
                        usage={
                            "fail_closed": True,
                            "no_auth": True,
                            "no_cookies": True,
                            "no_forms": True,
                            "no_writes": True,
                            "no_js": True,
                        },
                    )
                    event_id = accepted["event_id"]
                except Exception:
                    event_id = ""
            else:
                event_id = ""
            try:
                self.health424.record(
                    identity=ident,
                    source_id=task["source_id"],
                    state="degraded",
                    error_class=type(exc).__name__,
                    metadata={"build": BUILD, "task_id": task["task_id"]},
                )
            except Exception:
                pass
            self._record_run(
                task=task,
                identity=ident,
                state="failed",
                execution_mode=execution_mode,
                authorization_mode=authorization_mode,
                final_url=target,
                event_id=event_id,
                error_class=type(exc).__name__,
            )
            raise RuntimeError("controlled surface retrieval failed: " + type(exc).__name__) from exc

    def execute_replay(self, *, identity, task_id, transport, resolver):
        return self._execute(
            identity=identity,
            task_id=task_id,
            transport=transport,
            resolver=resolver,
            execution_mode="deterministic_replay",
            authorization_mode="test_replay",
            live=False,
        )

    def execute_live(self, *, identity, task_id, confirmation):
        task = self._task(task_id)
        self._authorize(identity, task)
        if str(confirmation or "").strip().upper() != CONFIRM:
            raise PermissionError(f"explicit {CONFIRM} confirmation required")
        if not self._live_lock.acquire(blocking=False):
            raise RuntimeError("controlled surface retrieval worker is busy")
        try:
            return self._execute(
                identity=identity,
                task_id=task_id,
                transport=PinnedSurfaceTransport441(),
                resolver=None,
                execution_mode="live_pinned_public_get",
                authorization_mode="explicit_task_confirmation",
                live=True,
            )
        finally:
            self._live_lock.release()

    def execute_authorized_loop_task(self, *, identity, task_id):
        task = self._task(task_id)
        ident = self._authorize(identity, task)
        loop_id = str((task.get("scope") or {}).get("build439_loop_id") or "").strip()
        if not loop_id:
            raise PermissionError("task is not bound to a Build-439 investigation loop")
        loop = self.loop439.loop(loop_id)
        if loop["case_id"] != task["case_id"]:
            raise PermissionError("Build-439 loop/task case mismatch")
        if loop["state"] != "active":
            raise PermissionError("Build-439 loop is not actively authorized")
        if task["source_id"] not in set(loop["scope"].get("allowed_source_ids") or []):
            raise PermissionError("task source is outside the authorized Build-439 loop scope")
        if not self._live_lock.acquire(blocking=False):
            raise RuntimeError("controlled surface retrieval worker is busy")
        try:
            return self._execute(
                identity=ident,
                task_id=task_id,
                transport=PinnedSurfaceTransport441(),
                resolver=None,
                execution_mode="live_pinned_public_get",
                authorization_mode="authorized_build439_loop",
                live=True,
            )
        finally:
            self._live_lock.release()

    def run(self, run_id):
        row = self.db.one("SELECT * FROM surface_retrieval_run_441 WHERE run_id=?", (str(run_id),))
        if not row:
            raise KeyError("surface retrieval run not found")
        out = dict(row)
        out["redirect_chain"] = json.loads(out.pop("redirect_chain_json"))
        out["resolved_hosts"] = json.loads(out.pop("resolved_hosts_json"))
        return out

    def case_runs(self, case_id):
        return [
            self.run(r["run_id"])
            for r in self.db.all(
                "SELECT run_id FROM surface_retrieval_run_441 WHERE case_id=? ORDER BY created_at,run_id",
                (str(case_id),),
            )
        ]

    def verify_integrity(self):
        bad = []
        for row in self.db.all("SELECT * FROM surface_retrieval_run_441"):
            item = dict(row)
            if self._rh(item) != item.get("record_hash"):
                bad.append({"run_id": item.get("run_id"), "reason": "run_hash_mismatch"})
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        count = int(self.db.one("SELECT COUNT(*) n FROM surface_retrieval_run_441")["n"])
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "runs": count,
            "integrity_valid": self.verify_integrity()["valid"],
            "controlled_surface_network_executor": True,
            "live_public_http_get": True,
            "single_page_tasks_only": True,
            "robots_required_fail_closed": True,
            "dns_public_validation": True,
            "dns_ip_pinning": True,
            "exact_registered_host_only": True,
            "same_host_redirects_only": True,
            "max_redirects": MAX_REDIRECTS,
            "max_response_bytes": MAX_BYTES_HARD,
            "max_timeout_seconds": MAX_TIMEOUT_HARD,
            "public_access_mode_only": True,
            "authenticated_sources_supported": False,
            "cookies_supported": False,
            "forms_supported": False,
            "write_methods_supported": False,
            "javascript_execution": False,
            "environment_proxy_use": False,
            "onion_execution": False,
            "fixture_live_execution": False,
            "explicit_task_confirmation_supported": True,
            "authorized_build439_loop_execution_supported": True,
            "autonomous_scope_expansion": False,
            "access_control_bypass": False,
            "truth_determined": False,
            "production_release_ready": False,
        }
