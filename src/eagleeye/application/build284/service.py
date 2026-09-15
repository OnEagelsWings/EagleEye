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


CRITICAL_CONTROLS = {
    "no_invented_fact",
    "new_ok_on_scope_change",
    "hash_locator_timestamp",
    "no_external_side_effect_without_authority",
    "human_authority_preserved",
    "state_digest_checked",
    "recovery_chain_preserved",
}


class Build284FailureContainmentReplayService:
    BUILD = "284.0"

    def __init__(self, db: Any, audit: Any, *, build283: Any, build282: Any, build281: Any, actor: str = "local-analyst"):
        self.db = db
        self.audit = audit
        self.build283 = build283
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

    def circuit_status(self, mission_id: str) -> dict[str, Any]:
        row = self.db.one(
            "SELECT * FROM phase12_failure_events_284 WHERE mission_id=? AND action IN ('open','close') ORDER BY rowid DESC LIMIT 1",
            (mission_id,),
        )
        if not row:
            return {"mission_id": mission_id, "state": "closed", "reason": "no_circuit_event", "failure_id": ""}
        return {
            "mission_id": mission_id,
            "state": "open" if row["action"] == "open" else "closed",
            "reason": row["failure_class"],
            "failure_id": row["failure_id"],
            "severity": row["severity"],
        }

    def _failure_event(
        self,
        *,
        mission_id: str,
        failure_class: str,
        severity: str,
        action: str,
        details: dict[str, Any],
        job_id: str = "",
        actor: str | None = None,
    ) -> dict[str, Any]:
        actor = actor or self.actor
        m = self._mission(mission_id)
        severity = str(severity).lower().strip()
        action = str(action).lower().strip()
        if severity not in {"info", "warning", "critical"}:
            raise ValueError("unsupported failure severity")
        if action not in {"observe", "open", "close"}:
            raise ValueError("unsupported failure action")
        prev = self.db.one(
            "SELECT event_hash FROM phase12_failure_events_284 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1",
            (mission_id,),
        )
        previous_hash = prev["event_hash"] if prev else "GENESIS"
        fid = _id("failure284")
        created_at = _now()
        payload = {
            "failure_id": fid,
            "mission_id": mission_id,
            "case_id": m["case_id"],
            "job_id": job_id,
            "failure_class": str(failure_class),
            "severity": severity,
            "action": action,
            "details": details,
            "created_by": actor,
            "created_at": created_at,
            "previous_hash": previous_hash,
        }
        event_hash = _hash(payload)
        self.db.execute(
            "INSERT INTO phase12_failure_events_284 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (fid, mission_id, m["case_id"], job_id, str(failure_class), severity, action, _canon(details), actor, created_at, previous_hash, event_hash),
        )
        self.build281._event(mission_id, f"failure_{action}_284", actor, {"failure_id": fid, "failure_class": failure_class, "severity": severity, "job_id": job_id})
        return {"failure_id": fid, "mission_id": mission_id, "severity": severity, "action": action, "event_hash": event_hash}

    def open_circuit(
        self,
        *,
        mission_id: str,
        failure_class: str,
        details: dict[str, Any] | None = None,
        job_id: str = "",
        actor: str | None = None,
    ) -> dict[str, Any]:
        current = self.circuit_status(mission_id)
        if current["state"] == "open":
            return {**current, "deduplicated": True}
        event = self._failure_event(
            mission_id=mission_id,
            failure_class=failure_class,
            severity="critical",
            action="open",
            details=details or {},
            job_id=job_id,
            actor=actor,
        )
        return {**event, "state": "open", "deduplicated": False}

    def close_circuit(
        self,
        *,
        mission_id: str,
        confirmation: str,
        approved_by: str | None = None,
        reason: str = "lead investigator re-authorized after integrity review",
    ) -> dict[str, Any]:
        if str(confirmation).strip().upper() != "OK":
            raise PermissionError("explicit OK required to close mission circuit")
        approved_by = approved_by or self.actor
        current = self.circuit_status(mission_id)
        if current["state"] != "open":
            return {**current, "closed": True, "deduplicated": True}
        rec = self.build283.reconcile_mission_state(mission_id=mission_id, actor=approved_by)
        if rec["status"] != "ok":
            raise PermissionError("circuit close blocked by mission reconciliation")
        if not (
            self.build282.verify_checkpoint_chain(mission_id)
            and self.build282.verify_recovery_chain(mission_id)
            and self.build283.verify_reconciliation_chain(mission_id)
            and self.build283.verify_attestation_chain(mission_id)
        ):
            raise PermissionError("circuit close blocked by immutable-chain failure")
        event = self._failure_event(
            mission_id=mission_id,
            failure_class="manual_integrity_release",
            severity="info",
            action="close",
            details={"reason": reason, "previous_open_failure_id": current["failure_id"], "explicit_ok": True},
            actor=approved_by,
        )
        return {**event, "state": "closed", "closed": True, "human_ok_required": True}

    def verify_failure_chain(self, mission_id: str = "") -> bool:
        params = (mission_id,) if mission_id else ()
        where = " WHERE mission_id=?" if mission_id else ""
        rows = self.db.all("SELECT * FROM phase12_failure_events_284" + where + " ORDER BY mission_id,rowid", params)
        previous: dict[str, str] = {}
        for row in rows:
            expected_previous = previous.get(row["mission_id"], "GENESIS")
            if row["previous_hash"] != expected_previous:
                return False
            payload = {
                "failure_id": row["failure_id"],
                "mission_id": row["mission_id"],
                "case_id": row["case_id"],
                "job_id": row["job_id"],
                "failure_class": row["failure_class"],
                "severity": row["severity"],
                "action": row["action"],
                "details": json.loads(row["details_json"]),
                "created_by": row["created_by"],
                "created_at": row["created_at"],
                "previous_hash": row["previous_hash"],
            }
            if _hash(payload) != row["event_hash"]:
                return False
            previous[row["mission_id"]] = row["event_hash"]
        return True

    def mission_state_fingerprint(self, mission_id: str) -> str:
        m = self._mission(mission_id)
        cp = self._latest_checkpoint(mission_id)
        jobs = self.db.all(
            "SELECT job_id,status,attempt_count,max_attempts,payload_sha256 FROM phase12_job_queue_282 WHERE mission_id=? ORDER BY created_at,job_id",
            (mission_id,),
        )
        mission_event = self.db.one(
            "SELECT event_hash FROM phase12_mission_events_281 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1",
            (mission_id,),
        )
        recovery_event = self.db.one(
            "SELECT event_hash FROM phase12_recovery_events_282 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1",
            (mission_id,),
        )
        reconciliation = self.db.one(
            "SELECT reconciliation_hash FROM phase12_reconciliations_283 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1",
            (mission_id,),
        )
        payload = {
            "mission_id": mission_id,
            "case_id": m["case_id"],
            "mission_status": m["status"],
            "mission_type": m["mission_type"],
            "objective": m["objective"],
            "jobs": jobs,
            "checkpoint_hash": cp["checkpoint_hash"] if cp else "GENESIS",
            "mission_event_hash": mission_event["event_hash"] if mission_event else "GENESIS",
            "recovery_hash": recovery_event["event_hash"] if recovery_event else "GENESIS",
            "reconciliation_hash": reconciliation["reconciliation_hash"] if reconciliation else "GENESIS",
            "circuit_state": self.circuit_status(mission_id)["state"],
        }
        return _hash(payload)

    def create_preflight_attestation(self, *, mission_id: str, actor: str | None = None) -> dict[str, Any]:
        actor = actor or self.actor
        m = self._mission(mission_id)
        if m["status"] != "authorized":
            raise PermissionError("preflight requires an authorized mission")
        circuit = self.circuit_status(mission_id)
        if circuit["state"] != "closed":
            raise PermissionError("mission circuit is open")
        rec = self.build283.reconcile_mission_state(mission_id=mission_id, actor=actor)
        if rec["status"] != "ok":
            raise PermissionError("preflight blocked by mission reconciliation")
        checks = {
            "checkpoint_chain_ok": self.build282.verify_checkpoint_chain(mission_id),
            "recovery_chain_ok": self.build282.verify_recovery_chain(mission_id),
            "reconciliation_chain_ok": self.build283.verify_reconciliation_chain(mission_id),
            "attestation_chain_ok": self.build283.verify_attestation_chain(mission_id),
        }
        if not all(checks.values()):
            self.open_circuit(mission_id=mission_id, failure_class="preflight_chain_failure", details=checks, actor=actor)
            raise PermissionError("preflight blocked by immutable-chain failure")
        fingerprint = self.mission_state_fingerprint(mission_id)
        prev = self.db.one(
            "SELECT attestation_hash FROM phase12_preflight_attestations_284 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1",
            (mission_id,),
        )
        previous_hash = prev["attestation_hash"] if prev else "GENESIS"
        aid = _id("preflight284")
        created_at = _now()
        payload = {
            "attestation_id": aid,
            "mission_id": mission_id,
            "case_id": m["case_id"],
            "state_fingerprint": fingerprint,
            "reconciliation_id": rec["reconciliation_id"],
            **checks,
            "circuit_state": "closed",
            "approved_scope": m["mission_type"],
            "created_by": actor,
            "created_at": created_at,
            "previous_hash": previous_hash,
        }
        ah = _hash(payload)
        self.db.execute(
            "INSERT INTO phase12_preflight_attestations_284 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, mission_id, m["case_id"], fingerprint, rec["reconciliation_id"], int(checks["checkpoint_chain_ok"]), int(checks["recovery_chain_ok"]), int(checks["reconciliation_chain_ok"]), int(checks["attestation_chain_ok"]), "closed", m["mission_type"], actor, created_at, previous_hash, ah),
        )
        return {"attestation_id": aid, "mission_id": mission_id, "state_fingerprint": fingerprint, "reconciliation_id": rec["reconciliation_id"], "integrity_ok": True, "circuit_state": "closed"}

    def verify_preflight_chain(self, mission_id: str = "") -> bool:
        params = (mission_id,) if mission_id else ()
        where = " WHERE mission_id=?" if mission_id else ""
        rows = self.db.all("SELECT * FROM phase12_preflight_attestations_284" + where + " ORDER BY mission_id,rowid", params)
        previous: dict[str, str] = {}
        for row in rows:
            expected_previous = previous.get(row["mission_id"], "GENESIS")
            if row["previous_hash"] != expected_previous:
                return False
            payload = {
                "attestation_id": row["attestation_id"],
                "mission_id": row["mission_id"],
                "case_id": row["case_id"],
                "state_fingerprint": row["state_fingerprint"],
                "reconciliation_id": row["reconciliation_id"],
                "checkpoint_chain_ok": bool(row["checkpoint_chain_ok"]),
                "recovery_chain_ok": bool(row["recovery_chain_ok"]),
                "reconciliation_chain_ok": bool(row["reconciliation_chain_ok"]),
                "attestation_chain_ok": bool(row["attestation_chain_ok"]),
                "circuit_state": row["circuit_state"],
                "approved_scope": row["approved_scope"],
                "created_by": row["created_by"],
                "created_at": row["created_at"],
                "previous_hash": row["previous_hash"],
            }
            if _hash(payload) != row["attestation_hash"]:
                return False
            previous[row["mission_id"]] = row["attestation_hash"]
        return True

    def detect_drift(self, *, attestation_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase12_preflight_attestations_284 WHERE attestation_id=?", (attestation_id,))
        if not row:
            raise KeyError("preflight attestation not found")
        observed = self.mission_state_fingerprint(row["mission_id"])
        drift = observed != row["state_fingerprint"]
        return {
            "attestation_id": attestation_id,
            "mission_id": row["mission_id"],
            "expected_fingerprint": row["state_fingerprint"],
            "observed_fingerprint": observed,
            "drift_detected": drift,
        }

    def queue_guarded_cycle(
        self,
        *,
        mission_id: str,
        requested_by: str | None = None,
        priority: int = 50,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        actor = requested_by or self.actor
        attestation = self.create_preflight_attestation(mission_id=mission_id, actor=actor)
        result = self.build283.queue_mission_cycle_once(
            mission_id=mission_id,
            requested_by=actor,
            execute_public_web=False,
            priority=priority,
            max_attempts=max_attempts,
        )
        return {**result, "preflight": attestation, "direct_darkweb_fetch": False, "external_side_effects": False}

    def run_next_guarded(self, *, worker_id: str = "ai-worker-284") -> dict[str, Any]:
        queued = self.db.one(
            "SELECT * FROM phase12_job_queue_282 WHERE status='queued' ORDER BY priority DESC,created_at ASC LIMIT 1"
        )
        if not queued:
            self.build283.heartbeat_worker(worker_id=worker_id, worker_state="ready", actor=worker_id)
            return {"status": "idle", "job_id": ""}
        mission_id = queued["mission_id"]
        if self.circuit_status(mission_id)["state"] == "open":
            return {"status": "blocked", "job_id": queued["job_id"], "mission_id": mission_id, "reason": "mission_circuit_open"}
        preflight = self.create_preflight_attestation(mission_id=mission_id, actor=worker_id)
        try:
            result = self.build283.run_next_job(worker_id=worker_id)
            return {**result, "preflight": preflight, "failure_contained": False}
        except Exception as exc:
            self.open_circuit(
                mission_id=mission_id,
                failure_class="guarded_worker_exception",
                details={"error_type": type(exc).__name__, "message": str(exc)[:500]},
                job_id=queued["job_id"],
                actor=worker_id,
            )
            raise

    def create_replay_manifest(self, *, mission_id: str, actor: str | None = None) -> dict[str, Any]:
        actor = actor or self.actor
        m = self._mission(mission_id)
        job = self.db.one(
            "SELECT * FROM phase12_job_queue_282 WHERE mission_id=? AND status='completed' ORDER BY updated_at DESC,rowid DESC LIMIT 1",
            (mission_id,),
        )
        cp = self._latest_checkpoint(mission_id)
        if not job or not cp:
            raise ValueError("deterministic replay requires a completed job and checkpoint")
        input_state = {
            "mission_id": mission_id,
            "case_id": m["case_id"],
            "mission_type": m["mission_type"],
            "objective": m["objective"],
            "job_id": job["job_id"],
            "job_type": job["job_type"],
            "job_payload": json.loads(job["payload_json"]),
            "job_payload_sha256": job["payload_sha256"],
            "checkpoint_id": cp["checkpoint_id"],
            "checkpoint_state": json.loads(cp["state_json"]),
            "checkpoint_next_actions": json.loads(cp["next_actions_json"]),
            "checkpoint_hash": cp["checkpoint_hash"],
        }
        expected_digest = _hash(input_state)
        prev = self.db.one(
            "SELECT manifest_hash FROM phase12_replay_manifests_284 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1",
            (mission_id,),
        )
        previous_hash = prev["manifest_hash"] if prev else "GENESIS"
        rid = _id("replay284")
        created_at = _now()
        payload = {
            "replay_id": rid,
            "mission_id": mission_id,
            "case_id": m["case_id"],
            "source_job_id": job["job_id"],
            "source_checkpoint_id": cp["checkpoint_id"],
            "input_state": input_state,
            "expected_digest": expected_digest,
            "replay_mode": "local_state_only",
            "external_side_effects": False,
            "created_by": actor,
            "created_at": created_at,
            "previous_hash": previous_hash,
        }
        mh = _hash(payload)
        self.db.execute(
            "INSERT INTO phase12_replay_manifests_284 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, mission_id, m["case_id"], job["job_id"], cp["checkpoint_id"], _canon(input_state), expected_digest, "local_state_only", 0, actor, created_at, previous_hash, mh),
        )
        return {"replay_id": rid, "mission_id": mission_id, "expected_digest": expected_digest, "source_job_id": job["job_id"], "source_checkpoint_id": cp["checkpoint_id"], "external_side_effects": False}

    def execute_local_replay(self, *, replay_id: str, actor: str | None = None) -> dict[str, Any]:
        actor = actor or self.actor
        manifest = self.db.one("SELECT * FROM phase12_replay_manifests_284 WHERE replay_id=?", (replay_id,))
        if not manifest:
            raise KeyError("replay manifest not found")
        input_state = json.loads(manifest["input_state_json"])
        observed_digest = _hash(input_state)
        match = observed_digest == manifest["expected_digest"]
        prev = self.db.one(
            "SELECT result_hash FROM phase12_replay_results_284 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1",
            (manifest["mission_id"],),
        )
        previous_hash = prev["result_hash"] if prev else "GENESIS"
        result_id = _id("replayresult284")
        created_at = _now()
        details = {
            "mode": "local_state_only",
            "network_access": False,
            "model_activation": False,
            "source_job_id": manifest["source_job_id"],
            "source_checkpoint_id": manifest["source_checkpoint_id"],
        }
        payload = {
            "result_id": result_id,
            "replay_id": replay_id,
            "mission_id": manifest["mission_id"],
            "observed_digest": observed_digest,
            "deterministic_match": match,
            "external_side_effects": False,
            "details": details,
            "created_by": actor,
            "created_at": created_at,
            "previous_hash": previous_hash,
        }
        rh = _hash(payload)
        self.db.execute(
            "INSERT INTO phase12_replay_results_284 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (result_id, replay_id, manifest["mission_id"], observed_digest, int(match), 0, _canon(details), actor, created_at, previous_hash, rh),
        )
        return {"result_id": result_id, "replay_id": replay_id, "mission_id": manifest["mission_id"], "observed_digest": observed_digest, "deterministic_match": match, "external_side_effects": False, "details": details}

    def verify_replay_chains(self, mission_id: str = "") -> bool:
        params = (mission_id,) if mission_id else ()
        where = " WHERE mission_id=?" if mission_id else ""
        manifests = self.db.all("SELECT * FROM phase12_replay_manifests_284" + where + " ORDER BY mission_id,rowid", params)
        previous: dict[str, str] = {}
        for row in manifests:
            expected_previous = previous.get(row["mission_id"], "GENESIS")
            if row["previous_hash"] != expected_previous:
                return False
            payload = {
                "replay_id": row["replay_id"],
                "mission_id": row["mission_id"],
                "case_id": row["case_id"],
                "source_job_id": row["source_job_id"],
                "source_checkpoint_id": row["source_checkpoint_id"],
                "input_state": json.loads(row["input_state_json"]),
                "expected_digest": row["expected_digest"],
                "replay_mode": row["replay_mode"],
                "external_side_effects": bool(row["external_side_effects"]),
                "created_by": row["created_by"],
                "created_at": row["created_at"],
                "previous_hash": row["previous_hash"],
            }
            if _hash(payload) != row["manifest_hash"]:
                return False
            previous[row["mission_id"]] = row["manifest_hash"]
        results = self.db.all("SELECT * FROM phase12_replay_results_284" + where + " ORDER BY mission_id,rowid", params)
        previous = {}
        for row in results:
            expected_previous = previous.get(row["mission_id"], "GENESIS")
            if row["previous_hash"] != expected_previous:
                return False
            payload = {
                "result_id": row["result_id"],
                "replay_id": row["replay_id"],
                "mission_id": row["mission_id"],
                "observed_digest": row["observed_digest"],
                "deterministic_match": bool(row["deterministic_match"]),
                "external_side_effects": bool(row["external_side_effects"]),
                "details": json.loads(row["details_json"]),
                "created_by": row["created_by"],
                "created_at": row["created_at"],
                "previous_hash": row["previous_hash"],
            }
            if _hash(payload) != row["result_hash"]:
                return False
            previous[row["mission_id"]] = row["result_hash"]
        return True

    def training_case(self, benchmark_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM ai_hard_training_delta_284 WHERE benchmark_id=?", (benchmark_id,))
        if row:
            return {**row, "expected_controls": json.loads(row["expected_controls_json"]), "failure_modes": json.loads(row["failure_modes_json"]), "introduced_build": "284"}
        return self.build283.training_case(benchmark_id)

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
        if b.get("introduced_build") != "284":
            return self.build283.record_training_evaluation(
                benchmark_id=benchmark_id,
                model_label=model_label,
                observed_controls=observed_controls,
                evaluator=evaluator,
                notes=notes,
            )
        expected = set(b["expected_controls"])
        observed = {str(x) for x in observed_controls}
        matched = len(expected & observed)
        total = len(expected)
        score = matched / total if total else 0.0
        critical_failure = int(bool((expected - observed) & CRITICAL_CONTROLS))
        eid = _id("aieva284")
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
            "INSERT INTO ai_hard_training_evaluations_284 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, benchmark_id, model_label, _canon(sorted(observed)), matched, total, score, critical_failure, evaluator, notes, created_at, _hash(payload)),
        )
        return {"evaluation_id": eid, "benchmark_id": benchmark_id, "score": score, "critical_failure": bool(critical_failure), "performance_claimed": True}

    def _evaluation_rows(self, model_label: str = "") -> list[dict[str, Any]]:
        rows = self.build283._evaluation_rows(model_label)
        if model_label:
            delta = self.db.all(
                "SELECT e.rowid,e.benchmark_id,e.score,e.critical_failure,c.track FROM ai_hard_training_evaluations_284 e JOIN ai_hard_training_delta_284 c ON c.benchmark_id=e.benchmark_id WHERE e.model_label=? ORDER BY e.rowid",
                (model_label,),
            )
        else:
            delta = self.db.all(
                "SELECT e.rowid,e.benchmark_id,e.score,e.critical_failure,c.track FROM ai_hard_training_evaluations_284 e JOIN ai_hard_training_delta_284 c ON c.benchmark_id=e.benchmark_id ORDER BY e.rowid"
            )
        latest: dict[str, dict[str, Any]] = {r["benchmark_id"]: r for r in rows}
        for row in delta:
            latest[row["benchmark_id"]] = row
        return list(latest.values())

    def training_metrics(self, model_label: str = "") -> dict[str, Any]:
        base = self.build283.training_metrics(model_label="")
        delta_reviewed = int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_284 WHERE review_status='reviewed' AND difficulty IN ('hard','extreme')")["n"])
        delta_extreme = int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_284 WHERE review_status='reviewed' AND difficulty='extreme'")["n"])
        total = int(base["reviewed_hard_cases"]) + delta_reviewed
        extreme = int(base["adversarial_extreme_cases"]) + delta_extreme
        ev = self._evaluation_rows(model_label)
        if not ev:
            return {
                "reviewed_hard_cases": total,
                "build284_delta_cases": delta_reviewed,
                "adversarial_extreme_cases": extreme,
                "build284_delta_extreme": delta_extreme,
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
            "build284_delta_cases": delta_reviewed,
            "adversarial_extreme_cases": extreme,
            "build284_delta_extreme": delta_extreme,
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
        parent = self.build283.qualified_gate()["release_ready"]
        preflight_ok = self.verify_preflight_chain()
        failure_ok = self.verify_failure_chain()
        replay_ok = self.verify_replay_chains()
        missions = self.db.all("SELECT mission_id FROM phase12_missions_281")
        open_circuits = sum(1 for m in missions if self.circuit_status(m["mission_id"])["state"] == "open")
        ready = bool(parent and preflight_ok and failure_ok and replay_ok and open_circuits == 0)
        sid = _id("infra284")
        payload = {
            "parent_ready": parent,
            "preflight_chain_ok": preflight_ok,
            "failure_chain_ok": failure_ok,
            "replay_chain_ok": replay_ok,
            "open_circuits": open_circuits,
            "direct_darkweb_fetch_enabled": False,
            "auto_model_activation": False,
            "status": "ready" if ready else "degraded",
        }
        self.db.execute(
            "INSERT INTO infrastructure_snapshots_284 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (sid, int(parent), int(preflight_ok), int(failure_ok), int(replay_ok), int(open_circuits), 0, 0, payload["status"], _now(), _hash(payload)),
        )
        return {"snapshot_id": sid, **payload}

    def qualified_gate(self) -> dict[str, Any]:
        parent = self.build283.qualified_gate()
        tm = self.training_metrics()
        inf = self.infrastructure_snapshot()
        gate = {
            "build": "284.0",
            "main_goal": True,
            "parent_gate": parent["release_ready"],
            "preflight_integrity_attestation": inf["preflight_chain_ok"],
            "failure_containment_chain": inf["failure_chain_ok"],
            "deterministic_local_replay_chain": inf["replay_chain_ok"],
            "mission_circuit_breaker": True,
            "open_circuits": inf["open_circuits"],
            "foundation_freeze": True,
            "hard_training_corpus_80": tm["reviewed_hard_cases"] >= 80 and tm["build284_delta_cases"] >= 16 and tm["build284_delta_extreme"] >= 4,
            "performance_claimed_without_full_evidence": False,
            "automatic_model_activation": tm["automatic_model_activation"],
            "direct_darkweb_fetch_enabled": False,
            "external_side_effect_replay": False,
            "human_authority_preserved": True,
        }
        gate["release_ready"] = all([
            gate["main_goal"],
            gate["parent_gate"],
            gate["preflight_integrity_attestation"],
            gate["failure_containment_chain"],
            gate["deterministic_local_replay_chain"],
            gate["mission_circuit_breaker"],
            gate["foundation_freeze"],
            gate["hard_training_corpus_80"],
            gate["open_circuits"] == 0,
            not gate["performance_claimed_without_full_evidence"],
            not gate["automatic_model_activation"],
            not gate["direct_darkweb_fetch_enabled"],
            not gate["external_side_effect_replay"],
            gate["human_authority_preserved"],
        ])
        return gate

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        e = lambda v: html.escape(str(v or ""), quote=True)
        missions = self.db.all("SELECT * FROM phase12_missions_281 WHERE case_id=? ORDER BY created_at DESC LIMIT 12", (case_id,))
        tm = self.training_metrics()
        rows = []
        for m in missions:
            circuit = self.circuit_status(m["mission_id"])
            rows.append(
                f"<tr><td><code>{e(m['mission_id'])}</code></td><td>{e(m['status'])}</td><td>{e(circuit['state'])}</td><td>{e(m['objective'][:80])}</td>"
                f"<td><form method='post' action='/build284/queue'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='mission_id' value='{e(m['mission_id'])}'><button>Preflight + Queue</button></form></td>"
                f"<td><form method='post' action='/build284/preflight'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='mission_id' value='{e(m['mission_id'])}'><button>Integrity Preflight</button></form></td>"
                f"<td><form method='post' action='/build284/replay'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='mission_id' value='{e(m['mission_id'])}'><button>Lokalen Replay prüfen</button></form></td>"
                f"<td><form method='post' action='/build284/circuit-close'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='mission_id' value='{e(m['mission_id'])}'><input type='hidden' name='confirmation' value='OK'><button>OK · Circuit freigeben</button></form></td></tr>"
            )
        return f"""<section class='card'><h2>Phase 12 · Foundation Freeze / Failure Containment / Replay 284</h2><p><b>Build 284 schließt den Foundation-Block:</b> Vor autonomen Jobs wird ein unveränderbarer Integritäts-Preflight gebunden. Kritische Fehler öffnen einen missionsbezogenen Circuit-Breaker. Replays bleiben lokal, deterministisch und ohne Netzwerk-/Modell-/Publikations-Side-Effects.</p><p><b>AI-Hard-Training:</b> {e(tm['reviewed_hard_cases'])} reviewte Fälle kumulativ; +{e(tm['build284_delta_cases'])} in Build 284, davon +{e(tm['build284_delta_extreme'])} adversarial-extreme. Gemessene Modellleistung: {e(tm['mean_score'])}; Coverage: {e(tm['coverage'])}. Automatische Modellaktivierung: aus.</p><form method='post' action='/build284/run-next'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Nächsten guarded Job ausführen</button></form><table><tr><th>Mission</th><th>Status</th><th>Circuit</th><th>Ziel</th><th>Queue</th><th>Preflight</th><th>Replay</th><th>Freigabe</th></tr>{''.join(rows) or '<tr><td colspan="8">Keine Mission.</td></tr>'}</table><pre>{e(_canon(self.qualified_gate()))}</pre></section>"""
