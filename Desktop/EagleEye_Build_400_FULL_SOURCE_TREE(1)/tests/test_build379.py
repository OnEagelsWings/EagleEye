from __future__ import annotations

import ast
import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app379 import create_workspace_app379
from eagleeye.phase16.external_qualification379 import POLICY
from eagleeye_pro.core.app_context import AppContext

PW = "Orbit-Pine-Quartz-379!"


def ctx(tmp_path):
    return AppContext(base_dir=tmp_path, actor="test379")


def admin(c):
    u = c.team_identity_359.create_initial_admin(username="admin379", display_name="Admin 379", password=PW)
    return {**u, "session_id": "admin-session-379"}


def case(c, a, title="Qualification Case"):
    return c.build379.team_create_case(identity=a, title=title, client="QA", purpose="authorized build379 qualification", legal_basis="public_data")


def _payload(c, *, fingerprint=None, independent=True, overrides=None):
    metrics = {
        "duration_seconds": 3600,
        "crawler_jobs": 500,
        "failure_injections": 50,
        "workers": 2,
        "recovery_ratio": 1.0,
        "p95_lease_recovery_seconds": 0.5,
        "p95_queue_dispatch_seconds": 0.5,
        "p95_failure_containment_seconds": 0.5,
        "stale_leases_after_recovery": 0,
        "cross_case_leaks": 0,
        "evidence_loss_events": 0,
        "automatic_eviction_events": 0,
        "unauthorized_network_escalations": 0,
        "audit_chain_consistent": True,
    }
    metrics.update(overrides or {})
    return {
        "policy": POLICY,
        "build": "379.0",
        "code_fingerprint": fingerprint or c.build379.code_fingerprint(),
        "reviewer_id": "external-reviewer-fixture",
        "independent_reviewer": independent,
        "metrics": metrics,
        "evidence_artifacts": [
            {"name": "soak.json", "sha256": "1" * 64},
            {"name": "load.json", "sha256": "2" * 64},
            {"name": "failure.json", "sha256": "3" * 64},
        ],
    }


def _write_receipt(c, payload, *, tamper_signature=False):
    q = Path(c.paths.base_dir) / "qualification_379"
    q.mkdir(parents=True, exist_ok=True)
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    (q / "trusted_external_reviewer_ed25519.pem").write_bytes(
        public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
    signature = private.sign(body)
    if tamper_signature:
        signature = bytes([signature[0] ^ 1]) + signature[1:]
    (q / "external_receipt.json").write_text(
        json.dumps({"signed_payload": payload, "signature_b64": base64.b64encode(signature).decode()}, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def test_001_version(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build379.version_status() == {"runtime_build":"379.0","schema_version":"379.0","package_version":"379.0.0","coherent":True}


def test_002_phase_progress(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build379.phase16_status(); assert s["builds_completed"]==19 and s["crawler_improvement_build"]==379


def test_003_schema_no_new_tables(tmp_path):
    with ctx(tmp_path) as c:
        m=c.build379.schema_metrics(); assert m["within_gate"] and (m["table"],m["index"],m["trigger"])==(165,133,8) and m["external_qualification_new_tables"]==0
        assert not any("379" in r["name"] for r in c.db.all("SELECT name FROM sqlite_master WHERE type='table'"))


def test_004_contract_min_duration(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.contract()["minimum_duration_seconds"]==3600


def test_005_contract_min_jobs(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.contract()["minimum_crawler_jobs"]==500


def test_006_contract_min_failures(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.contract()["minimum_failure_injections"]==50


def test_007_contract_min_workers(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.contract()["minimum_workers"]==2


def test_008_contract_recovery_ratio(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.contract()["minimum_recovery_ratio"]==0.99


def test_009_contract_recovery_slo(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.contract()["maximum_p95_lease_recovery_seconds"]==10.0


def test_010_contract_queue_slo(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.contract()["maximum_p95_queue_dispatch_seconds"]==30.0


def test_011_contract_containment_slo(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.contract()["maximum_p95_failure_containment_seconds"]==10.0


def test_012_contract_zero_leaks(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.contract()["maximum_cross_case_leaks"]==0


def test_013_contract_zero_loss(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.contract()["maximum_evidence_loss_events"]==0


def test_014_contract_no_auto_eviction(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.contract()["maximum_automatic_eviction_events"]==0


def test_015_status_no_runtime_fault_api(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.status()["runtime_fault_injection_api"] is False


def test_016_status_no_direct_network(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.status()["direct_network_authority"] is False


def test_017_status_no_scope_expansion(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.status()["automatic_scope_expansion"] is False


def test_018_status_receipt_ed25519(tmp_path):
    with ctx(tmp_path) as c: assert c.external_qualification_379.status()["external_receipt_signature"]=="Ed25519"


def test_019_receipt_not_run_by_default(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build379.external_qualification_status(); assert s["state"]=="not_run" and not s["externally_validated"] and not s["receipt_present"]


def test_020_valid_signed_receipt_validates(tmp_path):
    with ctx(tmp_path) as c:
        _write_receipt(c,_payload(c)); s=c.build379.external_qualification_status(); assert s["signature_valid"] and s["fingerprint_match"] and s["externally_validated"] and s["state"]=="validated"


def test_021_receipt_never_grants_network_scope(tmp_path):
    with ctx(tmp_path) as c:
        _write_receipt(c,_payload(c)); assert c.build379.external_qualification_status()["network_scope_granted"] is False


def test_022_bad_signature_rejected(tmp_path):
    with ctx(tmp_path) as c:
        _write_receipt(c,_payload(c),tamper_signature=True); s=c.build379.external_qualification_status(); assert not s["externally_validated"] and s["state"]=="invalid_receipt"


def test_023_wrong_fingerprint_rejected(tmp_path):
    with ctx(tmp_path) as c:
        _write_receipt(c,_payload(c,fingerprint="0"*64)); s=c.build379.external_qualification_status(); assert s["signature_valid"] and not s["fingerprint_match"] and not s["externally_validated"]


def test_024_weak_metrics_rejected(tmp_path):
    with ctx(tmp_path) as c:
        _write_receipt(c,_payload(c,overrides={"crawler_jobs":499})); s=c.build379.external_qualification_status(); assert not s["externally_validated"] and s["metric_gates"]["crawler_jobs"] is False


def test_025_non_independent_reviewer_rejected(tmp_path):
    with ctx(tmp_path) as c:
        _write_receipt(c,_payload(c,independent=False)); s=c.build379.external_qualification_status(); assert not s["externally_validated"] and s["metric_gates"]["independent_reviewer"] is False


def test_026_bad_evidence_hash_rejected(tmp_path):
    with ctx(tmp_path) as c:
        p=_payload(c); p["evidence_artifacts"][0]["sha256"]="xyz"; _write_receipt(c,p); s=c.build379.external_qualification_status(); assert not s["externally_validated"] and not s["metric_gates"]["evidence_artifacts"]


def test_027_runtime_snapshot_no_network(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build379.qualification_snapshot(); assert s["network_execution_by_snapshot"] is False and s["fault_injection_performed_by_runtime"] is False


def test_028_runtime_snapshot_ready_clean(tmp_path):
    with ctx(tmp_path) as c: assert c.build379.qualification_snapshot()["ready_for_bounded_work"] is True


def test_029_runtime_snapshot_holds_on_expired_lease(tmp_path):
    with ctx(tmp_path) as c:
        j=c.job_engine_348.enqueue(job_type="governed_crawl_v1",payload={},case_id="case379-expired",idempotency_key="expired379")
        c.db.execute("UPDATE phase15_jobs SET status='running',lease_owner='dead-worker',lease_expires_at='2000-01-01T00:00:00+00:00' WHERE job_id=?",(j["job_id"],))
        assert c.build379.qualification_snapshot(case_id="case379-expired")["ready_for_bounded_work"] is False


def test_030_crawler_status_increment(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build379.crawler_status(); assert s["crawler_improvement_build"]==379 and s["qualification_soak_load_failure_harness"] and s["qualification_recovery_slo_measurement"]


def test_031_crawler_status_no_boot_connections(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build379.crawler_status(); assert s["automatic_external_connections_on_boot"]==0 and s["background_workers_started_on_boot"]==0


def test_032_crawler_status_no_fault_api(tmp_path):
    with ctx(tmp_path) as c: assert c.build379.crawler_status()["production_fault_injection_api"] is False


def test_033_ai_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s=c.ai_autonomy_379.status(); assert not s["fault_injection_authority"] and not s["external_receipt_authority"] and not s["production_decision_authority"]


def test_034_ai_dossier_has_qualification_context(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; out=c.build379.run_autonomous_investigation(case_id=cid,max_ticks=1); assert "phase16_external_qualification_v379" in out["dossier"] and out["fault_injection_authority"] is False


def test_035_opsec_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s=c.opsec_supervisor_379.status(); assert not s["production_fault_injection_authority"] and not s["external_receipt_signing_authority"] and not s["system_mutations"]


def test_036_opsec_cancels_queued_fault_marker(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; j=c.job_engine_348.enqueue(job_type="governed_crawl_v1",payload={"phase16_qualification_fault_injection_v379":True},case_id=cid,idempotency_key="faultqueued379")
        out=c.build379.autonomous_opsec_protect(case_id=cid); assert j["job_id"] in out["cancelled_qualification_fault_jobs"] and c.job_engine_348.get(j["job_id"])["status"]=="cancelled"


def test_037_opsec_running_fault_drains_not_killed(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; j=c.job_engine_348.enqueue(job_type="governed_crawl_v1",payload={"qualification379_fault_injection":True},case_id=cid,idempotency_key="faultrunning379")
        c.db.execute("UPDATE phase15_jobs SET status='running',lease_owner='worker379',lease_expires_at='2999-01-01T00:00:00+00:00' WHERE job_id=?",(j["job_id"],))
        out=c.build379.autonomous_opsec_protect(case_id=cid); assert j["job_id"] in out["running_fault_jobs_drain_required"] and c.job_engine_348.get(j["job_id"])["status"]=="running"


def test_038_opsec_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); c1=case(c,a,"A")["case_id"]; c2=case(c,a,"B")["case_id"]; j=c.job_engine_348.enqueue(job_type="governed_crawl_v1",payload={"phase16_qualification_fault_injection_v379":True},case_id=c2,idempotency_key="faultcase379")
        c.build379.autonomous_opsec_protect(case_id=c1); assert c.job_engine_348.get(j["job_id"])["status"]=="queued"


def test_039_object_store_pressure_no_eviction(tmp_path):
    with ctx(tmp_path) as c:
        p=c.image_live_validation_377.storage_pressure(incoming_bytes=c.image_live_validation_377.global_hard_bytes+1); assert p["state"]=="hard_limit" and p["deletion_or_eviction_automatic"] is False


def test_040_receipt_paths_outside_install_tree(tmp_path):
    with ctx(tmp_path) as c:
        paths=c.external_qualification_379.receipt_paths(); assert str(tmp_path) in paths["directory"] and "qualification_379" in paths["directory"]


def test_041_metric_gates_complete(tmp_path):
    with ctx(tmp_path) as c:
        gates=c.external_qualification_379._metric_gates(_payload(c)); assert len(gates)==16 and all(gates.values())


def test_042_metric_gate_stale_lease_failure(tmp_path):
    with ctx(tmp_path) as c:
        gates=c.external_qualification_379._metric_gates(_payload(c,overrides={"stale_leases_after_recovery":1})); assert gates["stale_leases"] is False


def test_043_metric_gate_unauthorized_network_failure(tmp_path):
    with ctx(tmp_path) as c:
        gates=c.external_qualification_379._metric_gates(_payload(c,overrides={"unauthorized_network_escalations":1})); assert gates["unauthorized_network"] is False


def test_044_health_truthful(tmp_path):
    app=create_workspace_app379(base_dir=tmp_path); client=TestClient(app); h=client.get("/health").json(); assert h["build"]=="379.0" and h["phase16_builds_completed"]==19 and h["external_qualification_validated"] is False and h["production_fault_injection_api"] is False and h["production_release_ready"] is False; app.state.context.close()


def test_045_web_requires_auth(tmp_path):
    app=create_workspace_app379(base_dir=tmp_path); client=TestClient(app); assert client.get("/api/build379/final-status").status_code==401; app.state.context.close()


def test_046_no_direct_network_imports_new_core(tmp_path):
    root=Path(__file__).parents[1]
    for rel in ["src/eagleeye/phase16/external_qualification379.py","src/eagleeye/application/build379/service.py","src/eagleeye/interfaces/web/app379.py"]:
        tree=ast.parse((root/rel).read_text()); imports={n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import)}|{str(n.module or '').split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
        assert not ({"requests","httpx","urllib","socket","ssl","subprocess"}&imports)


def test_047_roadmap_marks_379(tmp_path):
    root=Path(__file__).parents[1]; t=(root/"CRAWLER_ROADMAP_BUILD_370_TO_380.md").read_text(encoding="utf-8").casefold(); assert "379" in t and "soak" in t and "recovery" in t


def test_048_masterplan_progress_19_of_20(tmp_path):
    root=Path(__file__).parents[1]; t=(root/"PHASE_16_MASTERPLAN_BUILD_361_TO_380.md").read_text(encoding="utf-8"); assert "379" in t and ("19/20" in t or "19 of 20" in t)


def test_049_external_guide_truthful(tmp_path):
    root=Path(__file__).parents[1]; t=(root/"EXTERNAL_QUALIFICATION_GUIDE_BUILD_379.md").read_text(encoding="utf-8").casefold(); assert "ed25519" in t and "fingerprint" in t and "not_run" in t


def test_050_no_literal_true_gate(tmp_path):
    with ctx(tmp_path) as c: assert c.build379.active_gate_literal_true_lines()==[]


def test_051_production_always_false_before_380(tmp_path):
    with ctx(tmp_path) as c:
        _write_receipt(c,_payload(c)); gate=c.build379.qualified_gate(); assert gate["production_release_ready"] is False and gate["build380_final_decision_required"] is True


def test_052_code_fingerprint_sha256(tmp_path):
    with ctx(tmp_path) as c:
        fp=c.build379.code_fingerprint(); assert len(fp)==64 and all(ch in "0123456789abcdef" for ch in fp)
