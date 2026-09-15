from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

POLICY = "phase16.external-qualification.v379"
AI_POLICY = "phase16.autonomous-investigation.v379"
OPSEC_POLICY = "phase16.defensive-opsec-supervisor.v379"
FAULT_MARKERS = {"phase16_qualification_fault_injection_v379", "qualification379_fault_injection"}


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _json(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return default


def _is_sha256(value: Any) -> bool:
    text = str(value or "").lower()
    return len(text) == 64 and all(c in "0123456789abcdef" for c in text)


class ExternalQualification379:
    """Read-only qualification overlay for the final pre-production build.

    The operational runtime contains no failure-injection method. Local synthetic
    fault injection lives only in the offline qualification harness. External
    validation can be satisfied only by a fingerprint-bound Ed25519-signed receipt
    from a separately configured trust anchor.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        operations365: Any,
        crawler369: Any,
        workflow374: Any,
        image377: Any,
        jobs: Any,
        base_dir: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.operations365 = operations365
        self.crawler369 = crawler369
        self.workflow374 = workflow374
        self.image377 = image377
        self.jobs = jobs
        self.base_dir = Path(base_dir)
        self.actor = actor

    def contract(self) -> dict[str, Any]:
        return {
            "policy": POLICY,
            "build": "379.0",
            "minimum_duration_seconds": 3600,
            "minimum_crawler_jobs": 500,
            "minimum_failure_injections": 50,
            "minimum_workers": 2,
            "minimum_recovery_ratio": 0.99,
            "maximum_p95_lease_recovery_seconds": 10.0,
            "maximum_p95_queue_dispatch_seconds": 30.0,
            "maximum_p95_failure_containment_seconds": 10.0,
            "maximum_stale_leases_after_recovery": 0,
            "maximum_cross_case_leaks": 0,
            "maximum_evidence_loss_events": 0,
            "maximum_automatic_eviction_events": 0,
            "maximum_unauthorized_network_escalations": 0,
            "audit_chain_consistent_required": True,
            "minimum_sha256_bound_evidence_artifacts": 3,
            "external_reviewer_independence_required": True,
            "receipt_signature": "Ed25519",
            "receipt_fingerprint_binding_required": True,
            "receipt_grants_network_scope": False,
        }

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY,
            "crawler_improvement_build": 379,
            "runtime_fault_injection_api": False,
            "local_prequalification_supported": True,
            "external_receipt_required": True,
            "external_receipt_signature": "Ed25519",
            "external_receipt_fingerprint_bound": True,
            "external_receipt_grants_network_scope": False,
            "automatic_evidence_eviction": False,
            "automatic_scope_expansion": False,
            "direct_network_authority": False,
            "production_decision_owned_by_build380": True,
        }

    def runtime_snapshot(self, *, case_id: str = "") -> dict[str, Any]:
        ops = self.operations365.metrics(case_id=case_id)
        worker = self.operations365.worker_health(case_id=case_id)
        crawler = self.crawler369.soak_snapshot(case_id=case_id) if case_id else {
            "stale_running_leases": int((self.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE job_type='governed_crawl_v1' AND status='running' AND lease_expires_at<>'' AND lease_expires_at<datetime('now')") or {}).get("c") or 0),
            "backpressure": {"global_backpressure": False, "case_backpressure": False},
            "network_execution_by_snapshot": False,
        }
        pressure = self.image377.storage_pressure(case_id=case_id or None)
        backpressure = self.crawler369.backpressure(case_id=case_id) if case_id else {
            "global_backpressure": bool((self.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE job_type='governed_crawl_v1' AND status IN ('queued','running')") or {}).get("c", 0) >= 64),
            "case_backpressure": False,
        }
        ready = (
            int(worker.get("expired_worker_leases") or 0) == 0
            and int(crawler.get("stale_running_leases") or 0) == 0
            and not bool(backpressure.get("global_backpressure"))
            and not bool(backpressure.get("case_backpressure"))
            and str(pressure.get("state") or "normal") != "hard_limit"
        )
        return {
            "policy": POLICY,
            "case_id": case_id,
            "operations": ops,
            "worker_health": worker,
            "crawler": crawler,
            "backpressure": backpressure,
            "object_store_pressure": pressure,
            "ready_for_bounded_work": ready,
            "network_execution_by_snapshot": False,
            "fault_injection_performed_by_runtime": False,
        }

    def _qualification_dir(self) -> Path:
        return self.base_dir / "qualification_379"

    def receipt_paths(self) -> dict[str, str]:
        q = self._qualification_dir()
        return {
            "directory": str(q),
            "trusted_reviewer_public_key": str(q / "trusted_external_reviewer_ed25519.pem"),
            "external_receipt": str(q / "external_receipt.json"),
        }

    def _metric_gates(self, payload: Mapping[str, Any]) -> dict[str, bool]:
        metrics = dict(payload.get("metrics") or {})
        evidence = list(payload.get("evidence_artifacts") or [])
        contract = self.contract()
        artifact_hashes = [str(x.get("sha256") or "") for x in evidence if isinstance(x, Mapping)]
        return {
            "duration": int(metrics.get("duration_seconds") or 0) >= int(contract["minimum_duration_seconds"]),
            "crawler_jobs": int(metrics.get("crawler_jobs") or 0) >= int(contract["minimum_crawler_jobs"]),
            "failure_injections": int(metrics.get("failure_injections") or 0) >= int(contract["minimum_failure_injections"]),
            "workers": int(metrics.get("workers") or 0) >= int(contract["minimum_workers"]),
            "recovery_ratio": float(metrics.get("recovery_ratio") or 0.0) >= float(contract["minimum_recovery_ratio"]),
            "lease_recovery_p95": float(metrics.get("p95_lease_recovery_seconds") or 1e9) <= float(contract["maximum_p95_lease_recovery_seconds"]),
            "queue_dispatch_p95": float(metrics.get("p95_queue_dispatch_seconds") or 1e9) <= float(contract["maximum_p95_queue_dispatch_seconds"]),
            "failure_containment_p95": float(metrics.get("p95_failure_containment_seconds") or 1e9) <= float(contract["maximum_p95_failure_containment_seconds"]),
            "stale_leases": int(metrics.get("stale_leases_after_recovery") or 0) <= int(contract["maximum_stale_leases_after_recovery"]),
            "cross_case_leaks": int(metrics.get("cross_case_leaks") or 0) <= int(contract["maximum_cross_case_leaks"]),
            "evidence_loss": int(metrics.get("evidence_loss_events") or 0) <= int(contract["maximum_evidence_loss_events"]),
            "automatic_eviction": int(metrics.get("automatic_eviction_events") or 0) <= int(contract["maximum_automatic_eviction_events"]),
            "unauthorized_network": int(metrics.get("unauthorized_network_escalations") or 0) <= int(contract["maximum_unauthorized_network_escalations"]),
            "audit_chain": bool(metrics.get("audit_chain_consistent")) is bool(contract["audit_chain_consistent_required"]),
            "evidence_artifacts": len(artifact_hashes) >= int(contract["minimum_sha256_bound_evidence_artifacts"]) and all(_is_sha256(x) for x in artifact_hashes),
            "independent_reviewer": bool(payload.get("independent_reviewer")),
        }

    def external_receipt_status(self, *, code_fingerprint: str) -> dict[str, Any]:
        paths = self.receipt_paths()
        key_path = Path(paths["trusted_reviewer_public_key"])
        receipt_path = Path(paths["external_receipt"])
        base = {
            "policy": POLICY,
            "build": "379.0",
            "receipt_present": receipt_path.is_file(),
            "trust_anchor_present": key_path.is_file(),
            "signature_valid": False,
            "fingerprint_match": False,
            "metric_gates": {},
            "valid": False,
            "externally_validated": False,
            "state": "not_run",
            "network_scope_granted": False,
        }
        if not receipt_path.is_file() or not key_path.is_file():
            return base
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            payload = receipt.get("signed_payload")
            signature_b64 = str(receipt.get("signature_b64") or "")
            if not isinstance(payload, dict) or not signature_b64:
                return {**base, "state": "invalid_receipt"}
            pub = serialization.load_pem_public_key(key_path.read_bytes())
            if not isinstance(pub, Ed25519PublicKey):
                return {**base, "state": "invalid_trust_anchor"}
            pub.verify(base64.b64decode(signature_b64, validate=True), _canon(payload))
            fp_match = str(payload.get("code_fingerprint") or "") == str(code_fingerprint)
            build_match = str(payload.get("build") or "") == "379.0"
            policy_match = str(payload.get("policy") or "") == POLICY
            gates = self._metric_gates(payload)
            valid = fp_match and build_match and policy_match and all(gates.values())
            return {
                **base,
                "signature_valid": True,
                "fingerprint_match": fp_match,
                "build_match": build_match,
                "policy_match": policy_match,
                "metric_gates": gates,
                "valid": valid,
                "externally_validated": valid,
                "state": "validated" if valid else "receipt_failed_gates",
                "reviewer_id": str(payload.get("reviewer_id") or ""),
                "network_scope_granted": False,
            }
        except Exception as exc:
            return {**base, "state": "invalid_receipt", "error": type(exc).__name__}


class AutonomousInvestigation379:
    def __init__(self, *, base378: Any, qualification379: ExternalQualification379) -> None:
        self.base378 = base378
        self.qualification379 = qualification379

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.base378, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def status(self) -> dict[str, Any]:
        base = dict(self.base378.status())
        base.update({
            "policy_version": AI_POLICY,
            "runtime_qualification_context": True,
            "stability_hold_aware": True,
            "fault_injection_authority": False,
            "external_receipt_authority": False,
            "production_decision_authority": False,
        })
        return base

    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        snap = self.qualification379.runtime_snapshot(case_id=case_id)
        out = dict(self.base378.run_cycle(case_id=case_id, max_ticks=max_ticks))
        out["phase16_external_qualification_v379"] = snap
        dossier = dict(out.get("dossier") or {})
        dossier["phase16_external_qualification_v379"] = {
            "ready_for_bounded_work": snap["ready_for_bounded_work"],
            "stale_leases": int((snap.get("worker_health") or {}).get("expired_worker_leases") or 0),
            "backpressure": snap.get("backpressure") or {},
            "object_store_pressure": (snap.get("object_store_pressure") or {}).get("state"),
            "external_validation_runtime_claim": False,
        }
        out["dossier"] = dossier
        if not snap["ready_for_bounded_work"]:
            out["state"] = "operations_hold"
            out["research_hold_reason"] = "build379_runtime_stability_gate"
        out["fault_injection_authority"] = False
        out["external_receipt_authority"] = False
        return out


class DefensiveOpsecSupervisor379:
    def __init__(self, db: Any, audit: Any, *, base378: Any, qualification379: ExternalQualification379, jobs: Any) -> None:
        self.db = db
        self.audit = audit
        self.base378 = base378
        self.qualification379 = qualification379
        self.jobs = jobs

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.base378, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _qualification_fault_jobs(self, case_id: str) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT job_id,status,payload_json FROM phase15_jobs WHERE case_id=? AND status IN ('queued','running','workflow_paused')", (str(case_id),))
        out = []
        for row in rows:
            payload = _json(row.get("payload_json"), {}) or {}
            marker = next((m for m in FAULT_MARKERS if payload.get(m) is True), "")
            if marker:
                out.append({"job_id": row["job_id"], "status": row["status"], "marker": marker, "reason": "qualification_fault_marker_in_operational_case"})
        return out

    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        violations = self._qualification_fault_jobs(case_id)
        cancelled: list[str] = []
        drain_required: list[str] = []
        for item in violations:
            jid = str(item["job_id"])
            if item["status"] in {"queued", "workflow_paused"}:
                self.jobs.cancel(jid, actor="opsec379")
                cancelled.append(jid)
            else:
                drain_required.append(jid)
            self.audit.log("OPSEC379_QUALIFICATION_FAULT_BLOCKED", "crawler_job", jid, case_id=case_id, details={**item, "policy": OPSEC_POLICY})
        inherited = dict(self.base378.protect_case(case_id=case_id))
        inherited.update({
            "policy_v379": OPSEC_POLICY,
            "qualification_fault_violations": violations,
            "cancelled_qualification_fault_jobs": cancelled,
            "running_fault_jobs_drain_required": drain_required,
            "production_fault_injection_authority": False,
            "external_receipt_signing_authority": False,
            "automatic_evidence_eviction": False,
            "system_mutations": False,
        })
        return inherited

    def status(self) -> dict[str, Any]:
        base = dict(self.base378.status())
        base.update({
            "policy_v379": OPSEC_POLICY,
            "qualification_fault_marker_containment": True,
            "production_fault_injection_authority": False,
            "external_receipt_signing_authority": False,
            "automatic_evidence_eviction": False,
            "firewall_mutation": False,
            "os_mutation": False,
            "tor_configuration_mutation": False,
            "credential_mutation": False,
            "acl_mutation": False,
            "system_mutations": False,
        })
        return base
