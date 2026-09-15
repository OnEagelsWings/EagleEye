from __future__ import annotations

import io
import ast
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app360 import create_workspace_app360

ADMIN_PW="Correct-Horse-Battery-Staple-360!"
REVIEW_PW="Velvet-Cedar-Quartz-360!"
ANALYST_PW="Saffron-Cedar-Quartz-360!"


def ctx(tmp_path): return AppContext(base_dir=tmp_path,actor="test360")
def admin(c):
    u=c.team_identity_359.create_initial_admin(username="admin360",display_name="Admin User",password=ADMIN_PW)
    return {**u,"session_id":"test-admin-360"}
def case(c,a,title="Final Case"):
    return c.build360.team_create_case(identity=a,title=title,client="",purpose="public research",legal_basis="public_data")
def add(c,a,cid,username,display,global_role,case_role,password):
    c.build360.team_create_user(identity=a,username=username,display_name=display,global_role=global_role,password=password)
    return c.build360.assign_case_role(identity=a,case_id=cid,username=username,case_role=case_role,notes="Build 360 qualification")
def source(c,a,cid,url="https://final.example.org/"):
    s=c.build360.register_crawler_source(display_name="Final source",seed_urls=[url],terms_ref="public terms",max_depth=0,max_pages=1)
    c.build360.team_review_crawler_source(identity=a,case_id=cid,source_id=s["source_id"],decision="approve_read_only",rationale="Human reviewed public read-only source")
    return s
def png_bytes():
    out=io.BytesIO(); Image.new("RGB",(16,16),(120,80,40)).save(out,format="PNG"); return out.getvalue()


def test_version_schema_and_phase_complete(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build360.version_status()=={"runtime_build":"360.0","schema_version":"360.0","package_version":"360.0.0","coherent":True}
        m=c.build360.schema_metrics(); assert (m["table"],m["index"],m["trigger"])==(141,128,8) and m["within_gate"]
        assert c.build360.architecture_status()["phase15_builds_completed"]==20


def test_external_validation_is_truthfully_incomplete(tmp_path):
    with ctx(tmp_path) as c:
        ext=c.build360.external_validation_matrix(); assert all(v["status"] in {"not_run","not_validated"} for v in ext.values())
        assert not c.build360.external_validation_complete()
        assert c.build360.qualified_gate()["production_release_ready"] is False


def test_readiness_rubric_is_bounded_and_production_false(tmp_path):
    with ctx(tmp_path) as c:
        r=c.build360.readiness_assessment(); assert 0<=r["operative_production_readiness_score"]<=100 and 0<=r["internal_engineering_readiness_percent"]<=100
        assert r["production_release_ready"] is False and r["blocking_gaps"]


def test_crawler_marks_build360_without_live_tor(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build360.crawler_release_qualification(); assert s["crawler_improvement_build"]==360 and s["live_tor_gateway"]=="not_run"


def test_no_literal_true_in_final_gate(tmp_path):
    with ctx(tmp_path) as c: assert c.build360.active_gate_literal_true_lines()==[]


def test_cross_case_rbac_still_enforced(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a,"A"); cb=case(c,a,"B")
        add(c,a,ca["case_id"],"analyst360","Analyst User","investigator","analyst",ANALYST_PW)
        c.build360.authorize("analyst360",case_id=ca["case_id"],capability="case.read")
        with pytest.raises(PermissionError): c.build360.authorize("analyst360",case_id=cb["case_id"],capability="case.read")


def test_four_eyes_export_survives_final_build(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a); cid=ca["case_id"]
        add(c,a,cid,"review360","Reviewer User","reviewer","reviewer",REVIEW_PW)
        c.build360.create_investigation_intake(case_id=cid,objective="Research public facts",key_questions=["What changed?"])
        d=c.build360.build_investigation_dossier(case_id=cid)
        req=c.build360.request_dossier_export(case_id=cid,identity=a,report_id=d.get("report_id",""))
        with pytest.raises(PermissionError): c.build360.review_dossier_export(task_id=req["task_id"],identity=a,decision="approve",rationale="same actor")
        c.build360.review_dossier_export(task_id=req["task_id"],identity="review360",decision="approve",rationale="Independent evidence review")
        out=c.build360.execute_dossier_export(task_id=req["task_id"],identity=a); assert out["state"]=="exported"


def test_crawler_expired_lease_recovery_is_lead_only(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a); cid=ca["case_id"]
        add(c,a,cid,"analyst360","Analyst User","investigator","analyst",ANALYST_PW); s=source(c,a,cid)
        out=c.build360.team_enqueue_crawl(identity="analyst360",case_id=cid,source_id=s["source_id"]); jid=out["job"]["job_id"]
        c.db.execute("UPDATE phase15_jobs SET status='running',lease_owner='crashed',lease_expires_at='2000-01-01T00:00:00+00:00' WHERE job_id=?",(jid,))
        with pytest.raises(PermissionError): c.build360.recover_expired_crawler_leases(identity="analyst360",case_id=cid)
        assert c.build360.recover_expired_crawler_leases(identity=a,case_id=cid)["count"]==1


def test_dead_letter_not_auto_recovered(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a); cid=ca["case_id"]; s=source(c,a,cid)
        out=c.build360.team_enqueue_crawl(identity=a,case_id=cid,source_id=s["source_id"]); jid=out["job"]["job_id"]
        c.db.execute("UPDATE phase15_jobs SET status='dead_letter',lease_owner='dead',lease_expires_at='2000-01-01T00:00:00+00:00' WHERE job_id=?",(jid,))
        assert c.build360.recover_expired_crawler_leases(identity=a,case_id=cid)["count"]==0
        assert c.db.one("SELECT status FROM phase15_jobs WHERE job_id=?",(jid,))["status"]=="dead_letter"


def test_opsec_preflight_blocks_private_ip(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a); cid=ca["case_id"]
        cap=c.build360.create_clearnet_capsule(case_id=cid,egress_hosts=["example.org"])
        blocked=c.build360.preflight_request(cap["search_run_id"],url="https://example.org/",resolved_ips=["127.0.0.1"],browser_webrtc_disabled=True,dns_via_approved_profile=True)
        assert blocked["final_disposition"]=="block"


def test_opsec_preflight_can_allow_public_approved_target(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a); cid=ca["case_id"]
        cap=c.build360.create_clearnet_capsule(case_id=cid,egress_hosts=["example.org"])
        out=c.build360.preflight_request(cap["search_run_id"],url="https://example.org/",resolved_ips=["93.184.216.34"],browser_webrtc_disabled=True,dns_via_approved_profile=True)
        assert out["final_disposition"] in {"allow","allow_for_gateway"}


def test_voice_export_remains_manual_ui(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a); cid=ca["case_id"]
        p=c.build360.team_voice_propose(identity=a,case_id=cid,transcript="Exportiere das Dossier")
        out=c.build360.team_voice_execute(identity=a,intent_id=p["intent_id"],confirmed=True)
        assert p["manual_ui_required"] and out["state"]=="manual_ui_required" and not out["executed"]


def test_voice_go_requires_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a); cid=ca["case_id"]
        p=c.build360.team_voice_propose(identity=a,case_id=cid,transcript="GO")
        assert p["requires_confirmation"]


def test_dossier_still_marks_hypotheses_for_review(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a); cid=ca["case_id"]
        c.build360.create_investigation_intake(case_id=cid,objective="Research public facts",key_questions=["What is supported?"])
        d=c.build360.build_investigation_dossier(case_id=cid)
        assert d.get("case_id")==cid and d.get("guardrails",{}).get("hypothesis_auto_promoted_to_fact") is False


def test_image_ingest_is_local_and_hash_bound(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a); cid=ca["case_id"]
        out=c.build360.ingest_image(case_id=cid,content=png_bytes(),declared_media_type="image/png",filename="test.png",provenance={"test":"build360"})
        assert out.get("media_id") and out.get("object",{}).get("sha256") and out.get("inspection",{}).get("disposition") in {"review_pending","accepted","safe"}


def test_access_chain_consistent(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a); c.build360.authorize(a,case_id=ca["case_id"],capability="case.read")
        assert c.team_governance_359.verify_audit_chain()["chain_consistent"]


def test_final_capabilities_never_claim_external_validation(tmp_path):
    with ctx(tmp_path) as c:
        for cap in c.build360.capabilities(): assert cap["states"]["externally_validated"] is False


def test_final_status_has_all_required_surfaces(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build360.final_status(); assert set(["gate","readiness","external_validation","crawler","schema","version"]).issubset(s)


def test_server_app_requires_login_and_exposes_final_status(tmp_path):
    root=tmp_path/"web"; app=create_workspace_app360(base_dir=root)
    with TestClient(app) as client:
        h=client.get('/health'); assert h.status_code==200 and h.json()["build"]=="360.0"
        assert client.get('/api/build360').status_code==401
        token=(root/'data/security_360/local_session_token').read_text().strip()
        assert client.get('/security/start',params={'token':token},follow_redirects=False).status_code==303
        assert client.post('/security/bootstrap',data={'username':'admin360','display_name':'Admin User','password':ADMIN_PW},follow_redirects=False).status_code==303
        assert client.post('/security/login',data={'username':'admin360','password':ADMIN_PW},follow_redirects=False).status_code==303
        assert client.get('/api/build360').status_code==200
        fs=client.get('/api/build360/final-status'); assert fs.status_code==200 and fs.json()["build"]=="360.0"


def test_new_build360_module_has_no_direct_network_or_subprocess_imports():
    files=[Path('src/eagleeye/application/build360/service.py')]
    names=set()
    for path in files:
        tree=ast.parse(path.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import): names.update(x.name.split('.')[0] for x in n.names)
            elif isinstance(n,ast.ImportFrom) and n.module: names.add(n.module.split('.')[0])
    assert not names.intersection({'requests','httpx','aiohttp','urllib','socket','subprocess'})


def test_build360_does_not_claim_live_tor_or_remote_team(tmp_path):
    with ctx(tmp_path) as c:
        a=c.build360.architecture_status(); assert not a["built_in_live_tor_transport"] and not a["multi_user_remote_server"]
