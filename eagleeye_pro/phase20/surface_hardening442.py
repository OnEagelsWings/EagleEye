from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import secrets
import socket
import ssl
import threading
import time

from eagleeye_pro.phase20.retrieval_isolation451 import ProcessSurfaceTransport451

BUILD = "442.0"
POLICY_ID = "phase20.surface-hardening-validation.v442"
LIVE_CONFIRM = "SURFACE442_LIVE"
EXTERNAL_VALIDATE_CONFIRM = "VALIDATE442_EXTERNAL"
MAX_ATTEMPTS = 3
BASE_BACKOFF_SECONDS = 0.5
MAX_SOURCE_TASKS_PER_MINUTE = 6
MIN_SOURCE_INTERVAL_SECONDS = 1.0
TRANSIENT_HTTP = {408, 425, 429, 500, 502, 503, 504}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value):
    return hashlib.sha256(_canon(value).encode()).hexdigest()


class StablePublicResolver442:
    """Task-scoped public DNS resolver with pinning and rebind detection.

    The first lookup establishes the pinned IP set used for every connection in
    the task. Later lookups are observed for safety, but the connection remains
    pinned to the original set. A later non-public answer fails closed before
    the next fetch.
    """

    def __init__(self, resolver):
        self.resolver = resolver
        self.pinned = {}
        self.lookups = {}
        self.public_set_changes = []
        self.rebind_violations = []

    def _lookup(self, host):
        values = sorted({str(x) for x in self.resolver(host)})
        if not values:
            raise PermissionError("target hostname did not resolve")
        parsed = []
        for value in values:
            try:
                address = ipaddress.ip_address(value)
            except ValueError as exc:
                raise PermissionError("resolver returned a non-IP address") from exc
            if not address.is_global:
                self.rebind_violations.append(
                    {"host": host, "address": value, "reason": "non_public_dns_answer"}
                )
                raise PermissionError("DNS rebind/non-public address detected")
            parsed.append(str(address))
        return tuple(parsed)

    def __call__(self, host):
        host = str(host).casefold().rstrip(".")
        current = self._lookup(host)
        self.lookups.setdefault(host, []).append(list(current))
        if host not in self.pinned:
            self.pinned[host] = current
            return list(current)

        original = self.pinned[host]
        if current != original:
            self.public_set_changes.append(
                {
                    "host": host,
                    "pinned": list(original),
                    "observed": list(current),
                }
            )
        return list(original)

    def report(self):
        return {
            "pinned": {k: list(v) for k, v in self.pinned.items()},
            "lookups": self.lookups,
            "public_set_changes": self.public_set_changes,
            "rebind_violations": self.rebind_violations,
            "pinning_active": True,
            "non_public_rebind_fail_closed": True,
        }


class RetryingTransport442:
    """Transport decorator with bounded retry/backoff and attempt telemetry."""

    transport_kind = "surface442_retry_wrapper"
    externally_configured = True

    def __init__(
        self,
        inner,
        *,
        recorder,
        sleeper,
        max_attempts=MAX_ATTEMPTS,
        base_backoff=BASE_BACKOFF_SECONDS,
    ):
        self.inner = inner
        self.recorder = recorder
        self.sleeper = sleeper
        self.max_attempts = max(1, min(int(max_attempts), MAX_ATTEMPTS))
        self.base_backoff = max(0.0, float(base_backoff))
        self.requires_resolved_ips = bool(getattr(inner, "requires_resolved_ips", False))
        self.attempts = 0

    @property
    def security_report(self):
        return getattr(self.inner, "security_report", {})

    @property
    def _inner_kind(self):
        return str(getattr(self.inner, "transport_kind", type(self.inner).__name__))

    def _transient_exception(self, exc):
        if isinstance(exc, ssl.SSLCertVerificationError):
            return False
        return isinstance(exc, (TimeoutError, socket.timeout, ConnectionError, OSError))

    def fetch(self, url, **kwargs):
        last_exc = None
        for attempt in range(1, self.max_attempts + 1):
            self.attempts += 1
            started = time.monotonic()
            try:
                response = self.inner.fetch(url, **kwargs)
                status = int(getattr(response, "status", 0) or 0)
                transient = status in TRANSIENT_HTTP
                delay = 0.0
                if transient and attempt < self.max_attempts:
                    delay = self.base_backoff * (2 ** (attempt - 1))
                self.recorder(
                    attempt=attempt,
                    url=str(url),
                    transport=self._inner_kind,
                    http_status=status,
                    error_class="",
                    transient=transient,
                    delay_seconds=delay,
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                )
                if transient and attempt < self.max_attempts:
                    self.sleeper(delay)
                    continue
                return response
            except Exception as exc:
                last_exc = exc
                transient = self._transient_exception(exc)
                delay = 0.0
                if transient and attempt < self.max_attempts:
                    delay = self.base_backoff * (2 ** (attempt - 1))
                self.recorder(
                    attempt=attempt,
                    url=str(url),
                    transport=self._inner_kind,
                    http_status=0,
                    error_class=type(exc).__name__,
                    transient=transient,
                    delay_seconds=delay,
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                )
                if transient and attempt < self.max_attempts:
                    self.sleeper(delay)
                    continue
                raise
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("retry transport exhausted without response")


class SurfaceRetrievalHardening442:
    def __init__(
        self,
        db,
        audit,
        *,
        surface441,
        registry421,
        crawler425,
        health424,
        governance,
        loop439,
        actor="local-analyst",
        clock=None,
        sleeper=None,
    ):
        self.db = db
        self.audit = audit
        self.surface441 = surface441
        self.registry421 = registry421
        self.crawler425 = crawler425
        self.health424 = health424
        self.governance = governance
        self.loop439 = loop439
        self.actor = actor
        self.clock = clock or time.time
        self.sleep = sleeper or time.sleep
        self._source_locks = {}
        self._source_locks_guard = threading.Lock()
        self._live_worker_lock = threading.Lock()
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS surface_hardening_run_442(
            hardening_run_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            case_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            state TEXT NOT NULL,
            execution_mode TEXT NOT NULL,
            authorization_mode TEXT NOT NULL,
            worker_id TEXT NOT NULL,
            rate_snapshot_json TEXT NOT NULL,
            dns_report_json TEXT NOT NULL,
            attempt_count INTEGER NOT NULL,
            surface441_run_id TEXT NOT NULL,
            external_validation INTEGER NOT NULL,
            error_class TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_surface442_case
            ON surface_hardening_run_442(case_id,created_at);
            CREATE INDEX IF NOT EXISTS idx_surface442_source
            ON surface_hardening_run_442(source_id,created_at);

            CREATE TABLE IF NOT EXISTS surface_failure_telemetry_442(
            telemetry_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            case_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            attempt INTEGER NOT NULL,
            url TEXT NOT NULL,
            transport TEXT NOT NULL,
            http_status INTEGER NOT NULL,
            error_class TEXT NOT NULL,
            transient INTEGER NOT NULL,
            backoff_ms INTEGER NOT NULL,
            elapsed_ms INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_surface442_telemetry_task
            ON surface_failure_telemetry_442(task_id,created_at);

            CREATE TABLE IF NOT EXISTS surface_rate_window_442(
            rate_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            started_epoch REAL NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_surface442_rate_source
            ON surface_rate_window_442(source_id,started_epoch);
            """
        )
        self.db.conn.commit()

    def _rh(self, row):
        return _sha({k: row[k] for k in row if k != "record_hash"})

    def _identity(self, identity):
        return self.surface441._identity(identity)

    def _task(self, task_id):
        return self.surface441._task(task_id)

    def _source_lock(self, source_id):
        with self._source_locks_guard:
            if source_id not in self._source_locks:
                self._source_locks[source_id] = threading.Lock()
            return self._source_locks[source_id]

    def _rate_gate(self, source_id, task_id):
        now = float(self.clock())
        window_start = now - 60.0
        rows = self.db.all(
            "SELECT started_epoch FROM surface_rate_window_442 "
            "WHERE source_id=? AND started_epoch>=? ORDER BY started_epoch DESC",
            (str(source_id), window_start),
        )
        recent = [float(r["started_epoch"]) for r in rows]
        if len(recent) >= MAX_SOURCE_TASKS_PER_MINUTE:
            retry_after = max(1.0, 60.0 - (now - min(recent)))
            raise PermissionError(
                f"Build 442 source rate limit reached; retry after {int(retry_after)} seconds"
            )
        if recent and now - recent[0] < MIN_SOURCE_INTERVAL_SECONDS:
            retry_after = MIN_SOURCE_INTERVAL_SECONDS - (now - recent[0])
            raise PermissionError(
                f"Build 442 minimum source interval active; retry after {retry_after:.2f} seconds"
            )

        row = {
            "rate_id": "rate442_" + secrets.token_hex(8),
            "source_id": str(source_id),
            "task_id": str(task_id),
            "started_epoch": now,
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO surface_rate_window_442 VALUES(?,?,?,?,?,?)",
            tuple(row.values()),
        )
        return {
            "source_id": str(source_id),
            "window_seconds": 60,
            "max_tasks": MAX_SOURCE_TASKS_PER_MINUTE,
            "minimum_interval_seconds": MIN_SOURCE_INTERVAL_SECONDS,
            "prior_tasks_in_window": len(recent),
            "started_epoch": now,
        }

    def _record_attempt(
        self,
        *,
        task,
        attempt,
        url,
        transport,
        http_status,
        error_class,
        transient,
        delay_seconds,
        elapsed_ms,
    ):
        row = {
            "telemetry_id": "tel442_" + secrets.token_hex(8),
            "task_id": task["task_id"],
            "case_id": task["case_id"],
            "source_id": task["source_id"],
            "attempt": int(attempt),
            "url": str(url),
            "transport": str(transport)[:200],
            "http_status": int(http_status or 0),
            "error_class": str(error_class or "")[:200],
            "transient": 1 if transient else 0,
            "backoff_ms": int(max(0.0, float(delay_seconds)) * 1000),
            "elapsed_ms": max(0, int(elapsed_ms or 0)),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO surface_failure_telemetry_442 VALUES("
            + ",".join("?" for _ in row)
            + ")",
            tuple(row.values()),
        )
        return row

    def _record_run(
        self,
        *,
        task,
        identity,
        state,
        execution_mode,
        authorization_mode,
        worker_id,
        rate_snapshot,
        dns_report,
        attempt_count,
        surface441_run_id="",
        external_validation=False,
        error_class="",
    ):
        row = {
            "hardening_run_id": "hard442_" + secrets.token_hex(10),
            "task_id": task["task_id"],
            "case_id": task["case_id"],
            "source_id": task["source_id"],
            "state": str(state),
            "execution_mode": str(execution_mode),
            "authorization_mode": str(authorization_mode),
            "worker_id": str(worker_id),
            "rate_snapshot_json": _canon(rate_snapshot or {}),
            "dns_report_json": _canon(dns_report or {}),
            "attempt_count": int(attempt_count or 0),
            "surface441_run_id": str(surface441_run_id or ""),
            "external_validation": 1 if external_validation else 0,
            "error_class": str(error_class or "")[:200],
            "created_by": str(identity["username"]),
            "created_at": _now(),
            "completed_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO surface_hardening_run_442 VALUES("
            + ",".join("?" for _ in row)
            + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "surface_hardening_run_442",
            "surface_hardening_run_442",
            row["hardening_run_id"],
            task["case_id"],
            {
                "task_id": task["task_id"],
                "state": state,
                "attempt_count": row["attempt_count"],
                "external_validation": bool(external_validation),
            },
        )
        return self.run(row["hardening_run_id"])

    def _default_resolver(self, host):
        infos = socket.getaddrinfo(str(host), None, type=socket.SOCK_STREAM)
        return sorted({str(item[4][0]) for item in infos})

    def _execute_hardened(
        self,
        *,
        identity,
        task_id,
        transport,
        resolver,
        execution_mode,
        authorization_mode,
        live,
        external_validation=False,
    ):
        task = self._task(task_id)
        ident = self.surface441._authorize(identity, task)
        if task["state"] != "planned":
            raise ValueError("surface crawl task must be planned")
        source, _target, _host = self.surface441._source_and_target(task, live=live)
        if source["access_mode"] != "public":
            raise PermissionError("Build 442 hardening supports public sources only")

        rate_snapshot = self._rate_gate(task["source_id"], task["task_id"])
        worker_id = "surface442_" + secrets.token_hex(8)
        source_lock = self._source_lock(task["source_id"])
        if not source_lock.acquire(blocking=False):
            raise RuntimeError("source-scoped Build 442 worker is busy")

        stable = StablePublicResolver442(resolver)
        wrapped = RetryingTransport442(
            transport,
            recorder=lambda **kw: self._record_attempt(task=task, **kw),
            sleeper=self.sleep,
        )
        try:
            result = self.surface441._execute(
                identity=ident,
                task_id=task_id,
                transport=wrapped,
                resolver=stable,
                execution_mode=execution_mode,
                authorization_mode=authorization_mode,
                live=live,
            )
            surface_run = result.get("run") or {}
            hard = self._record_run(
                task=task,
                identity=ident,
                state=str(surface_run.get("state") or "completed"),
                execution_mode=execution_mode,
                authorization_mode=authorization_mode,
                worker_id=worker_id,
                rate_snapshot=rate_snapshot,
                dns_report=stable.report(),
                attempt_count=wrapped.attempts,
                surface441_run_id=str(surface_run.get("run_id") or ""),
                external_validation=external_validation,
            )
            return {**result, "hardening": hard}
        except Exception as exc:
            self._record_run(
                task=task,
                identity=ident,
                state="failed",
                execution_mode=execution_mode,
                authorization_mode=authorization_mode,
                worker_id=worker_id,
                rate_snapshot=rate_snapshot,
                dns_report=stable.report(),
                attempt_count=wrapped.attempts,
                external_validation=external_validation,
                error_class=type(exc).__name__,
            )
            raise
        finally:
            source_lock.release()

    def execute_replay(self, *, identity, task_id, transport, resolver):
        return self._execute_hardened(
            identity=identity,
            task_id=task_id,
            transport=transport,
            resolver=resolver,
            execution_mode="deterministic_hardened_replay",
            authorization_mode="test_replay",
            live=False,
        )

    def execute_live(self, *, identity, task_id, confirmation):
        task = self._task(task_id)
        self.surface441._authorize(identity, task)
        if str(confirmation or "").strip().upper() != LIVE_CONFIRM:
            raise PermissionError(f"explicit {LIVE_CONFIRM} confirmation required")
        if not self._live_worker_lock.acquire(blocking=False):
            raise RuntimeError("Build 442 live worker is busy")
        try:
            return self._execute_hardened(
                identity=identity,
                task_id=task_id,
                transport=ProcessSurfaceTransport451(),
                resolver=self._default_resolver,
                execution_mode="live_hardened_pinned_public_get",
                authorization_mode="explicit_task_confirmation",
                live=True,
            )
        finally:
            self._live_worker_lock.release()

    def execute_authorized_loop_task(self, *, identity, task_id):
        task = self._task(task_id)
        ident = self.surface441._authorize(identity, task)
        loop_id = str((task.get("scope") or {}).get("build439_loop_id") or "").strip()
        if not loop_id:
            raise PermissionError("task is not bound to a Build-439 investigation loop")
        loop = self.loop439.loop(loop_id)
        if loop["case_id"] != task["case_id"]:
            raise PermissionError("Build-439 loop/task case mismatch")
        if loop["state"] != "active":
            raise PermissionError("Build-439 loop is not actively authorized")
        if task["source_id"] not in set(loop["scope"].get("allowed_source_ids") or []):
            raise PermissionError("task source is outside authorized Build-439 scope")
        if not self._live_worker_lock.acquire(blocking=False):
            raise RuntimeError("Build 442 live worker is busy")
        try:
            return self._execute_hardened(
                identity=ident,
                task_id=task_id,
                transport=ProcessSurfaceTransport451(),
                resolver=self._default_resolver,
                execution_mode="live_hardened_pinned_public_get",
                authorization_mode="authorized_build439_loop",
                live=True,
            )
        finally:
            self._live_worker_lock.release()

    def validate_external_task(self, *, identity, task_id, confirmation):
        if str(confirmation or "").strip().upper() != EXTERNAL_VALIDATE_CONFIRM:
            raise PermissionError(
                f"explicit {EXTERNAL_VALIDATE_CONFIRM} confirmation required"
            )
        task = self._task(task_id)
        self.surface441._authorize(identity, task)
        source = self.registry421.get(task["source_id"])
        if bool((source.get("coverage") or {}).get("fixture_only")):
            raise PermissionError("external validation cannot use synthetic fixture sources")
        if not self._live_worker_lock.acquire(blocking=False):
            raise RuntimeError("Build 442 live worker is busy")
        try:
            result = self._execute_hardened(
                identity=identity,
                task_id=task_id,
                transport=ProcessSurfaceTransport451(),
                resolver=self._default_resolver,
                execution_mode="external_validation_public_get",
                authorization_mode="explicit_external_validation",
                live=True,
                external_validation=True,
            )
            hard = result["hardening"]
            return {
                "build": BUILD,
                "task_id": task_id,
                "case_id": task["case_id"],
                "result": "PASS" if hard["state"] == "completed" else "HOLD",
                "hardening": hard,
                "surface": result.get("run"),
                "external_network_contacted": True,
                "scope": "one reviewed public Build-425 task",
                "production_release_ready": False,
            }
        finally:
            self._live_worker_lock.release()

    def run_case_selftest(self, *, identity, case_id):
        from eagleeye.crawler.engine import FetchResponse

        ident = self._identity(identity)
        self.governance.authorize(
            ident,
            case_id=str(case_id),
            capability="crawler.run",
            object_type="surface_hardening_442",
            object_id=str(case_id),
        )
        token = secrets.token_hex(5)
        base = f"https://surface442-{token}.example.org/"
        source = self.registry421.register(
            identity=ident,
            name="Build 442 Synthetic Surface Fixture " + token,
            source_type="website",
            access_mode="public",
            base_url=base,
            capabilities=["public_pages", "case_fixture"],
            coverage={"fixture_only": True, "live_execution_forbidden": True},
            license_note="Synthetic Build 442 hardening replay source.",
        )
        target = base + "page"
        task = self.crawler425.create_task(
            identity=ident,
            case_id=str(case_id),
            source_id=source["source_id"],
            target=target,
            objective="Build 442 deterministic hardening qualification",
            scope={"allowed_hosts": [f"surface442-{token}.example.org"]},
            budget={"max_pages": 1, "max_bytes": 100000, "max_seconds": 5},
        )
        robots_url = base + "robots.txt"

        class SequenceTransport:
            transport_kind = "surface442_sequence_replay"
            externally_configured = False
            requires_resolved_ips = False

            def __init__(self):
                self.calls = []
                self.target_attempt = 0

            def fetch(self, url, **kwargs):
                self.calls.append(str(url))
                if str(url) == robots_url:
                    return FetchResponse(
                        robots_url,
                        200,
                        {"content-type": "text/plain"},
                        b"User-agent: *\nAllow: /\n",
                        1,
                    )
                if str(url) == target:
                    self.target_attempt += 1
                    if self.target_attempt == 1:
                        return FetchResponse(
                            target,
                            503,
                            {"content-type": "text/plain"},
                            b"temporary",
                            2,
                        )
                    return FetchResponse(
                        target,
                        200,
                        {"content-type": "text/plain"},
                        ("Build 442 retry success " + token).encode(),
                        2,
                    )
                raise KeyError(str(url))

        transport = SequenceTransport()
        old_sleep = self.sleep
        self.sleep = lambda _seconds: None
        try:
            result = self.execute_replay(
                identity=ident,
                task_id=task["task_id"],
                transport=transport,
                resolver=lambda _host: ["93.184.216.34"],
            )
        finally:
            self.sleep = old_sleep

        telemetry = self.task_telemetry(task["task_id"])
        checks = {
            "surface_completed": result["run"]["state"] == "completed",
            "hardening_completed": result["hardening"]["state"] == "completed",
            "retry_happened": transport.target_attempt == 2,
            "transient_503_recorded": any(
                int(x["http_status"]) == 503 and bool(x["transient"]) for x in telemetry
            ),
            "backoff_recorded": any(int(x["backoff_ms"]) > 0 for x in telemetry),
            "dns_pin_recorded": bool(result["hardening"]["dns_report"]["pinned"]),
            "no_rebind_violation": not result["hardening"]["dns_report"]["rebind_violations"],
            "deterministic_no_network": result["hardening"]["execution_mode"]
            == "deterministic_hardened_replay",
            "integrity_valid": self.verify_integrity()["valid"],
        }
        return {
            "build": BUILD,
            "case_id": str(case_id),
            "result": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "task_id": task["task_id"],
            "hardening": result["hardening"],
            "telemetry": telemetry,
            "note": "Synthetic replay validates retry, backoff, telemetry and DNS pinning without external sockets.",
        }

    def run(self, hardening_run_id):
        row = self.db.one(
            "SELECT * FROM surface_hardening_run_442 WHERE hardening_run_id=?",
            (str(hardening_run_id),),
        )
        if not row:
            raise KeyError("Build-442 hardening run not found")
        out = dict(row)
        out["rate_snapshot"] = json.loads(out.pop("rate_snapshot_json"))
        out["dns_report"] = json.loads(out.pop("dns_report_json"))
        out["external_validation"] = bool(out["external_validation"])
        return out

    def case_runs(self, case_id):
        return [
            self.run(r["hardening_run_id"])
            for r in self.db.all(
                "SELECT hardening_run_id FROM surface_hardening_run_442 "
                "WHERE case_id=? ORDER BY created_at,hardening_run_id",
                (str(case_id),),
            )
        ]

    def task_telemetry(self, task_id):
        return [
            dict(r)
            for r in self.db.all(
                "SELECT * FROM surface_failure_telemetry_442 "
                "WHERE task_id=? ORDER BY created_at,telemetry_id",
                (str(task_id),),
            )
        ]

    def verify_integrity(self):
        bad = []
        for table, key in (
            ("surface_hardening_run_442", "hardening_run_id"),
            ("surface_failure_telemetry_442", "telemetry_id"),
            ("surface_rate_window_442", "rate_id"),
        ):
            for row in self.db.all(f"SELECT * FROM {table}"):
                item = dict(row)
                if self._rh(item) != item.get("record_hash"):
                    bad.append(
                        {
                            "table": table,
                            "id": item.get(key),
                            "reason": "record_hash_mismatch",
                        }
                    )
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        runs = int(self.db.one("SELECT COUNT(*) n FROM surface_hardening_run_442")["n"])
        attempts = int(self.db.one("SELECT COUNT(*) n FROM surface_failure_telemetry_442")["n"])
        validations = int(
            self.db.one(
                "SELECT COUNT(*) n FROM surface_hardening_run_442 WHERE external_validation=1"
            )["n"]
        )
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "runs": runs,
            "attempt_telemetry_events": attempts,
            "external_validation_runs": validations,
            "integrity_valid": self.verify_integrity()["valid"],
            "surface441_boundary_retained": True,
            "dns_rebinding_defense": True,
            "task_scoped_dns_ip_pinning": True,
            "non_public_dns_fail_closed": True,
            "public_dns_change_observed_but_original_pin_retained": True,
            "bounded_retry": True,
            "max_attempts": MAX_ATTEMPTS,
            "exponential_backoff": True,
            "transient_http_statuses": sorted(TRANSIENT_HTTP),
            "per_source_rate_limit": True,
            "max_source_tasks_per_minute": MAX_SOURCE_TASKS_PER_MINUTE,
            "minimum_source_interval_seconds": MIN_SOURCE_INTERVAL_SECONDS,
            "source_scoped_worker_lock": True,
            "single_concurrent_live_worker": True,
            "ephemeral_transport_per_live_run": True,
            "shared_cookie_or_session_state": False,
            "process_isolation": True,
            "os_sandbox_qualified": False,
            "retrieval_worker_inherits_environment": False,
            "executable_archive_intake_blocked": True,
            "malware_scanner_qualified": False,
            "failure_telemetry": True,
            "tls_certificate_validation_inherited_from_441_transport": True,
            "robots_fail_closed_inherited_from_441": True,
            "same_host_redirect_boundary_inherited_from_441": True,
            "external_validation_requires_explicit_confirmation": True,
            "automatic_external_validation": False,
            "external_network_on_startup": False,
            "authenticated_sources_supported": False,
            "autonomous_scope_expansion": False,
            "access_control_bypass": False,
            "production_release_ready": False,
        }
