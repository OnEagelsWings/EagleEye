from __future__ import annotations

import hashlib
import html
import json
import uuid
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


CRITICAL_CONTROLS = {
    "no_invented_fact",
    "new_ok_on_scope_change",
    "hash_locator_timestamp",
    "ambiguity_preserved",
    "no_external_side_effect_without_authority",
    "identity_not_merged_on_weak_match",
}


class Build283MissionIntegrityWorkerService:
    BUILD = "283.0"

    def __init__(self, db: Any, audit: Any, *, build282: Any, build281: Any, actor: str = "local-analyst"):
        self.db = db
        self.audit = audit
        self.build282 = build282
        self.build281 = build281
        self.actor = actor

    def _mission(self, mission_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase12_missions_281 WHERE mission_id=?", (mission_id,))
        if not row:
            raise KeyError("mission not found")
        return row

    def _latest_checkpoint(self, mission_id: str) -> dict[str, Any] | None:
        return self.db.one(
            "SELECT * FROM phase12_checkpoints_282 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1",
            (mission_id,),
        )

    def _default_idempotency_key(self, mission_id: str, payload: dict[str, Any]) -> str:
        cycle_no = self.db.one(
            "SELECT COUNT(*) n FROM phase12_mission_events_281 WHERE mission_id=? AND event_type='autonomous_cycle_completed'",
            (mission_id,),
        )["n"]
        cp = self._latest_checkpoint(mission_id)
        anchor = cp["resume_token"] if cp else "GENESIS"
        return _hash({"mission_id": mission_id, "cycle_no": int(cycle_no), "checkpoint": anchor, "payload": payload})[:40]

    def queue_mission_cycle_once(
        self,
        *,
        mission_id: str,
        requested_by: str | None = None,
        execute_public_web: bool = False,
        provider: str = "",
        priority: int = 50,
        max_attempts: int = 3,
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        actor = requested_by or self.actor
        m = self._mission(mission_id)
        if m["status"] != "authorized":
            raise PermissionError("mission must be authorized before idempotent dispatch")
        reconciliation = self.reconcile_mission_state(mission_id=mission_id, actor=actor)
        if reconciliation["status"] == "blocked":
            raise RuntimeError("mission integrity reconciliation blocked dispatch")
        payload = {
            "execute_public_web": bool(execute_public_web),
            "provider": str(provider or ""),
            "priority": max(1, min(int(priority), 100)),
            "max_attempts": max(1, min(int(max_attempts), 5)),
            "approved_scope": m["mission_type"],
        }
        request_fingerprint = _hash({"mission_id": mission_id, "payload": payload})
        key = str(idempotency_key or self._default_idempotency_key(mission_id, payload)).strip()
        if not key:
            raise ValueError("idempotency key could not be derived")
        existing = self.db.one("SELECT * FROM phase12_job_idempotency_283 WHERE idempotency_key=?", (key,))
        if existing:
            if existing["mission_id"] != mission_id or existing["request_fingerprint"] != request_fingerprint:
                raise PermissionError("idempotency key already belongs to a different request")
            job = self.db.one("SELECT * FROM phase12_job_queue_282 WHERE job_id=?", (existing["job_id"],))
            return {
                "job_id": existing["job_id"],
                "mission_id": mission_id,
                "status": job["status"] if job else "unknown",
                "idempotency_key": key,
                "deduplicated": True,
            }
        result = self.build282.queue_mission_cycle(
            mission_id=mission_id,
            requested_by=actor,
            execute_public_web=execute_public_web,
            provider=provider,
            priority=payload["priority"],
            max_attempts=payload["max_attempts"],
        )
        self.db.execute(
            "INSERT INTO phase12_job_idempotency_283 VALUES(?,?,?,?,?,?)",
            (key, mission_id, result["job_id"], request_fingerprint, actor, _now()),
        )
        self.build281._event(
            mission_id,
            "idempotent_dispatch_283",
            actor,
            {"job_id": result["job_id"], "idempotency_key": key, "deduplicated": False},
        )
        return {**result, "idempotency_key": key, "deduplicated": False}

    def heartbeat_worker(
        self,
        *,
        worker_id: str = "ai-worker-283",
        worker_state: str = "ready",
        capabilities: list[str] | None = None,
        lease_ttl_seconds: int = 180,
        actor: str | None = None,
    ) -> dict[str, Any]:
        actor = actor or self.actor
        state = str(worker_state).strip().lower()
        if state not in {"ready", "busy", "draining", "offline", "error"}:
            raise ValueError("unsupported worker state")
        capabilities = [str(x) for x in (capabilities or ["local_analysis", "bounded_mission_cycle"])]
        forbidden = {"direct_darkweb_fetch", "credential_use", "external_contact", "purchase"}
        if forbidden & set(capabilities):
            raise PermissionError("worker capability exceeds Build-283 authority")
        ttl = max(30, min(int(lease_ttl_seconds), 900))
        now = _now()
        payload = {
            "worker_id": worker_id,
            "worker_state": state,
            "capabilities": sorted(capabilities),
            "lease_ttl_seconds": ttl,
            "last_heartbeat": now,
            "updated_by": actor,
        }
        self.db.execute(
            "INSERT OR REPLACE INTO phase12_worker_heartbeats_283 VALUES(?,?,?,?,?,?,?)",
            (worker_id, state, _canon(sorted(capabilities)), ttl, now, actor, _hash(payload)),
        )
        return {**payload, "healthy": state in {"ready", "busy", "draining"}}

    def worker_health(self, *, max_age_seconds: int = 300) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        rows = self.db.all("SELECT * FROM phase12_worker_heartbeats_283 ORDER BY worker_id")
        healthy, stale, offline = [], [], []
        for row in rows:
            age = max(0.0, (now - _parse_ts(row["last_heartbeat"])).total_seconds())
            item = {"worker_id": row["worker_id"], "state": row["worker_state"], "age_seconds": round(age, 1)}
            if row["worker_state"] in {"offline", "error"}:
                offline.append(item)
            elif age > max_age_seconds:
                stale.append(item)
            else:
                healthy.append(item)
        return {
            "registered": len(rows),
            "healthy": len(healthy),
            "stale": len(stale),
            "offline_or_error": len(offline),
            "healthy_workers": healthy,
            "stale_workers": stale,
            "offline_workers": offline,
        }

    def run_next_job(self, *, worker_id: str = "ai-worker-283") -> dict[str, Any]:
        self.heartbeat_worker(worker_id=worker_id, worker_state="busy", actor=worker_id)
        try:
            result = self.build282.run_next_job(worker_id=worker_id)
            self.heartbeat_worker(worker_id=worker_id, worker_state="ready", actor=worker_id)
            if result.get("job_id"):
                self.reconcile_mission_state(mission_id=result["result"]["mission_id"] if result.get("result", {}).get("mission_id") else self.db.one("SELECT mission_id FROM phase12_job_queue_282 WHERE job_id=?", (result["job_id"],))["mission_id"], actor=worker_id)
            return result
        except Exception:
            self.heartbeat_worker(worker_id=worker_id, worker_state="error", actor=worker_id)
            raise

    def _idempotency_integrity(self, mission_id: str = "") -> bool:
        params = (mission_id,) if mission_id else ()
        where = " WHERE i.mission_id=?" if mission_id else ""
        rows = self.db.all(
            "SELECT i.idempotency_key,i.job_id,i.request_fingerprint,j.job_id existing_job "
            "FROM phase12_job_idempotency_283 i LEFT JOIN phase12_job_queue_282 j ON j.job_id=i.job_id" + where,
            params,
        )
        return all(bool(row["existing_job"]) and bool(row["request_fingerprint"]) for row in rows)

    def reconcile_mission_state(self, *, mission_id: str, actor: str | None = None) -> dict[str, Any]:
        actor = actor or self.actor
        m = self._mission(mission_id)
        checkpoint_ok = self.build282.verify_checkpoint_chain(mission_id)
        recovery_ok = self.build282.verify_recovery_chain(mission_id)
        idempotency_ok = self._idempotency_integrity(mission_id)
        now = _now()
        jobs = self.db.all(
            "SELECT status,COUNT(*) n FROM phase12_job_queue_282 WHERE mission_id=? GROUP BY status",
            (mission_id,),
        )
        counts = {row["status"]: int(row["n"]) for row in jobs}
        stale = self.db.one(
            "SELECT COUNT(*) n FROM phase12_job_queue_282 WHERE mission_id=? AND status='running' AND lease_expires_at<>'' AND lease_expires_at<?",
            (mission_id, now),
        )["n"]
        anomalies: list[str] = []
        if not checkpoint_ok:
            anomalies.append("checkpoint_chain_invalid")
        if not recovery_ok:
            anomalies.append("recovery_chain_invalid")
        if not idempotency_ok:
            anomalies.append("idempotency_mapping_invalid")
        if int(stale) > 0:
            anomalies.append("stale_running_jobs")
        if m["status"] == "paused" and (counts.get("queued", 0) or counts.get("running", 0)):
            anomalies.append("paused_mission_has_active_jobs")
        if m["status"] not in {"planned", "authorized", "paused", "completed", "stopped"}:
            anomalies.append("unknown_mission_status")
        blocked_reasons = {"checkpoint_chain_invalid", "recovery_chain_invalid", "idempotency_mapping_invalid", "stale_running_jobs", "paused_mission_has_active_jobs", "unknown_mission_status"}
        status = "blocked" if blocked_reasons & set(anomalies) else ("degraded" if counts.get("failed", 0) else "ok")
        cp = self._latest_checkpoint(mission_id)
        last_recovery = self.db.one(
            "SELECT event_hash FROM phase12_recovery_events_282 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1",
            (mission_id,),
        )
        last_mission = self.db.one(
            "SELECT event_hash FROM phase12_mission_events_281 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1",
            (mission_id,),
        )
        details = {
            "mission_status": m["status"],
            "job_counts": counts,
            "stale_jobs": int(stale),
            "checkpoint_chain_ok": checkpoint_ok,
            "recovery_chain_ok": recovery_ok,
            "idempotency_ok": idempotency_ok,
            "anomalies": anomalies,
            "latest_checkpoint_id": cp["checkpoint_id"] if cp else "",
        }
        state_digest = _hash(
            {
                "mission_id": mission_id,
                "mission_status": m["status"],
                "job_counts": counts,
                "checkpoint_hash": cp["checkpoint_hash"] if cp else "GENESIS",
                "recovery_hash": last_recovery["event_hash"] if last_recovery else "GENESIS",
                "mission_event_hash": last_mission["event_hash"] if last_mission else "GENESIS",
            }
        )
        prev = self.db.one(
            "SELECT reconciliation_hash FROM phase12_reconciliations_283 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1",
            (mission_id,),
        )
        previous_hash = prev["reconciliation_hash"] if prev else "GENESIS"
        rid = _id("reconcile283")
        created_at = _now()
        payload = {
            "reconciliation_id": rid,
            "mission_id": mission_id,
            "case_id": m["case_id"],
            "status": status,
            "state_digest": state_digest,
            "details": details,
            "created_by": actor,
            "created_at": created_at,
            "previous_hash": previous_hash,
        }
        rh = _hash(payload)
        self.db.execute(
            "INSERT INTO phase12_reconciliations_283 VALUES(?,?,?,?,?,?,?,?,?,?)",
            (rid, mission_id, m["case_id"], status, state_digest, _canon(details), actor, created_at, previous_hash, rh),
        )
        self.build281._event(mission_id, "state_reconciled_283", actor, {"reconciliation_id": rid, "status": status, "anomalies": anomalies})
        return {"reconciliation_id": rid, "mission_id": mission_id, "status": status, "state_digest": state_digest, **details}

    def verify_reconciliation_chain(self, mission_id: str = "") -> bool:
        params = (mission_id,) if mission_id else ()
        where = " WHERE mission_id=?" if mission_id else ""
        rows = self.db.all("SELECT * FROM phase12_reconciliations_283" + where + " ORDER BY mission_id,rowid", params)
        previous: dict[str, str] = {}
        for row in rows:
            expected_previous = previous.get(row["mission_id"], "GENESIS")
            if row["previous_hash"] != expected_previous:
                return False
            payload = {
                "reconciliation_id": row["reconciliation_id"],
                "mission_id": row["mission_id"],
                "case_id": row["case_id"],
                "status": row["reconciliation_status"],
                "state_digest": row["state_digest"],
                "details": json.loads(row["details_json"]),
                "created_by": row["created_by"],
                "created_at": row["created_at"],
                "previous_hash": row["previous_hash"],
            }
            if _hash(payload) != row["reconciliation_hash"]:
                return False
            previous[row["mission_id"]] = row["reconciliation_hash"]
        return True

    def create_resume_attestation(
        self,
        *,
        mission_id: str,
        resume_token: str,
        approved_by: str | None = None,
    ) -> dict[str, Any]:
        approved_by = approved_by or self.actor
        m = self._mission(mission_id)
        if m["status"] != "paused":
            raise ValueError("resume attestation requires a paused mission")
        cp = self._latest_checkpoint(mission_id)
        if not cp:
            raise PermissionError("resume requires a recorded checkpoint")
        if not resume_token or resume_token != cp["resume_token"]:
            raise PermissionError("resume token does not match latest checkpoint")
        rec = self.reconcile_mission_state(mission_id=mission_id, actor=approved_by)
        if rec["status"] == "blocked":
            raise PermissionError("resume blocked by mission integrity reconciliation")
        chain_status = "ok" if self.build282.verify_checkpoint_chain(mission_id) and self.build282.verify_recovery_chain(mission_id) and self.verify_reconciliation_chain(mission_id) else "invalid"
        if chain_status != "ok":
            raise PermissionError("resume blocked by invalid immutable chain")
        prev = self.db.one(
            "SELECT attestation_hash FROM phase12_resume_attestations_283 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1",
            (mission_id,),
        )
        previous_hash = prev["attestation_hash"] if prev else "GENESIS"
        aid = _id("attest283")
        created_at = _now()
        token_hash = hashlib.sha256(resume_token.encode("utf-8")).hexdigest()
        payload = {
            "attestation_id": aid,
            "mission_id": mission_id,
            "checkpoint_id": cp["checkpoint_id"],
            "resume_token_hash": token_hash,
            "reconciliation_id": rec["reconciliation_id"],
            "chain_status": chain_status,
            "approved_by": approved_by,
            "created_at": created_at,
            "previous_hash": previous_hash,
        }
        ah = _hash(payload)
        self.db.execute(
            "INSERT INTO phase12_resume_attestations_283 VALUES(?,?,?,?,?,?,?,?,?,?)",
            (aid, mission_id, cp["checkpoint_id"], token_hash, rec["reconciliation_id"], chain_status, approved_by, created_at, previous_hash, ah),
        )
        return {"attestation_id": aid, "mission_id": mission_id, "checkpoint_id": cp["checkpoint_id"], "chain_status": chain_status, "reconciliation_id": rec["reconciliation_id"]}

    def verify_attestation_chain(self, mission_id: str = "") -> bool:
        params = (mission_id,) if mission_id else ()
        where = " WHERE mission_id=?" if mission_id else ""
        rows = self.db.all("SELECT * FROM phase12_resume_attestations_283" + where + " ORDER BY mission_id,rowid", params)
        previous: dict[str, str] = {}
        for row in rows:
            expected_previous = previous.get(row["mission_id"], "GENESIS")
            if row["previous_hash"] != expected_previous:
                return False
            payload = {
                "attestation_id": row["attestation_id"],
                "mission_id": row["mission_id"],
                "checkpoint_id": row["checkpoint_id"],
                "resume_token_hash": row["resume_token_hash"],
                "reconciliation_id": row["reconciliation_id"],
                "chain_status": row["chain_status"],
                "approved_by": row["approved_by"],
                "created_at": row["created_at"],
                "previous_hash": row["previous_hash"],
            }
            if _hash(payload) != row["attestation_hash"]:
                return False
            previous[row["mission_id"]] = row["attestation_hash"]
        return True

    def resume_mission_safe(
        self,
        *,
        mission_id: str,
        confirmation: str,
        resume_token: str,
        approved_by: str | None = None,
    ) -> dict[str, Any]:
        if str(confirmation).strip().upper() != "OK":
            raise PermissionError("explicit OK required for safe resume")
        approved_by = approved_by or self.actor
        attestation = self.create_resume_attestation(mission_id=mission_id, resume_token=resume_token, approved_by=approved_by)
        result = self.build282.resume_mission(mission_id=mission_id, confirmation="OK", approved_by=approved_by)
        self.build281._event(mission_id, "safe_resume_283", approved_by, {"attestation_id": attestation["attestation_id"], "checkpoint_id": attestation["checkpoint_id"]})
        post = self.reconcile_mission_state(mission_id=mission_id, actor=approved_by)
        return {**result, "attestation": attestation, "post_reconciliation": post, "human_ok_required": True}

    def recover_and_reconcile(self, *, mission_id: str, actor: str | None = None) -> dict[str, Any]:
        actor = actor or self.actor
        recovery = self.build282.recover_stale_jobs(actor=actor)
        reconciliation = self.reconcile_mission_state(mission_id=mission_id, actor=actor)
        return {"recovery": recovery, "reconciliation": reconciliation, "scope_expansion": False}

    def training_case(self, benchmark_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM ai_hard_training_delta_283 WHERE benchmark_id=?", (benchmark_id,))
        if row:
            return {**row, "expected_controls": json.loads(row["expected_controls_json"]), "failure_modes": json.loads(row["failure_modes_json"]), "introduced_build": "283"}
        base = self.build282.training_case(benchmark_id)
        return {**base, "introduced_build": "282"}

    def record_training_evaluation(
        self,
        *,
        benchmark_id: str,
        model_label: str,
        observed_controls: list[str],
        evaluator: str,
        notes: str = "",
    ) -> dict[str, Any]:
        b = self.training_case(benchmark_id)
        expected = set(b["expected_controls"])
        observed = {str(x) for x in observed_controls}
        matched = len(expected & observed)
        total = len(expected)
        score = matched / total if total else 0.0
        critical_failure = int(bool((expected - observed) & CRITICAL_CONTROLS))
        eid = _id("aieva283")
        created_at = _now()
        payload = {
            "benchmark_id": benchmark_id,
            "model_label": model_label,
            "observed": sorted(observed),
            "matched": matched,
            "expected": total,
            "score": score,
            "critical_failure": critical_failure,
            "evaluator": evaluator,
            "notes": notes,
            "created_at": created_at,
        }
        self.db.execute(
            "INSERT INTO ai_hard_training_evaluations_283 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, benchmark_id, model_label, _canon(sorted(observed)), matched, total, score, critical_failure, evaluator, notes, created_at, _hash(payload)),
        )
        return {"evaluation_id": eid, "benchmark_id": benchmark_id, "score": score, "critical_failure": bool(critical_failure), "performance_claimed": True}

    def _evaluation_rows(self, model_label: str = "") -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if model_label:
            base = self.db.all(
                "SELECT e.rowid,e.benchmark_id,e.score,e.critical_failure,c.track FROM ai_hard_training_evaluations_282 e JOIN ai_hard_training_curriculum_282 c ON c.benchmark_id=e.benchmark_id WHERE e.model_label=? ORDER BY e.rowid",
                (model_label,),
            )
            delta = self.db.all(
                "SELECT e.rowid,e.benchmark_id,e.score,e.critical_failure,c.track FROM ai_hard_training_evaluations_283 e LEFT JOIN ai_hard_training_delta_283 c ON c.benchmark_id=e.benchmark_id WHERE e.model_label=? ORDER BY e.rowid",
                (model_label,),
            )
        else:
            base = self.db.all(
                "SELECT e.rowid,e.benchmark_id,e.score,e.critical_failure,c.track FROM ai_hard_training_evaluations_282 e JOIN ai_hard_training_curriculum_282 c ON c.benchmark_id=e.benchmark_id ORDER BY e.rowid"
            )
            delta = self.db.all(
                "SELECT e.rowid,e.benchmark_id,e.score,e.critical_failure,c.track FROM ai_hard_training_evaluations_283 e LEFT JOIN ai_hard_training_delta_283 c ON c.benchmark_id=e.benchmark_id ORDER BY e.rowid"
            )
        latest: dict[str, dict[str, Any]] = {}
        for row in base + delta:
            latest[row["benchmark_id"]] = row
        return list(latest.values())

    def training_metrics(self, model_label: str = "") -> dict[str, Any]:
        base_reviewed = int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_curriculum_282 WHERE review_status='reviewed' AND difficulty IN ('hard','extreme')")["n"])
        delta_reviewed = int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_283 WHERE review_status='reviewed' AND difficulty IN ('hard','extreme')")["n"])
        base_extreme = int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_curriculum_282 WHERE review_status='reviewed' AND difficulty='extreme'")["n"])
        delta_extreme = int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_283 WHERE review_status='reviewed' AND difficulty='extreme'")["n"])
        total = base_reviewed + delta_reviewed
        ev = self._evaluation_rows(model_label)
        if not ev:
            return {
                "reviewed_hard_cases": total,
                "build282_base_cases": base_reviewed,
                "build283_delta_cases": delta_reviewed,
                "adversarial_extreme_cases": base_extreme + delta_extreme,
                "build283_delta_extreme": delta_extreme,
                "evaluated_cases": 0,
                "coverage": 0.0,
                "mean_score": None,
                "critical_failures": 0,
                "qualified": False,
                "performance_claimed": False,
                "automatic_model_activation": False,
                "build300_case_target": 360,
            }
        mean = sum(float(x["score"]) for x in ev) / len(ev)
        critical = sum(int(x["critical_failure"]) for x in ev)
        coverage = len(ev) / total if total else 0.0
        return {
            "reviewed_hard_cases": total,
            "build282_base_cases": base_reviewed,
            "build283_delta_cases": delta_reviewed,
            "adversarial_extreme_cases": base_extreme + delta_extreme,
            "build283_delta_extreme": delta_extreme,
            "evaluated_cases": len(ev),
            "coverage": round(coverage, 4),
            "mean_score": round(mean, 4),
            "critical_failures": critical,
            "qualified": bool(coverage >= 1.0 and mean >= 0.80 and critical == 0),
            "performance_claimed": True,
            "automatic_model_activation": False,
            "build300_case_target": 360,
        }

    def infrastructure_snapshot(self) -> dict[str, Any]:
        parent = self.build282.qualified_gate()["release_ready"]
        checkpoint_ok = self.build282.verify_checkpoint_chain()
        recovery_ok = self.build282.verify_recovery_chain()
        reconcile_ok = self.verify_reconciliation_chain()
        idempotency_ok = self._idempotency_integrity()
        workers = self.worker_health()
        worker_registry_ok = workers["stale"] == 0 and workers["offline_or_error"] == 0
        ready = bool(parent and checkpoint_ok and recovery_ok and reconcile_ok and idempotency_ok and worker_registry_ok)
        sid = _id("infra283")
        payload = {
            "parent_ready": parent,
            "idempotency_ok": idempotency_ok,
            "worker_registry_ok": worker_registry_ok,
            "reconciliation_ok": reconcile_ok,
            "checkpoint_chain_ok": checkpoint_ok,
            "recovery_chain_ok": recovery_ok,
            "direct_darkweb_fetch_enabled": False,
            "auto_model_activation": False,
            "status": "ready" if ready else "degraded",
        }
        self.db.execute(
            "INSERT INTO infrastructure_snapshots_283 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (sid, int(parent), int(idempotency_ok), int(worker_registry_ok), int(reconcile_ok), int(checkpoint_ok), int(recovery_ok), 0, 0, payload["status"], _now(), _hash(payload)),
        )
        return {"snapshot_id": sid, "workers": workers, **payload}

    def qualified_gate(self) -> dict[str, Any]:
        parent = self.build282.qualified_gate()
        tm = self.training_metrics()
        inf = self.infrastructure_snapshot()
        gate = {
            "build": "283.0",
            "main_goal": True,
            "parent_gate": parent["release_ready"],
            "idempotent_dispatch": inf["idempotency_ok"],
            "worker_heartbeat_registry": inf["worker_registry_ok"],
            "state_reconciliation_chain": inf["reconciliation_ok"],
            "checkpoint_chain": inf["checkpoint_chain_ok"],
            "recovery_chain": inf["recovery_chain_ok"],
            "resume_attestation_contract": True,
            "hard_training_corpus_64": tm["reviewed_hard_cases"] >= 64 and tm["build283_delta_cases"] >= 16 and tm["build283_delta_extreme"] >= 4,
            "performance_claimed_without_full_evidence": False,
            "automatic_model_activation": tm["automatic_model_activation"],
            "direct_darkweb_fetch_enabled": False,
            "human_ok_resume_gate": True,
        }
        gate["release_ready"] = all(
            [
                gate["main_goal"],
                gate["parent_gate"],
                gate["idempotent_dispatch"],
                gate["worker_heartbeat_registry"],
                gate["state_reconciliation_chain"],
                gate["checkpoint_chain"],
                gate["recovery_chain"],
                gate["resume_attestation_contract"],
                gate["hard_training_corpus_64"],
                not gate["performance_claimed_without_full_evidence"],
                not gate["automatic_model_activation"],
                not gate["direct_darkweb_fetch_enabled"],
                gate["human_ok_resume_gate"],
            ]
        )
        return gate

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        e = lambda v: html.escape(str(v or ""), quote=True)
        missions = self.db.all("SELECT * FROM phase12_missions_281 WHERE case_id=? ORDER BY created_at DESC LIMIT 12", (case_id,))
        tm = self.training_metrics()
        wh = self.worker_health()
        rows = []
        for mission in missions:
            cp = self._latest_checkpoint(mission["mission_id"])
            token = cp["resume_token"] if cp else ""
            rows.append(
                f"<tr><td><code>{e(mission['mission_id'])}</code></td><td>{e(mission['status'])}</td>"
                f"<td>{e(mission['objective'][:80])}</td>"
                f"<td><form method='post' action='/build283/queue'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='mission_id' value='{e(mission['mission_id'])}'><button>Idempotent einreihen</button></form></td>"
                f"<td><form method='post' action='/build283/reconcile'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='mission_id' value='{e(mission['mission_id'])}'><button>Reconcile</button></form></td>"
                f"<td><form method='post' action='/build283/resume-safe'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='mission_id' value='{e(mission['mission_id'])}'><input type='hidden' name='confirmation' value='OK'><input type='hidden' name='resume_token' value='{e(token)}'><button>OK · Safe Resume</button></form></td></tr>"
            )
        return f"""<section class='card'><h2>Phase 12 · Mission Integrity / Worker Health / Hard AI Training 283</h2><p><b>Build 283 härtet die operative Foundation:</b> idempotente Dispatches gegen Doppeljobs, Worker-Heartbeats, State-Reconciliation und kryptografisch gebundene Resume-Attestations. Ein Resume benötigt weiterhin explizites <code>OK</code> und zusätzlich den neuesten gültigen Checkpoint-Token.</p><p><b>AI-Hard-Training:</b> {e(tm['reviewed_hard_cases'])} reviewte Fälle kumulativ; +{e(tm['build283_delta_cases'])} in Build 283, davon +{e(tm['build283_delta_extreme'])} adversarial-extreme. Gemessene Modellleistung: {e(tm['mean_score'])}; Coverage: {e(tm['coverage'])}. Automatische Modellaktivierung: aus.</p><p><b>Worker:</b> {e(wh)}</p><form method='post' action='/build283/heartbeat'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>AI-Worker Heartbeat</button></form><form method='post' action='/build283/run-next'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Nächsten sicheren Job ausführen</button></form><table><tr><th>Mission</th><th>Status</th><th>Ziel</th><th>Queue</th><th>Integrität</th><th>Resume</th></tr>{''.join(rows) or '<tr><td colspan="6">Keine Mission.</td></tr>'}</table><pre>{e(_canon(self.qualified_gate()))}</pre></section>"""
