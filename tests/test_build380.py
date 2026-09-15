from __future__ import annotations

import ast
import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app380 import create_workspace_app380
from eagleeye.phase16.external_qualification379 import POLICY as Q379_POLICY
from eagleeye_pro.core.app_context import AppContext

PW = "Orbit-Pine-Quartz-380!"


def ctx(tmp_path):
    return AppContext(base_dir=tmp_path, actor="test380")


def admin(c):
    u = c.team_identity_359.create_initial_admin(username="admin380", display_name="Admin 380", password=PW)
    return {**u, "session_id": "admin-session-380"}


def case(c, a, title="Final Pilot Case"):
    return c.build380.team_create_case(identity=a, title=title, client="QA", purpose="authorized build380 final qualification", legal_basis="public_data")


def _receipt_payload(c):
    fp = c.professional_pilot_380.historical_build379_fingerprint()
    return {
        "policy": Q379_POLICY,
        "build": "379.0",
        "code_fingerprint": fp,
        "reviewer_id": "independent-reviewer-380-fixture",
        "independent_reviewer": True,
        "metrics": {
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
        },
        "evidence_artifacts": [
            {"name": "soak.json", "sha256": "1" * 64},
            {"name": "load.json", "sha256": "2" * 64},
            {"name": "failure.json", "sha256": "3" * 64},
        ],
    }


def _write_receipt(c):
    q = Path(c.paths.base_dir) / "qualification_379"
    q.mkdir(parents=True, exist_ok=True)
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    (q / "trusted_external_reviewer_ed25519.pem").write_bytes(
        public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    payload = _receipt_payload(c)
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
    signature = private.sign(body)
    (q / "external_receipt.json").write_text(
        json.dumps({"signed_payload": payload, "signature_b64": base64.b64encode(signature).decode()}, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def test_001_version(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build380.version_status() == {"runtime_build":"380.0","schema_version":"380.0","package_version":"380.0.0","coherent":True}


def test_002_phase_complete(tmp_path):
    with ctx(tmp_path) as c:
        s=c.professional_pilot_380.status(); assert s["phase16_builds_completed"]==20 and s["phase16_total_builds"]==20


def test_003_schema_no_new_tables(tmp_path):
    with ctx(tmp_path) as c:
        m=c.build380.schema_metrics(); assert m["within_gate"] and (m["table"],m["index"],m["trigger"])==(165,133,8) and m["build380_new_tables"]==0
        assert not any("380" in r["name"] for r in c.db.all("SELECT name FROM sqlite_master WHERE type='table'"))


def test_004_decision_taxonomy_not_ready():
    from eagleeye.phase16.professional_pilot380 import ProfessionalPilotDecision380
    assert ProfessionalPilotDecision380.classify(local_ready=False, external_qualified=False)=="not_ready"


def test_005_decision_taxonomy_pilot():
    from eagleeye.phase16.professional_pilot380 import ProfessionalPilotDecision380
    assert ProfessionalPilotDecision380.classify(local_ready=True, external_qualified=False)=="professional_pilot_only"


def test_006_decision_taxonomy_production_candidate():
    from eagleeye.phase16.professional_pilot380 import ProfessionalPilotDecision380
    assert ProfessionalPilotDecision380.classify(local_ready=True, external_qualified=True)=="production_candidate"


def test_007_no_auto_production_promotion(tmp_path):
    with ctx(tmp_path) as c: assert c.professional_pilot_380.status()["automatic_production_promotion"] is False


def test_008_human_release_required(tmp_path):
    with ctx(tmp_path) as c: assert c.professional_pilot_380.status()["human_release_decision_required"] is True


def test_009_decision_layer_no_network(tmp_path):
    with ctx(tmp_path) as c: assert c.professional_pilot_380.status()["network_execution_by_decision_layer"] is False


def test_010_historical_379_fingerprint(tmp_path):
    with ctx(tmp_path) as c:
        fp=c.professional_pilot_380.historical_build379_fingerprint(); assert len(fp)==64 and all(x in "0123456789abcdef" for x in fp)


def test_011_external_not_run_default(tmp_path):
    with ctx(tmp_path) as c:
        m=c.build380.external_validation_matrix(); assert m["build379_independent_operational_qualification"]=="not_run"


def test_012_local_tls_recorded(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.external_validation_matrix()["local_loopback_tls"]=="validated_local"


def test_013_local_operations_recorded(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.external_validation_matrix()["local_operations_runtime"]=="validated_local"


def test_014_postgres_external_gap(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.external_validation_matrix()["postgres_team_backend"]=="not_run"


def test_015_object_store_external_gap(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.external_validation_matrix()["s3_minio_object_store"]=="not_run"


def test_016_tor_external_gap(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.external_validation_matrix()["real_tor_daemon_and_onion_service"]=="not_run"


def test_017_entity_external_gap(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.external_validation_matrix()["entity_resolution_real_world_holdout"]=="not_run"


def test_018_image_external_gap(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.external_validation_matrix()["external_image_provider_analyst_validation"]=="not_run"


def test_019_voice_external_gap(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.external_validation_matrix()["external_voice_stt_multi_analyst_validation"]=="not_run"


def test_020_pilot_slo_gate_pass(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build380.final_crawler_slo_gate(); assert s["pilot_slo_gate_pass"] is True and s["local_prequalification_state"]=="pass"


def test_021_production_slo_gate_not_run(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build380.final_crawler_slo_gate(); assert s["production_slo_gate_pass"] is False and s["external_slo_state"]=="not_run"


def test_022_local_recovery_ratio(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.final_crawler_slo_gate()["local_metrics"]["recovery_ratio"]>=0.99


def test_023_local_no_cross_case_leak(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.final_crawler_slo_gate()["local_metrics"]["cross_case_leaks"]==0


def test_024_local_no_evidence_loss(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.final_crawler_slo_gate()["local_metrics"]["evidence_loss_events"]==0


def test_025_local_no_network_escalation(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.final_crawler_slo_gate()["local_metrics"]["unauthorized_network_escalations"]==0


def test_026_telemetry_no_network(tmp_path):
    with ctx(tmp_path) as c:
        t=c.build380.pilot_telemetry(); assert t["network_execution_by_telemetry"] is False and t["background_workers_started_by_telemetry"]==0


def test_027_telemetry_ready_clean(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.pilot_telemetry()["runtime_ready_for_bounded_work"] is True


def test_028_crawler_status_increment(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build380.crawler_status(); assert s["crawler_improvement_build"]==380 and s["final_slo_gate"] and s["final_professional_pilot_telemetry"]


def test_029_crawler_no_auto_promotion(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.crawler_status()["automatic_production_promotion"] is False


def test_030_restricted_scope_no_auto_merge(tmp_path):
    with ctx(tmp_path) as c: assert "automatic_identity_merge" in c.professional_pilot_380.restricted_scope()["kept_disabled_or_separately_gated"]


def test_031_restricted_scope_no_auto_expand(tmp_path):
    with ctx(tmp_path) as c: assert "automatic_scope_expansion" in c.professional_pilot_380.restricted_scope()["kept_disabled_or_separately_gated"]


def test_032_valid_external_receipt_changes_classification(tmp_path):
    with ctx(tmp_path) as c:
        _write_receipt(c); d=c.professional_pilot_380.current_decision(local_ready=True); assert d["external_qualification_validated"] and d["decision"]=="production_candidate"


def test_033_receipt_never_grants_network_scope(tmp_path):
    with ctx(tmp_path) as c:
        _write_receipt(c); d=c.professional_pilot_380.current_decision(local_ready=True); assert d["network_scope_granted_by_decision"] is False


def test_034_ai_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s=c.ai_autonomy_380.status(); assert not s["production_decision_authority"] and not s["release_authority"] and not s["automatic_network_authority"]


def test_035_ai_dossier_readiness_context(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; out=c.build380.run_autonomous_investigation(case_id=cid,max_ticks=1); assert "phase16_final_readiness_v380" in out["dossier"] and out["production_decision_authority"] is False


def test_036_opsec_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s=c.opsec_supervisor_380.status(); assert not s["production_override_authority"] and not s["automatic_release_authority"] and not s["system_mutations"]


def test_037_opsec_cancels_queued_override(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; j=c.job_engine_348.enqueue(job_type="governed_crawl_v1",payload={"force_production_candidate":True},case_id=cid,idempotency_key="override380")
        out=c.build380.autonomous_opsec_protect(case_id=cid); assert j["job_id"] in out["cancelled_override_jobs"] and c.job_engine_348.get(j["job_id"])["status"]=="cancelled"


def test_038_opsec_running_override_drains(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; j=c.job_engine_348.enqueue(job_type="governed_crawl_v1",payload={"bypass_final_gate":True},case_id=cid,idempotency_key="override-running380")
        c.db.execute("UPDATE phase15_jobs SET status='running',lease_owner='worker380',lease_expires_at='2999-01-01T00:00:00+00:00' WHERE job_id=?",(j["job_id"],))
        out=c.build380.autonomous_opsec_protect(case_id=cid); assert j["job_id"] in out["running_override_jobs_drain_required"] and c.job_engine_348.get(j["job_id"])["status"]=="running"


def test_039_opsec_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); c1=case(c,a,"A")["case_id"]; c2=case(c,a,"B")["case_id"]; j=c.job_engine_348.enqueue(job_type="governed_crawl_v1",payload={"production_override":True},case_id=c2,idempotency_key="override-case380")
        c.build380.autonomous_opsec_protect(case_id=c1); assert c.job_engine_348.get(j["job_id"])["status"]=="queued"


def test_040_health_truthful(tmp_path):
    app=create_workspace_app380(base_dir=tmp_path); client=TestClient(app); h=client.get("/health").json(); assert h["build"]=="380.0" and h["phase16_builds_completed"]==20 and h["phase16_complete"] is True and h["production_release_ready"] is False; app.state.context.close()


def test_041_web_requires_auth(tmp_path):
    app=create_workspace_app380(base_dir=tmp_path); client=TestClient(app); assert client.get("/api/build380/final-status").status_code==401; app.state.context.close()


def test_042_no_direct_network_imports_new_core(tmp_path):
    root=Path(__file__).parents[1]
    for rel in ["src/eagleeye/phase16/professional_pilot380.py","src/eagleeye/application/build380/service.py","src/eagleeye/interfaces/web/app380.py"]:
        tree=ast.parse((root/rel).read_text()); imports={n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import)}|{str(n.module or '').split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
        assert not ({"requests","httpx","urllib","socket","ssl","subprocess"}&imports)


def test_043_roadmap_marks_380_completed(tmp_path):
    root=Path(__file__).parents[1]; t=(root/"CRAWLER_ROADMAP_BUILD_370_TO_380.md").read_text(encoding="utf-8").casefold(); assert "380" in t and "completed" in t and "pilot" in t and "slo" in t


def test_044_masterplan_progress_20_of_20(tmp_path):
    root=Path(__file__).parents[1]; t=(root/"PHASE_16_MASTERPLAN_BUILD_361_TO_380.md").read_text(encoding="utf-8"); assert "Build 380 actual status" in t and "20/20" in t


def test_045_final_assessment_truthful(tmp_path):
    root=Path(__file__).parents[1]; t=(root/"FINAL_READINESS_ASSESSMENT_BUILD_380.md").read_text(encoding="utf-8").casefold(); assert "professional_pilot_only" in t and "not_run" in t and "production_candidate=false" in t


def test_046_phase_final_status_truthful(tmp_path):
    root=Path(__file__).parents[1]; t=(root/"PHASE_16_FINAL_STATUS_BUILD_380.md").read_text(encoding="utf-8").casefold(); assert "20/20" in t and "professional_pilot_only" in t


def test_047_no_literal_true_gate(tmp_path):
    with ctx(tmp_path) as c: assert c.build380.active_gate_literal_true_lines()==[]


def test_048_code_fingerprint_sha256(tmp_path):
    with ctx(tmp_path) as c:
        fp=c.build380.code_fingerprint(); assert len(fp)==64 and all(ch in "0123456789abcdef" for ch in fp)


def test_049_historical_379_evidence_available(tmp_path):
    with ctx(tmp_path) as c: assert c.build380._historical_379_ready() is True


def test_050_capabilities_no_false_external_claim(tmp_path):
    with ctx(tmp_path) as c: assert not any(x["states"]["externally_validated"] for x in c.build380.capabilities())


def test_051_pilot_default_scope_has_governed_crawler(tmp_path):
    with ctx(tmp_path) as c: assert "governed_crawler_with_budgets" in c.professional_pilot_380.restricted_scope()["professional_pilot_default_scope"]


def test_052_current_readiness_with_local_inputs_is_pilot(tmp_path):
    with ctx(tmp_path) as c:
        d=c.professional_pilot_380.current_decision(local_ready=True); assert d["decision"]=="professional_pilot_only" and d["professional_pilot_ready"] and not d["production_candidate"]


def test_053_unvalidated_specialties_remain_listed(tmp_path):
    with ctx(tmp_path) as c:
        d=c.professional_pilot_380.current_decision(local_ready=True); assert len(d["remaining_external_validation_items"])>=10


def test_054_no_new_execution_authority(tmp_path):
    with ctx(tmp_path) as c: assert c.professional_pilot_380.status()["new_execution_authority"] is False
