from __future__ import annotations

import hashlib
import html
import json
import os
import tempfile
import time
from collections import deque
from pathlib import Path
from typing import Any

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _text(value: Any, limit: int = 5000) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


def _loads(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


class Build249OperationalStressRedTeamService:
    """Controlled, local-only operational stress qualification for the Build-250 freeze.

    The harness deliberately avoids autonomous external collection. It stresses local data,
    orchestration, recovery, evidence I/O and fail-closed routing, then turns failures into
    explicit release blockers. It is a qualification layer, not an exploitation framework.
    """

    BUILD = "249.0"
    PROFILES = {
        "smoke": {"entities": 400, "evidence_bytes": 2 * 1024 * 1024, "db_queries": 100},
        "standard": {"entities": 2500, "evidence_bytes": 8 * 1024 * 1024, "db_queries": 500},
        "heavy": {"entities": 8000, "evidence_bytes": 16 * 1024 * 1024, "db_queries": 1500},
    }
    REVIEW = {"accepted", "needs_remediation", "false_positive"}
    BLOCKER_SEVERITY = {"critical", "high"}

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        production: Any,
        runtime: Any,
        monitoring: Any,
        workflow: Any,
        orchestration: Any,
        opsec: Any,
        sentinel: Any,
        graph: Any,
        evidence_vault: Any,
        recovery: Any,
        legacy_redteam: Any,
        training: Any,
        conversation: Any,
        base_dir: str | Path,
        actor: str = "local-analyst",
    ):
        self.db, self.audit = db, audit
        self.production, self.runtime, self.monitoring, self.workflow = production, runtime, monitoring, workflow
        self.orchestration, self.opsec, self.sentinel = orchestration, opsec, sentinel
        self.graph, self.evidence_vault, self.recovery = graph, evidence_vault, recovery
        self.legacy_redteam, self.training, self.conversation = legacy_redteam, training, conversation
        self.base_dir, self.actor = Path(base_dir).resolve(), actor
        conversation._stress249 = self
        sentinel._stress249 = self

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: dict[str, Any], actor: str) -> None:
        prev = self.db.one("SELECT event_hash FROM stress_events_249 WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        prev_hash = (prev or {}).get("event_hash", "")
        eid, created = new_id("stress_evt249"), now_ts()
        digest = _hash({"prev": prev_hash, "event": eid, "type": event_type, "object": object_id, "payload": payload, "actor": actor, "created": created})
        self.db.execute(
            "INSERT INTO stress_events_249 VALUES(?,?,?,?,?,?,?,?,?,?)",
            (eid, case_id, event_type, object_type, object_id, actor, dumps(payload), prev_hash, digest, created),
        )
        try:
            self.audit.log("build249_" + event_type, object_type, object_id, case_id, payload)
        except Exception:
            pass

    def create_campaign(self, *, case_id: str, title: str, profile: str, approved_by: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"STRESS 249 {case_id} KAMPAGNE ANLEGEN":
            raise PermissionError("explicit approval required")
        if profile not in self.PROFILES:
            raise ValueError("unsupported stress profile")
        title = _text(title, 500)
        if len(title) < 5:
            raise ValueError("title too short")
        cid, created = new_id("stress249"), now_ts()
        config = dict(self.PROFILES[profile])
        payload = {"campaign_id": cid, "case_id": case_id, "title": title, "profile": profile, "config": config, "approved_by": approved_by, "created_at": created}
        self.db.execute(
            "INSERT INTO stress_campaigns_249 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (cid, case_id, title, profile, "created", dumps(config), approved_by, created, None, None, _hash(payload)),
        )
        self._event(case_id, "campaign_created", "stress_campaign", cid, {"profile": profile, "automatic_external_action": False}, approved_by)
        return {**payload, "status": "created", "automatic_external_action": False}

    def campaign(self, campaign_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM stress_campaigns_249 WHERE campaign_id=?", (campaign_id,))
        if not row:
            raise KeyError(campaign_id)
        out = dict(row)
        out["config"] = _loads(out.pop("config_json", ""), {})
        out["results"] = [self._result(x) for x in self.db.all("SELECT * FROM stress_results_249 WHERE campaign_id=? ORDER BY rowid", (campaign_id,))]
        out["blockers"] = [dict(x) for x in self.db.all("SELECT * FROM release_blockers_249 WHERE campaign_id=? ORDER BY rowid", (campaign_id,))]
        return out

    def _result(self, row: Any) -> dict[str, Any]:
        d = dict(row)
        d["metrics"] = _loads(d.pop("metrics_json", ""), {})
        d["findings"] = _loads(d.pop("findings_json", ""), [])
        d["remediation"] = _loads(d.pop("remediation_json", ""), [])
        review = self.db.one("SELECT * FROM stress_result_reviews_249 WHERE result_id=?", (d["result_id"],))
        d["review"] = dict(review) if review else None
        return d

    def run_campaign(self, *, campaign_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        camp = self.campaign(campaign_id)
        if confirmation != f"STRESS 249 {campaign_id} AUSFUEHREN":
            raise PermissionError("explicit approval required")
        if camp["status"] not in {"created", "completed_with_blockers", "completed"}:
            raise ValueError("campaign is not runnable")
        if camp["results"]:
            return {"campaign_id": campaign_id, "status": camp["status"], "results": camp["results"], "idempotent": True}
        now = now_ts()
        self.db.execute("UPDATE stress_campaigns_249 SET status='running',started_at=? WHERE campaign_id=?", (now, campaign_id))
        scenarios = [
            ("sqlite_integrity_and_query_pressure", self._scenario_sqlite),
            ("large_case_graph_payload", self._scenario_graph),
            ("evidence_hash_io", self._scenario_evidence_io),
            ("agent_interruption_resume", self._scenario_agent_recovery),
            ("ai_runtime_fail_closed", self._scenario_ai_fail_closed),
            ("backup_recovery_preflight", self._scenario_recovery),
            ("monitoring_and_opsec_control_plane", self._scenario_monitoring_opsec),
        ]
        results = []
        for name, fn in scenarios:
            started = time.perf_counter()
            try:
                status, severity, metrics, findings, remediation = fn(camp)
            except Exception as exc:
                status, severity = "fail", "high"
                metrics = {"exception_type": type(exc).__name__}
                findings = [f"scenario_exception:{type(exc).__name__}:{_text(exc, 800)}"]
                remediation = ["Reproduce and fix the local failure before Build 250 release freeze."]
            duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
            result = self._store_result(camp, name, status, severity, duration_ms, metrics, findings, remediation, actor)
            results.append(result)
        blockers = self._create_blockers(camp, results)
        final = "completed_with_blockers" if blockers else "completed"
        self.db.execute("UPDATE stress_campaigns_249 SET status=?,completed_at=? WHERE campaign_id=?", (final, now_ts(), campaign_id))
        self._event(camp["case_id"], "campaign_completed", "stress_campaign", campaign_id, {"status": final, "blockers": len(blockers), "results": len(results)}, actor)
        return {"campaign_id": campaign_id, "status": final, "results": results, "release_blockers": blockers, "automatic_release": False}

    def _store_result(self, camp: dict[str, Any], scenario: str, status: str, severity: str, duration_ms: float, metrics: dict[str, Any], findings: list[str], remediation: list[str], actor: str) -> dict[str, Any]:
        rid, created = new_id("stressres249"), now_ts()
        payload = {"result_id": rid, "campaign_id": camp["campaign_id"], "case_id": camp["case_id"], "scenario": scenario, "status": status, "severity": severity, "duration_ms": duration_ms, "metrics": metrics, "findings": findings, "remediation": remediation, "created_by": actor, "created_at": created}
        self.db.execute(
            "INSERT INTO stress_results_249 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, camp["campaign_id"], camp["case_id"], scenario, status, severity, duration_ms, dumps(metrics), dumps(findings), dumps(remediation), actor, created, _hash(payload)),
        )
        self._event(camp["case_id"], "scenario_completed", "stress_result", rid, {"scenario": scenario, "status": status, "severity": severity, "duration_ms": duration_ms}, actor)
        return self._result(self.db.one("SELECT * FROM stress_results_249 WHERE result_id=?", (rid,)))

    def _scenario_sqlite(self, camp: dict[str, Any]):
        integrity = self.db.one("PRAGMA integrity_check")
        integrity_value = next(iter(integrity.values())) if integrity else "unknown"
        count = int(camp["config"].get("db_queries", 100))
        start = time.perf_counter()
        for _ in range(count):
            self.db.one("SELECT COUNT(*) AS n FROM cases")
            self.db.one("SELECT value FROM meta WHERE key='schema_version'")
        elapsed = max(0.000001, time.perf_counter() - start)
        qps = round((count * 2) / elapsed, 1)
        findings = [] if integrity_value == "ok" else ["sqlite_integrity_failed"]
        status = "pass" if not findings else "fail"
        return status, ("critical" if findings else "info"), {"integrity": integrity_value, "query_rounds": count, "queries_per_second": qps}, findings, (["Repair or restore the database before release."] if findings else [])

    def _scenario_graph(self, camp: dict[str, Any]):
        n = max(50, min(10000, int(camp["config"].get("entities", 500))))
        nodes = [{"id": f"n{i}", "type": "entity" if i % 3 else "claim", "confidence": round(((i % 100) + 1) / 100, 2)} for i in range(n)]
        adj: dict[int, list[int]] = {i: [] for i in range(n)}
        edges = []
        for i in range(n - 1):
            adj[i].append(i + 1); adj[i + 1].append(i); edges.append((i, i + 1))
            j = i + 17
            if j < n:
                adj[i].append(j); adj[j].append(i); edges.append((i, j))
        q, seen = deque([(0, 0)]), {0}; distance = -1
        while q:
            node, depth = q.popleft()
            if node == n - 1:
                distance = depth; break
            for nxt in adj[node]:
                if nxt not in seen:
                    seen.add(nxt); q.append((nxt, depth + 1))
        digest = _hash({"nodes": nodes, "edges": edges})
        size = len(_canon(nodes)) + len(_canon(edges))
        findings = []
        if distance < 0: findings.append("synthetic_graph_path_failed")
        if size > 25_000_000: findings.append("graph_payload_memory_budget_exceeded")
        return ("pass" if not findings else "fail"), ("high" if findings else "info"), {"nodes": n, "edges": len(edges), "path_distance": distance, "serialized_bytes": size, "snapshot_sha256": digest}, findings, (["Profile or optimize graph projection before Build 250."] if findings else [])

    def _scenario_evidence_io(self, camp: dict[str, Any]):
        total = max(256 * 1024, min(32 * 1024 * 1024, int(camp["config"].get("evidence_bytes", 2 * 1024 * 1024))))
        chunk = hashlib.sha256(b"eagleeye-build249-controlled-evidence-stress").digest() * 2048
        root = self.base_dir / "data" / "stress249_tmp"
        root.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix="ev249_", suffix=".bin", dir=root)
        os.close(fd)
        path = Path(name)
        start = time.perf_counter(); written = 0
        try:
            with path.open("wb") as f:
                while written < total:
                    part = chunk[: min(len(chunk), total - written)]
                    f.write(part); written += len(part)
            h = hashlib.sha256()
            with path.open("rb") as f:
                for block in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(block)
            elapsed = max(0.000001, time.perf_counter() - start)
            throughput = round((written / 1024 / 1024) / elapsed, 2)
            findings = [] if path.stat().st_size == written and len(h.hexdigest()) == 64 else ["evidence_io_hash_mismatch"]
            if throughput < 2.0:
                findings.append("evidence_io_degraded")
            status = "pass" if not findings else ("warn" if findings == ["evidence_io_degraded"] else "fail")
            severity = "medium" if status == "warn" else ("high" if status == "fail" else "info")
            return status, severity, {"bytes": written, "throughput_mb_s": throughput, "sha256": h.hexdigest(), "temporary_artifact_removed": True}, findings, (["Investigate local disk/AV contention before production stress freeze."] if findings else [])
        finally:
            try: path.unlink(missing_ok=True)
            except Exception: pass
            try: root.rmdir()
            except Exception: pass

    def _scenario_agent_recovery(self, camp: dict[str, Any]):
        cid = camp["case_id"]
        run = self.orchestration.create_run(case_id=cid, objective="Build 249 controlled local interruption and resume qualification; no external action.", priority=5, max_tokens=2000, max_cost=0.0, max_seconds=120, actor="stress249", confirmation=f"AGENT RUN 242 {cid} ANLEGEN")
        if run["status"] == "paused_opsec":
            return "pass", "info", {"containment": "opsec_paused_run", "run_id": run["run_id"]}, [], []
        ready = self.orchestration.ready_tasks(run_id=run["run_id"])
        if not ready:
            return "fail", "high", {"run_id": run["run_id"]}, ["no_initial_agent_task_ready"], ["Fix orchestration readiness before Build 250."]
        task = ready[0]
        self.orchestration.start_task(task_id=task["task_id"], worker_id="stress249-local-worker", actor="stress249", confirmation=f"AGENT TASK 242 {task['task_id']} STARTEN")
        self.orchestration.checkpoint_task(task_id=task["task_id"], checkpoint={"stress249": "before_simulated_restart"}, tokens_used=7, cost_used=0.0)
        recovered = self.orchestration.recover_interrupted(actor="stress249-recovery")
        state = self.orchestration.run(run["run_id"])
        ok = recovered["recovered_tasks"] >= 1 and any(t["task_id"] == task["task_id"] and t["status"] == "ready" for t in state["tasks"])
        try:
            self.orchestration.pause_run(run_id=run["run_id"], reason="Build 249 stress campaign completed; keep synthetic run paused.", actor="stress249", confirmation=f"AGENT RUN 242 {run['run_id']} PAUSIEREN")
        except Exception:
            pass
        return ("pass" if ok else "fail"), ("info" if ok else "critical"), {"run_id": run["run_id"], "recovered_tasks": recovered["recovered_tasks"], "resumable": recovered["resumable"]}, ([] if ok else ["agent_resume_failed"]), ([] if ok else ["Fix persistence/resume before Build 250."])

    def _scenario_ai_fail_closed(self, camp: dict[str, Any]):
        cid = camp["case_id"]
        decision = self.runtime.route(case_id=cid, task_type="investigation_dialogue", language="de", requested_context=4096, input_tokens=999999, output_tokens=1024, actor="stress249")
        local_backends = {"ollama_local", "llama_cpp_local", "sentence_transformers_local", "rules_local"}
        ok = decision.get("automatic_external_fallback") is False and decision.get("backend") in local_backends and decision.get("status") == "budget_blocked"
        findings = [] if ok else ["ai_runtime_failed_to_fail_closed"]
        return ("pass" if ok else "fail"), ("info" if ok else "critical"), {"route_status": decision.get("status"), "backend": decision.get("backend"), "external_fallback": decision.get("automatic_external_fallback")}, findings, ([] if ok else ["Block external fallback and enforce runtime budgets before Build 250."])

    def _scenario_recovery(self, camp: dict[str, Any]):
        pre = self.recovery.preflight()
        schema = str(pre.get("schema_version") or "")
        try:
            schema_compatible = int(schema.split(".", 1)[0]) >= 249
        except Exception:
            schema_compatible = False
        ok = pre.get("passed") is True and pre.get("integrity") == "ok" and schema_compatible
        findings = [] if ok else ["recovery_preflight_failed"]
        return ("pass" if ok else "fail"), ("info" if ok else "critical"), {"integrity": pre.get("integrity"), "schema": pre.get("schema_version"), "table_count": pre.get("table_count")}, findings, ([] if ok else ["Repair migration/backup/recovery path before Build 250."])

    def _scenario_monitoring_opsec(self, camp: dict[str, Any]):
        cid = camp["case_id"]
        mon = self.monitoring.dashboard(case_id=cid)
        state = self.sentinel.opsec_state(cid)
        rt = self.runtime.context(cid).get("production_ai_runtime_247", {})
        recent = rt.get("recent_routes", [])
        unexpected = [x for x in recent if x.get("backend") not in {"ollama_local", "llama_cpp_local", "sentence_transformers_local", "rules_local"}]
        ok = not unexpected and state.get("mode") in {"normal", "guarded", "restricted", "paused_opsec"}
        findings = [] if ok else (["unexpected_ai_runtime_egress"] if unexpected else ["unknown_opsec_state"])
        severity = "critical" if unexpected else ("high" if findings else "info")
        return ("pass" if ok else "fail"), severity, {"watchlists": mon.get("watchlists"), "targets": mon.get("targets"), "due": mon.get("due"), "opsec_mode": state.get("mode"), "opsec_level": state.get("last_risk_level"), "unexpected_runtime_backends": len(unexpected)}, findings, ([] if ok else ["Resolve OPSEC/runtime control-plane finding before Build 250."])

    def _create_blockers(self, camp: dict[str, Any], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        blockers = []
        for result in results:
            if result["status"] == "pass" or result["severity"] not in self.BLOCKER_SEVERITY:
                continue
            bid, created = new_id("block249"), now_ts()
            title = f"Build 250 blocker: {result['scenario']}"
            detail = "; ".join(result.get("findings") or ["stress qualification failed"])
            payload = {"blocker_id": bid, "campaign_id": camp["campaign_id"], "result_id": result["result_id"], "case_id": camp["case_id"], "category": result["scenario"], "severity": result["severity"], "title": title, "detail": detail, "status": "open", "created_at": created}
            self.db.execute("INSERT INTO release_blockers_249 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (bid, camp["campaign_id"], result["result_id"], camp["case_id"], result["scenario"], result["severity"], title, detail, "open", created, None, "", _hash(payload)))
            blockers.append(dict(self.db.one("SELECT * FROM release_blockers_249 WHERE blocker_id=?", (bid,))))
        return blockers

    def review_result(self, *, result_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM stress_results_249 WHERE result_id=?", (result_id,))
        if not row:
            raise KeyError(result_id)
        if confirmation != f"STRESS RESULT 249 {result_id} PRUEFEN":
            raise PermissionError("explicit approval required")
        if reviewer == row["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in self.REVIEW or len(_text(rationale, 5000)) < 20:
            raise ValueError("invalid review")
        rid, reviewed = new_id("stressrev249"), now_ts()
        self.db.execute("INSERT INTO stress_result_reviews_249 VALUES(?,?,?,?,?,?,?,?,?)", (rid, result_id, row["campaign_id"], row["case_id"], decision, _text(rationale, 5000), reviewer, reviewed, _hash({"review": rid, "result": result_id, "decision": decision})))
        self._event(row["case_id"], "result_reviewed", "stress_result", result_id, {"decision": decision}, reviewer)
        return dict(self.db.one("SELECT * FROM stress_result_reviews_249 WHERE review_id=?", (rid,)))

    def resolve_blocker(self, *, blocker_id: str, note: str, actor: str, confirmation: str) -> dict[str, Any]:
        b = self.db.one("SELECT * FROM release_blockers_249 WHERE blocker_id=?", (blocker_id,))
        if not b:
            raise KeyError(blocker_id)
        if confirmation != f"STRESS BLOCKER 249 {blocker_id} SCHLIESSEN":
            raise PermissionError("explicit approval required")
        if len(_text(note, 5000)) < 20:
            raise ValueError("substantive resolution note required")
        result_review = self.db.one("SELECT * FROM stress_result_reviews_249 WHERE result_id=?", (b["result_id"],))
        if not result_review or result_review["decision"] not in {"accepted", "false_positive"}:
            raise PermissionError("independent result review required before blocker closure")
        self.db.execute("UPDATE release_blockers_249 SET status='resolved',resolved_at=?,resolution_note=? WHERE blocker_id=?", (now_ts(), _text(note, 5000), blocker_id))
        self._event(b["case_id"], "blocker_resolved", "release_blocker", blocker_id, {"note": _text(note, 500)}, actor)
        return dict(self.db.one("SELECT * FROM release_blockers_249 WHERE blocker_id=?", (blocker_id,)))

    def release_gate(self, *, campaign_id: str) -> dict[str, Any]:
        camp = self.campaign(campaign_id)
        results = camp["results"]
        open_blockers = [b for b in camp["blockers"] if b["status"] != "resolved"]
        unreviewed = [r["result_id"] for r in results if not r.get("review")]
        remediation_reviews = [r["result_id"] for r in results if r.get("review") and r["review"]["decision"] == "needs_remediation"]
        status = "candidate_pass" if results and not open_blockers and not unreviewed and not remediation_reviews else "blocked"
        return {"campaign_id": campaign_id, "status": status, "open_blockers": len(open_blockers), "unreviewed_results": unreviewed, "needs_remediation_reviews": remediation_reviews, "automatic_build250_release": False, "real_world_external_stress_still_required": True}

    def stage_training(self, *, case_id: str, actor: str, limit: int = 50, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"STRESS TRAINING 249 {case_id} VORBEREITEN":
            raise PermissionError("explicit approval required")
        rows = self.db.all("""SELECT s.*,r.decision,r.rationale,r.reviewer FROM stress_results_249 s
            JOIN stress_result_reviews_249 r ON r.result_id=s.result_id
            WHERE s.case_id=? ORDER BY r.reviewed_at LIMIT ?""", (case_id, max(1, min(200, int(limit)))))
        ids = []
        for row in rows:
            streams = ["operational_stress_249"]
            if row["scenario"] in {"ai_runtime_fail_closed", "monitoring_and_opsec_control_plane", "agent_interruption_resume"}:
                streams.append("opsec_stress_249")
            for stream in streams:
                if self.db.one("SELECT link_id FROM stress_training_links_249 WHERE result_id=? AND stream=?", (row["result_id"], stream)):
                    continue
                context = {"training_stream": stream, "scenario": row["scenario"], "status": row["status"], "severity": row["severity"], "duration_ms": row["duration_ms"], "metrics": _loads(row["metrics_json"], {}), "findings": _loads(row["findings_json"], []), "review_decision": row["decision"], "safe_boundary": "controlled local stress only; no autonomous external exploitation; no stealth guarantee"}
                instruction = "Bewerte einen kontrollierten lokalen Produktions-Stresstest. Trenne technische Beobachtung von Schlussfolgerung, priorisiere sichere Remediation und wahre fail-closed, Evidence- und OPSEC-Gates."
                response = f"Review: {row['decision']}. {row['rationale']}"
                ex = self.training.add_example(case_id=case_id, instruction=instruction, response=response, context=context, source_type=stream, source_ref=row["result_id"], created_by=actor, confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")
                lid, created = new_id("stresstrain249"), now_ts()
                self.db.execute("INSERT INTO stress_training_links_249 VALUES(?,?,?,?,?,?,?,?)", (lid, case_id, row["result_id"], ex["example_id"], stream, actor, created, _hash({"link": lid, "example": ex["example_id"], "stream": stream})))
                ids.append(ex["example_id"])
        return {"case_id": case_id, "created": len(ids), "training_example_ids": ids, "review_status": "pending", "automatic_model_or_policy_activation": False}

    def context(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        latest = self.db.one("SELECT campaign_id,status,profile,completed_at FROM stress_campaigns_249 WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        blockers = [dict(x) for x in self.db.all("SELECT blocker_id,severity,title,status FROM release_blockers_249 WHERE case_id=? AND status='open' ORDER BY rowid DESC LIMIT 20", (case_id,))]
        gate = self.release_gate(campaign_id=latest["campaign_id"]) if latest and latest["status"].startswith("completed") else {"status": "not_ready"}
        return {"operational_stress_context_249": {"latest_campaign": dict(latest) if latest else None, "open_release_blockers": blockers, "build250_gate": gate, "rules": ["Stress-test results are operational qualification data, not investigative evidence.", "No stress scenario authorizes autonomous external collection or exploitation.", "High/critical failures remain Build-250 blockers until independently reviewed and resolved."]}}

    def dashboard(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        camp = self.db.one("SELECT * FROM stress_campaigns_249 WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        open_blockers = int((self.db.one("SELECT COUNT(*) AS n FROM release_blockers_249 WHERE case_id=? AND status='open'", (case_id,)) or {"n": 0})["n"])
        results = int((self.db.one("SELECT COUNT(*) AS n FROM stress_results_249 WHERE case_id=?", (case_id,)) or {"n": 0})["n"])
        reviews = int((self.db.one("SELECT COUNT(*) AS n FROM stress_result_reviews_249 WHERE case_id=?", (case_id,)) or {"n": 0})["n"])
        return {"build": self.BUILD, "campaign_id": (camp or {}).get("campaign_id", ""), "campaign_status": (camp or {}).get("status", "not_started"), "profile": (camp or {}).get("profile", ""), "results": results, "reviews": reviews, "open_blockers": open_blockers}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        d = self.dashboard(case_id); e = lambda x: html.escape(str(x or ""), quote=True)
        return f"""<section class='card' id='build249'><h2>Operational Stress &amp; Red-Team Qualification · Build 249</h2><p>Kontrollierte lokale Belastungs- und Ausfalltests vor dem Build-250-Freeze. Keine autonome externe Exploitation oder Collection.</p><div class='metrics'><div class='metric'><div class='label'>Campaign</div><div class='value'>{e(d['campaign_status'])}</div></div><div class='metric'><div class='label'>Results</div><div class='value'>{d['results']}</div></div><div class='metric'><div class='label'>Reviews</div><div class='value'>{d['reviews']}</div></div><div class='metric'><div class='label'>Open blockers</div><div class='value'>{d['open_blockers']}</div></div></div><div class='grid'><div class='card'><h3>Stress campaign</h3><form method='post' action='/build249/campaign'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='title' value='Build 249 Production Qualification' required><select name='profile'><option value='smoke'>Smoke</option><option value='standard' selected>Standard</option><option value='heavy'>Heavy</option></select><button>Kampagne anlegen</button></form><form method='post' action='/build249/run'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='campaign_id' placeholder='Campaign-ID' required><button>Kontrolliert ausführen</button></form><p class='muted'>Tests: SQLite/Query pressure, großer Graph-Payload, Evidence Hash/I/O, Agent Resume, AI fail-closed, Recovery-Preflight, Monitoring/OPSEC control plane.</p></div><div class='card'><h3>Review &amp; Build-250 Gate</h3><form method='post' action='/build249/review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='result_id' placeholder='Result-ID' required><select name='decision'><option>accepted</option><option>needs_remediation</option><option>false_positive</option></select><textarea name='rationale' placeholder='Unabhängige Review-Begründung' required></textarea><button>Ergebnis prüfen</button></form><form method='post' action='/build249/gate'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='campaign_id' placeholder='Campaign-ID' required><button>Build-250 Gate prüfen</button></form></div><div class='card'><h3>Training</h3><form method='post' action='/build249/training'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Reviewte Stressdaten vorbereiten</button></form><p class='muted'>Co-AI und OPSEC Sentinel: pending → Redaction → Human Review → Qualification. Keine automatische Aktivierung.</p></div></div></section>"""
