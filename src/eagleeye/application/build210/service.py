from __future__ import annotations

import hashlib
import html
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from eagleeye_pro.core.database import dumps, new_id, now_ts


TERMINAL_TASK_STATES = {"succeeded", "dead_letter", "cancelled", "blocked_dependency"}
ACTIVE_TASK_STATES = {"leased", "running"}
CLAIMABLE_TASK_STATES = {"queued", "retry_wait"}
MISFIRE_POLICIES = {"coalesce", "skip", "bounded_catchup", "manual"}
PROMPT_INJECTION_MARKERS = (
    "ignore previous instructions",
    "reveal the system prompt",
    "bypass policy",
    "disable audit",
    "execute this command",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_ts(value: str) -> datetime:
    value = (value or "").strip()
    if not value:
        return datetime.fromtimestamp(0, timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canonical_json(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _loads(value: str, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


def _canonical_source_ref(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        parts = urlsplit(value)
        scheme = parts.scheme.lower()
        host = (parts.hostname or "").lower()
        port = parts.port
        netloc = host
        if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
            netloc = f"{host}:{port}"
        query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
        path = parts.path or "/"
        return urlunsplit((scheme, netloc, path, query, ""))
    except Exception:
        return value[:2000]


def _safe_text(value: Any, limit: int = 4000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


class Build210MonitoringAlertOperationsService:
    """Durable single-host monitoring scheduler with lease-based recovery.

    Build 210 deliberately keeps execution semantics at-least-once while making
    stored outcomes idempotent. External actions remain disabled by default and
    every identity/claim result remains a review candidate.
    """

    BUILD = "210.0"
    TASK_TYPES = (
        "collect_source",
        "normalize_observation",
        "deduplicate_observation",
        "assess_claim_impact",
        "ai_investigator_review",
        "evaluate_alert_policy",
        "deliver_local_alert",
    )

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        orchestrator: Any,
        monitoring: Any,
        runtime: Any,
        agents: Any,
        agent_runtime: Any,
        social: Any,
        news: Any,
        retrieval: Any,
        workspace: Any,
        actor: str = "system",
    ) -> None:
        self.db = db
        self.audit = audit
        self.orchestrator = orchestrator
        self.monitoring = monitoring
        self.runtime = runtime
        self.agents = agents
        self.agent_runtime = agent_runtime
        self.social = social
        self.news = news
        self.retrieval = retrieval
        self.workspace = workspace
        self.actor = actor

    # ------------------------------------------------------------------
    # Policy and schedule lifecycle
    # ------------------------------------------------------------------
    def seed_monitoring_operations(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "MONITORING OPERATIONS 210 ANLEGEN":
            raise PermissionError("explicit approval required")
        now = now_ts()
        policy = {
            "execution_semantics": "at_least_once_exactly_once_observable_outcome",
            "scheduler": {
                "durable": True,
                "leader_lease_seconds": 30,
                "task_lease_seconds": 90,
                "heartbeat_seconds": 20,
                "restart_recovery": "expired_leases_only",
            },
            "parallel_programming": {
                "control_plane": "asyncio_taskgroup",
                "worker_isolation": "spawned_process",
                "blocking_adapter": "bounded_thread_pool",
                "database": "sqlite_wal_short_transactions",
                "single_host": True,
            },
            "ai_investigation": {
                "continuous_build_training": True,
                "ai_chat_as_co_investigator": True,
                "review_required": True,
                "citations_required": True,
                "automatic_identity_confirmation": False,
            },
            "social_research": {
                "continuous_build_deepening": True,
                "public_sources_only": True,
                "account_resolution_candidate_only": True,
                "thread_reconstruction_candidate_only": True,
            },
            "opsec": {
                "investigator_protection": "strict",
                "case_isolation": True,
                "secrets_in_payloads": False,
                "content_is_untrusted_data": True,
                "automatic_external_action": False,
            },
            "firefox_workspace": {
                "reuse_existing_browser": True,
                "open_as_tabs": True,
                "max_parallel_search_engines": 3,
                "single_action_approval": True,
            },
            "alerts": {
                "local_ui_enabled": True,
                "external_delivery_enabled": False,
                "human_review_required": True,
            },
        }
        self.db.execute(
            "INSERT OR REPLACE INTO monitor_runtime_policies_210 VALUES(?,?,?,?,?)",
            ("default", dumps(policy), "active", now, now),
        )
        self._event("system", "", "", "monitoring_policy_seeded", policy, "seed210")
        return {
            "policy_id": "default",
            "durable_scheduler": True,
            "lease_recovery": True,
            "parallel_worker_isolation": "spawned_process",
            "ai_investigator_training": True,
            "social_research_deepening": True,
            "opsec_preserved": True,
            "automatic_external_action": False,
        }

    def create_schedule(
        self,
        *,
        case_id: str,
        name: str,
        question: str,
        source_ids: Sequence[str],
        interval_minutes: int,
        monitor_id: str = "",
        timezone_name: str = "Europe/Berlin",
        misfire_policy: str = "coalesce",
        max_catchup_runs: int = 1,
        jitter_seconds: int = 15,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"MONITOR SCHEDULE 210 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        if not case_id.strip() or not name.strip() or not question.strip():
            raise ValueError("case_id, name and question are required")
        if misfire_policy not in MISFIRE_POLICIES:
            raise ValueError("invalid misfire policy")
        source_ids = tuple(dict.fromkeys(s.strip() for s in source_ids if s and s.strip()))
        floor_minutes = self._source_polling_floor(source_ids)
        effective_minutes = max(int(interval_minutes), floor_minutes, 1)
        now_dt = _utc_now()
        now = _iso(now_dt)
        schedule_id = new_id("schedule210")
        monitor_id = monitor_id.strip() or new_id("monitor210")
        policy = {
            "local_processing": True,
            "external_uploads": False,
            "external_alerts": False,
            "human_review_required": True,
            "automatic_identity_confirmation": False,
            "automatic_contact": False,
            "content_is_untrusted_data": True,
            "source_rate_limits_enforced": True,
            "build209_process_isolation_reused": True,
            "build201_source_runtime_reused": True,
            "build195_claim_impact_semantics_reused": True,
            "ai_co_investigator": True,
            "social_research_deepening": True,
        }
        next_run = _iso(now_dt + timedelta(minutes=effective_minutes))
        self.db.execute(
            """INSERT INTO monitor_schedules_210
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                schedule_id,
                monitor_id,
                case_id,
                _safe_text(name, 300),
                _safe_text(question, 4000),
                dumps(list(source_ids)),
                effective_minutes * 60,
                timezone_name,
                misfire_policy,
                max(0, min(int(max_catchup_runs), 100)),
                max(0, min(int(jitter_seconds), 3600)),
                "draft",
                next_run,
                "",
                0,
                dumps(policy),
                now,
                now,
            ),
        )
        self._event(monitor_id, "", "", "schedule_created", {
            "schedule_id": schedule_id,
            "case_id": case_id,
            "source_ids": list(source_ids),
            "interval_minutes": effective_minutes,
            "polling_floor_minutes": floor_minutes,
        }, new_id("corr210"))
        return {
            "schedule_id": schedule_id,
            "monitor_id": monitor_id,
            "case_id": case_id,
            "status": "draft",
            "next_run_at": next_run,
            "interval_minutes": effective_minutes,
            "polling_floor_minutes": floor_minutes,
            "external_alerts": False,
            "review_required": True,
        }

    def activate_schedule(self, *, schedule_id: str, approved_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"MONITOR SCHEDULE 210 {schedule_id} AKTIVIEREN":
            raise PermissionError("explicit approval required")
        row = self._require_schedule(schedule_id)
        now = now_ts()
        self.db.execute(
            "UPDATE monitor_schedules_210 SET status='active',revision=revision+1,updated_at=? WHERE schedule_id=?",
            (now, schedule_id),
        )
        self._event(row["monitor_id"], "", "", "schedule_activated", {"schedule_id": schedule_id, "approved_by": approved_by}, new_id("corr210"))
        return {"schedule_id": schedule_id, "status": "active", "approved_by": approved_by, "automatic_external_action": False}

    def pause_schedule(self, *, schedule_id: str, reason: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"MONITOR SCHEDULE 210 {schedule_id} PAUSIEREN":
            raise PermissionError("explicit approval required")
        row = self._require_schedule(schedule_id)
        self.db.execute(
            "UPDATE monitor_schedules_210 SET status='paused',revision=revision+1,updated_at=? WHERE schedule_id=?",
            (now_ts(), schedule_id),
        )
        self._event(row["monitor_id"], "", "", "schedule_paused", {"schedule_id": schedule_id, "reason": _safe_text(reason, 500)}, new_id("corr210"))
        return {"schedule_id": schedule_id, "status": "paused"}

    def trigger_run(self, *, schedule_id: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"MONITOR RUN 210 {schedule_id} STARTEN":
            raise PermissionError("explicit approval required")
        schedule = self._require_schedule(schedule_id)
        scheduled_for = now_ts()
        return self._materialize_run(schedule, scheduled_for=scheduled_for, trigger_type="manual")

    def materialize_due_runs(self, *, owner_id: str, now: str | None = None, limit: int = 25) -> dict[str, Any]:
        now = now or now_ts()
        lease = self.acquire_role_lease(role_key="scheduler", owner_id=owner_id, lease_seconds=30)
        if not lease["acquired"]:
            return {"leader": False, "materialized": 0, "schedule_ids": []}
        rows = self.db.all(
            "SELECT * FROM monitor_schedules_210 WHERE status='active' AND next_run_at<=? ORDER BY next_run_at LIMIT ?",
            (now, max(1, min(int(limit), 250))),
        )
        created: list[str] = []
        for schedule in rows:
            result = self._handle_due_schedule(schedule, now)
            if result.get("created"):
                created.append(schedule["schedule_id"])
        return {"leader": True, "materialized": len(created), "schedule_ids": created, "lease_token": lease["lease_token"]}

    # ------------------------------------------------------------------
    # Leases, task lifecycle and recovery
    # ------------------------------------------------------------------
    def acquire_role_lease(self, *, role_key: str, owner_id: str, lease_seconds: int = 30) -> dict[str, Any]:
        now_dt = _utc_now()
        now = _iso(now_dt)
        expires = _iso(now_dt + timedelta(seconds=max(5, int(lease_seconds))))
        token = secrets.token_urlsafe(24)
        with self.db.transaction(immediate=True):
            row = self.db.one("SELECT * FROM scheduler_leases_210 WHERE role_key=?", (role_key,))
            if row and row["lease_owner"] != owner_id and _parse_ts(row["lease_expires_at"]) > now_dt:
                return {"acquired": False, "role_key": role_key, "lease_owner": row["lease_owner"], "lease_expires_at": row["lease_expires_at"]}
            if row:
                self.db.execute(
                    """UPDATE scheduler_leases_210 SET lease_owner=?,lease_token=?,lease_expires_at=?,heartbeat_at=?,
                    revision=revision+1,updated_at=? WHERE role_key=?""",
                    (owner_id, token, expires, now, now, role_key),
                )
            else:
                self.db.execute(
                    "INSERT INTO scheduler_leases_210 VALUES(?,?,?,?,?,?,?)",
                    (role_key, owner_id, token, expires, now, 0, now),
                )
        return {"acquired": True, "role_key": role_key, "lease_owner": owner_id, "lease_token": token, "lease_expires_at": expires}

    def claim_tasks(
        self,
        *,
        worker_id: str,
        capabilities: Sequence[str],
        limit: int = 4,
        lease_seconds: int = 90,
    ) -> list[dict[str, Any]]:
        caps = tuple(dict.fromkeys(str(c) for c in capabilities if c))
        if not caps:
            return []
        claimed: list[dict[str, Any]] = []
        max_claims = max(1, min(int(limit), 64))
        for _ in range(max_claims):
            lease = self._claim_one(worker_id=worker_id, capabilities=caps, lease_seconds=lease_seconds)
            if not lease:
                break
            claimed.append(lease)
        return claimed

    def _claim_one(self, *, worker_id: str, capabilities: Sequence[str], lease_seconds: int) -> dict[str, Any] | None:
        now_dt = _utc_now()
        now = _iso(now_dt)
        expires = _iso(now_dt + timedelta(seconds=max(15, int(lease_seconds))))
        token = secrets.token_urlsafe(32)
        with self.db.transaction(immediate=True):
            if "*" in capabilities:
                rows = self.db.all(
                    """SELECT * FROM monitor_tasks_210
                    WHERE status IN ('queued','retry_wait') AND available_at<=? AND remaining_dependencies=0
                    ORDER BY priority DESC,created_at ASC LIMIT 100""",
                    (now,),
                )
            else:
                placeholders = ",".join("?" for _ in capabilities)
                rows = self.db.all(
                    f"""SELECT * FROM monitor_tasks_210
                    WHERE status IN ('queued','retry_wait') AND available_at<=? AND remaining_dependencies=0
                    AND task_type IN ({placeholders})
                    ORDER BY priority DESC,created_at ASC LIMIT 100""",
                    (now, *capabilities),
                )
            for row in rows:
                if not self._source_slot_available(row["source_id"]):
                    continue
                cur = self.db.execute(
                    """UPDATE monitor_tasks_210 SET status='leased',lease_owner=?,lease_token=?,lease_expires_at=?,
                    heartbeat_at=?,attempt=attempt+1,revision=revision+1,error_code='',error_text='',updated_at=?
                    WHERE task_id=? AND revision=? AND status IN ('queued','retry_wait') AND remaining_dependencies=0""",
                    (worker_id, token, expires, now, now, row["task_id"], row["revision"]),
                )
                if cur.rowcount != 1:
                    continue
                leased = dict(row)
                leased.update({
                    "status": "leased",
                    "lease_owner": worker_id,
                    "lease_token": token,
                    "lease_expires_at": expires,
                    "heartbeat_at": now,
                    "attempt": int(row["attempt"]) + 1,
                    "revision": int(row["revision"]) + 1,
                    "input": _loads(row["input_json"], {}),
                })
                self._event_for_task(row, "task_leased", {"worker_id": worker_id, "attempt": leased["attempt"]})
                return leased
        return None

    def start_task(self, *, task_id: str, worker_id: str, lease_token: str) -> dict[str, Any]:
        now = now_ts()
        with self.db.transaction(immediate=True):
            row = self._require_current_lease(task_id, worker_id, lease_token)
            cur = self.db.execute(
                "UPDATE monitor_tasks_210 SET status='running',revision=revision+1,updated_at=? WHERE task_id=? AND status='leased' AND lease_token=?",
                (now, task_id, lease_token),
            )
            if cur.rowcount != 1 and row["status"] != "running":
                raise RuntimeError("task cannot transition to running")
        self._event_for_task(row, "task_started", {"worker_id": worker_id})
        return {"task_id": task_id, "status": "running", "lease_expires_at": row["lease_expires_at"]}

    def heartbeat(
        self,
        *,
        task_id: str,
        worker_id: str,
        lease_token: str,
        checkpoint: Mapping[str, Any] | None = None,
        extend_seconds: int = 90,
    ) -> dict[str, Any]:
        now_dt = _utc_now()
        now = _iso(now_dt)
        expires = _iso(now_dt + timedelta(seconds=max(15, int(extend_seconds))))
        checkpoint_json = dumps(dict(checkpoint or {}))
        with self.db.transaction(immediate=True):
            self._require_current_lease(task_id, worker_id, lease_token)
            cur = self.db.execute(
                """UPDATE monitor_tasks_210 SET heartbeat_at=?,lease_expires_at=?,checkpoint_json=?,revision=revision+1,updated_at=?
                WHERE task_id=? AND lease_owner=? AND lease_token=? AND status IN ('leased','running')""",
                (now, expires, checkpoint_json, now, task_id, worker_id, lease_token),
            )
            if cur.rowcount != 1:
                raise RuntimeError("lease heartbeat conflict")
        return {"task_id": task_id, "heartbeat_at": now, "lease_expires_at": expires, "checkpoint": dict(checkpoint or {})}

    def complete_task(
        self,
        *,
        task_id: str,
        worker_id: str,
        lease_token: str,
        output: Mapping[str, Any],
    ) -> dict[str, Any]:
        output_clean = self._redact_payload(dict(output))
        output_json = dumps(output_clean)
        output_hash = hashlib.sha256(output_json.encode("utf-8")).hexdigest()
        now = now_ts()
        with self.db.transaction(immediate=True):
            row = self.db.one("SELECT * FROM monitor_tasks_210 WHERE task_id=?", (task_id,))
            if not row:
                raise KeyError(task_id)
            if row["status"] == "succeeded":
                return {"task_id": task_id, "status": "succeeded", "idempotent_replay": True, "output_sha256": row["output_sha256"]}
            self._require_current_lease(task_id, worker_id, lease_token, row=row)
            cur = self.db.execute(
                """UPDATE monitor_tasks_210 SET status='succeeded',output_json=?,output_sha256=?,lease_owner='',lease_token='',
                lease_expires_at='',heartbeat_at='',revision=revision+1,updated_at=?
                WHERE task_id=? AND lease_owner=? AND lease_token=? AND status IN ('leased','running')""",
                (output_json, output_hash, now, task_id, worker_id, lease_token),
            )
            if cur.rowcount != 1:
                raise RuntimeError("terminal task commit conflict")
            self.db.execute(
                """UPDATE monitor_tasks_210 SET remaining_dependencies=MAX(remaining_dependencies-1,0),updated_at=?
                WHERE task_id IN (SELECT task_id FROM monitor_task_dependencies_210 WHERE depends_on_task_id=?)""",
                (now, task_id),
            )
            self._refresh_run_state(row["run_id"], now)
        self._event_for_task(row, "task_succeeded", {"worker_id": worker_id, "output_sha256": output_hash})
        return {"task_id": task_id, "status": "succeeded", "idempotent_replay": False, "output_sha256": output_hash}

    def fail_task(
        self,
        *,
        task_id: str,
        worker_id: str,
        lease_token: str,
        error_code: str,
        error_text: str,
        retryable: bool = True,
    ) -> dict[str, Any]:
        now_dt = _utc_now()
        now = _iso(now_dt)
        with self.db.transaction(immediate=True):
            row = self.db.one("SELECT * FROM monitor_tasks_210 WHERE task_id=?", (task_id,))
            if not row:
                raise KeyError(task_id)
            if row["status"] in TERMINAL_TASK_STATES:
                return {"task_id": task_id, "status": row["status"], "idempotent_replay": True}
            self._require_current_lease(task_id, worker_id, lease_token, row=row)
            attempt = int(row["attempt"])
            max_attempts = int(row["max_attempts"])
            should_retry = bool(retryable and attempt < max_attempts)
            if should_retry:
                delay = min(900, 5 * (2 ** max(0, attempt - 1)))
                available_at = _iso(now_dt + timedelta(seconds=delay))
                status = "retry_wait"
            else:
                delay = None
                available_at = now
                status = "dead_letter"
            self.db.execute(
                """UPDATE monitor_tasks_210 SET status=?,available_at=?,lease_owner='',lease_token='',lease_expires_at='',
                heartbeat_at='',error_code=?,error_text=?,revision=revision+1,updated_at=? WHERE task_id=?""",
                (status, available_at, _safe_text(error_code, 100), _safe_text(error_text, 1000), now, task_id),
            )
            if status == "dead_letter":
                self._store_dead_letter(row, error_code, error_text, now)
                self._block_descendants(task_id, now)
            self._refresh_run_state(row["run_id"], now)
        self._event_for_task(row, "task_failed", {"status": status, "error_code": error_code, "retryable": should_retry})
        return {"task_id": task_id, "status": status, "retry_scheduled": should_retry, "retry_after_seconds": delay}

    def recover_expired_leases(self, *, now: str | None = None) -> dict[str, Any]:
        now = now or now_ts()
        recovered = 0
        dead = 0
        rows = self.db.all(
            "SELECT * FROM monitor_tasks_210 WHERE status IN ('leased','running') AND lease_expires_at<>'' AND lease_expires_at<=? ORDER BY lease_expires_at",
            (now,),
        )
        for candidate in rows:
            with self.db.transaction(immediate=True):
                row = self.db.one("SELECT * FROM monitor_tasks_210 WHERE task_id=?", (candidate["task_id"],))
                if not row or row["status"] not in ACTIVE_TASK_STATES or not row["lease_expires_at"] or row["lease_expires_at"] > now:
                    continue
                if int(row["attempt"]) < int(row["max_attempts"]):
                    self.db.execute(
                        """UPDATE monitor_tasks_210 SET status='queued',available_at=?,lease_owner='',lease_token='',lease_expires_at='',
                        heartbeat_at='',error_code='LEASE_EXPIRED',error_text='worker lease expired; task recovered',revision=revision+1,updated_at=?
                        WHERE task_id=?""",
                        (now, now, row["task_id"]),
                    )
                    recovered += 1
                    event_type = "lease_recovered"
                else:
                    self.db.execute(
                        """UPDATE monitor_tasks_210 SET status='dead_letter',lease_owner='',lease_token='',lease_expires_at='',heartbeat_at='',
                        error_code='LEASE_EXPIRED_MAX_ATTEMPTS',error_text='lease expired after maximum attempts',revision=revision+1,updated_at=?
                        WHERE task_id=?""",
                        (now, row["task_id"]),
                    )
                    self._store_dead_letter(row, "LEASE_EXPIRED_MAX_ATTEMPTS", "lease expired after maximum attempts", now)
                    self._block_descendants(row["task_id"], now)
                    dead += 1
                    event_type = "lease_dead_lettered"
                self._refresh_run_state(row["run_id"], now)
            self._event_for_task(row, event_type, {"previous_worker": row["lease_owner"], "previous_attempt": row["attempt"]})
        return {"recovered": recovered, "dead_lettered": dead, "valid_leases_untouched": True}

    def cancel_task(self, *, task_id: str, reason: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"MONITOR TASK 210 {task_id} ABBRECHEN":
            raise PermissionError("explicit approval required")
        row = self.db.one("SELECT * FROM monitor_tasks_210 WHERE task_id=?", (task_id,))
        if not row:
            raise KeyError(task_id)
        if row["status"] in TERMINAL_TASK_STATES:
            return {"task_id": task_id, "status": row["status"], "idempotent": True}
        now = now_ts()
        with self.db.transaction(immediate=True):
            self.db.execute(
                """UPDATE monitor_tasks_210 SET status='cancelled',lease_owner='',lease_token='',lease_expires_at='',heartbeat_at='',
                error_code='CANCELLED_BY_ANALYST',error_text=?,revision=revision+1,updated_at=? WHERE task_id=?""",
                (_safe_text(reason, 1000), now, task_id),
            )
            self._block_descendants(task_id, now)
            self._refresh_run_state(row["run_id"], now)
        self._event_for_task(row, "task_cancelled", {"reason": _safe_text(reason, 500)})
        return {"task_id": task_id, "status": "cancelled", "idempotent": False}

    # ------------------------------------------------------------------
    # Observation deduplication, claim impact and alert outbox
    # ------------------------------------------------------------------
    def persist_observation(
        self,
        *,
        monitor_id: str,
        run_id: str,
        source_id: str,
        source_ref: str,
        published_at: str,
        title: str,
        summary: str,
        claims: Sequence[Mapping[str, Any]],
        entities: Sequence[Mapping[str, Any]],
        provenance: Mapping[str, Any],
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"OBSERVATION 210 {monitor_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        canonical_ref = _canonical_source_ref(source_ref)
        clean_claims = self._redact_payload(list(claims))
        clean_entities = self._redact_payload(list(entities))
        clean_provenance = self._redact_payload(dict(provenance))
        clean_title = _safe_text(title, 1000)
        clean_summary = _safe_text(summary, 8000)
        content_payload = {
            "canonical_source_ref": canonical_ref,
            "title": clean_title.strip(),
            "summary": " ".join(clean_summary.split()),
            "claims": clean_claims,
            "entities": clean_entities,
        }
        content_hash = _sha256(content_payload)
        claim_fp = _sha256([
            {
                "subject": _safe_text(c.get("subject"), 500).casefold(),
                "predicate": _safe_text(c.get("predicate"), 500).casefold(),
                "object": _safe_text(c.get("object") or c.get("value"), 1000).casefold(),
                "time": _safe_text(c.get("time") or c.get("date"), 200),
                "location": _safe_text(c.get("location"), 500).casefold(),
            }
            for c in clean_claims if isinstance(c, Mapping)
        ])
        observed = now_ts()
        injection = any(marker in (clean_title + " " + clean_summary).casefold() for marker in PROMPT_INJECTION_MARKERS)
        with self.db.transaction(immediate=True):
            existing = self.db.one(
                "SELECT * FROM monitor_observations_210 WHERE monitor_id=? AND source_id=? AND content_sha256=?",
                (monitor_id, source_id, content_hash),
            )
            if existing:
                self.db.execute(
                    "UPDATE monitor_observations_210 SET duplicate_count=duplicate_count+1,last_seen_at=? WHERE observation_id=?",
                    (observed, existing["observation_id"]),
                )
                return {
                    "observation_id": existing["observation_id"],
                    "duplicate": True,
                    "duplicate_count": int(existing["duplicate_count"]) + 1,
                    "content_sha256": content_hash,
                    "semantic_action": "candidate_only",
                }
            observation_id = new_id("obs210")
            self.db.execute(
                """INSERT INTO monitor_observations_210 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    observation_id,
                    monitor_id,
                    run_id,
                    source_id,
                    canonical_ref,
                    observed,
                    published_at or "",
                    clean_title,
                    clean_summary,
                    dumps(clean_claims),
                    dumps(clean_entities),
                    dumps(clean_provenance),
                    content_hash,
                    claim_fp,
                    0,
                    observed,
                    1 if injection else 0,
                    "candidate",
                    "possible_duplicate_review_only",
                    observed,
                ),
            )
        self._event(monitor_id, run_id, "", "observation_persisted", {
            "observation_id": observation_id,
            "source_id": source_id,
            "content_sha256": content_hash,
            "prompt_injection_candidate": injection,
        }, new_id("corr210"))
        return {
            "observation_id": observation_id,
            "duplicate": False,
            "content_sha256": content_hash,
            "claim_fingerprint": claim_fp,
            "review_status": "candidate",
            "prompt_injection_candidate": injection,
            "automatic_identity_confirmation": False,
        }

    def assess_claim_impact(
        self,
        *,
        monitor_id: str,
        run_id: str,
        observation_id: str,
        claim_id: str,
        old_state: Mapping[str, Any],
        new_state: Mapping[str, Any],
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"CLAIM IMPACT 210 {claim_id} BEWERTEN":
            raise PermissionError("explicit approval required")
        observation = self.db.one("SELECT * FROM monitor_observations_210 WHERE observation_id=?", (observation_id,))
        if not observation:
            raise KeyError(observation_id)
        impact_type, severity, reason_code, explanation = self._classify_impact(observation, old_state, new_state)
        idem = _sha256({
            "monitor_id": monitor_id,
            "observation_id": observation_id,
            "claim_id": claim_id,
            "old": old_state,
            "new": new_state,
            "type": impact_type,
        })
        with self.db.transaction(immediate=True):
            existing = self.db.one("SELECT * FROM claim_impacts_210 WHERE idempotency_key=?", (idem,))
            if existing:
                return dict(existing) | {"idempotent_replay": True}
            impact_id = new_id("impact210")
            self.db.execute(
                "INSERT INTO claim_impacts_210 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    impact_id,
                    monitor_id,
                    run_id,
                    observation_id,
                    claim_id,
                    impact_type,
                    severity,
                    reason_code,
                    explanation,
                    dumps(self._redact_payload(dict(old_state))),
                    dumps(self._redact_payload(dict(new_state))),
                    idem,
                    "candidate",
                    now_ts(),
                ),
            )
        self._event(monitor_id, run_id, "", "claim_impact_candidate", {
            "impact_id": impact_id,
            "claim_id": claim_id,
            "impact_type": impact_type,
            "severity": severity,
        }, new_id("corr210"))
        return {
            "impact_id": impact_id,
            "impact_type": impact_type,
            "severity": severity,
            "reason_code": reason_code,
            "explanation": explanation,
            "review_status": "candidate",
            "idempotent_replay": False,
        }

    def create_alert_for_impact(
        self,
        *,
        impact_id: str,
        case_id: str,
        title: str,
        recommended_action: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"ALERT 210 {impact_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        impact = self.db.one("SELECT * FROM claim_impacts_210 WHERE impact_id=?", (impact_id,))
        if not impact:
            raise KeyError(impact_id)
        dedup_key = _sha256({
            "monitor_id": impact["monitor_id"],
            "claim_id": impact["claim_id"],
            "impact_type": impact["impact_type"],
            "severity": impact["severity"],
        })
        now = now_ts()
        with self.db.transaction(immediate=True):
            existing = self.db.one("SELECT * FROM alerts_210 WHERE alert_dedup_key=?", (dedup_key,))
            if existing:
                return dict(existing) | {"idempotent_replay": True, "external_delivery": False}
            alert_id = new_id("alert210")
            self.db.execute(
                "INSERT INTO alerts_210 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    alert_id,
                    impact["monitor_id"],
                    impact["run_id"],
                    case_id,
                    impact_id,
                    impact["severity"],
                    _safe_text(title, 500),
                    _safe_text(impact["explanation"], 4000),
                    _safe_text(recommended_action, 1000),
                    "pending_review",
                    dedup_key,
                    now,
                    "",
                    "",
                ),
            )
            outbox_id = new_id("outbox210")
            delivery_key = _sha256({"alert_id": alert_id, "channel": "local_review_ui"})
            self.db.execute(
                "INSERT INTO alert_outbox_210 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (outbox_id, alert_id, "local_review_ui", "pending", delivery_key, 0, now, "", "", now, now),
            )
        self._event(impact["monitor_id"], impact["run_id"], "", "alert_created", {
            "alert_id": alert_id,
            "impact_id": impact_id,
            "severity": impact["severity"],
            "external_delivery": False,
        }, new_id("corr210"))
        return {
            "alert_id": alert_id,
            "status": "pending_review",
            "outbox_id": outbox_id,
            "local_delivery": True,
            "external_delivery": False,
            "idempotent_replay": False,
        }

    def deliver_local_outbox(self, *, limit: int = 50) -> dict[str, Any]:
        now = now_ts()
        delivered = 0
        rows = self.db.all(
            "SELECT * FROM alert_outbox_210 WHERE status IN ('pending','retry_wait') AND available_at<=? ORDER BY created_at LIMIT ?",
            (now, max(1, min(int(limit), 500))),
        )
        for row in rows:
            with self.db.transaction(immediate=True):
                current = self.db.one("SELECT * FROM alert_outbox_210 WHERE outbox_id=?", (row["outbox_id"],))
                if not current or current["status"] not in {"pending", "retry_wait"}:
                    continue
                self.db.execute(
                    "UPDATE alert_outbox_210 SET status='delivered_local',attempt=attempt+1,delivered_at=?,updated_at=? WHERE outbox_id=?",
                    (now, now, row["outbox_id"]),
                )
                delivered += 1
        return {"delivered": delivered, "channel": "local_review_ui", "external_delivery": False}

    def acknowledge_alert(self, *, alert_id: str, analyst: str, decision: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"ALERT 210 {alert_id} BEARBEITEN":
            raise PermissionError("explicit approval required")
        if decision not in {"acknowledged", "dismissed", "needs_investigation"}:
            raise ValueError("invalid alert decision")
        row = self.db.one("SELECT * FROM alerts_210 WHERE alert_id=?", (alert_id,))
        if not row:
            raise KeyError(alert_id)
        now = now_ts()
        self.db.execute(
            "UPDATE alerts_210 SET status=?,acknowledged_at=?,acknowledged_by=? WHERE alert_id=?",
            (decision, now, _safe_text(analyst, 200), alert_id),
        )
        self._event(row["monitor_id"], row["run_id"], "", "alert_reviewed", {"alert_id": alert_id, "decision": decision, "analyst": analyst}, new_id("corr210"))
        return {"alert_id": alert_id, "status": decision, "reviewed_by": analyst}

    # ------------------------------------------------------------------
    # Runtime and dashboard
    # ------------------------------------------------------------------
    def execute_builtin_task(self, *, task_id: str, worker_id: str, lease_token: str) -> dict[str, Any]:
        """Execute only local, deterministic Build-210 control tasks.

        Source collection, model inference and social/network access are never
        simulated here; those task types require their approved executors.
        """
        row = self._require_current_lease(task_id, worker_id, lease_token)
        task_type = row["task_type"]
        if task_type not in {"evaluate_alert_policy", "deliver_local_alert"}:
            raise ValueError("task type requires an approved external or model executor")
        self.start_task(task_id=task_id, worker_id=worker_id, lease_token=lease_token)
        if task_type == "evaluate_alert_policy":
            run = self.db.one("SELECT * FROM monitor_runs_210 WHERE run_id=?", (row["run_id"],)) or {}
            schedule = self.db.one("SELECT * FROM monitor_schedules_210 WHERE schedule_id=?", (run.get("schedule_id", ""),)) or {}
            impacts = self.db.all(
                "SELECT * FROM claim_impacts_210 WHERE run_id=? AND severity IN ('medium','high','critical') ORDER BY created_at",
                (row["run_id"],),
            )
            alert_ids: list[str] = []
            for impact in impacts:
                created = self.create_alert_for_impact(
                    impact_id=impact["impact_id"],
                    case_id=row["case_id"],
                    title=f"{impact['impact_type']}: {impact['claim_id']}",
                    recommended_action="Candidate evidence and provenance must be reviewed by an analyst.",
                    confirmation=f"ALERT 210 {impact['impact_id']} ANLEGEN",
                )
                alert_ids.append(created["alert_id"])
            output = {"evaluated_impacts": len(impacts), "alert_ids": alert_ids, "external_delivery": False}
        else:
            output = self.deliver_local_outbox(limit=100)
        return self.complete_task(task_id=task_id, worker_id=worker_id, lease_token=lease_token, output=output)

    def scheduler_tick(self, *, owner_id: str) -> dict[str, Any]:
        recovered = self.recover_expired_leases()
        schedules = self.materialize_due_runs(owner_id=owner_id)
        outbox = self.deliver_local_outbox()
        return {
            "build": self.BUILD,
            "leader": schedules["leader"],
            "materialized": schedules["materialized"],
            "recovered": recovered["recovered"],
            "dead_lettered": recovered["dead_lettered"],
            "local_alerts_delivered": outbox["delivered"],
            "external_actions": 0,
        }

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        def count(sql: str, params: Sequence[Any] = ()) -> int:
            row = self.db.one(sql, params) or {}
            return int(row.get("n") or 0)

        schedules = self.db.all(
            "SELECT * FROM monitor_schedules_210 WHERE case_id=? ORDER BY updated_at DESC LIMIT 50",
            (case_id,),
        )
        runs = self.db.all(
            "SELECT * FROM monitor_runs_210 WHERE case_id=? ORDER BY created_at DESC LIMIT 50",
            (case_id,),
        )
        tasks = self.db.all(
            "SELECT * FROM monitor_tasks_210 WHERE case_id=? ORDER BY created_at DESC LIMIT 100",
            (case_id,),
        )
        alerts = self.db.all(
            "SELECT * FROM alerts_210 WHERE case_id=? ORDER BY created_at DESC LIMIT 50",
            (case_id,),
        )
        return {
            "build": self.BUILD,
            "case_id": case_id,
            "counts": {
                "schedules": len(schedules),
                "active_schedules": sum(1 for r in schedules if r["status"] == "active"),
                "runs": len(runs),
                "ready_tasks": count("SELECT COUNT(*) AS n FROM monitor_tasks_210 WHERE case_id=? AND status IN ('queued','retry_wait') AND remaining_dependencies=0", (case_id,)),
                "active_tasks": count("SELECT COUNT(*) AS n FROM monitor_tasks_210 WHERE case_id=? AND status IN ('leased','running')", (case_id,)),
                "dead_letter": count("SELECT COUNT(*) AS n FROM monitor_tasks_210 WHERE case_id=? AND status='dead_letter'", (case_id,)),
                "pending_alerts": sum(1 for r in alerts if r["status"] == "pending_review"),
            },
            "schedules": schedules,
            "runs": runs,
            "tasks": tasks,
            "alerts": alerts,
            "guarantees": {
                "valid_leases_survive_restart": True,
                "expired_leases_recovered": True,
                "terminal_commits_idempotent": True,
                "semantic_dedup_auto_delete": False,
                "external_alerts": False,
                "human_review_required": True,
            },
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        data = self.dashboard(case_id=case_id)
        esc = lambda v: html.escape(str(v or ""), quote=True)
        c = data["counts"]
        schedules = "".join(
            """<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>
            <form class='inline' method='post' action='/monitor210/schedule-action'>
            <input type='hidden' name='csrf' value='{}'><input type='hidden' name='case_id' value='{}'>
            <input type='hidden' name='schedule_id' value='{}'>
            <button class='small' name='action' value='activate'>Aktivieren</button>
            <button class='small ghost' name='action' value='run'>Jetzt ausführen</button>
            <button class='small danger' name='action' value='pause'>Pausieren</button></form></td></tr>""".format(
                esc(row["name"]), esc(row["status"]), esc(row["next_run_at"]), esc(int(row["interval_seconds"]) // 60),
                esc(csrf), esc(case_id), esc(row["schedule_id"]),
            )
            for row in data["schedules"]
        ) or "<tr><td colspan='5'>Noch keine Monitoring-Schedule.</td></tr>"
        tasks = "".join(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                esc(row["task_type"]), esc(row["source_id"] or "—"), esc(row["status"]), esc(row["attempt"]), esc(row["remaining_dependencies"])
            )
            for row in data["tasks"][:40]
        ) or "<tr><td colspan='5'>Keine Tasks vorhanden.</td></tr>"
        alerts = "".join(
            """<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>
            <form class='inline' method='post' action='/monitor210/alert'>
            <input type='hidden' name='csrf' value='{}'><input type='hidden' name='case_id' value='{}'>
            <input type='hidden' name='alert_id' value='{}'>
            <button class='small' name='decision' value='acknowledged'>Bestätigen</button>
            <button class='small ghost' name='decision' value='needs_investigation'>Weiter ermitteln</button>
            <button class='small danger' name='decision' value='dismissed'>Verwerfen</button></form></td></tr>""".format(
                esc(row["severity"]), esc(row["title"]), esc(row["status"]), esc(row["created_at"]),
                esc(csrf), esc(case_id), esc(row["alert_id"]),
            )
            for row in data["alerts"]
        ) or "<tr><td colspan='5'>Keine Alerts vorhanden.</td></tr>"
        return f"""
        <div class='notice'><b>Monitoring &amp; Alert Operations 210</b><br>
        Dauerhafte Scheduler, atomare Leases, selektive Neustart-Recovery, mehrstufige Deduplikation und Claim-Impact.
        AI-Ermittler, AI-Chat, Social-Media-Recherche und OPSEC bleiben verbindliche Querschnittsanforderungen. Externe Alerts und automatische Identitätsbestätigung bleiben deaktiviert.</div>
        <div class='metrics'>
          <div class='metric'><div class='label'>Schedules</div><div class='value'>{c['schedules']}</div></div>
          <div class='metric'><div class='label'>Aktiv</div><div class='value'>{c['active_schedules']}</div></div>
          <div class='metric'><div class='label'>Bereite Tasks</div><div class='value'>{c['ready_tasks']}</div></div>
          <div class='metric'><div class='label'>Aktive Leases</div><div class='value'>{c['active_tasks']}</div></div>
          <div class='metric'><div class='label'>Dead Letter</div><div class='value'>{c['dead_letter']}</div></div>
          <div class='metric'><div class='label'>Alerts im Review</div><div class='value'>{c['pending_alerts']}</div></div>
        </div>
        <div class='panel'><h2>Neue Monitoring-Schedule</h2>
          <form method='post' action='/monitor210/schedule'>
            <input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'>
            <div class='form-grid'>
              <div class='field'><label>Name</label><input name='name' required></div>
              <div class='field'><label>Intervall in Minuten</label><input name='interval_minutes' type='number' min='1' value='60' required></div>
              <div class='field'><label>Quellen-IDs, komma­getrennt</label><input name='source_ids' placeholder='gdelt_monitor, bluesky_search_watch'></div>
              <div class='field'><label>Misfire-Policy</label><select name='misfire_policy'><option>coalesce</option><option>skip</option><option>bounded_catchup</option><option>manual</option></select></div>
            </div>
            <div class='field'><label>Monitoring-Frage</label><textarea name='question' rows='3' required></textarea></div>
            <p><button>Schedule als Entwurf anlegen</button></p>
          </form>
        </div>
        <div class='panel'><h2>Schedules</h2><div class='table-wrap'><table><thead><tr><th>Name</th><th>Status</th><th>Nächster Lauf</th><th>Minuten</th><th>Steuerung</th></tr></thead><tbody>{schedules}</tbody></table></div></div>
        <div class='panel'><h2>Task-DAG und Workerstatus</h2><div class='table-wrap'><table><thead><tr><th>Task</th><th>Quelle</th><th>Status</th><th>Versuch</th><th>Offene Abhängigkeiten</th></tr></thead><tbody>{tasks}</tbody></table></div></div>
        <div class='panel'><h2>Alert-Review</h2><div class='table-wrap'><table><thead><tr><th>Schwere</th><th>Titel</th><th>Status</th><th>Zeit</th><th>Entscheidung</th></tr></thead><tbody>{alerts}</tbody></table></div></div>
        """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _source_polling_floor(self, source_ids: Sequence[str]) -> int:
        floors: list[int] = []
        for source_id in source_ids:
            row = self.db.one("SELECT polling_floor_minutes FROM monitoring_source_profiles_195 WHERE source_id=?", (source_id,))
            if row:
                floors.append(int(row["polling_floor_minutes"]))
                continue
            runtime = self.db.one("SELECT min_interval_seconds FROM source_runtime_profiles_201 WHERE source_id=?", (source_id,))
            if runtime:
                floors.append(max(1, (int(runtime["min_interval_seconds"]) + 59) // 60))
        return max(floors or [1])

    def _require_schedule(self, schedule_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM monitor_schedules_210 WHERE schedule_id=?", (schedule_id,))
        if not row:
            raise KeyError(schedule_id)
        return row

    def _handle_due_schedule(self, schedule: Mapping[str, Any], now: str) -> dict[str, Any]:
        scheduled_for = schedule["next_run_at"]
        now_dt = _parse_ts(now)
        due_dt = _parse_ts(scheduled_for)
        interval = timedelta(seconds=int(schedule["interval_seconds"]))
        lateness = max(0.0, (now_dt - due_dt).total_seconds())
        missed = int(lateness // max(1, int(schedule["interval_seconds"])))
        policy = schedule["misfire_policy"]
        if missed > 0 and policy == "manual":
            self.db.execute(
                "UPDATE monitor_schedules_210 SET status='paused',revision=revision+1,updated_at=? WHERE schedule_id=?",
                (now, schedule["schedule_id"]),
            )
            self._event(schedule["monitor_id"], "", "", "schedule_paused_misfire", {"schedule_id": schedule["schedule_id"], "missed": missed}, new_id("corr210"))
            return {"created": False, "reason": "manual_misfire_review"}
        if missed > 0 and policy == "skip":
            next_dt = due_dt
            while next_dt <= now_dt:
                next_dt += interval
            self.db.execute(
                "UPDATE monitor_schedules_210 SET next_run_at=?,revision=revision+1,updated_at=? WHERE schedule_id=?",
                (_iso(next_dt), now, schedule["schedule_id"]),
            )
            self._event(schedule["monitor_id"], "", "", "schedule_misfire_skipped", {"schedule_id": schedule["schedule_id"], "missed": missed}, new_id("corr210"))
            return {"created": False, "reason": "misfire_skipped"}
        result = self._materialize_run(schedule, scheduled_for=scheduled_for, trigger_type="scheduled")
        return {"created": not result.get("idempotent_replay", False), **result}

    def _materialize_run(self, schedule: Mapping[str, Any], *, scheduled_for: str, trigger_type: str) -> dict[str, Any]:
        correlation_id = new_id("corr210")
        run_id = new_id("run210")
        now = now_ts()
        source_ids = _loads(schedule["source_ids_json"], []) or ["local_fixture_210"]
        with self.db.transaction(immediate=True):
            existing = self.db.one(
                "SELECT * FROM monitor_runs_210 WHERE schedule_id=? AND scheduled_for=?",
                (schedule["schedule_id"], scheduled_for),
            )
            if existing:
                return {"run_id": existing["run_id"], "status": existing["status"], "idempotent_replay": True, "tasks": 0}
            self.db.execute(
                "INSERT INTO monitor_runs_210 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, schedule["schedule_id"], schedule["case_id"], scheduled_for, trigger_type, "queued", correlation_id, now, "", "", ""),
            )
            task_count = self._create_task_dag(run_id, schedule, source_ids, scheduled_for, now)
            next_run = self._next_scheduled_time(schedule, scheduled_for)
            self.db.execute(
                """UPDATE monitor_schedules_210 SET last_run_at=?,next_run_at=?,revision=revision+1,updated_at=?
                WHERE schedule_id=?""",
                (scheduled_for, next_run, now, schedule["schedule_id"]),
            )
        self._event(schedule["monitor_id"], run_id, "", "run_materialized", {
            "schedule_id": schedule["schedule_id"],
            "scheduled_for": scheduled_for,
            "trigger_type": trigger_type,
            "task_count": task_count,
            "source_ids": source_ids,
        }, correlation_id)
        return {"run_id": run_id, "status": "queued", "idempotent_replay": False, "tasks": task_count, "scheduled_for": scheduled_for}

    def _create_task_dag(
        self,
        run_id: str,
        schedule: Mapping[str, Any],
        source_ids: Sequence[str],
        scheduled_for: str,
        now: str,
    ) -> int:
        all_impact_and_ai: list[str] = []
        count = 0
        policy = _loads(schedule["policy_json"], {})
        for source_id in source_ids:
            source_partition = _sha256(f"{schedule['case_id']}:{schedule['monitor_id']}:{source_id}")[:24]
            common = {
                "schema_version": self.BUILD,
                "schedule_id": schedule["schedule_id"],
                "monitor_id": schedule["monitor_id"],
                "case_id": schedule["case_id"],
                "question": schedule["question"],
                "source_id": source_id,
                "scheduled_for": scheduled_for,
                "policy": policy,
                "content_is_untrusted_data": True,
            }
            collect = self._insert_task(run_id, schedule["case_id"], "collect_source", source_partition, source_id, 90, [], common, scheduled_for, now)
            normalize = self._insert_task(run_id, schedule["case_id"], "normalize_observation", source_partition, source_id, 80, [collect], common, scheduled_for, now)
            dedup = self._insert_task(run_id, schedule["case_id"], "deduplicate_observation", source_partition, source_id, 70, [normalize], common, scheduled_for, now)
            impact = self._insert_task(run_id, schedule["case_id"], "assess_claim_impact", source_partition, source_id, 60, [dedup], common, scheduled_for, now)
            ai_review = self._insert_task(run_id, schedule["case_id"], "ai_investigator_review", source_partition, source_id, 55, [impact], common | {
                "ai_role": "co_investigator",
                "citations_required": True,
                "social_research_deepening": True,
                "suggestions_only": True,
            }, scheduled_for, now)
            all_impact_and_ai.extend([impact, ai_review])
            count += 5
        alert_partition = _sha256(f"{schedule['case_id']}:{schedule['monitor_id']}:alerts")[:24]
        alert = self._insert_task(
            run_id, schedule["case_id"], "evaluate_alert_policy", alert_partition, "", 40,
            all_impact_and_ai, {
                "schema_version": self.BUILD,
                "monitor_id": schedule["monitor_id"],
                "case_id": schedule["case_id"],
                "human_review_required": True,
                "external_delivery_enabled": False,
            }, scheduled_for, now,
        )
        self._insert_task(
            run_id, schedule["case_id"], "deliver_local_alert", alert_partition, "", 30,
            [alert], {
                "schema_version": self.BUILD,
                "channel": "local_review_ui",
                "external_delivery_enabled": False,
            }, scheduled_for, now,
        )
        return count + 2

    def _insert_task(
        self,
        run_id: str,
        case_id: str,
        task_type: str,
        partition_key: str,
        source_id: str,
        priority: int,
        dependencies: Sequence[str],
        input_payload: Mapping[str, Any],
        scheduled_for: str,
        now: str,
    ) -> str:
        task_id = new_id("task210")
        idem = _sha256({
            "run_id": run_id,
            "task_type": task_type,
            "source_id": source_id,
            "scheduled_for": scheduled_for,
        })
        self.db.execute(
            """INSERT INTO monitor_tasks_210 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                task_id, run_id, case_id, task_type, partition_key, source_id, priority, "queued", 0, 3,
                len(dependencies), now, "", "", "", "", 0, idem, dumps(self._redact_payload(dict(input_payload))),
                dumps({}), "", dumps({}), "", "", now, now,
            ),
        )
        for parent in dependencies:
            self.db.execute(
                "INSERT INTO monitor_task_dependencies_210 VALUES(?,?,?)",
                (task_id, parent, now),
            )
        return task_id

    def _next_scheduled_time(self, schedule: Mapping[str, Any], scheduled_for: str) -> str:
        base = _parse_ts(scheduled_for) + timedelta(seconds=int(schedule["interval_seconds"]))
        jitter = int(schedule["jitter_seconds"])
        if jitter:
            deterministic = int(_sha256(f"{schedule['schedule_id']}:{_iso(base)}")[:8], 16)
            base += timedelta(seconds=deterministic % (jitter + 1))
        return _iso(base)

    def _source_slot_available(self, source_id: str) -> bool:
        if not source_id:
            return True
        profile = self.db.one("SELECT max_parallel FROM source_runtime_profiles_201 WHERE source_id=?", (source_id,))
        max_parallel = int(profile["max_parallel"]) if profile else 2
        circuit = self.db.one("SELECT state,retry_after FROM source_circuits_201 WHERE source_id=?", (source_id,))
        if circuit and circuit["state"] == "open" and (not circuit["retry_after"] or _parse_ts(circuit["retry_after"]) > _utc_now()):
            return False
        active = self.db.one(
            "SELECT COUNT(*) AS n FROM monitor_tasks_210 WHERE source_id=? AND status IN ('leased','running')",
            (source_id,),
        )
        return int((active or {}).get("n") or 0) < max_parallel

    def _require_current_lease(
        self,
        task_id: str,
        worker_id: str,
        lease_token: str,
        *,
        row: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        current = dict(row or self.db.one("SELECT * FROM monitor_tasks_210 WHERE task_id=?", (task_id,)) or {})
        if not current:
            raise KeyError(task_id)
        if current["status"] not in ACTIVE_TASK_STATES:
            raise RuntimeError("task has no active lease")
        if current["lease_owner"] != worker_id or not secrets.compare_digest(current["lease_token"], lease_token):
            raise PermissionError("lease conflict")
        if _parse_ts(current["lease_expires_at"]) <= _utc_now():
            raise PermissionError("lease expired")
        return current

    def _refresh_run_state(self, run_id: str, now: str) -> None:
        counts = self.db.all("SELECT status,COUNT(*) AS n FROM monitor_tasks_210 WHERE run_id=? GROUP BY status", (run_id,))
        by_status = {r["status"]: int(r["n"]) for r in counts}
        if not by_status:
            return
        nonterminal = sum(n for status, n in by_status.items() if status not in TERMINAL_TASK_STATES)
        if nonterminal:
            status = "running" if any(s in by_status for s in ACTIVE_TASK_STATES) else "queued"
            self.db.execute(
                "UPDATE monitor_runs_210 SET status=?,started_at=CASE WHEN started_at='' THEN ? ELSE started_at END WHERE run_id=?",
                (status, now, run_id),
            )
        else:
            failed = by_status.get("dead_letter", 0) + by_status.get("blocked_dependency", 0)
            status = "completed_with_errors" if failed else "completed"
            self.db.execute("UPDATE monitor_runs_210 SET status=?,finished_at=? WHERE run_id=?", (status, now, run_id))

    def _store_dead_letter(self, row: Mapping[str, Any], error_code: str, error_text: str, now: str) -> None:
        self.db.execute(
            """INSERT OR IGNORE INTO dead_letter_tasks_210 VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                new_id("dead210"), row["task_id"], row["run_id"], row["task_type"], _safe_text(error_code, 100),
                _safe_text(error_text, 1000), dumps(self._redact_payload(_loads(row["input_json"], {}))), now, "pending_review",
            ),
        )

    def _block_descendants(self, task_id: str, now: str) -> None:
        frontier = [task_id]
        seen: set[str] = set()
        while frontier:
            parent = frontier.pop()
            for child in self.db.all("SELECT task_id FROM monitor_task_dependencies_210 WHERE depends_on_task_id=?", (parent,)):
                child_id = child["task_id"]
                if child_id in seen:
                    continue
                seen.add(child_id)
                row = self.db.one("SELECT status FROM monitor_tasks_210 WHERE task_id=?", (child_id,))
                if row and row["status"] not in TERMINAL_TASK_STATES:
                    self.db.execute(
                        """UPDATE monitor_tasks_210 SET status='blocked_dependency',error_code='UPSTREAM_TERMINAL_FAILURE',
                        error_text='upstream task failed or was cancelled',lease_owner='',lease_token='',lease_expires_at='',heartbeat_at='',
                        revision=revision+1,updated_at=? WHERE task_id=?""",
                        (now, child_id),
                    )
                frontier.append(child_id)

    def _classify_impact(
        self,
        observation: Mapping[str, Any],
        old_state: Mapping[str, Any],
        new_state: Mapping[str, Any],
    ) -> tuple[str, str, str, str]:
        if int(observation.get("prompt_injection_candidate") or 0):
            return ("manual_review_required", "high", "UNTRUSTED_SOURCE_CONTENT", "Source content contains a prompt-injection candidate and requires analyst review.")
        relation = str(new_state.get("relation") or "").casefold()
        old_value = old_state.get("value")
        new_value = new_state.get("value")
        if old_value != new_value and relation in {"contradicts", "contradiction", "widerspricht"}:
            return ("claim_contradicted", "high", "VALUE_CONTRADICTION", "The new candidate evidence contradicts the stored claim value.")
        if old_value != new_value:
            return ("claim_changed", "medium", "VALUE_CHANGED", "The candidate claim value changed and requires review.")
        if old_state.get("review_status") != new_state.get("review_status"):
            return ("claim_status_changed", "medium", "REVIEW_STATUS_CHANGED", "The candidate review status changed.")
        return ("corroboration_added", "low", "NEW_SUPPORTING_EVIDENCE", "Additional candidate evidence supports the existing claim without confirming it automatically.")

    def _redact_payload(self, value: Any) -> Any:
        secret_markers = {"token", "secret", "password", "authorization", "cookie", "session", "api_key", "private_key"}
        if isinstance(value, Mapping):
            result: dict[str, Any] = {}
            for key, item in value.items():
                lowered = str(key).casefold().replace("-", "_")
                result[str(key)] = "[REDACTED]" if any(marker in lowered for marker in secret_markers) else self._redact_payload(item)
            return result
        if isinstance(value, list):
            return [self._redact_payload(item) for item in value[:1000]]
        if isinstance(value, tuple):
            return [self._redact_payload(item) for item in value[:1000]]
        if isinstance(value, str):
            return _safe_text(value, 20000)
        return value

    def _event_for_task(self, task: Mapping[str, Any], event_type: str, payload: Mapping[str, Any]) -> None:
        run = self.db.one("SELECT schedule_id,correlation_id FROM monitor_runs_210 WHERE run_id=?", (task["run_id"],)) or {}
        schedule = self.db.one("SELECT monitor_id FROM monitor_schedules_210 WHERE schedule_id=?", (run.get("schedule_id", ""),)) or {}
        self._event(schedule.get("monitor_id", ""), task["run_id"], task["task_id"], event_type, payload, run.get("correlation_id", new_id("corr210")))

    def _event(
        self,
        monitor_id: str,
        run_id: str,
        task_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        correlation_id: str,
    ) -> None:
        monitor_id = monitor_id or "system"
        previous = self.db.one(
            "SELECT event_hash FROM monitor_events_210 WHERE monitor_id=? ORDER BY created_at DESC,event_id DESC LIMIT 1",
            (monitor_id,),
        )
        prev_hash = previous["event_hash"] if previous else ""
        created = now_ts()
        clean = self._redact_payload(dict(payload))
        event_payload = {
            "monitor_id": monitor_id,
            "run_id": run_id,
            "task_id": task_id,
            "event_type": event_type,
            "actor": self.actor,
            "correlation_id": correlation_id,
            "payload": clean,
            "created_at": created,
            "prev_hash": prev_hash,
        }
        event_hash = _sha256(event_payload)
        self.db.execute(
            "INSERT INTO monitor_events_210 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (new_id("event210"), monitor_id, run_id, task_id, event_type, self.actor, correlation_id, dumps(clean), created, prev_hash, event_hash),
        )
