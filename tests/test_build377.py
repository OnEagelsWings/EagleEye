from __future__ import annotations

import ast
import io
import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from eagleeye.interfaces.web.app377 import create_workspace_app377
from eagleeye_pro.core.app_context import AppContext

PW = "Orbit-Pine-Quartz-377!"
SEED = "https://example.org/image377-source"


def ctx(tmp_path):
    return AppContext(base_dir=tmp_path, actor="test377")


def admin(c):
    u = c.team_identity_359.create_initial_admin(username="admin377", display_name="Admin 377", password=PW)
    return {**u, "session_id": "admin-session-377"}


def case(c, a):
    return c.build377.team_create_case(identity=a, title="Image Validation Case", client="QA", purpose="authorized image pipeline evaluation", legal_basis="public_data")


def image_bytes(fmt="PNG", color=(20, 40, 60)):
    b = io.BytesIO()
    Image.new("RGB", (32, 24), color=color).save(b, format=fmt)
    return b.getvalue()


def source(c):
    s = c.crawler_frontier_352.register_source(display_name="Image Source", seed_urls=[SEED], terms_ref="public read-only terms", max_depth=0, max_pages=1, requests_per_minute=5, max_response_bytes=1000000)
    if s["review_status"] == "pending_review":
        s = c.crawler_frontier_352.review_source(s["source_id"], decision="approve_read_only", rationale="reviewed public image source", reviewer="admin377")
    return s


def crawl(c, cid, s, rid="crawl377"):
    sr = "sr_" + rid
    at = "2026-09-10T04:00:00+00:00"
    c.db.execute("INSERT INTO phase15_search_runs(search_run_id,case_id,task_id,search_kind,state,opsec_state,network_profile_ref,workspace_ref,policy_version,created_by,created_at,completed_at,summary_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (sr, cid, None, "crawler", "completed", "green", None, None, "test377", "test377", at, at, "{}"))
    c.db.execute("INSERT INTO phase15_crawl_runs(crawl_run_id,case_id,source_id,search_run_id,status,pages_fetched,pages_stored,bytes_fetched,started_at,completed_at,created_at,summary_json,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (rid, cid, s["source_id"], sr, "succeeded", 1, 1, 100, at, at, at, json.dumps({"transport_kind":"static_replay_v1"}), "h"*64))
    return sr, rid


def ingest(c, cid, *, data=None, s=None, rid="", sr=None):
    data = data or image_bytes()
    return c.build377.image_ingest(case_id=cid, content=data, declared_media_type="image/png", filename="fixture.png", search_run_id=sr, source_id=(s["source_id"] if s else None), crawl_run_id=rid, source_url=(SEED + "/fixture.png" if s else ""))


def test_version(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build377.version_status() == {"runtime_build":"377.0","schema_version":"377.0","package_version":"377.0.0","coherent":True}


def test_phase_progress(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build377.phase16_status()["builds_completed"] == 17
        assert c.build377.phase16_status()["crawler_improvement_build"] == 377


def test_schema_no_new_tables(tmp_path):
    with ctx(tmp_path) as c:
        _ = c.build377
        m = c.build377.schema_metrics()
        assert m["within_gate"] and m["image_validation_new_tables"] == 0
        assert not any("377" in r["name"] for r in c.db.all("SELECT name FROM sqlite_master WHERE type='table'"))


def test_image_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s = c.image_live_validation_377.status()
        assert s["image_agent_network_authority"] is False
        assert s["automatic_reverse_image_search"] is False
        assert s["automatic_face_identity"] is False
        assert s["automatic_scene_location_confirmation"] is False


def test_crawler_increment(tmp_path):
    with ctx(tmp_path) as c:
        s = c.build377.crawler_status()
        assert s["image_media_provenance"] and s["exact_image_dedup_before_object_write"] and s["object_store_pressure_control"]
        assert s["automatic_reverse_image_search"] is False


def test_ingest_new_image(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        o=ingest(c,cid)
        assert o["deduplicated"] is False and o["new_object_written"] is True
        assert o["inspection"]["format"] == "PNG"


def test_exact_duplicate_suppresses_new_object(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; data=image_bytes()
        first=ingest(c,cid,data=data); before=c.db.one("SELECT COUNT(*) c FROM phase15_objects WHERE case_id=?",(cid,))["c"]
        second=ingest(c,cid,data=data); after=c.db.one("SELECT COUNT(*) c FROM phase15_objects WHERE case_id=?",(cid,))["c"]
        assert second["deduplicated"] and not second["new_object_written"] and first["media_id"]==second["media_id"] and before==after


def test_dedup_is_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); c1=case(c,a)["case_id"]; c2=case(c,a)["case_id"]; data=image_bytes()
        x=ingest(c,c1,data=data); y=ingest(c,c2,data=data)
        assert not y["deduplicated"] and x["media_id"] != y["media_id"]


def test_handoff_has_no_raw_bytes(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; o=ingest(c,cid)
        row=c.db.one("SELECT task_json FROM phase15_agent_tasks WHERE task_id=?",(o["handoff"]["task_id"],)); p=json.loads(row["task_json"])
        assert p["raw_image_bytes_in_task"] is False and p["network_budget"] == 0


def test_handoff_never_confirms_identity(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; o=ingest(c,cid)
        assert o["handoff"]["payload"]["identity_confirmed"] is False and o["handoff"]["payload"]["scene_location_confirmed"] is False


def test_technical_signals_persisted(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; o=ingest(c,cid)
        asset=c.build377.image_asset(o["media_id"])
        assert "manipulation_signals_v1" in asset["metadata"]
        assert asset["metadata"]["manipulation_signals_v1"]["manipulation_confirmed"] is False


def test_crawl_provenance_chain(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); sr,rid=crawl(c,cid,s); o=ingest(c,cid,s=s,rid=rid,sr=sr)
        p=c.build377.image_provenance(case_id=cid)[0]
        assert p["media_id"]==o["media_id"] and p["crawl_run_id"]==rid and p["source_id"]==s["source_id"] and p["provenance_integrity_valid"]


def test_cross_case_crawl_run_blocked(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); c1=case(c,a)["case_id"]; c2=case(c,a)["case_id"]; s=source(c); sr,rid=crawl(c,c1,s)
        try: ingest(c,c2,s=s,rid=rid,sr=sr)
        except PermissionError: pass
        else: raise AssertionError("cross case crawl run should be blocked")


def test_crawl_source_mismatch_blocked(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s1=source(c); s2=c.crawler_frontier_352.register_source(display_name="Other",seed_urls=["https://other.example.org/"],terms_ref="terms",max_depth=0,max_pages=1,requests_per_minute=5,max_response_bytes=1000000); s2=c.crawler_frontier_352.review_source(s2["source_id"],decision="approve_read_only",rationale="ok",reviewer="admin377"); sr,rid=crawl(c,cid,s1)
        try: ingest(c,cid,s=s2,rid=rid,sr=sr)
        except PermissionError: pass
        else: raise AssertionError("source mismatch should be blocked")


def test_storage_pressure_normal(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        assert c.build377.image_storage_pressure(case_id=cid)["state"] == "normal"


def test_storage_pressure_soft_limit(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        p=c.image_live_validation_377
        o=p.storage_pressure(case_id=cid,incoming_bytes=p.case_soft_bytes+1)
        assert o["state"] == "soft_limit" and o["allow_new_media_object"] and o["throttle_media_discovery"]


def test_storage_pressure_hard_limit(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        p=c.image_live_validation_377
        o=p.storage_pressure(case_id=cid,incoming_bytes=p.case_hard_bytes+1)
        assert o["state"] == "hard_limit" and o["allow_new_media_object"] is False


def test_storage_pressure_never_auto_deletes(tmp_path):
    with ctx(tmp_path) as c:
        assert c.image_live_validation_377.storage_pressure(incoming_bytes=10**10)["deletion_or_eviction_automatic"] is False


def test_hard_pressure_blocks_new_media_without_allocating(tmp_path):
    with ctx(tmp_path) as c:
        from eagleeye.phase16.image_live_validation377 import ImageMediaPipeline377
        a=admin(c); cid=case(c,a)["case_id"]
        p=ImageMediaPipeline377(c.db,c.audit,build376=c.build376,build355=c.build355,image_agent=c.image_intelligence_agent_353,media_crawler=c.media_crawler_353,jobs=c.job_engine_348,case_soft_bytes=10,case_hard_bytes=20,global_soft_bytes=100,global_hard_bytes=200)
        try:p.ingest_image(case_id=cid,content=image_bytes(),declared_media_type="image/png",filename="x.png")
        except PermissionError as exc: assert "hard_limit" in str(exc)
        else: raise AssertionError("hard pressure should block")


def test_case_summary(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; ingest(c,cid)
        s=c.build377.image_case_summary(case_id=cid)
        assert s["image_assets"]==1 and s["external_network_used"] is False and s["identity_confirmed"] is False


def test_case_summary_handoff_count(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; data=image_bytes(); ingest(c,cid,data=data); ingest(c,cid,data=data)
        assert c.build377.image_case_summary(case_id=cid)["handoff_records"]==2


def test_visual_geo_requires_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; o=ingest(c,cid)
        try:c.build377.visual_geolocation(media_id=o["media_id"],confirmation="NO")
        except PermissionError:pass
        else:raise AssertionError("confirmation required")


def test_visual_geo_after_confirmation_remains_hypothesis(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; o=ingest(c,cid)
        g=c.build377.visual_geolocation(media_id=o["media_id"],confirmation="ANALYZE")
        assert g["geolocation"]["scene_location_confirmed"] is False and g["technical_signals"]["authenticity_confirmed"] is False


def test_no_reverse_image_auto_job_from_ingest(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; ingest(c,cid)
        n=c.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE case_id=? AND job_type='reverse_image_search_lead_v1'",(cid,))["c"]
        assert n==0


def test_no_media_fetch_auto_job_from_ingest(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; ingest(c,cid)
        n=c.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE case_id=? AND job_type='media_image_fetch_v1'",(cid,))["c"]
        assert n==0


def test_ai_status_no_direct_image_network(tmp_path):
    with ctx(tmp_path) as c:
        assert c.ai_autonomy_377.status()["direct_image_network_authority"] is False


def test_ai_cycle_adds_image_summary(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; ingest(c,cid)
        out=c.build377.run_autonomous_investigation(case_id=cid,max_ticks=1)
        assert "phase16_image_validation_v377" in out["dossier"] and out["direct_image_network_authority"] is False


def test_opsec_status(tmp_path):
    with ctx(tmp_path) as c:
        s=c.opsec_supervisor_377.status(); assert s["raw_image_job_payload_block"] and s["auto_reverse_image_search_block"] and s["system_mutations"] is False


def test_opsec_cancels_identity_claim_job(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        j=c.job_engine_348.enqueue(job_type="image_intelligence_handoff_v377",payload={"identity_confirmation_allowed":True,"raw_image_bytes_in_job":False},case_id=cid,rate_budget={"max_requests":0})
        r=c.build377.autonomous_opsec_protect(case_id=cid)
        assert j["job_id"] in r["cancelled_image_jobs"] and c.job_engine_348.get(j["job_id"])["status"]=="cancelled"


def test_opsec_cancels_raw_bytes_job(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        j=c.job_engine_348.enqueue(job_type="image_intelligence_handoff_v377",payload={"raw_image_bytes_in_job":True},case_id=cid,rate_budget={"max_requests":0})
        r=c.build377.autonomous_opsec_protect(case_id=cid)
        assert j["job_id"] in r["cancelled_image_jobs"]


def test_opsec_cancels_auto_scope_expansion(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        j=c.job_engine_348.enqueue(job_type="reverse_image_search_lead_v1",payload={"automatic_image_scope_expansion":True},case_id=cid,rate_budget={"max_requests":0})
        r=c.build377.autonomous_opsec_protect(case_id=cid)
        assert j["job_id"] in r["cancelled_image_jobs"]


def test_opsec_no_system_mutation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; r=c.build377.autonomous_opsec_protect(case_id=cid)
        assert r["system_mutations"] is False and r["firewall_mutations"] is False and r["tor_mutations"] is False


def test_existing_phase15_image_agent_remains_networkless(tmp_path):
    with ctx(tmp_path) as c:
        assert c.image_intelligence_agent_353.status()["network_access"] is False


def test_existing_similarity_remains_identity_neutral(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build354.architecture_status()["similarity_is_identity_evidence"] is False


def test_existing_geo_remains_hypothesis_only(tmp_path):
    with ctx(tmp_path) as c:
        assert c.visual_geo_355.status()["geolocation_output"] == "hypothesis_only"


def test_no_direct_network_imports_new_modules():
    root=Path(__file__).resolve().parents[1]
    for rel in ["src/eagleeye/phase16/image_live_validation377.py","src/eagleeye/application/build377/service.py"]:
        tree=ast.parse((root/rel).read_text())
        names={n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) and n.names}
        names|={n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module}
        assert not names.intersection({"requests","httpx","aiohttp","socket","subprocess","urllib"})


def test_no_literal_true_gate(tmp_path):
    with ctx(tmp_path) as c: assert c.build377.active_gate_literal_true_lines()==[]


def test_production_false_without_external_validation(tmp_path):
    with ctx(tmp_path) as c:
        g=c.build377.qualified_gate(); assert g["production_release_ready"] is False and g["external_image_source_validation"]=="not_run"


def test_web_health(tmp_path):
    app=create_workspace_app377(base_dir=tmp_path)
    try:
        r=TestClient(app).get('/health'); assert r.status_code==200 and r.json()["build"]=="377.0" and r.json()["crawler_improvement_build"]==377
    finally: app.state.context.close()


def test_web_image_summary_requires_auth(tmp_path):
    app=create_workspace_app377(base_dir=tmp_path)
    try: assert TestClient(app).get('/api/cases/x/image377/summary').status_code==401
    finally: app.state.context.close()


def test_web_pressure_requires_auth(tmp_path):
    app=create_workspace_app377(base_dir=tmp_path)
    try: assert TestClient(app).get('/api/cases/x/image377/storage-pressure').status_code==401
    finally: app.state.context.close()


def test_roadmap_contains_377_increment():
    t=(Path(__file__).resolve().parents[1]/"CRAWLER_ROADMAP_BUILD_370_TO_380.md").read_text().lower()
    assert "377" in t and "image" in t and "dedup" in t and "pressure" in t


def test_masterplan_phase_progress_17():
    t=(Path(__file__).resolve().parents[1]/"PHASE_16_MASTERPLAN_BUILD_361_TO_380.md").read_text()
    assert "Build 377 actual status" in t and "17/20" in t
