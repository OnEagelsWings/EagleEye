from __future__ import annotations

import json
from pathlib import Path
from typing import Any

POLICY = "phase16.professional-pilot-production-decision.v380"
AI_POLICY = "phase16.ai-final-readiness.v380"
OPSEC_POLICY = "phase16.opsec-final-readiness.v380"

PRODUCTION_OVERRIDE_MARKERS = (
    "production_override",
    "bypass_final_gate",
    "force_production_candidate",
    "skip_external_qualification",
)


def _json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value or "")
    except Exception:
        return default


class ProfessionalPilotDecision380:
    """Final Phase-16 readiness aggregation.

    This service never performs network activity and never grants new execution
    authority. It combines already-existing qualification, crawler, workflow,
    dossier, entity, image, voice and OPSEC state into a reviewable decision.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        build379: Any,
        qualification379: Any,
        operations365: Any,
        crawler369: Any,
        workflow374: Any,
        entity_eval372: Any,
        dossier376: Any,
        image377: Any,
        voice378: Any,
        jobs: Any,
        base_dir: Any,
        install_dir: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.build379 = build379
        self.qualification379 = qualification379
        self.operations365 = operations365
        self.crawler369 = crawler369
        self.workflow374 = workflow374
        self.entity_eval372 = entity_eval372
        self.dossier376 = dossier376
        self.image377 = image377
        self.voice378 = voice378
        self.jobs = jobs
        self.base_dir = Path(base_dir)
        self.install_dir = Path(install_dir)
        self.actor = actor

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY,
            "build": "380.0",
            "phase16_builds_completed": 20,
            "phase16_total_builds": 20,
            "professional_pilot_telemetry": True,
            "final_crawler_slo_gate": True,
            "production_decision": True,
            "network_execution_by_decision_layer": False,
            "new_execution_authority": False,
            "automatic_production_promotion": False,
            "external_qualification_required_for_production_candidate": True,
            "human_release_decision_required": True,
        }

    def historical_build379_fingerprint(self) -> str:
        try:
            payload = json.loads((self.install_dir / "BUILD_379_TEST_EVIDENCE.json").read_text(encoding="utf-8"))
            value = str(payload.get("code_fingerprint") or "")
            return value if len(value) == 64 else ""
        except Exception:
            return ""

    def external_validation_matrix(self) -> dict[str, Any]:
        ext = self.qualification379.external_receipt_status(code_fingerprint=self.historical_build379_fingerprint())
        return {
            "build379_independent_operational_qualification": ext.get("state", "not_run"),
            "postgres_team_backend": "not_run",
            "s3_minio_object_store": "not_run",
            "team_search_backend": "not_run",
            "external_remote_team_clients": "not_run",
            "corporate_live_connectors": "not_run",
            "procurement_live_connectors": "not_run",
            "reference_archive_live_connectors": "not_run",
            "external_long_running_crawler_soak_load": "not_run",
            "real_tor_daemon_and_onion_service": "not_run",
            "entity_resolution_real_world_holdout": "not_run",
            "external_graph_analyst_usability": "not_run",
            "external_multi_analyst_workflow": "not_run",
            "ai_real_case_planning_evaluation": "not_run",
            "professional_dossier_review": "not_run",
            "external_image_provider_analyst_validation": "not_run",
            "external_voice_stt_multi_analyst_validation": "not_run",
            "local_loopback_tls": "validated_local",
            "local_operations_runtime": "validated_local",
        }

    def restricted_scope(self) -> dict[str, Any]:
        return {
            "professional_pilot_default_scope": [
                "local_or_controlled_private_workspace",
                "case_scoped_rbac",
                "human_reviewed_clearnet_sources",
                "governed_crawler_with_budgets",
                "entity_resolution_with_independent_human_review",
                "evidence_first_dossier",
                "local_image_intelligence_review",
                "local_voice_intent_preview_and_confirmation",
                "defensive_opsec_supervision",
            ],
            "kept_disabled_or_separately_gated": [
                "automatic_identity_merge",
                "automatic_scope_expansion",
                "unreviewed_live_connectors",
                "tor_live_without_separate_validation_and_confirmation",
                "external_reverse_image_without_review",
                "public_remote_team_deployment_without_validation",
                "automatic_production_promotion",
                "firewall_os_tor_credential_acl_mutation",
            ],
        }

    def crawler_slo_gate(self) -> dict[str, Any]:
        try:
            raw = json.loads((self.install_dir / "LOCAL_PREQUALIFICATION_BUILD_379.json").read_text(encoding="utf-8"))
            local = raw if isinstance(raw, dict) and raw.get("build") == "379.0" else {}
        except Exception:
            local = {}
        metrics = dict(local.get("metrics") or {})
        checks = dict(local.get("checks") or {})
        ext = self.qualification379.external_receipt_status(code_fingerprint=self.historical_build379_fingerprint())
        local_pass = bool(local) and local.get("result") == "pass" and all(bool(v) for v in checks.values())
        external_pass = bool(ext.get("externally_validated"))
        return {
            "policy": POLICY,
            "local_prequalification_state": "pass" if local_pass else "fail_or_missing",
            "external_slo_state": "validated" if external_pass else "not_run",
            "pilot_slo_gate_pass": local_pass,
            "production_slo_gate_pass": local_pass and external_pass,
            "local_metrics": {
                "crawler_jobs_created": int(metrics.get("crawler_jobs_created") or 0),
                "failure_injections": int(metrics.get("failure_injections") or 0),
                "workers": int(metrics.get("workers") or 0),
                "recovery_ratio": float(metrics.get("recovery_ratio") or 0.0),
                "p95_lease_recovery_seconds": float(metrics.get("p95_lease_recovery_seconds") or 0.0),
                "p95_queue_dispatch_seconds": float(metrics.get("p95_queue_dispatch_seconds") or 0.0),
                "p95_failure_containment_seconds": float(metrics.get("p95_failure_containment_seconds") or 0.0),
                "stale_leases_after_recovery": int(metrics.get("stale_leases_after_recovery") or 0),
                "cross_case_leaks": int(metrics.get("cross_case_leaks") or 0),
                "evidence_loss_events": int(metrics.get("evidence_loss_events") or 0),
                "unauthorized_network_escalations": int(metrics.get("unauthorized_network_escalations") or 0),
                "accelerated_local_simulation": bool(metrics.get("accelerated_local_simulation")),
            },
            "truthful_note": "Local accelerated prequalification supports a controlled professional pilot only. Production SLO status requires the independent Build-379 signed receipt.",
        }

    def pilot_telemetry(self, *, case_id: str = "") -> dict[str, Any]:
        runtime = self.qualification379.runtime_snapshot(case_id=case_id)
        crawler = dict(self.build379.crawler_status())
        ext = self.qualification379.external_receipt_status(code_fingerprint=self.historical_build379_fingerprint())
        return {
            "policy": POLICY,
            "build": "380.0",
            "case_id": str(case_id),
            "runtime_ready_for_bounded_work": bool(runtime.get("ready_for_bounded_work")),
            "worker_health": runtime.get("worker_health") or {},
            "backpressure": runtime.get("backpressure") or {},
            "object_store_pressure": runtime.get("object_store_pressure") or {},
            "crawler_improvement_build": 380,
            "crawler_queue_lease_stability": bool(crawler.get("qualification_queue_lease_stability")),
            "case_isolation": bool(crawler.get("qualification_case_isolation")),
            "automatic_evidence_eviction": False,
            "external_qualification_state": ext.get("state", "not_run"),
            "network_execution_by_telemetry": False,
            "background_workers_started_by_telemetry": 0,
        }

    @staticmethod
    def classify(*, local_ready: bool, external_qualified: bool) -> str:
        if not local_ready:
            return "not_ready"
        if external_qualified:
            return "production_candidate"
        return "professional_pilot_only"

    def current_decision(self, *, local_ready: bool) -> dict[str, Any]:
        ext = self.qualification379.external_receipt_status(code_fingerprint=self.historical_build379_fingerprint())
        external = bool(ext.get("externally_validated"))
        decision = self.classify(local_ready=local_ready, external_qualified=external)
        matrix = self.external_validation_matrix()
        remaining = sorted(k for k, v in matrix.items() if v == "not_run")
        return {
            "policy": POLICY,
            "build": "380.0",
            "decision": decision,
            "professional_pilot_ready": decision in {"professional_pilot_only", "production_candidate"},
            "production_candidate": decision == "production_candidate",
            "production_release_ready": decision == "production_candidate",
            "external_qualification_validated": external,
            "external_qualification_state": ext.get("state", "not_run"),
            "remaining_external_validation_items": remaining,
            "production_scope_if_candidate": "restricted_core_clearweb; unvalidated specialty paths remain separately gated",
            "human_release_decision_required": True,
            "automatic_production_promotion": False,
            "network_scope_granted_by_decision": False,
            "truthful_note": "Current package is a professional-pilot candidate when local gates pass. It becomes only a production candidate after independent Build-379 qualification; unvalidated specialty capabilities remain separately gated.",
        }


class AutonomousInvestigation380:
    def __init__(self, *, base379: Any, readiness380: ProfessionalPilotDecision380) -> None:
        self.base379 = base379
        self.readiness380 = readiness380

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.base379, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def status(self) -> dict[str, Any]:
        base = dict(self.base379.status())
        base.update({
            "policy_version": AI_POLICY,
            "final_readiness_context": True,
            "production_decision_authority": False,
            "release_authority": False,
            "scope_expansion_authority": False,
            "automatic_network_authority": False,
        })
        return base

    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        out = dict(self.base379.run_cycle(case_id=case_id, max_ticks=max_ticks))
        telemetry = self.readiness380.pilot_telemetry(case_id=case_id)
        out["phase16_final_readiness_v380"] = telemetry
        dossier = dict(out.get("dossier") or {})
        dossier["phase16_final_readiness_v380"] = {
            "runtime_ready_for_bounded_work": telemetry["runtime_ready_for_bounded_work"],
            "external_qualification_state": telemetry["external_qualification_state"],
            "production_decision_authority": False,
        }
        out["dossier"] = dossier
        out["production_decision_authority"] = False
        out["release_authority"] = False
        return out


class DefensiveOpsecSupervisor380:
    def __init__(self, db: Any, audit: Any, *, base379: Any, jobs: Any) -> None:
        self.db = db
        self.audit = audit
        self.base379 = base379
        self.jobs = jobs

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.base379, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _override_jobs(self, case_id: str) -> list[dict[str, Any]]:
        rows = self.db.all(
            "SELECT job_id,status,payload_json FROM phase15_jobs WHERE case_id=? AND status IN ('queued','running','workflow_paused')",
            (str(case_id),),
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            payload = _json(row.get("payload_json"), {}) or {}
            marker = next((m for m in PRODUCTION_OVERRIDE_MARKERS if payload.get(m) is True), "")
            if marker:
                out.append({"job_id": row["job_id"], "status": row["status"], "marker": marker, "reason": "production_gate_override_in_operational_job"})
        return out

    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        violations = self._override_jobs(case_id)
        cancelled: list[str] = []
        drain_required: list[str] = []
        for item in violations:
            jid = str(item["job_id"])
            if item["status"] in {"queued", "workflow_paused"}:
                self.jobs.cancel(jid, actor="opsec380")
                cancelled.append(jid)
            else:
                drain_required.append(jid)
            self.audit.log("OPSEC380_PRODUCTION_GATE_OVERRIDE_BLOCKED", "crawler_job", jid, case_id=case_id, details={**item, "policy": OPSEC_POLICY})
        inherited = dict(self.base379.protect_case(case_id=case_id))
        inherited.update({
            "policy_v380": OPSEC_POLICY,
            "production_gate_override_violations": violations,
            "cancelled_override_jobs": cancelled,
            "running_override_jobs_drain_required": drain_required,
            "production_override_authority": False,
            "automatic_release_authority": False,
            "automatic_evidence_eviction": False,
            "system_mutations": False,
        })
        return inherited

    def status(self) -> dict[str, Any]:
        base = dict(self.base379.status())
        base.update({
            "policy_v380": OPSEC_POLICY,
            "production_gate_override_containment": True,
            "production_override_authority": False,
            "automatic_release_authority": False,
            "automatic_evidence_eviction": False,
            "firewall_mutation": False,
            "os_mutation": False,
            "tor_configuration_mutation": False,
            "credential_mutation": False,
            "acl_mutation": False,
            "system_mutations": False,
        })
        return base
