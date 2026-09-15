from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit

from eagleeye.infrastructure.providers import (
    NormalizedProviderItem,
    ProviderAdapter,
    ProviderAuthorizationError,
    ProviderCircuitOpenError,
    ProviderDefinition,
    ProviderFrameworkError,
    ProviderHttpRequest,
    ProviderRateLimitError,
    ProviderReplayError,
    ProviderRunRequest,
    ProviderTransportError,
    ProviderTransportResponse,
    ProviderValidationError,
    PublicEndpointPolicy,
    ReplayFixtureStore,
    UrllibPublicTransport,
    canonicalize_public_url,
    default_adapters,
)
from eagleeye.infrastructure.providers.policy import sanitize_mapping, validate_public_scope


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(timespec="seconds")


def _sha(*parts: Any) -> str:
    material = "\0".join(_json(part) if isinstance(part, (dict, list, tuple)) else str(part) for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class ProviderCollection120Service:
    """Canonical public-provider execution and controlled intake framework.

    Provider outputs are normalized into an untrusted intake zone. This service has
    no path that writes directly to reviewed evidence, entities, relations or graph
    state. Live execution is human-approved, provider-scoped and replayable.
    """

    RUN_MODES = {"live", "replay"}
    INTAKE_STATES = {"new", "deferred", "duplicate", "rejected", "ready_for_review"}
    RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
    APPROVAL_PHRASE = "PROVIDER RUN APPROVED"

    def __init__(
        self,
        db: Any,
        audit: Any,
        storage_root: str | Path,
        *,
        transport: Any | None = None,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
        policy: PublicEndpointPolicy | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.policy = policy or PublicEndpointPolicy()
        self.transport = transport or UrllibPublicTransport(self.policy)
        self.clock = clock or time.time
        self.sleeper = sleeper or time.sleep
        self.replay_store = ReplayFixtureStore(self.storage_root / "replay")
        self._adapters: dict[str, ProviderAdapter] = {}
        self.ensure_schema()
        for adapter in default_adapters():
            self.register_adapter(adapter)

    def ensure_schema(self) -> None:
        from eagleeye.infrastructure.providers.schema import ensure_provider_schema_120

        ensure_provider_schema_120(self.db)

    # ---------- provider catalog ----------
    def register_adapter(self, adapter: ProviderAdapter) -> dict[str, Any]:
        definition = adapter.definition
        adapter.validate_request  # contract surface validation
        adapter.build_requests
        adapter.normalize
        now = _iso(self.clock())
        values = definition.as_dict()
        self.db.execute(
            """INSERT INTO provider_catalog_120(
                provider_key,label,provider_type,public_only,supports_live,supports_replay,
                allowed_hosts_json,rate_limit_per_minute,min_interval_seconds,timeout_seconds,
                max_attempts,backoff_base_seconds,circuit_failure_threshold,circuit_cooldown_seconds,
                max_response_bytes,terms_profile,enabled,metadata_json,registered_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(provider_key) DO UPDATE SET
                label=excluded.label,provider_type=excluded.provider_type,public_only=excluded.public_only,
                supports_live=excluded.supports_live,supports_replay=excluded.supports_replay,
                allowed_hosts_json=excluded.allowed_hosts_json,rate_limit_per_minute=excluded.rate_limit_per_minute,
                min_interval_seconds=excluded.min_interval_seconds,timeout_seconds=excluded.timeout_seconds,
                max_attempts=excluded.max_attempts,backoff_base_seconds=excluded.backoff_base_seconds,
                circuit_failure_threshold=excluded.circuit_failure_threshold,
                circuit_cooldown_seconds=excluded.circuit_cooldown_seconds,
                max_response_bytes=excluded.max_response_bytes,terms_profile=excluded.terms_profile,
                enabled=excluded.enabled,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",
            (
                definition.provider_key, definition.label, definition.provider_type,
                int(definition.public_only), int(definition.supports_live), int(definition.supports_replay),
                _json(list(definition.allowed_hosts)), definition.rate_limit_per_minute,
                definition.min_interval_seconds, definition.timeout_seconds, definition.max_attempts,
                definition.backoff_base_seconds, definition.circuit_failure_threshold,
                definition.circuit_cooldown_seconds, definition.max_response_bytes,
                definition.terms_profile, int(definition.enabled), _json(sanitize_mapping(dict(definition.metadata))), now, now,
            ),
        )
        self.db.execute(
            "INSERT OR IGNORE INTO provider_state_120(provider_key,updated_at) VALUES(?,?)",
            (definition.provider_key, now),
        )
        self._adapters[definition.provider_key] = adapter
        return values

    def list_providers(self, *, enabled_only: bool = True) -> list[dict[str, Any]]:
        sql = "SELECT * FROM provider_catalog_120"
        params: tuple[Any, ...] = ()
        if enabled_only:
            sql += " WHERE enabled=1"
        sql += " ORDER BY provider_type,label"
        rows = self.db.all(sql, params)
        return [self._decode_provider(row) for row in rows]

    def provider(self, provider_key: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM provider_catalog_120 WHERE provider_key=?", (provider_key,))
        if not row:
            raise KeyError(provider_key)
        return self._decode_provider(row)

    @staticmethod
    def _decode_provider(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["allowed_hosts"] = json.loads(result.pop("allowed_hosts_json", "[]"))
        result["metadata"] = json.loads(result.pop("metadata_json", "{}"))
        for key in ("public_only", "supports_live", "supports_replay", "enabled"):
            result[key] = bool(result.get(key))
        return result

    # ---------- execution ----------
    def execute(
        self,
        *,
        case_id: str,
        provider_key: str,
        query: str,
        purpose: str,
        approved_by: str,
        confirmation: str,
        mode: str = "replay",
        target_id: str = "",
        search_intent_id: str = "",
        search_query_id: str = "",
        max_results: int = 50,
        record_replay: bool = True,
    ) -> dict[str, Any]:
        mode = mode.casefold().strip()
        if mode not in self.RUN_MODES:
            raise ProviderValidationError("mode must be live or replay")
        if confirmation.strip() != self.APPROVAL_PHRASE:
            raise ProviderAuthorizationError("explicit provider-run approval phrase is required")
        if not approved_by.strip() or len(purpose.strip()) < 10:
            raise ProviderAuthorizationError("approver and substantive purpose are required")
        if not 1 <= int(max_results) <= 500:
            raise ProviderValidationError("max_results outside safe bounds")
        validate_public_scope(query, purpose)
        self._validate_case_target(case_id, target_id)
        adapter = self._adapters.get(provider_key)
        if not adapter:
            raise ProviderValidationError(f"provider adapter is not loaded: {provider_key}")
        definition = adapter.definition
        if not definition.enabled:
            raise ProviderAuthorizationError("provider is disabled")
        if mode == "live" and not definition.supports_live:
            raise ProviderAuthorizationError("provider does not support live execution")
        if mode == "replay" and not definition.supports_replay:
            raise ProviderAuthorizationError("provider does not support replay execution")
        if search_intent_id or search_query_id:
            self._validate_search_approval(
                case_id=case_id,
                provider_key=provider_key,
                query=query,
                search_intent_id=search_intent_id,
                search_query_id=search_query_id,
            )
        request = ProviderRunRequest(
            case_id=case_id,
            provider_key=provider_key,
            query=query.strip(),
            purpose=purpose.strip(),
            approved_by=approved_by.strip(),
            target_id=target_id.strip(),
            search_intent_id=search_intent_id.strip(),
            search_query_id=search_query_id.strip(),
            max_results=int(max_results),
        )
        adapter.validate_request(request)
        http_requests = tuple(adapter.build_requests(request))
        if not http_requests or len(http_requests) > 25:
            raise ProviderValidationError("provider produced an invalid request count")
        run_id = _id("prun120")
        correlation_id = _id("corr120")
        started_epoch = self.clock()
        started_at = _iso(started_epoch)
        self.db.execute(
            """INSERT INTO provider_runs_120(
                run_id,case_id,target_id,provider_key,search_intent_id,search_query_id,
                query_text,purpose,approved_by,mode,status,correlation_id,request_count,started_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_id, case_id, target_id or None, provider_key, search_intent_id or None,
                search_query_id or None, request.query, request.purpose, request.approved_by,
                mode, "running", correlation_id, len(http_requests), started_at,
            ),
        )
        self._event(case_id, provider_key, run_id, approved_by, "ProviderRunStarted", {
            "mode": mode, "query_fingerprint": _sha(request.query), "request_count": len(http_requests),
            "search_intent_id": search_intent_id, "search_query_id": search_query_id,
        })
        normalized: list[NormalizedProviderItem] = []
        attempts = 0
        total_latency = 0
        fixture_ids: list[str] = []
        try:
            for index, http_request in enumerate(http_requests):
                response, used_attempts = self._execute_request(
                    run_id=run_id,
                    request_index=index,
                    provider=definition,
                    http_request=http_request,
                    mode=mode,
                )
                attempts += used_attempts
                total_latency += int(response.elapsed_ms)
                if not 200 <= response.status_code < 300:
                    raise ProviderTransportError(f"provider returned HTTP {response.status_code}")
                items = list(adapter.normalize(response, request))[: request.max_results - len(normalized)]
                normalized.extend(items)
                if mode == "live" and record_replay:
                    fixture_ids.append(self._record_fixture(provider_key, response, run_id))
                if len(normalized) >= request.max_results:
                    break
            intake_ids, duplicate_count = self._store_intake(run_id, request, normalized)
            result_count = len(intake_ids)
            denominator = max(1, result_count + duplicate_count)
            gain = round(result_count / denominator, 6)
            completed = _iso(self.clock())
            self.db.execute(
                """UPDATE provider_runs_120 SET status='succeeded',attempt_count=?,result_count=?,duplicate_count=?,
                information_gain=?,completed_at=? WHERE run_id=?""",
                (attempts, result_count, duplicate_count, gain, completed, run_id),
            )
            self._record_run_success(definition, total_latency, result_count, duplicate_count)
            self._event(case_id, provider_key, run_id, approved_by, "ProviderRunCompleted", {
                "result_count": result_count, "duplicate_count": duplicate_count,
                "information_gain": gain, "fixture_ids": fixture_ids,
            })
            self.audit.log("complete", "provider_run_120", run_id, case_id, {
                "provider_key": provider_key, "mode": mode, "candidate_only": True,
                "result_count": result_count, "duplicate_count": duplicate_count,
            })
            return self.get_run(run_id)
        except Exception as exc:
            completed = _iso(self.clock())
            error_class = type(exc).__name__
            error_text = str(exc)[:4000]
            self.db.execute(
                """UPDATE provider_runs_120 SET status='failed',attempt_count=?,error_class=?,error_text=?,completed_at=?
                WHERE run_id=?""",
                (attempts, error_class, error_text, completed, run_id),
            )
            self._record_run_failure(definition)
            self._event(case_id, provider_key, run_id, approved_by, "ProviderRunFailed", {
                "error_class": error_class, "error": error_text[:1000],
            })
            self.audit.log("fail", "provider_run_120", run_id, case_id, {
                "provider_key": provider_key, "error_class": error_class,
            })
            raise

    def _execute_request(
        self,
        *,
        run_id: str,
        request_index: int,
        provider: ProviderDefinition,
        http_request: ProviderHttpRequest,
        mode: str,
    ) -> tuple[ProviderTransportResponse, int]:
        canonical = self.policy.validate_url(
            http_request.url,
            allowed_hosts=provider.allowed_hosts,
            resolve_dns=False,
        )
        safe_request = ProviderHttpRequest(canonical, method=http_request.method, headers=http_request.headers, label=http_request.label)
        if mode == "replay":
            response = self._load_replay(provider.provider_key, canonical)
            self.policy.validate_url(response.final_url, allowed_hosts=provider.allowed_hosts, resolve_dns=False)
            self._record_attempt(run_id, request_index, 1, safe_request, response, "replayed", self.clock())
            return response, 1

        self._check_circuit(provider)
        last_error: Exception | None = None
        for attempt_number in range(1, provider.max_attempts + 1):
            now = self.clock()
            self._consume_rate_limit(provider, now)
            try:
                response = self.transport.fetch(
                    safe_request,
                    allowed_hosts=provider.allowed_hosts,
                    timeout_seconds=provider.timeout_seconds,
                    max_response_bytes=provider.max_response_bytes,
                )
                self.policy.validate_url(response.final_url, allowed_hosts=provider.allowed_hosts, resolve_dns=False)
                if len(response.body) > provider.max_response_bytes:
                    raise ProviderTransportError("provider response exceeds configured byte limit")
                retryable = response.status_code in self.RETRYABLE_STATUS or response.status_code >= 500
                outcome = "retryable_http" if retryable else "success" if 200 <= response.status_code < 300 else "permanent_http"
                self._record_attempt(run_id, request_index, attempt_number, safe_request, response, outcome, now)
                if retryable:
                    raise ProviderTransportError(f"transient provider HTTP {response.status_code}")
                self._request_success(provider)
                return response, attempt_number
            except ProviderValidationError as exc:
                last_error = exc
                self._record_attempt(run_id, request_index, attempt_number, safe_request, None, "policy_error", now, exc)
                self._request_failure(provider)
                raise
            except (ProviderTransportError, TimeoutError, OSError) as exc:
                last_error = exc
                if not self._attempt_already_recorded(run_id, request_index, attempt_number):
                    self._record_attempt(run_id, request_index, attempt_number, safe_request, None, "transport_error", now, exc)
                self._request_failure(provider)
                if attempt_number >= provider.max_attempts:
                    break
                delay = min(10.0, provider.backoff_base_seconds * (2 ** (attempt_number - 1)))
                self.sleeper(delay)
        raise ProviderTransportError(str(last_error or "provider request failed"))

    def _record_attempt(
        self,
        run_id: str,
        request_index: int,
        attempt_number: int,
        request: ProviderHttpRequest,
        response: ProviderTransportResponse | None,
        outcome: str,
        epoch: float,
        error: Exception | None = None,
    ) -> None:
        body = response.body if response else b""
        self.db.execute(
            """INSERT INTO provider_attempts_120(
                attempt_id,run_id,request_index,attempt_number,requested_url,final_url,status_code,outcome,
                error_class,error_text,response_sha256,response_bytes,elapsed_ms,attempted_at_epoch,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                _id("patt120"), run_id, request_index, attempt_number, request.url,
                response.final_url if response else "", response.status_code if response else None, outcome,
                type(error).__name__ if error else "", str(error)[:2000] if error else "",
                hashlib.sha256(body).hexdigest() if body else "", len(body),
                int(response.elapsed_ms) if response else 0, epoch, _iso(epoch),
            ),
        )

    def _attempt_already_recorded(self, run_id: str, request_index: int, attempt_number: int) -> bool:
        return bool(self.db.one(
            "SELECT attempt_id FROM provider_attempts_120 WHERE run_id=? AND request_index=? AND attempt_number=?",
            (run_id, request_index, attempt_number),
        ))

    # ---------- approval and scope ----------
    def _validate_case_target(self, case_id: str, target_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise ProviderValidationError("case does not exist")
        if target_id:
            row = self.db.one("SELECT case_id FROM targets WHERE target_id=?", (target_id,))
            if not row or row["case_id"] != case_id:
                raise ProviderValidationError("target does not belong to case")

    def _validate_search_approval(
        self,
        *,
        case_id: str,
        provider_key: str,
        query: str,
        search_intent_id: str,
        search_query_id: str,
    ) -> None:
        if not search_intent_id or not search_query_id:
            raise ProviderAuthorizationError("intent and query approval references must be supplied together")
        row = self.db.one(
            """SELECT q.query_text,q.provider,q.state query_state,q.intent_id,
                      i.case_id,i.state intent_state
               FROM search_queries_114 q JOIN search_intents_114 i ON i.intent_id=q.intent_id
               WHERE q.query_id=?""",
            (search_query_id,),
        )
        if not row or row["intent_id"] != search_intent_id or row["case_id"] != case_id:
            raise ProviderAuthorizationError("search approval references do not belong to this case")
        if row["intent_state"] != "approved" or row["query_state"] != "approved":
            raise ProviderAuthorizationError("search intent and query require approval")
        if str(row["provider"]) != provider_key:
            raise ProviderAuthorizationError("approved query names a different provider")
        if " ".join(str(row["query_text"]).split()).casefold() != " ".join(query.split()).casefold():
            raise ProviderAuthorizationError("execution query differs from approved query")

    # ---------- controls ----------
    def _state(self, provider_key: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM provider_state_120 WHERE provider_key=?", (provider_key,))
        if not row:
            now = _iso(self.clock())
            self.db.execute("INSERT INTO provider_state_120(provider_key,updated_at) VALUES(?,?)", (provider_key, now))
            row = self.db.one("SELECT * FROM provider_state_120 WHERE provider_key=?", (provider_key,))
        return row or {}

    def _check_circuit(self, provider: ProviderDefinition) -> None:
        state = self._state(provider.provider_key)
        now = self.clock()
        if state.get("circuit_state") == "open":
            if now < float(state.get("open_until_epoch") or 0):
                raise ProviderCircuitOpenError("provider circuit is open")
            self.db.execute(
                "UPDATE provider_state_120 SET circuit_state='half_open',updated_at=? WHERE provider_key=?",
                (_iso(now), provider.provider_key),
            )

    def _consume_rate_limit(self, provider: ProviderDefinition, now: float) -> None:
        state = self._state(provider.provider_key)
        if now < float(state.get("next_allowed_epoch") or 0):
            raise ProviderRateLimitError("provider minimum interval has not elapsed")
        count = self.db.one(
            """SELECT COUNT(*) count FROM provider_attempts_120 a
               JOIN provider_runs_120 r ON r.run_id=a.run_id
               WHERE r.provider_key=? AND a.attempted_at_epoch>? AND a.outcome!='replayed'""",
            (provider.provider_key, now - 60.0),
        )
        if int((count or {}).get("count", 0)) >= provider.rate_limit_per_minute:
            raise ProviderRateLimitError("provider per-minute rate limit reached")
        self.db.execute(
            "UPDATE provider_state_120 SET next_allowed_epoch=?,updated_at=? WHERE provider_key=?",
            (now + provider.min_interval_seconds, _iso(now), provider.provider_key),
        )

    def _request_success(self, provider: ProviderDefinition) -> None:
        now = self.clock()
        self.db.execute(
            """UPDATE provider_state_120 SET circuit_state='closed',consecutive_failures=0,
            open_until_epoch=0,last_success_at=?,updated_at=? WHERE provider_key=?""",
            (_iso(now), _iso(now), provider.provider_key),
        )

    def _request_failure(self, provider: ProviderDefinition) -> None:
        state = self._state(provider.provider_key)
        failures = int(state.get("consecutive_failures") or 0) + 1
        now = self.clock()
        circuit = "open" if failures >= provider.circuit_failure_threshold else str(state.get("circuit_state") or "closed")
        open_until = now + provider.circuit_cooldown_seconds if circuit == "open" else float(state.get("open_until_epoch") or 0)
        self.db.execute(
            """UPDATE provider_state_120 SET circuit_state=?,consecutive_failures=?,open_until_epoch=?,
            last_failure_at=?,updated_at=? WHERE provider_key=?""",
            (circuit, failures, open_until, _iso(now), _iso(now), provider.provider_key),
        )

    def _record_run_success(self, provider: ProviderDefinition, latency: int, results: int, duplicates: int) -> None:
        now = _iso(self.clock())
        self.db.execute(
            """UPDATE provider_state_120 SET total_runs=total_runs+1,successful_runs=successful_runs+1,
            total_latency_ms=total_latency_ms+?,total_results=total_results+?,total_duplicates=total_duplicates+?,
            last_success_at=?,updated_at=? WHERE provider_key=?""",
            (latency, results, duplicates, now, now, provider.provider_key),
        )

    def _record_run_failure(self, provider: ProviderDefinition) -> None:
        now = _iso(self.clock())
        self.db.execute(
            """UPDATE provider_state_120 SET total_runs=total_runs+1,failed_runs=failed_runs+1,
            last_failure_at=?,updated_at=? WHERE provider_key=?""",
            (now, now, provider.provider_key),
        )

    # ---------- replay ----------
    def _record_fixture(self, provider_key: str, response: ProviderTransportResponse, run_id: str) -> str:
        saved = self.replay_store.save(provider_key, response, metadata={"source_run_id": run_id})
        fixture_id = _id("pfix120")
        self.db.execute(
            """INSERT OR IGNORE INTO provider_replay_fixtures_120(
                fixture_id,provider_key,request_fingerprint,fixture_path,fixture_sha256,response_sha256,
                source_run_id,sanitized,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                fixture_id, provider_key, saved["request_fingerprint"], saved["path"], saved["sha256"],
                saved["response_sha256"], run_id or None, int(bool(saved["sanitized"])), _iso(self.clock()),
            ),
        )
        row = self.db.one(
            """SELECT fixture_id FROM provider_replay_fixtures_120
               WHERE provider_key=? AND request_fingerprint=? AND fixture_sha256=?""",
            (provider_key, saved["request_fingerprint"], saved["sha256"]),
        )
        return str((row or {}).get("fixture_id") or fixture_id)

    def import_replay_fixture(
        self,
        *,
        provider_key: str,
        response: ProviderTransportResponse,
        source_run_id: str = "",
    ) -> str:
        if provider_key not in self._adapters:
            raise ProviderValidationError("unknown provider")
        definition = self._adapters[provider_key].definition
        self.policy.validate_url(response.requested_url, allowed_hosts=definition.allowed_hosts, resolve_dns=False)
        self.policy.validate_url(response.final_url, allowed_hosts=definition.allowed_hosts, resolve_dns=False)
        if len(response.body) > definition.max_response_bytes:
            raise ProviderValidationError("fixture response exceeds provider byte limit")
        return self._record_fixture(provider_key, response, source_run_id)

    def _load_replay(self, provider_key: str, requested_url: str) -> ProviderTransportResponse:
        fingerprint = self.replay_store.request_fingerprint(provider_key, requested_url)
        row = self.db.one(
            """SELECT * FROM provider_replay_fixtures_120
               WHERE provider_key=? AND request_fingerprint=? ORDER BY created_at DESC LIMIT 1""",
            (provider_key, fingerprint),
        )
        if not row:
            raise ProviderReplayError("no replay fixture for provider request")
        response = self.replay_store.load(row["fixture_path"], row["fixture_sha256"])
        if hashlib.sha256(response.body).hexdigest() != row["response_sha256"]:
            raise ProviderReplayError("replay response hash mismatch")
        return response

    # ---------- intake ----------
    def _store_intake(
        self,
        run_id: str,
        request: ProviderRunRequest,
        items: Iterable[NormalizedProviderItem],
    ) -> tuple[list[str], int]:
        ids: list[str] = []
        duplicates = 0
        now = _iso(self.clock())
        for item in items:
            title = item.title.strip()[:1000]
            if not title:
                continue
            canonical = canonicalize_public_url(item.url)
            host = (urlsplit(canonical).hostname or "").casefold()
            raw = sanitize_mapping(dict(item.raw_payload))
            raw_json = _json(raw)
            if len(raw_json.encode("utf-8")) > 200_000:
                raw = {"truncated": True, "original_sha256": hashlib.sha256(raw_json.encode("utf-8")).hexdigest()}
                raw_json = _json(raw)
            fingerprint = _sha(title.casefold(), canonical, item.snippet.strip(), raw)
            intake_id = _id("pint120")
            try:
                self.db.execute(
                    """INSERT INTO provider_intake_120(
                        intake_id,case_id,target_id,run_id,provider_key,title,url,canonical_url,source_host,
                        snippet,source_type,published_at,content_fingerprint,raw_payload_json,review_status,
                        candidate_only,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        intake_id, request.case_id, request.target_id or None, run_id, request.provider_key,
                        title, item.url[:4000], canonical[:4000], host[:253], item.snippet[:10000],
                        item.source_type[:100], item.published_at[:100], fingerprint, raw_json,
                        "new", 1, now, now,
                    ),
                )
                ids.append(intake_id)
            except sqlite3.IntegrityError:
                existing = self.db.one(
                    """SELECT intake_id FROM provider_intake_120
                       WHERE case_id=? AND provider_key=? AND canonical_url=? AND content_fingerprint=?""",
                    (request.case_id, request.provider_key, canonical, fingerprint),
                )
                if existing:
                    duplicates += 1
                else:
                    raise
        return ids, duplicates

    def list_intake(
        self,
        case_id: str,
        *,
        review_status: str = "",
        provider_key: str = "",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        self._validate_case_target(case_id, "")
        if review_status and review_status not in self.INTAKE_STATES:
            raise ProviderValidationError("invalid intake state")
        bounded_limit = max(1, min(int(limit), 1000))
        rows = self.db.all(
            """SELECT * FROM provider_intake_120
               WHERE case_id=?
                 AND (?='' OR review_status=?)
                 AND (?='' OR provider_key=?)
               ORDER BY created_at DESC LIMIT ?""",
            (case_id, review_status, review_status, provider_key, provider_key, bounded_limit),
        )
        for row in rows:
            row["raw_payload"] = json.loads(row.pop("raw_payload_json", "{}"))
            row["candidate_only"] = bool(row.get("candidate_only"))
        return rows

    def update_intake_status(self, intake_id: str, status: str, actor: str, reason: str) -> dict[str, Any]:
        if status not in self.INTAKE_STATES:
            raise ProviderValidationError("invalid intake state")
        if len(reason.strip()) < 8:
            raise ProviderValidationError("substantive intake decision reason is required")
        row = self.db.one("SELECT * FROM provider_intake_120 WHERE intake_id=?", (intake_id,))
        if not row:
            raise KeyError(intake_id)
        if not actor.strip():
            raise ProviderValidationError("intake decision actor is required")
        transitions = {
            "new": {"deferred", "duplicate", "rejected", "ready_for_review"},
            "deferred": {"new", "rejected", "ready_for_review"},
            "ready_for_review": {"deferred", "rejected"},
            "duplicate": set(),
            "rejected": set(),
        }
        current = str(row.get("review_status") or "new")
        if status not in transitions.get(current, set()):
            raise ProviderValidationError(f"invalid intake transition: {current} -> {status}")
        self.db.execute(
            "UPDATE provider_intake_120 SET review_status=?,updated_at=? WHERE intake_id=?",
            (status, _iso(self.clock()), intake_id),
        )
        self._event(row["case_id"], row["provider_key"], row["run_id"], actor, "ProviderIntakeStatusChanged", {
            "intake_id": intake_id, "status": status, "reason": reason[:1000],
        })
        return self.db.one("SELECT * FROM provider_intake_120 WHERE intake_id=?", (intake_id,)) or {}

    # ---------- observability ----------
    def get_run(self, run_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM provider_runs_120 WHERE run_id=?", (run_id,))
        if not row:
            raise KeyError(run_id)
        row["attempts"] = self.db.all(
            "SELECT * FROM provider_attempts_120 WHERE run_id=? ORDER BY request_index,attempt_number",
            (run_id,),
        )
        row["intake"] = self.db.all(
            "SELECT * FROM provider_intake_120 WHERE run_id=? ORDER BY created_at,intake_id",
            (run_id,),
        )
        for item in row["intake"]:
            item["raw_payload"] = json.loads(item.pop("raw_payload_json", "{}"))
            item["candidate_only"] = bool(item.get("candidate_only"))
        row["candidate_only"] = True
        return row

    def list_runs(self, case_id: str, limit: int = 100) -> list[dict[str, Any]]:
        self._validate_case_target(case_id, "")
        return self.db.all(
            "SELECT * FROM provider_runs_120 WHERE case_id=? ORDER BY started_at DESC LIMIT ?",
            (case_id, max(1, min(int(limit), 1000))),
        )

    def health_check(self, provider_key: str) -> dict[str, Any]:
        adapter = self._adapters.get(provider_key)
        if not adapter:
            raise KeyError(provider_key)
        state = self._state(provider_key)
        total = int(state.get("total_runs") or 0)
        successes = int(state.get("successful_runs") or 0)
        success_rate = successes / total if total else None
        avg_latency = int(state.get("total_latency_ms") or 0) / successes if successes else None
        circuit = state.get("circuit_state", "closed")
        status = "blocked" if circuit == "open" else "degraded" if success_rate is not None and success_rate < 0.8 else "healthy"
        return {
            "provider": self.provider(provider_key),
            "adapter": adapter.health_check(),
            "status": status,
            "circuit_state": circuit,
            "consecutive_failures": int(state.get("consecutive_failures") or 0),
            "success_rate": success_rate,
            "average_latency_ms": avg_latency,
            "total_runs": total,
            "successful_runs": successes,
            "failed_runs": int(state.get("failed_runs") or 0),
            "total_results": int(state.get("total_results") or 0),
            "total_duplicates": int(state.get("total_duplicates") or 0),
            "last_success_at": state.get("last_success_at", ""),
            "last_failure_at": state.get("last_failure_at", ""),
        }

    def health_all(self) -> list[dict[str, Any]]:
        return [self.health_check(item["provider_key"]) for item in self.list_providers(enabled_only=False)]

    # ---------- audit hash chain ----------
    def _event(
        self,
        case_id: str,
        provider_key: str,
        run_id: str,
        actor: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        now = _iso(self.clock())
        event_id = _id("pevt120")
        previous_row = self.db.one(
            """SELECT event_hash FROM provider_events_120
               WHERE case_id=? AND provider_key=? ORDER BY sequence DESC LIMIT 1""",
            (case_id, provider_key),
        )
        previous = previous_row["event_hash"] if previous_row else "GENESIS"
        safe_payload = sanitize_mapping(payload)
        digest = _sha(event_id, case_id, provider_key, run_id, actor, event_type, safe_payload, previous, now)
        self.db.execute(
            """INSERT INTO provider_events_120(
                event_id,case_id,provider_key,run_id,actor,event_type,payload_json,previous_hash,event_hash,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (event_id, case_id, provider_key, run_id, actor, event_type, _json(safe_payload), previous, digest, now),
        )

    def verify_event_chain(self, case_id: str, provider_key: str) -> bool:
        rows = self.db.all(
            """SELECT * FROM provider_events_120 WHERE case_id=? AND provider_key=? ORDER BY sequence""",
            (case_id, provider_key),
        )
        previous = "GENESIS"
        for row in rows:
            payload = json.loads(row["payload_json"])
            expected = _sha(
                row["event_id"], row["case_id"], row["provider_key"], row["run_id"], row["actor"],
                row["event_type"], payload, previous, row["created_at"],
            )
            if row["previous_hash"] != previous or row["event_hash"] != expected:
                return False
            previous = row["event_hash"]
        return True
