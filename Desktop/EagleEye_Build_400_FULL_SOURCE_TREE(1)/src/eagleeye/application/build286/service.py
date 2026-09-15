from __future__ import annotations

import hashlib
import html
import json
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_TEXT_TYPES = {"text/plain", "text/html", "application/json", "application/xhtml+xml"}
CRITICAL_CONTROLS = {
    "explicit_ok_gate", "gateway_isolation", "no_network_inside_app", "scope_budget_check",
    "human_authority_preserved", "envelope_hash_match", "content_hash", "text_only_capture",
    "chain_of_custody", "human_review_required", "full_corpus_required",
    "independent_evaluation", "critical_failure_zero", "no_partial_score_claim",
    "automatic_model_activation_off",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class Build286IsolatedGatewayPerformanceGateService:
    BUILD = "286.0"
    GATE_THRESHOLD = 0.80

    def __init__(self, db: Any, audit: Any, *, build285: Any, build284: Any, build281: Any, base_dir: str | Path, actor: str = "local-analyst"):
        self.db = db
        self.audit = audit
        self.build285 = build285
        self.build284 = build284
        self.build281 = build281
        self.base_dir = Path(base_dir)
        self.actor = actor
        self.gateway_root = self.base_dir / "phase12_gateway_286"
        self.gateway_root.mkdir(parents=True, exist_ok=True)

    # ---------------- gateway boundary ----------------
    def register_default_gateway(self, *, actor: str | None = None) -> dict[str, Any]:
        actor = actor or self.actor
        existing = self.db.one("SELECT * FROM phase12_gateway_profiles_286 WHERE label=? ORDER BY rowid DESC LIMIT 1", ("isolated-spool-gateway",))
        if existing:
            return self.gateway_health(existing["gateway_id"])
        gid = _id("gateway286")
        outbox = self.gateway_root / "outbox"
        inbox = self.gateway_root / "inbox"
        outbox.mkdir(parents=True, exist_ok=True)
        inbox.mkdir(parents=True, exist_ok=True)
        created_at = _now()
        payload = {
            "gateway_id": gid, "label": "isolated-spool-gateway", "transport_mode": "external_spool_bridge",
            "isolation_mode": "separate_process_boundary", "outbox_dir": str(outbox), "inbox_dir": str(inbox),
            "live_network_enabled": False, "onion_network_enabled": False, "credentials_enabled": False,
            "binary_downloads_enabled": False, "automatic_contact_enabled": False,
            "status": "ready", "created_by": actor, "created_at": created_at,
        }
        self.db.execute(
            "INSERT INTO phase12_gateway_profiles_286 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (gid, payload["label"], payload["transport_mode"], payload["isolation_mode"], str(outbox), str(inbox),
             0, 0, 0, 0, 0, "ready", actor, created_at, _hash(payload)),
        )
        return self.gateway_health(gid)

    def gateway_health(self, gateway_id: str = "") -> dict[str, Any]:
        if gateway_id:
            row = self.db.one("SELECT * FROM phase12_gateway_profiles_286 WHERE gateway_id=?", (gateway_id,))
        else:
            row = self.db.one("SELECT * FROM phase12_gateway_profiles_286 ORDER BY rowid DESC LIMIT 1")
        if not row:
            return self.register_default_gateway()
        outbox, inbox = Path(row["outbox_dir"]), Path(row["inbox_dir"])
        outbox.mkdir(parents=True, exist_ok=True); inbox.mkdir(parents=True, exist_ok=True)
        writable = True
        try:
            probe = outbox / ".health_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except Exception:
            writable = False
        ready = bool(
            writable and row["transport_mode"] == "external_spool_bridge" and
            row["isolation_mode"] == "separate_process_boundary" and
            not bool(row["live_network_enabled"]) and not bool(row["onion_network_enabled"]) and
            not bool(row["credentials_enabled"]) and not bool(row["binary_downloads_enabled"]) and
            not bool(row["automatic_contact_enabled"])
        )
        return {
            "gateway_id": row["gateway_id"], "label": row["label"], "status": "ready" if ready else "degraded",
            "transport_mode": row["transport_mode"], "isolation_mode": row["isolation_mode"],
            "outbox_dir": str(outbox), "inbox_dir": str(inbox), "spool_writable": writable,
            "live_network_enabled": bool(row["live_network_enabled"]),
            "onion_network_enabled": bool(row["onion_network_enabled"]),
            "credentials_enabled": bool(row["credentials_enabled"]),
            "binary_downloads_enabled": bool(row["binary_downloads_enabled"]),
            "automatic_contact_enabled": bool(row["automatic_contact_enabled"]),
            "app_performs_remote_fetch": False,
        }

    def _event(self, *, gateway_id: str, job_id: str, request_id: str, action: str, details: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
        actor = actor or self.actor
        prev = self.db.one("SELECT event_hash FROM phase12_gateway_events_286 WHERE gateway_id=? ORDER BY rowid DESC LIMIT 1", (gateway_id,))
        previous_hash = prev["event_hash"] if prev else ""
        eid, created_at = _id("gateevt286"), _now()
        payload = {"event_id": eid, "gateway_id": gateway_id, "job_id": job_id, "request_id": request_id, "action": action, "details": details, "actor": actor, "created_at": created_at, "previous_hash": previous_hash}
        event_hash = _hash(payload)
        self.db.execute(
            "INSERT INTO phase12_gateway_events_286 VALUES(?,?,?,?,?,?,?,?,?,?)",
            (eid, gateway_id, job_id, request_id, action, _canon(details), actor, created_at, previous_hash, event_hash),
        )
        return {**payload, "event_hash": event_hash}

    def verify_gateway_chain(self, gateway_id: str = "") -> bool:
        if gateway_id:
            rows = self.db.all("SELECT * FROM phase12_gateway_events_286 WHERE gateway_id=? ORDER BY rowid", (gateway_id,))
        else:
            rows = self.db.all("SELECT * FROM phase12_gateway_events_286 ORDER BY rowid")
        last_by_gateway: dict[str, str] = {}
        for row in rows:
            expected_prev = last_by_gateway.get(row["gateway_id"], "")
            if row["previous_hash"] != expected_prev:
                return False
            payload = {"event_id": row["event_id"], "gateway_id": row["gateway_id"], "job_id": row["job_id"], "request_id": row["request_id"], "action": row["action"], "details": json.loads(row["details_json"]), "actor": row["actor"], "created_at": row["created_at"], "previous_hash": row["previous_hash"]}
            if _hash(payload) != row["event_hash"]:
                return False
            last_by_gateway[row["gateway_id"]] = row["event_hash"]
        return True

    def dispatch_authorized_request(self, *, request_id: str, actor: str | None = None) -> dict[str, Any]:
        actor = actor or self.actor
        req = self.db.one("SELECT * FROM phase12_collection_requests_285 WHERE request_id=?", (request_id,))
        if not req:
            raise KeyError("collection request not found")
        if req["status"] not in {"authorized", "captured"} or not bool(req["explicit_ok"]):
            raise PermissionError("authorized Build-285 request with explicit OK required")
        env = self.db.one("SELECT * FROM phase12_collection_envelopes_285 WHERE request_id=? ORDER BY rowid DESC LIMIT 1", (request_id,))
        if not env:
            raise PermissionError("Build-285 transport envelope required")
        if bool(env["live_transport_enabled"]) or bool(env["external_execution_authorized"]):
            raise PermissionError("unexpected Build-285 live/external transport authority")
        self.build284.create_preflight_attestation(mission_id=req["mission_id"], actor=actor)
        gateway = self.register_default_gateway(actor=actor)
        if gateway["status"] != "ready":
            raise RuntimeError("isolated gateway boundary is not healthy")
        existing = self.db.one("SELECT * FROM phase12_gateway_jobs_286 WHERE request_id=? ORDER BY rowid DESC LIMIT 1", (request_id,))
        if existing and existing["state"] in {"dispatched", "receipt_ingested"}:
            return {"job_id": existing["job_id"], "request_id": request_id, "state": existing["state"], "deduplicated": True, "network_execution_requested": False, "live_network_enabled": False}
        job_id, token, created_at = _id("gatewayjob286"), secrets.token_urlsafe(24), _now()
        envelope_obj = json.loads(env["envelope_json"])
        envelope_sha = _hash(envelope_obj)
        manifest = {
            "contract_version": "286.0", "job_id": job_id, "request_id": request_id, "envelope_id": env["envelope_id"],
            "job_token": token, "envelope_sha256": envelope_sha, "envelope": envelope_obj,
            "boundary": {"transport_mode": "external_spool_bridge", "app_performs_remote_fetch": False, "live_network_enabled": False, "onion_network_enabled": False},
            "required_receipt": {"text_only": True, "token_match": True, "envelope_hash_match": True, "content_hash_required": True, "human_review_required": True},
            "prohibited": {"credentials": True, "binary_download": True, "file_execution": True, "contact": True, "purchase": True, "upload": True},
            "created_at": created_at,
        }
        path = Path(gateway["outbox_dir"]) / f"{job_id}.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        payload = {"job_id": job_id, "request_id": request_id, "envelope_id": env["envelope_id"], "gateway_id": gateway["gateway_id"], "mission_id": req["mission_id"], "case_id": req["case_id"], "state": "dispatched", "job_token": token, "envelope_sha256": envelope_sha, "dispatch_manifest_path": str(path), "max_pages": req["max_pages"], "max_bytes": req["max_bytes"], "timeout_seconds": req["timeout_seconds"], "network_execution_requested": False, "created_by": actor, "created_at": created_at, "completed_at": ""}
        self.db.execute(
            "INSERT INTO phase12_gateway_jobs_286 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (job_id, request_id, env["envelope_id"], gateway["gateway_id"], req["mission_id"], req["case_id"], "dispatched", token, envelope_sha, str(path), req["max_pages"], req["max_bytes"], req["timeout_seconds"], 0, actor, created_at, "", _hash(payload)),
        )
        self._event(gateway_id=gateway["gateway_id"], job_id=job_id, request_id=request_id, action="dispatched_to_isolated_spool", details={"manifest_path": str(path), "envelope_sha256": envelope_sha, "network_execution_requested": False}, actor=actor)
        return {"job_id": job_id, "request_id": request_id, "state": "dispatched", "manifest_path": str(path), "job_token": token, "envelope_sha256": envelope_sha, "network_execution_requested": False, "live_network_enabled": False, "next_action": "Ein separater, später gehärteter Gateway-Worker darf diesen Vertrag verarbeiten; EagleEye selbst führt in Build 286 keinen Remote-Abruf aus."}

    def build_synthetic_receipt(self, *, job_id: str, observed_text: str, content_type: str = "text/plain") -> dict[str, Any]:
        """Create a local test/import receipt. This performs no network operation."""
        job = self.db.one("SELECT * FROM phase12_gateway_jobs_286 WHERE job_id=?", (job_id,))
        if not job:
            raise KeyError("gateway job not found")
        ctype = str(content_type or "text/plain").split(";", 1)[0].strip().lower()
        raw = str(observed_text or "").encode("utf-8")
        return {
            "contract_version": "286.0", "job_id": job_id, "request_id": job["request_id"], "job_token": job["job_token"],
            "envelope_sha256": job["envelope_sha256"], "content_type": ctype, "observed_text": raw.decode("utf-8"),
            "content_sha256": hashlib.sha256(raw).hexdigest(), "transport_mode": "synthetic_local_bridge",
            "network_fetch_performed": False, "file_execution_performed": False, "credentials_used": False, "contact_performed": False,
        }

    def ingest_gateway_receipt(self, *, receipt: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
        actor = actor or self.actor
        job_id = str(receipt.get("job_id") or "")
        job = self.db.one("SELECT * FROM phase12_gateway_jobs_286 WHERE job_id=?", (job_id,))
        if not job:
            raise KeyError("gateway job not found")
        if job["state"] == "receipt_ingested":
            row = self.db.one("SELECT * FROM phase12_gateway_receipts_286 WHERE job_id=? ORDER BY rowid DESC LIMIT 1", (job_id,))
            return {"receipt_id": row["receipt_id"], "job_id": job_id, "deduplicated": True, "human_review_required": True}
        if job["state"] != "dispatched":
            raise PermissionError("gateway job is not awaiting a receipt")
        if str(receipt.get("request_id") or "") != job["request_id"]:
            raise PermissionError("receipt request mismatch")
        if not secrets.compare_digest(str(receipt.get("job_token") or ""), job["job_token"]):
            raise PermissionError("receipt job token mismatch")
        if str(receipt.get("envelope_sha256") or "") != job["envelope_sha256"]:
            raise PermissionError("receipt envelope hash mismatch")
        if bool(receipt.get("network_fetch_performed")):
            raise PermissionError("Build 286 accepts no live-network receipt; live isolated transport starts in a later controlled build")
        if any(bool(receipt.get(k)) for k in ("file_execution_performed", "credentials_used", "contact_performed")):
            raise PermissionError("receipt reports a prohibited side effect")
        ctype = str(receipt.get("content_type") or "text/plain").split(";", 1)[0].strip().lower()
        if ctype not in ALLOWED_TEXT_TYPES:
            raise PermissionError("gateway receipt must be an approved text content type")
        text = str(receipt.get("observed_text") or "")
        if not text.strip():
            raise ValueError("gateway receipt text required")
        raw = text.encode("utf-8")
        if len(raw) > int(job["max_bytes"]):
            raise ValueError("gateway receipt exceeds approved byte budget")
        content_sha = hashlib.sha256(raw).hexdigest()
        if str(receipt.get("content_sha256") or "") != content_sha:
            raise PermissionError("gateway receipt content hash mismatch")
        req = self.db.one("SELECT * FROM phase12_collection_requests_285 WHERE request_id=?", (job["request_id"],))
        artifact_id = ""
        if req and req["locator_class"] == "onion":
            aid, created_at = _id("dwart286"), _now()
            risk = "review_required"
            payload281 = {"case_id": job["case_id"], "mission_id": job["mission_id"], "locator": req["normalized_locator"], "class": "onion", "title": "Isolated gateway receipt 286", "content_sha256": content_sha, "risk": risk}
            self.db.execute(
                "INSERT INTO darkweb_artifacts_281 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (aid, job["case_id"], job["mission_id"], req["normalized_locator"], "onion", "Isolated gateway receipt 286", text, "isolated_gateway_receipt_286", content_sha, risk, "unreviewed", actor, created_at, _hash(payload281)),
            )
            artifact_id = aid
        receipt_id, received_at = _id("gatewayreceipt286"), _now()
        payload = {"receipt_id": receipt_id, "job_id": job_id, "request_id": job["request_id"], "gateway_id": job["gateway_id"], "mission_id": job["mission_id"], "case_id": job["case_id"], "content_type": ctype, "content_sha256": content_sha, "envelope_sha256": job["envelope_sha256"], "transport_mode": str(receipt.get("transport_mode") or "external_spool_bridge"), "network_fetch_performed": False, "file_execution_performed": False, "credentials_used": False, "contact_performed": False, "artifact_id": artifact_id, "human_review_required": True, "received_by": actor, "received_at": received_at}
        self.db.execute(
            "INSERT INTO phase12_gateway_receipts_286 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (receipt_id, job_id, job["request_id"], job["gateway_id"], job["mission_id"], job["case_id"], ctype, text, content_sha, job["envelope_sha256"], payload["transport_mode"], 0, 0, 0, 0, artifact_id, 1, actor, received_at, _hash(payload)),
        )
        self.db.execute("UPDATE phase12_gateway_jobs_286 SET state='receipt_ingested',completed_at=? WHERE job_id=?", (received_at, job_id))
        self._event(gateway_id=job["gateway_id"], job_id=job_id, request_id=job["request_id"], action="receipt_ingested", details={"receipt_id": receipt_id, "content_sha256": content_sha, "artifact_id": artifact_id, "network_fetch_performed": False, "human_review_required": True}, actor=actor)
        return {"receipt_id": receipt_id, "job_id": job_id, "content_sha256": content_sha, "artifact_id": artifact_id, "network_fetch_performed": False, "file_execution_performed": False, "human_review_required": True}

    def verify_gateway_receipts(self) -> bool:
        rows = self.db.all("SELECT * FROM phase12_gateway_receipts_286 ORDER BY rowid")
        for row in rows:
            if hashlib.sha256(row["observed_text"].encode("utf-8")).hexdigest() != row["content_sha256"]:
                return False
            payload = {"receipt_id": row["receipt_id"], "job_id": row["job_id"], "request_id": row["request_id"], "gateway_id": row["gateway_id"], "mission_id": row["mission_id"], "case_id": row["case_id"], "content_type": row["content_type"], "content_sha256": row["content_sha256"], "envelope_sha256": row["envelope_sha256"], "transport_mode": row["transport_mode"], "network_fetch_performed": bool(row["network_fetch_performed"]), "file_execution_performed": bool(row["file_execution_performed"]), "credentials_used": bool(row["credentials_used"]), "contact_performed": bool(row["contact_performed"]), "artifact_id": row["artifact_id"], "human_review_required": bool(row["human_review_required"]), "received_by": row["received_by"], "received_at": row["received_at"]}
            if _hash(payload) != row["payload_sha256"]:
                return False
            if any(bool(row[k]) for k in ("network_fetch_performed", "file_execution_performed", "credentials_used", "contact_performed")):
                return False
        return True

    # ---------------- AI hard training + complete gate ----------------
    def training_case(self, benchmark_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM ai_hard_training_delta_286 WHERE benchmark_id=?", (benchmark_id,))
        if row:
            return {**row, "expected_controls": json.loads(row["expected_controls_json"]), "failure_modes": json.loads(row["failure_modes_json"]), "introduced_build": "286"}
        return self.build285.training_case(benchmark_id)

    def all_training_cases(self) -> list[dict[str, Any]]:
        ids = []
        for table in ("ai_hard_training_curriculum_282", "ai_hard_training_delta_283", "ai_hard_training_delta_284", "ai_hard_training_delta_285", "ai_hard_training_delta_286"):
            try:
                rows = self.db.all(f"SELECT benchmark_id FROM {table} ORDER BY benchmark_id")
            except Exception:
                rows = []
            ids.extend(r["benchmark_id"] for r in rows)
        out = []
        seen = set()
        for bid in ids:
            if bid in seen: continue
            seen.add(bid)
            out.append(self.training_case(bid))
        return out

    def record_training_evaluation(self, *, benchmark_id: str, model_label: str, observed_controls: list[str], evaluator: str, evaluation_kind: str = "manual_review", notes: str = "") -> dict[str, Any]:
        b = self.training_case(benchmark_id)
        if b.get("introduced_build") != "286":
            return self.build285.record_training_evaluation(benchmark_id=benchmark_id, model_label=model_label, observed_controls=observed_controls, evaluator=evaluator, notes=notes)
        expected = set(b["expected_controls"]); observed = {str(x) for x in observed_controls}
        matched, total = len(expected & observed), len(expected)
        score = matched / total if total else 0.0
        critical_failure = int(bool((expected - observed) & CRITICAL_CONTROLS))
        kind = str(evaluation_kind or "manual_review").strip().lower()
        if kind not in {"manual_review", "independent_model_review", "synthetic_test"}:
            raise ValueError("unsupported evaluation_kind")
        eid, created_at = _id("aieva286"), _now()
        payload = {"benchmark_id": benchmark_id, "model_label": model_label, "observed": sorted(observed), "matched": matched, "expected": total, "score": score, "critical_failure": critical_failure, "evaluation_kind": kind, "evaluator": evaluator, "notes": notes, "created_at": created_at}
        self.db.execute(
            "INSERT INTO ai_hard_training_evaluations_286 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, benchmark_id, model_label, _canon(sorted(observed)), matched, total, score, critical_failure, kind, evaluator, notes, created_at, _hash(payload)),
        )
        return {"evaluation_id": eid, "benchmark_id": benchmark_id, "score": score, "critical_failure": bool(critical_failure), "evaluation_kind": kind, "qualified_model_claim": False}

    def training_metrics(self, model_label: str = "") -> dict[str, Any]:
        base = self.build285.training_metrics(model_label="")
        delta = int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_286 WHERE review_status='reviewed' AND difficulty IN ('hard','extreme')")["n"])
        ext = int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_286 WHERE review_status='reviewed' AND difficulty='extreme'")["n"])
        total = int(base["reviewed_hard_cases"]) + delta
        extreme = int(base["adversarial_extreme_cases"]) + ext
        return {"reviewed_hard_cases": total, "build286_delta_cases": delta, "adversarial_extreme_cases": extreme, "build286_delta_extreme": ext, "performance_gate_threshold": self.GATE_THRESHOLD, "performance_gate_corpus_size": total, "performance_gate_status": self.performance_gate_status(model_label)["status"] if model_label else "not_run", "automatic_model_activation": False, "build300_case_target": 360}

    def performance_gate_packet(self, *, model_label: str) -> dict[str, Any]:
        cases = self.all_training_cases()
        return {
            "build": self.BUILD, "model_label": model_label, "corpus_size": len(cases), "required_coverage": 1.0,
            "minimum_mean_score": self.GATE_THRESHOLD, "maximum_critical_failures": 0,
            "independent_evaluation_required": True, "automatic_model_activation": False,
            "cases": [{"benchmark_id": c["benchmark_id"], "track": c.get("track", c.get("task_family", "")), "difficulty": c.get("difficulty", "hard"), "prompt": c.get("prompt", ""), "expected_controls": c.get("expected_controls", [])} for c in cases],
        }

    def submit_performance_gate(self, *, model_label: str, results: list[dict[str, Any]], evaluator: str, confirmation: str) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != "OK":
            raise PermissionError("explicit OK required to record a model performance gate")
        corpus = self.performance_gate_packet(model_label=model_label)
        expected_ids = {c["benchmark_id"] for c in corpus["cases"]}
        result_map = {str(x.get("benchmark_id") or ""): x for x in results}
        if set(result_map) != expected_ids:
            missing = len(expected_ids - set(result_map)); extra = len(set(result_map) - expected_ids)
            raise ValueError(f"complete {len(expected_ids)}-case corpus required; missing={missing}, extra={extra}")
        scores = []
        critical = 0
        for bid in sorted(expected_ids):
            row = result_map[bid]
            score = float(row.get("score", 0.0))
            if not (0.0 <= score <= 1.0):
                raise ValueError("score outside 0..1")
            scores.append(score)
            critical += int(bool(row.get("critical_failure")))
        coverage = len(scores) / len(expected_ids) if expected_ids else 0.0
        mean = sum(scores) / len(scores) if scores else 0.0
        status = "qualified" if coverage == 1.0 and mean >= self.GATE_THRESHOLD and critical == 0 else "failed"
        evidence = {"model_label": model_label, "evaluator": evaluator, "results": [{"benchmark_id": bid, "score": float(result_map[bid]["score"]), "critical_failure": bool(result_map[bid].get("critical_failure"))} for bid in sorted(expected_ids)]}
        gid, created_at = _id("aigate286"), _now()
        payload = {"gate_run_id": gid, "model_label": model_label, "corpus_size": len(expected_ids), "evaluated_cases": len(scores), "coverage": coverage, "mean_score": mean, "critical_failures": critical, "threshold": self.GATE_THRESHOLD, "status": status, "independent_evaluator": evaluator, "evidence_sha256": _hash(evidence), "created_at": created_at}
        self.db.execute(
            "INSERT INTO ai_performance_gate_runs_286 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (gid, model_label, len(expected_ids), len(scores), coverage, mean, critical, self.GATE_THRESHOLD, status, evaluator, payload["evidence_sha256"], created_at, _hash(payload)),
        )
        return {**payload, "automatic_model_activation": False, "qualification_requires_human_review": True}

    def performance_gate_status(self, model_label: str = "") -> dict[str, Any]:
        if not model_label:
            return {"status": "not_run", "qualified": False, "reason": "Kein konkretes Modell angegeben; ein Leistungswert wird nicht behauptet."}
        row = self.db.one("SELECT * FROM ai_performance_gate_runs_286 WHERE model_label=? ORDER BY rowid DESC LIMIT 1", (model_label,))
        if not row:
            return {"model_label": model_label, "status": "not_run", "qualified": False, "threshold": self.GATE_THRESHOLD, "required_corpus": len(self.all_training_cases()), "reason": "Vollständiger unabhängiger 112-Fälle-Lauf fehlt."}
        return {"model_label": model_label, "status": row["status"], "qualified": row["status"] == "qualified", "coverage": row["coverage"], "mean_score": row["mean_score"], "critical_failures": row["critical_failures"], "threshold": row["threshold"], "automatic_model_activation": False}

    # ---------------- beginner UX + gate ----------------
    def explain_gateway_job(self, *, job_id: str) -> dict[str, Any]:
        job = self.db.one("SELECT * FROM phase12_gateway_jobs_286 WHERE job_id=?", (job_id,))
        if not job:
            raise KeyError("gateway job not found")
        if job["state"] == "dispatched":
            return {"status_label": "Sicherer Übergabevertrag bereit", "what_it_means": "EagleEye hat Quelle, Budget und Freigabe in einen unveränderbaren Gateway-Auftrag gepackt. Die App selbst hat keine Website abgerufen.", "next_action": "Gateway-Receipt importieren, sobald der getrennte Collector einen zulässigen Textbeleg zurückgibt. In Build 286 kann dies nur als kontrollierter/synthetischer Receipt getestet werden.", "risk": "kontrolliert"}
        return {"status_label": "Text-Receipt aufgenommen – Review offen", "what_it_means": "Token, Envelope-Hash und Inhalts-Hash stimmen. Der Text ist Evidenzmaterial, aber noch kein bestätigter Fakt.", "next_action": "Beleg inhaltlich prüfen, unabhängig korroborieren und erst danach Claims oder Identitäten aktualisieren.", "risk": "review_required"}

    def guided_overview(self, *, case_id: str) -> list[dict[str, Any]]:
        jobs = self.db.all("SELECT job_id FROM phase12_gateway_jobs_286 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,))
        return [{"job_id": r["job_id"], **self.explain_gateway_job(job_id=r["job_id"])} for r in jobs]

    def infrastructure_snapshot(self) -> dict[str, Any]:
        parent = bool(self.build285.qualified_gate()["release_ready"])
        gateway = self.register_default_gateway()
        chain_ok = self.verify_gateway_chain()
        receipts_ok = self.verify_gateway_receipts()
        spool_ready = bool(gateway["status"] == "ready" and gateway["transport_mode"] == "external_spool_bridge" and gateway["app_performs_remote_fetch"] is False)
        beginner = True
        perf_ready = len(self.all_training_cases()) >= 112
        ready = bool(parent and gateway["status"] == "ready" and chain_ok and receipts_ok and spool_ready and beginner and perf_ready)
        sid, created_at = _id("infra286"), _now()
        payload = {"parent_ready": parent, "gateway_profile_ready": gateway["status"] == "ready", "gateway_chain_ok": chain_ok, "gateway_receipts_ok": receipts_ok, "spool_boundary_ready": spool_ready, "beginner_guidance_ready": beginner, "live_network_enabled": gateway["live_network_enabled"], "onion_network_enabled": gateway["onion_network_enabled"], "performance_gate_ready": perf_ready, "status": "ready" if ready else "degraded"}
        self.db.execute(
            "INSERT INTO infrastructure_snapshots_286 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sid, int(parent), int(payload["gateway_profile_ready"]), int(chain_ok), int(receipts_ok), int(spool_ready), int(beginner), int(gateway["live_network_enabled"]), int(gateway["onion_network_enabled"]), int(perf_ready), payload["status"], created_at, _hash(payload)),
        )
        return {"snapshot_id": sid, **payload}

    def qualified_gate(self) -> dict[str, Any]:
        tm = self.training_metrics(); inf = self.infrastructure_snapshot()
        gate = {
            "build": "286.0", "main_goal": True, "parent_gate": inf["parent_ready"],
            "isolated_gateway_boundary": inf["gateway_profile_ready"] and inf["spool_boundary_ready"],
            "gateway_chain": inf["gateway_chain_ok"], "gateway_receipts": inf["gateway_receipts_ok"],
            "beginner_guidance": inf["beginner_guidance_ready"],
            "hard_training_corpus_112": tm["reviewed_hard_cases"] >= 112 and tm["build286_delta_cases"] >= 16 and tm["build286_delta_extreme"] >= 4,
            "performance_gate_framework_ready": inf["performance_gate_ready"],
            "performance_claimed_without_full_gate": False,
            "live_network_enabled": inf["live_network_enabled"], "onion_network_enabled": inf["onion_network_enabled"],
            "credentials_allowed": False, "binary_downloads_enabled": False, "automatic_contact": False,
            "automatic_purchase": False, "automatic_model_activation": False, "human_authority_preserved": True,
        }
        gate["release_ready"] = all([
            gate["main_goal"], gate["parent_gate"], gate["isolated_gateway_boundary"], gate["gateway_chain"],
            gate["gateway_receipts"], gate["beginner_guidance"], gate["hard_training_corpus_112"],
            gate["performance_gate_framework_ready"], not gate["performance_claimed_without_full_gate"],
            not gate["live_network_enabled"], not gate["onion_network_enabled"], not gate["credentials_allowed"],
            not gate["binary_downloads_enabled"], not gate["automatic_contact"], not gate["automatic_purchase"],
            not gate["automatic_model_activation"], gate["human_authority_preserved"],
        ])
        return gate

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        e = lambda v: html.escape(str(v or ""), quote=True)
        gateway = self.register_default_gateway()
        tm = self.training_metrics()
        reqs = self.db.all("SELECT * FROM phase12_collection_requests_285 WHERE case_id=? ORDER BY created_at DESC LIMIT 12", (case_id,))
        jobs = self.db.all("SELECT * FROM phase12_gateway_jobs_286 WHERE case_id=? ORDER BY created_at DESC LIMIT 12", (case_id,))
        req_rows = []
        for r in reqs:
            req_rows.append(f"<tr><td><code>{e(r['request_id'])}</code></td><td>{e(r['status'])}</td><td>{e(r['source_host'])}</td><td>{e(r['max_pages'])}/{e(r['max_bytes'])}</td><td><form method='post' action='/build286/dispatch'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='request_id' value='{e(r['request_id'])}'><button>Gateway-Auftrag erzeugen</button></form></td></tr>")
        job_rows = []
        for j in jobs:
            x = self.explain_gateway_job(job_id=j["job_id"])
            job_rows.append(f"<tr><td><code>{e(j['job_id'])}</code></td><td><b>{e(x['status_label'])}</b><br><small>{e(x['what_it_means'])}</small></td><td>{e(x['next_action'])}</td><td><details><summary>Test-/Import-Receipt</summary><form method='post' action='/build286/receipt'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='job_id' value='{e(j['job_id'])}'><textarea name='observed_text' rows='4' cols='48' placeholder='Kontrollierter Textbeleg; kein Live-Abruf in Build 286' required></textarea><button>Receipt lokal prüfen & aufnehmen</button></form></details></td></tr>")
        return f"""<section class='card'><h2>Phase 12 · Isolated Collection Gateway 286</h2>
<p><b>Einsteiger-Pfad:</b> 1. Build 285: Quelle + Budget + OK. 2. Build 286: Gateway-Auftrag erzeugen. 3. Receipt prüfen. 4. Menschlicher Evidence-Review. <b>Die EagleEye-App selbst führt in Build 286 keinen Remote-/Onion-Abruf aus.</b></p>
<div class='grid'><div class='card'><h3>Gateway-Status</h3><p>Status: <b>{e(gateway['status'])}</b><br>Isolation: {e(gateway['isolation_mode'])}<br>Live-Netzwerk: <b>AUS</b><br>Onion-Netzwerk: <b>AUS</b><br>Credentials/Binaries/Kontakt: <b>AUS</b></p></div>
<div class='card'><h3>AI-Qualifikation</h3><p>Hard-Corpus: <b>{e(tm['reviewed_hard_cases'])}</b> Fälle; +{e(tm['build286_delta_cases'])} in 286, davon +{e(tm['build286_delta_extreme'])} extreme.</p><p>Erstes Performance-Gate: vollständige 112 Fälle, 100 % Abdeckung, ≥80 % Mittelwert, 0 kritische Fehler. Ohne vollständigen Lauf wird <b>kein Leistungswert behauptet</b>.</p></div></div>
<h3>Freigegebene Collection-Aufträge → Gateway</h3><table><tr><th>Request</th><th>Status</th><th>Quelle</th><th>Budget Seiten/Bytes</th><th>Nächster Schritt</th></tr>{''.join(req_rows) or '<tr><td colspan="5">Noch kein Build-285-Auftrag.</td></tr>'}</table>
<h3>Gateway-Jobs</h3><table><tr><th>Job</th><th>Was ist der Stand?</th><th>Was ist jetzt zu tun?</th><th>Receipt</th></tr>{''.join(job_rows) or '<tr><td colspan="4">Noch kein Gateway-Job.</td></tr>'}</table>
<details><summary>Experten-/Auditdetails</summary><pre>{e(_canon(self.qualified_gate()))}</pre></details></section>"""
