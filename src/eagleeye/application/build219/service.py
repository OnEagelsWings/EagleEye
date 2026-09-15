from __future__ import annotations

import hashlib
import html
import json
import math
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _loads(value: str, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


def _text(value: Any, limit: int = 20_000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.0


def _dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _future(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=max(1, int(seconds)))).isoformat()


def _shape_paths(value: Any, prefix: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        paths.append(prefix + ":object")
        for key in sorted(str(k) for k in value.keys()):
            paths.extend(_shape_paths(value.get(key), f"{prefix}.{key}"))
    elif isinstance(value, list):
        paths.append(prefix + ":array")
        for item in value[:3]:
            paths.extend(_shape_paths(item, prefix + "[]"))
    elif value is None:
        paths.append(prefix + ":null")
    elif isinstance(value, bool):
        paths.append(prefix + ":bool")
    elif isinstance(value, (int, float)):
        paths.append(prefix + ":number")
    else:
        paths.append(prefix + ":string")
    return sorted(set(paths))


def _path_exists(value: Any, path: str) -> bool:
    nodes = [value]
    for raw in path.split("."):
        is_array = raw.endswith("[]")
        key = raw[:-2] if is_array else raw
        next_nodes: list[Any] = []
        for node in nodes:
            if not isinstance(node, Mapping) or key not in node:
                continue
            child = node[key]
            if is_array:
                if isinstance(child, list) and child:
                    next_nodes.extend(child)
            else:
                next_nodes.append(child)
        nodes = next_nodes
        if not nodes:
            return False
    return True


class Build219SourceReliabilityLaboratoryService:
    """Reliability, drift, cooldown and human-supervised source-quality laboratory.

    Build 219 wraps the productive Build 218 adapters. It never creates a new source
    capability and never performs autonomous network activity. A human-approved run is
    admitted only when the adapter is not quarantined and its circuit is available.
    """

    BUILD = "219.0"
    FAILURE_THRESHOLD = 3
    CIRCUIT_COOLDOWN_SECONDS = 15 * 60

    CONTRACTS: dict[str, dict[str, Any]] = {
        "github_public": {
            "version": "github-user-v1",
            "required": ["login", "id", "html_url"],
            "optional": ["name", "bio", "location", "company", "created_at", "updated_at", "type"],
        },
        "gravatar_public": {
            "version": "gravatar-profile-v1",
            "required": ["entry[]"],
            "any_of": [["entry[].profileUrl", "entry[].profile_url"], ["entry[].displayName", "entry[].display_name", "entry[].preferredUsername"]],
            "optional": ["entry[].aboutMe", "entry[].currentLocation", "entry[].accounts"],
        },
        "wikidata_public": {
            "version": "wikidata-search-v1",
            "required": ["search[]", "search[].id", "search[].label"],
            "optional": ["search[].description", "search[].concepturi", "search[].match"],
        },
        "sherlock_local": {
            "version": "sherlock-csv-v1",
            "required": ["csv[]", "csv[].name", "csv[].url_user"],
            "any_of": [["csv[].exists", "csv[].status", "csv[].http_status"]],
            "optional": ["command_contract", "returncode", "stderr"],
        },
        "whatsmyname_local": {
            "version": "wmn-json-v1",
            "required": ["export"],
            "any_of": [["export.results[]", "export.sites[]"]],
            "optional": ["command_contract", "returncode", "stderr"],
        },
    }

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        source_pack: Any,
        conversation: Any,
        identity_ai: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.source_pack = source_pack
        self.conversation = conversation
        self.identity_ai = identity_ai
        self.actor = actor
        self.seed()

    # ---------------- lifecycle and guard ----------------
    def seed(self) -> dict[str, Any]:
        now = now_ts()
        seeded = 0
        for adapter in self.source_pack.catalog():
            key = adapter["adapter_key"]
            contract = self.CONTRACTS[key]
            existing = self.db.one("SELECT * FROM source_reliability_profiles_219 WHERE adapter_key=?", (key,))
            if existing:
                continue
            state = "degraded" if adapter["active"] else "not_configured"
            policy = {
                "failure_threshold": self.FAILURE_THRESHOLD,
                "circuit_cooldown_seconds": self.CIRCUIT_COOLDOWN_SECONDS,
                "breaking_drift_quarantines": True,
                "rate_limit_respected": True,
                "silent_failure_allowed": False,
            }
            payload = {
                "adapter_key": key,
                "state": state,
                "circuit_state": "closed",
                "contract_version": contract["version"],
                "policy": policy,
                "created_at": now,
            }
            self.db.execute(
                "INSERT INTO source_reliability_profiles_219 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (key, state, "closed", "", "", contract["version"], "", "", 0, 0, 0, 0, 0, "", "", "", "{}", dumps(policy), now, now, _hash(payload)),
            )
            seeded += 1
        return {"build": self.BUILD, "profiles_seeded": seeded, "automatic_live_checks": False}

    def preflight(self, *, adapter_key: str) -> dict[str, Any]:
        profile = self._profile(adapter_key)
        now = datetime.now(timezone.utc)
        open_until = _dt(profile["circuit_open_until"])
        if profile["state"] == "quarantined":
            return {"allowed": False, "decision": "quarantined", "reason": profile["quarantine_reason"]}
        if profile["state"] == "cooldown" and open_until and open_until > now:
            return {"allowed": False, "decision": "rate_limit_cooldown", "until": profile["circuit_open_until"]}
        if profile["circuit_state"] == "open" and open_until and open_until > now:
            return {"allowed": False, "decision": "circuit_open", "until": profile["circuit_open_until"]}
        if profile["circuit_state"] == "open" and (not open_until or open_until <= now):
            self.db.execute("UPDATE source_reliability_profiles_219 SET circuit_state='half_open',state='degraded',updated_at=? WHERE adapter_key=?", (now_ts(), adapter_key))
            return {"allowed": True, "decision": "half_open_probe", "single_probe_only": True}
        return {"allowed": True, "decision": "closed"}

    def run_adapter(
        self,
        *,
        case_id: str,
        adapter_key: str,
        target_type: str,
        target_value: str,
        purpose: str,
        actor: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"RELIABLE SOURCE 219 {case_id} {adapter_key} AUSFUEHREN":
            raise PermissionError("explicit approval required")
        guard = self.preflight(adapter_key=adapter_key)
        if not guard["allowed"]:
            return {"build": self.BUILD, "adapter_key": adapter_key, "status": "blocked", "result_count": 0, "reliability_guard": guard}
        started = datetime.now(timezone.utc)
        run = self.source_pack.run_adapter(
            case_id=case_id,
            adapter_key=adapter_key,
            target_type=target_type,
            target_value=target_value,
            purpose=purpose,
            actor=actor,
            confirmation=f"DIGITAL SOURCE 218 {case_id} {adapter_key} AUSFUEHREN",
        )
        latency = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        check = self.observe_run(run_id=run["run_id"], actor=actor, latency_override_ms=latency)
        return {**run, "build": self.BUILD, "reliability_check": check, "reliability_guard": guard}

    # ---------------- contracts, health and drift ----------------
    def check_contract(
        self,
        *,
        adapter_key: str,
        sample: Mapping[str, Any],
        actor: str,
        confirmation: str,
        check_type: str = "fixture",
    ) -> dict[str, Any]:
        if confirmation != f"SOURCE CONTRACT 219 {adapter_key} PRUEFEN":
            raise PermissionError("explicit approval required")
        if check_type not in {"fixture", "parser_contract", "canary", "manual"}:
            raise ValueError("unsupported contract check type")
        self.source_pack._adapter(adapter_key)
        contract = self.CONTRACTS[adapter_key]
        required = list(contract.get("required", []))
        missing = [path for path in required if not _path_exists(sample, path)]
        for alternatives in contract.get("any_of", []):
            if not any(_path_exists(sample, path) for path in alternatives):
                missing.append("ANY(" + " | ".join(alternatives) + ")")
        observed_paths = _shape_paths(sample)
        observed_fp = _hash(observed_paths)
        profile = self._profile(adapter_key)
        baseline = profile["baseline_fingerprint"]
        drift = "none"
        status = "healthy"
        unexpected: list[str] = []
        if missing:
            status, drift = "contract_failed", "breaking"
        elif baseline and observed_fp != baseline:
            status, drift = "drift_detected", "informational"
            unexpected = observed_paths[:250]
        check = self._record_check(
            adapter_key=adapter_key,
            check_type=check_type,
            status=status,
            latency_ms=0,
            http_status=0,
            result_count=self._sample_result_count(sample),
            observed_fingerprint=observed_fp,
            baseline_fingerprint=baseline,
            required_fields=required,
            missing_fields=missing,
            unexpected_fields=unexpected,
            drift_severity=drift,
            rate_limit={},
            retry_after_at="",
            error_class="ContractViolation" if missing else "",
            error_message="Missing required fields: " + ", ".join(missing) if missing else "",
            details={"contract_version": contract["version"], "shape_path_count": len(observed_paths)},
            actor=actor,
        )
        if not baseline and status == "healthy":
            self.db.execute("UPDATE source_reliability_profiles_219 SET baseline_fingerprint=?,last_observed_fingerprint=?,updated_at=? WHERE adapter_key=?", (observed_fp, observed_fp, now_ts(), adapter_key))
        if drift != "none":
            self._record_drift(adapter_key=adapter_key, check_id=check["check_id"], severity=drift, baseline=baseline, observed=observed_fp, changes={"missing": missing, "observed_paths": unexpected[:100]}, actor=actor)
        snapshot = self.calculate_snapshot(adapter_key=adapter_key, actor=actor)
        return {**check, "snapshot": snapshot}

    def observe_run(self, *, run_id: str, actor: str, latency_override_ms: int | None = None) -> dict[str, Any]:
        run = self.db.one("SELECT * FROM digital_source_runs_218 WHERE run_id=?", (run_id,))
        if not run:
            raise KeyError(run_id)
        metrics = _loads(run["metrics_json"], {})
        latency = int(latency_override_ms if latency_override_ms is not None else metrics.get("latency_ms") or 0)
        response_headers = dict(metrics.get("response_headers") or {})
        rate = self._rate_limit(response_headers)
        status = "healthy"
        error_class = run["error_class"]
        error_message = run["error_message"]
        retry_at = rate.get("retry_after_at", "")
        http_status = int(metrics.get("http_status") or 0)
        if run["status"] in {"completed", "not_found"}:
            status = "healthy"
        elif run["status"] == "blocked":
            status = "blocked"
        elif rate.get("exhausted") or http_status == 429:
            status = "rate_limited"
        else:
            status = "unavailable"
        check = self._record_check(
            adapter_key=run["adapter_key"], check_type="live_run", status=status, latency_ms=latency,
            http_status=http_status, result_count=int(run["result_count"]),
            observed_fingerprint=_text(metrics.get("response_fingerprint"), 128),
            baseline_fingerprint=self._profile(run["adapter_key"])["baseline_fingerprint"],
            required_fields=self.CONTRACTS[run["adapter_key"]].get("required", []), missing_fields=[], unexpected_fields=[],
            drift_severity="none", rate_limit=rate, retry_after_at=retry_at, error_class=error_class,
            error_message=error_message, details={"run_id": run_id, "run_status": run["status"], "evidence_source_id": run["evidence_source_id"]}, actor=actor,
        )
        snapshot = self.calculate_snapshot(adapter_key=run["adapter_key"], actor=actor)
        return {**check, "snapshot": snapshot}

    def _record_check(
        self, *, adapter_key: str, check_type: str, status: str, latency_ms: int, http_status: int,
        result_count: int, observed_fingerprint: str, baseline_fingerprint: str, required_fields: Sequence[str],
        missing_fields: Sequence[str], unexpected_fields: Sequence[str], drift_severity: str,
        rate_limit: Mapping[str, Any], retry_after_at: str, error_class: str, error_message: str,
        details: Mapping[str, Any], actor: str,
    ) -> dict[str, Any]:
        cid, now = new_id("check219"), now_ts()
        payload = {
            "check_id": cid, "adapter_key": adapter_key, "check_type": check_type, "status": status,
            "latency_ms": max(0, int(latency_ms)), "http_status": max(0, int(http_status)), "result_count": max(0, int(result_count)),
            "observed_fingerprint": observed_fingerprint, "baseline_fingerprint": baseline_fingerprint,
            "required_fields": list(required_fields), "missing_fields": list(missing_fields), "unexpected_fields": list(unexpected_fields),
            "drift_severity": drift_severity, "rate_limit": dict(rate_limit), "retry_after_at": retry_after_at,
            "error_class": error_class, "error_message": _text(error_message, 2000), "details": dict(details),
            "checked_by": actor, "checked_at": now,
        }
        self.db.execute(
            "INSERT INTO source_health_checks_219 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, adapter_key, check_type, status, payload["latency_ms"], payload["http_status"], payload["result_count"], observed_fingerprint,
             baseline_fingerprint, dumps(list(required_fields)), dumps(list(missing_fields)), dumps(list(unexpected_fields)), drift_severity,
             dumps(dict(rate_limit)), retry_after_at, error_class, payload["error_message"], dumps(dict(details)), actor, now, _hash(payload)),
        )
        self._apply_check_to_profile(adapter_key=adapter_key, status=status, observed_fingerprint=observed_fingerprint, retry_after_at=retry_after_at, error_message=payload["error_message"])
        return payload

    def _apply_check_to_profile(self, *, adapter_key: str, status: str, observed_fingerprint: str, retry_after_at: str, error_message: str) -> None:
        profile = self._profile(adapter_key)
        success = status == "healthy"
        soft_degradation = status == "drift_detected"
        hard_failure = status in {"unavailable", "contract_failed"}
        total_checks = int(profile["total_checks"]) + 1
        total_successes = int(profile["total_successes"]) + int(success)
        total_failures = int(profile["total_failures"]) + int(hard_failure)
        consecutive_successes = int(profile["consecutive_successes"]) + 1 if success else 0
        consecutive_failures = 0 if success else int(profile["consecutive_failures"]) + int(hard_failure)
        state = "healthy" if success and consecutive_successes >= 2 else "degraded" if success or soft_degradation else "unavailable"
        circuit = "closed" if success else profile["circuit_state"]
        open_until = "" if success else profile["circuit_open_until"]
        quarantine_reason = profile["quarantine_reason"]
        if status == "rate_limited":
            state, circuit, open_until = "cooldown", "open", retry_after_at or _future(self.CIRCUIT_COOLDOWN_SECONDS)
        elif status == "contract_failed":
            state, circuit = "quarantined", "open"
            open_until = ""
            quarantine_reason = error_message or "breaking parser contract drift"
        elif consecutive_failures >= self.FAILURE_THRESHOLD:
            state, circuit, open_until = "unavailable", "open", _future(self.CIRCUIT_COOLDOWN_SECONDS)
        now = now_ts()
        self.db.execute(
            """UPDATE source_reliability_profiles_219 SET state=?,circuit_state=?,circuit_open_until=?,quarantine_reason=?,
            last_observed_fingerprint=?,consecutive_successes=?,consecutive_failures=?,total_checks=?,total_successes=?,total_failures=?,
            last_success_at=?,last_failure_at=?,last_checked_at=?,updated_at=? WHERE adapter_key=?""",
            (state, circuit, open_until, quarantine_reason, observed_fingerprint or profile["last_observed_fingerprint"],
             consecutive_successes, consecutive_failures, total_checks, total_successes, total_failures,
             now if success else profile["last_success_at"], now if hard_failure else profile["last_failure_at"],
             now, now, adapter_key),
        )
        self.db.execute("UPDATE digital_source_adapters_218 SET health_status=?,updated_at=? WHERE adapter_key=?", (state, now, adapter_key))

    def _record_drift(self, *, adapter_key: str, check_id: str, severity: str, baseline: str, observed: str, changes: Mapping[str, Any], actor: str) -> dict[str, Any]:
        did, now = new_id("drift219"), now_ts()
        action = "quarantined" if severity == "breaking" else "recorded"
        payload = {"drift_id": did, "adapter_key": adapter_key, "check_id": check_id, "drift_type": "response_schema", "severity": severity, "baseline_fingerprint": baseline, "observed_fingerprint": observed, "changes": dict(changes), "action_taken": action, "detected_by": actor, "detected_at": now}
        self.db.execute("INSERT INTO source_drift_events_219 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (did, adapter_key, check_id, "response_schema", severity, baseline, observed, dumps(dict(changes)), action, actor, now, _hash(payload)))
        if severity == "breaking":
            self.db.execute("UPDATE source_reliability_profiles_219 SET state='quarantined',circuit_state='open',circuit_open_until='',quarantine_reason=?,updated_at=? WHERE adapter_key=?", ("breaking response contract drift", now, adapter_key))
        return payload

    # ---------------- reliability score and human review ----------------
    def calculate_snapshot(self, *, adapter_key: str, actor: str) -> dict[str, Any]:
        adapter = self.source_pack._adapter(adapter_key)
        checks = self.db.all("SELECT * FROM source_health_checks_219 WHERE adapter_key=? ORDER BY rowid DESC LIMIT 100", (adapter_key,))
        eligible = [x for x in checks if x["status"] not in {"blocked", "not_configured"}]
        successes = [x for x in eligible if x["status"] == "healthy"]
        availability = len(successes) / len(eligible) if eligible else 0.0
        breaking = sum(1 for x in eligible if x["drift_severity"] == "breaking" or x["status"] == "contract_failed")
        parser_stability = max(0.0, 1.0 - (breaking / max(1, len(eligible))))

        review_rows = self.db.all("""SELECT r.decision FROM digital_source_result_reviews_218 r
            JOIN digital_source_runs_218 x ON x.run_id=r.run_id WHERE x.adapter_key=?""", (adapter_key,))
        accepted = sum(1 for x in review_rows if x["decision"] == "accepted_candidate")
        rejected = sum(1 for x in review_rows if x["decision"] == "rejected")
        precision = accepted / max(1, accepted + rejected) if review_rows else 0.5

        bench = self.db.all("SELECT passed FROM digital_source_benchmark_results_218 WHERE adapter_key=?", (adapter_key,))
        recall = sum(int(x["passed"]) for x in bench) / len(bench) if bench else 0.5

        profile = self._profile(adapter_key)
        last_success = _dt(profile["last_success_at"])
        age_hours = (datetime.now(timezone.utc) - last_success).total_seconds() / 3600 if last_success else math.inf
        freshness = 1.0 if age_hours <= 24 else 0.85 if age_hours <= 168 else 0.55 if age_hours <= 720 else 0.25 if last_success else 0.0

        runs = self.db.all("SELECT evidence_source_id,status FROM digital_source_runs_218 WHERE adapter_key=? ORDER BY rowid DESC LIMIT 100", (adapter_key,))
        completed = [x for x in runs if x["status"] in {"completed", "not_found"}]
        provenance = sum(1 for x in completed if x["evidence_source_id"]) / len(completed) if completed else 0.5

        risk_scores = {"low": 1.0, "elevated": 0.85, "high": 0.68, "critical": 0.45}
        opsec = risk_scores.get(adapter["opsec_risk"], 0.6)

        latencies = [int(x["latency_ms"]) for x in eligible if int(x["latency_ms"]) > 0]
        median_latency = statistics.median(latencies) if latencies else 0
        latency_score = 1.0 if not latencies or median_latency <= 1000 else 0.85 if median_latency <= 5000 else 0.6 if median_latency <= 30000 else 0.3
        overall = (
            availability * 0.22 + parser_stability * 0.18 + precision * 0.14 + recall * 0.10 +
            freshness * 0.10 + provenance * 0.12 + opsec * 0.08 + latency_score * 0.06
        )
        state = profile["state"]
        if state == "quarantined":
            overall = min(overall, 0.2)
        metrics = {
            "checks": len(eligible), "successes": len(successes), "reviews": len(review_rows), "benchmarks": len(bench),
            "median_latency_ms": median_latency, "last_success_at": profile["last_success_at"], "circuit_state": profile["circuit_state"],
        }
        sid, now = new_id("snapshot219"), now_ts()
        payload = {"snapshot_id": sid, "adapter_key": adapter_key, "availability": availability, "parser_stability": parser_stability, "precision_score": precision, "recall_score": recall, "freshness": freshness, "provenance_quality": provenance, "opsec_score": opsec, "latency_score": latency_score, "overall_score": overall, "state": state, "sample_size": len(eligible), "metrics": metrics, "calculated_by": actor, "calculated_at": now}
        self.db.execute("INSERT INTO source_reliability_snapshots_219 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (sid, adapter_key, availability, parser_stability, precision, recall, freshness, provenance, opsec, latency_score, overall, state, len(eligible), dumps(metrics), actor, now, _hash(payload)))
        self.db.execute("UPDATE source_reliability_profiles_219 SET quality_json=?,updated_at=? WHERE adapter_key=?", (dumps(payload), now, adapter_key))
        return payload

    def review_adapter(
        self, *, case_id: str, adapter_key: str, decision: str, reason: str, reviewer: str, confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"SOURCE RELIABILITY REVIEW 219 {adapter_key} ABSCHLIESSEN":
            raise PermissionError("explicit approval required")
        if decision not in {"confirm_healthy", "confirm_degraded", "quarantine", "release_quarantine", "needs_more_observation"}:
            raise ValueError("invalid reliability review decision")
        if len(reason.strip()) < 20:
            raise ValueError("substantive reliability rationale required")
        self._case(case_id)
        profile = self._profile(adapter_key)
        if decision == "release_quarantine":
            latest = self.db.all("SELECT * FROM source_health_checks_219 WHERE adapter_key=? ORDER BY rowid DESC LIMIT 2", (adapter_key,))
            if len(latest) < 2 or any(x["status"] != "healthy" for x in latest):
                raise PermissionError("two recent healthy checks are required before quarantine release")
            self.db.execute("UPDATE source_reliability_profiles_219 SET state='degraded',circuit_state='closed',circuit_open_until='',quarantine_reason='',consecutive_failures=0,updated_at=? WHERE adapter_key=?", (now_ts(), adapter_key))
        elif decision == "quarantine":
            self.db.execute("UPDATE source_reliability_profiles_219 SET state='quarantined',circuit_state='open',circuit_open_until='',quarantine_reason=?,updated_at=? WHERE adapter_key=?", (_text(reason, 2000), now_ts(), adapter_key))
        elif decision == "confirm_healthy":
            self.db.execute("UPDATE source_reliability_profiles_219 SET state='healthy',circuit_state='closed',circuit_open_until='',updated_at=? WHERE adapter_key=?", (now_ts(), adapter_key))
        elif decision == "confirm_degraded":
            self.db.execute("UPDATE source_reliability_profiles_219 SET state='degraded',updated_at=? WHERE adapter_key=?", (now_ts(), adapter_key))

        snapshot = self.calculate_snapshot(adapter_key=adapter_key, actor=reviewer)
        refs = [x["evidence_source_id"] for x in self.db.all("SELECT evidence_source_id FROM digital_source_runs_218 WHERE case_id=? AND adapter_key=? AND evidence_source_id<>'' ORDER BY rowid DESC LIMIT 5", (case_id, adapter_key))]
        training = self.conversation.create_training_example(
            case_id=case_id,
            task_type="source_assessment",
            language="de",
            difficulty="production_source_reliability",
            input_payload={"adapter_key": adapter_key, "profile_before": dict(profile), "snapshot": snapshot},
            expected_output={"decision": decision, "reason": reason, "reliability_state": self._profile(adapter_key)["state"]},
            evidence_refs=refs,
            negative_constraints=["do not equate technical availability with identity truth", "do not hide source drift", "do not route to quarantined sources"],
            label=f"source reliability: {decision}", rationale=reason, created_by=reviewer,
            confirmation=f"TRAINING EXAMPLE 216 {case_id} ANLEGEN",
        )
        rid, now = new_id("review219"), now_ts()
        payload = {"review_id": rid, "adapter_key": adapter_key, "decision": decision, "reason": reason, "reviewer": reviewer, "training_example_id": training["example_id"], "created_at": now}
        self.db.execute("INSERT INTO source_reliability_reviews_219 VALUES(?,?,?,?,?,?,?,?)", (rid, adapter_key, decision, _text(reason, 5000), reviewer, training["example_id"], now, _hash(payload)))
        self._event(case_id, "source_reliability_reviewed", "source_adapter", adapter_key, {"decision": decision, "training_example_id": training["example_id"]}, reviewer)
        return payload

    # ---------------- canaries and dashboard ----------------
    def register_canary(
        self, *, adapter_key: str, title: str, target_type: str, target_value: str, expected_state: str,
        expected_min_results: int, execution_mode: str, notes: str, created_by: str, confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"SOURCE CANARY 219 {adapter_key} ANLEGEN":
            raise PermissionError("explicit approval required")
        if execution_mode not in {"fixture_only", "controlled_live"}:
            raise ValueError("invalid execution mode")
        self.source_pack._adapter(adapter_key)
        cid, now = new_id("canary219"), now_ts()
        payload = {"canary_id": cid, "adapter_key": adapter_key, "title": title, "target_type": target_type, "target_value": target_value, "expected_state": expected_state, "expected_min_results": max(0, int(expected_min_results)), "execution_mode": execution_mode, "active": True, "contains_personal_data": False, "notes": notes, "created_by": created_by, "created_at": now, "updated_at": now}
        self.db.execute("INSERT INTO source_canaries_219 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (cid, adapter_key, _text(title, 500), target_type, _text(target_value, 1000), expected_state, payload["expected_min_results"], execution_mode, 1, 0, _text(notes, 3000), created_by, now, now, _hash(payload)))
        return payload

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        profiles = []
        for row in self.db.all("SELECT p.*,a.title,a.adapter_kind,a.opsec_risk,a.active FROM source_reliability_profiles_219 p JOIN digital_source_adapters_218 a ON a.adapter_key=p.adapter_key ORDER BY p.adapter_key"):
            quality = _loads(row["quality_json"], {})
            profiles.append({**row, "quality": quality, "overall_score": quality.get("overall_score", 0.0)})
        return {
            "build": self.BUILD, "case_id": case_id, "profiles": profiles,
            "checks": self.db.all("SELECT * FROM source_health_checks_219 ORDER BY checked_at DESC LIMIT 40"),
            "drift": self.db.all("SELECT * FROM source_drift_events_219 ORDER BY detected_at DESC LIMIT 30"),
            "reviews": self.db.all("SELECT * FROM source_reliability_reviews_219 ORDER BY created_at DESC LIMIT 30"),
            "policy": {"silent_failures": False, "breaking_drift_quarantines": True, "human_release_required": True, "automatic_live_checks": False, "training_coupled": True},
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        base = self.source_pack.render_workspace_panel(case_id=case_id, csrf=csrf).replace("Fallarbeitsraum 218", "Fallarbeitsraum 219", 1)
        data = self.dashboard(case_id=case_id)
        esc = lambda x: html.escape(str(x if x is not None else ""), quote=True)
        options = "".join(f"<option value='{esc(x['adapter_key'])}'>{esc(x['title'])} · {esc(x['state'])}</option>" for x in data["profiles"])
        rows = "".join(
            f"<tr><td><code>{esc(x['adapter_key'])}</code></td><td>{esc(x['state'])}</td><td>{esc(x['circuit_state'])}</td><td>{esc(round(float(x['overall_score'] or 0),2))}</td><td>{esc(x['consecutive_failures'])}</td><td>{esc(x['last_checked_at'])}</td></tr>"
            for x in data["profiles"]
        )
        checks = "".join(
            f"<tr><td>{esc(x['adapter_key'])}</td><td>{esc(x['check_type'])}</td><td>{esc(x['status'])}</td><td>{esc(x['latency_ms'])}</td><td>{esc(x['drift_severity'])}</td><td>{esc(x['checked_at'])}</td></tr>"
            for x in data["checks"][:20]
        ) or "<tr><td colspan='6'>Noch keine Reliability-Prüfungen.</td></tr>"
        panel = f"""
<section class='card' id='build219_reliability'><h2>Source Reliability Laboratory · Build 219</h2>
<p>Health, Parservertrag, Drift, Rate Limits, Circuit Breaker und Quarantäne für alle produktiven Digital-Identity-Adapter. Technische Verfügbarkeit bleibt strikt von der inhaltlichen Wahrheit eines Personentreffers getrennt.</p>
<div class='grid two'><div>
<form method='post' action='/build219/run'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><h3>Reliability-geschützten Quellenlauf starten</h3><select name='adapter_key'>{options}</select><select name='target_type'><option>username</option><option>alias</option><option>email</option><option>name</option><option>organization</option></select><input name='target_value' placeholder='Geprüfter Suchwert' required><textarea name='purpose' rows='3' placeholder='Konkreter Fallzweck' required></textarea><button>Guard prüfen und Quelle ausführen</button></form>
<form method='post' action='/build219/snapshot'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='adapter_key'>{options}</select><button>Reliability-Snapshot berechnen</button></form></div>
<div><form method='post' action='/build219/contract-check'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><h3>Fixture-/Parservertrag prüfen</h3><select name='adapter_key'>{options}</select><textarea name='sample_json' rows='7' placeholder='Kontrolliertes JSON-Fixture' required></textarea><button>Vertrag prüfen</button></form>
<form method='post' action='/build219/review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><h3>Quellenstatus prüfen und AI trainieren</h3><select name='adapter_key'>{options}</select><select name='decision'><option value='confirm_healthy'>Healthy bestätigen</option><option value='confirm_degraded'>Degraded bestätigen</option><option value='needs_more_observation'>Weitere Beobachtung</option><option value='quarantine'>Quarantäne</option><option value='release_quarantine'>Quarantäne freigeben</option></select><textarea name='reason' rows='4' placeholder='Mindestens 20 Zeichen: technische und fachliche Begründung' required></textarea><button>Review und Trainingsentwurf speichern</button></form></div></div>
<div class='table-wrap'><table><thead><tr><th>Adapter</th><th>Zustand</th><th>Circuit</th><th>Score</th><th>Fehlerfolge</th><th>Letzte Prüfung</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class='table-wrap'><table><thead><tr><th>Adapter</th><th>Prüfung</th><th>Status</th><th>ms</th><th>Drift</th><th>Zeit</th></tr></thead><tbody>{checks}</tbody></table></div>
</section>
"""
        marker = "<section class='card' id='build218_sources'>"
        return base.replace(marker, panel + marker, 1) if marker in base else base + panel

    # ---------------- helpers ----------------
    def _rate_limit(self, headers: Mapping[str, Any]) -> dict[str, Any]:
        lower = {str(k).lower(): str(v) for k, v in headers.items()}
        remaining = lower.get("x-ratelimit-remaining", "")
        reset = lower.get("x-ratelimit-reset", "")
        retry_after = lower.get("retry-after", "")
        exhausted = remaining == "0"
        retry_at = ""
        if reset.isdigit():
            retry_at = datetime.fromtimestamp(int(reset), tz=timezone.utc).isoformat()
        elif retry_after.isdigit():
            retry_at = _future(int(retry_after))
        return {"limit": lower.get("x-ratelimit-limit", ""), "remaining": remaining, "reset_epoch": reset, "retry_after": retry_after, "retry_after_at": retry_at, "exhausted": exhausted}

    def _sample_result_count(self, sample: Mapping[str, Any]) -> int:
        if isinstance(sample.get("search"), list):
            return len(sample["search"])
        if isinstance(sample.get("entry"), list):
            return len(sample["entry"])
        if isinstance(sample.get("csv"), list):
            return len(sample["csv"])
        export = sample.get("export")
        if isinstance(export, Mapping):
            for key in ("results", "sites"):
                if isinstance(export.get(key), list):
                    return len(export[key])
        return 1 if sample else 0

    def _profile(self, adapter_key: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM source_reliability_profiles_219 WHERE adapter_key=?", (adapter_key,))
        if not row:
            raise KeyError(adapter_key)
        return row

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> str:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            return ""
        prev = self.db.one("SELECT event_hash FROM build219_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = prev["event_hash"] if prev else "0" * 64
        eid, now = new_id("evt219"), now_ts()
        safe = {k: v for k, v in dict(payload).items() if k not in {"target_value", "email", "token", "authorization", "raw", "stdout", "stderr"}}
        body = {"event_id": eid, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": safe, "previous_hash": previous, "created_at": now}
        event_hash = _hash(body)
        self.db.execute("INSERT INTO build219_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, event_type, object_type, object_id, actor, dumps(safe), previous, event_hash, now))
        if self.audit is not None and hasattr(self.audit, "log"):
            self.audit.log(event_type, object_type, object_id, case_id, safe)
        return eid
