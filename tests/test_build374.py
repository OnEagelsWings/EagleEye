from __future__ import annotations

import ast, hashlib, json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from eagleeye.crawler.engine import FetchResponse, StaticTransport
from eagleeye.interfaces.web.app374 import create_workspace_app374
from eagleeye_pro.core.app_context import AppContext

PW="Orbit-Pine-Quartz-374!"
SEED="https://example.org/workflow374-source"

def ctx(tmp_path): return AppContext(base_dir=tmp_path,actor="test374")
def admin(c):
    u=c.team_identity_359.create_initial_admin(username="admin374",display_name="Admin 374",password=PW);return {**u,"session_id":"admin-session-374"}
def case(c,a,title="Workflow Case"): return c.build374.team_create_case(identity=a,title=title,client="QA",purpose="authorized workflow test",legal_basis="public_data")
def analyst(c,a,cid,username="analyst374"):
    u=c.team_governance_359.create_user(identity=a,username=username,display_name="Analyst 374",global_role="read_only",password="Analyst-Quartz-Orbit-374!")
    c.team_governance_359.assign_case_role(identity=a,case_id=cid,username=username,case_role="analyst",notes="workflow handoff test")
    return {**u,"session_id":f"session-{username}"}
def source(c,*,url=SEED,max_pages=1,name="Workflow Source"):
    s=c.crawler_frontier_352.register_source(display_name=name,seed_urls=[url],terms_ref="public read-only terms",max_depth=0,max_pages=max_pages,requests_per_minute=5,max_response_bytes=100000)
    if s["review_status"]=="pending_review":s=c.crawler_frontier_352.review_source(s["source_id"],decision="approve_read_only",rationale="reviewed public source",reviewer="admin374")
    return s
def workflow(c,a,cid,s,budget=30,source_budget=20,max_active=3):
    return c.build374.configure_case_workflow(case_id=cid,identity=a,source_budgets={s["source_id"]:source_budget},case_request_budget=budget,max_active_crawls=max_active,confirmation="WORKFLOW")
def source_and_crawl(c,a,cid,*,url=SEED,max_pages=1):
    s=source(c,url=url,max_pages=max_pages)
    q=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"])
    robots="/".join(url.split("/",3)[:3])+"/robots.txt"
    t=StaticTransport({robots:FetchResponse(robots,404,{"content-type":"text/plain"},b"",1),url:FetchResponse(url,200,{"content-type":"text/html"},b"<html>Alice Example ID-1</html>",2)})
    c.build374.crawler_run_next(worker_id="crawl374",transport=t,resolver=lambda h:["93.184.216.34"],case_id=cid)
    f=c.db.one("SELECT fetch_id FROM phase15_crawl_fetches WHERE crawl_run_id=? AND status_code=200",(q["crawl_run_id"],))
    return s,q["crawl_run_id"],f["fetch_id"]
def ent(c,a,cid,name="Alice Example",email="alice@example.test",external="ID-1",refs=("source:A","source:B")):
    anchors=[]
    if email:anchors.append({"type":"email","value":email,"reliability":.95,"source_ref":refs[0]})
    if external:anchors.append({"type":"external_id","value":external,"reliability":.9,"source_ref":refs[1]})
    return c.build374.register_entity_candidate(case_id=cid,entity_type="person",display_name=name,identity=a,anchors=anchors)["entity"]["resolution_entity_id"]
def graph_fixture(c,a,cid):
    s,run,fetch=source_and_crawl(c,a,cid);left=ent(c,a,cid);right=ent(c,a,cid,refs=("source:C","source:D"));c.build374.compare_entities_v2(case_id=cid,left_entity_id=left,right_entity_id=right,identity=a);c.build374.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fetch,target_entity_id=left,candidate_entity_id=right,identity=a);c.build374.entity_lead_run_next(worker_id="entity374",case_id=cid);return s,left,right

def valid_record_hash(row):
    body={k:row[k] for k in row if k!="record_hash"};canon=json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str);return hashlib.sha256(canon.encode()).hexdigest()==row["record_hash"]

# 1
def test_schema_no_build374_tables(tmp_path):
    with ctx(tmp_path) as c:
        _=c.build374;m=c.build374.schema_metrics();assert m["within_gate"] and (m["table"],m["index"],m["trigger"])==(165,133,8);assert m["case_workflow_new_tables"]==0;assert not any("374" in r["name"] for r in c.db.all("SELECT name FROM sqlite_master WHERE type='table'"))
# 2
def test_version(tmp_path):
    with ctx(tmp_path) as c:assert c.build374.version_status()=={"runtime_build":"374.0","schema_version":"374.0","package_version":"374.0.0","coherent":True}
# 3
def test_phase_progress(tmp_path):
    with ctx(tmp_path) as c:s=c.build374.phase16_status();assert s["builds_completed"]==14 and s["crawler_improvement_build"]==374
# 4
def test_workflow_capabilities(tmp_path):
    with ctx(tmp_path) as c:
        s=c.case_workflow_374.status_capabilities();assert s["source_request_budgets"] and s["workflow_pause_resume"] and s["two_step_analyst_handoff"] and not s["automatic_scope_expansion"]
# 5
def test_configure_requires_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c)
        with pytest.raises(PermissionError):c.build374.configure_case_workflow(case_id=cid,identity=a,source_budgets={s["source_id"]:10},confirmation="GO")
# 6
def test_configure_requires_source_budget(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"]
        with pytest.raises(ValueError):c.build374.configure_case_workflow(case_id=cid,identity=a,source_budgets={},confirmation="WORKFLOW")
# 7
def test_configure_unknown_source_rejected(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"]
        with pytest.raises(KeyError):c.build374.configure_case_workflow(case_id=cid,identity=a,source_budgets={"nope":10},confirmation="WORKFLOW")
# 8
def test_configure_blocks_existing_active_crawl(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"])
        with pytest.raises(PermissionError):workflow(c,a,cid,s)
# 9
def test_configure_active(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);w=workflow(c,a,cid,s);assert w["state"]=="active" and w["current_owner"]=="admin374"
# 10
def test_state_record_nonclaimable(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);r=c.db.one("SELECT * FROM phase15_jobs WHERE job_type='case_workflow_state_v374' AND case_id=?",(cid,));assert r["status"]=="workflow_active" and json.loads(r["rate_budget_json"])["max_requests"]==0
# 11
def test_state_record_hash_valid(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);r=c.db.one("SELECT * FROM phase15_jobs WHERE job_type='case_workflow_state_v374' AND case_id=?",(cid,));assert valid_record_hash(r)
# 12
def test_reconfigure_generation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);x=workflow(c,a,cid,s);y=workflow(c,a,cid,s);assert y["generation"]==x["generation"]+1 and y["workflow_id"]==x["workflow_id"]
# 13
def test_budget_clamped(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);w=c.build374.configure_case_workflow(case_id=cid,identity=a,source_budgets={s["source_id"]:99999},case_request_budget=99999,max_active_crawls=99,confirmation="WORKFLOW");assert w["source_budgets"][s["source_id"]]==1000 and w["case_request_budget"]==5000 and w["max_active_crawls"]==8
# 14
def test_manual_crawl_requires_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s)
        with pytest.raises(PermissionError):c.build374.workflow_enqueue_source(case_id=cid,source_id=s["source_id"],identity=a,confirmation="GO")
# 15
def test_manual_crawl_enqueued_and_tagged(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);w=workflow(c,a,cid,s);out=c.build374.workflow_enqueue_source(case_id=cid,source_id=s["source_id"],identity=a,confirmation="CRAWL");r=c.job_engine_348.get(out["job"]["job_id"]);p=json.loads(r["payload_json"]);assert p["phase16_case_workflow_v374"] and p["workflow_id"]==w["workflow_id"] and p["workflow_reserved_requests"]==4 and valid_record_hash(r)
# 16
def test_usage_reserves_requests(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);c.build374.workflow_enqueue_source(case_id=cid,source_id=s["source_id"],identity=a,confirmation="CRAWL");st=c.build374.case_workflow_status(case_id=cid,identity=a);assert st["usage"]["case_reserved_requests"]==4 and st["usage"]["source_remaining_requests"][s["source_id"]]==16
# 17
def test_manual_source_not_budgeted(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s1=source(c,url="https://example.org/a");s2=source(c,url="https://example.net/b");workflow(c,a,cid,s1)
        with pytest.raises(PermissionError):c.build374.workflow_enqueue_source(case_id=cid,source_id=s2["source_id"],identity=a,confirmation="CRAWL")
# 18
def test_source_budget_exceeded(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s,source_budget=3)
        with pytest.raises(PermissionError):c.build374.workflow_enqueue_source(case_id=cid,source_id=s["source_id"],identity=a,confirmation="CRAWL")
# 19
def test_case_budget_exceeded(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s,budget=3,source_budget=20)
        with pytest.raises(PermissionError):c.build374.workflow_enqueue_source(case_id=cid,source_id=s["source_id"],identity=a,confirmation="CRAWL")
# 20
def test_active_crawl_limit(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s1=source(c,url="https://example.org/a");s2=source(c,url="https://example.net/b");c.build374.configure_case_workflow(case_id=cid,identity=a,source_budgets={s1["source_id"]:20,s2["source_id"]:20},case_request_budget=50,max_active_crawls=1,confirmation="WORKFLOW");c.build374.workflow_enqueue_source(case_id=cid,source_id=s1["source_id"],identity=a,confirmation="CRAWL")
        with pytest.raises(PermissionError):c.build374.workflow_enqueue_source(case_id=cid,source_id=s2["source_id"],identity=a,confirmation="CRAWL")
# 21
def test_pause_requires_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s)
        with pytest.raises(PermissionError):c.build374.pause_case_workflow(case_id=cid,identity=a,reason="pause",confirmation="GO")
# 22
def test_pause_queued_job(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);out=c.build374.workflow_enqueue_source(case_id=cid,source_id=s["source_id"],identity=a,confirmation="CRAWL");st=c.build374.pause_case_workflow(case_id=cid,identity=a,reason="analyst review",confirmation="PAUSE");assert st["state"]=="paused" and out["job"]["job_id"] in st["paused_job_ids"] and c.job_engine_348.get(out["job"]["job_id"])["status"]=="workflow_paused"
# 23
def test_pause_running_marks_drain(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);out=c.build374.workflow_enqueue_source(case_id=cid,source_id=s["source_id"],identity=a,confirmation="CRAWL");job=c.crawler_production_369.claim_next(worker_id="w374",case_id=cid);assert job and job["job_id"]==out["job"]["job_id"];st=c.build374.pause_case_workflow(case_id=cid,identity=a,reason="handover pause",confirmation="PAUSE");assert out["job"]["job_id"] in st["draining_job_ids"] and c.job_engine_348.get(out["job"]["job_id"])["status"]=="running" and json.loads(c.job_engine_348.get(out["job"]["job_id"])["payload_json"])["workflow_pause_requested_v374"] is True
# 24
def test_paused_blocks_new_crawl(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);c.build374.pause_case_workflow(case_id=cid,identity=a,reason="pause",confirmation="PAUSE")
        with pytest.raises(PermissionError):c.build374.workflow_enqueue_source(case_id=cid,source_id=s["source_id"],identity=a,confirmation="CRAWL")
# 25
def test_resume_requires_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);c.build374.pause_case_workflow(case_id=cid,identity=a,reason="pause",confirmation="PAUSE")
        with pytest.raises(PermissionError):c.build374.resume_case_workflow(case_id=cid,identity=a,confirmation="GO")
# 26
def test_resume_queued_job(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);out=c.build374.workflow_enqueue_source(case_id=cid,source_id=s["source_id"],identity=a,confirmation="CRAWL");c.build374.pause_case_workflow(case_id=cid,identity=a,reason="pause",confirmation="PAUSE");st=c.build374.resume_case_workflow(case_id=cid,identity=a,confirmation="RESUME");assert st["state"]=="active" and c.job_engine_348.get(out["job"]["job_id"])["status"]=="queued"
# 27
def test_complete_state(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);st=c.build374.complete_case_workflow(case_id=cid,identity=a,note="analysis complete",confirmation="COMPLETE");assert st["state"]=="completed"
# 28
def test_completed_blocks_pause(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);c.build374.complete_case_workflow(case_id=cid,identity=a,note="done",confirmation="COMPLETE")
        with pytest.raises(PermissionError):c.build374.pause_case_workflow(case_id=cid,identity=a,reason="again",confirmation="PAUSE")
# 29
def test_handoff_target_membership_required(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s)
        with pytest.raises(PermissionError):c.build374.handoff_case_workflow(case_id=cid,identity=a,to_username="nobody",note="handoff context complete",confirmation="HANDOFF")
# 30
def test_handoff_same_user_blocked(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s)
        with pytest.raises(ValueError):c.build374.handoff_case_workflow(case_id=cid,identity=a,to_username="admin374",note="handoff context complete",confirmation="HANDOFF")
# 31
def test_handoff_note_required(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);analyst(c,a,cid)
        with pytest.raises(ValueError):c.build374.handoff_case_workflow(case_id=cid,identity=a,to_username="analyst374",note="short",confirmation="HANDOFF")
# 32
def test_handoff_pending_and_hash(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);analyst(c,a,cid);st=c.build374.handoff_case_workflow(case_id=cid,identity=a,to_username="analyst374",note="transfer investigation context",confirmation="HANDOFF");assert st["state"]=="handoff_pending" and st["handoff"]["status"]=="pending_acceptance" and len(st["handoff"]["packet_hash"])==64
# 33
def test_handoff_pauses_queued_work(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);analyst(c,a,cid);out=c.build374.workflow_enqueue_source(case_id=cid,source_id=s["source_id"],identity=a,confirmation="CRAWL");st=c.build374.handoff_case_workflow(case_id=cid,identity=a,to_username="analyst374",note="transfer investigation context",confirmation="HANDOFF");assert out["job"]["job_id"] in st["paused_job_ids"]
# 34
def test_accept_only_target(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);analyst(c,a,cid);c.build374.handoff_case_workflow(case_id=cid,identity=a,to_username="analyst374",note="transfer investigation context",confirmation="HANDOFF")
        with pytest.raises(PermissionError):c.build374.accept_case_handoff(case_id=cid,identity=a,confirmation="ACCEPT")
# 35
def test_accept_requires_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);b=analyst(c,a,cid);c.build374.handoff_case_workflow(case_id=cid,identity=a,to_username="analyst374",note="transfer investigation context",confirmation="HANDOFF")
        with pytest.raises(PermissionError):c.build374.accept_case_handoff(case_id=cid,identity=b,confirmation="GO")
# 36
def test_accept_changes_owner_and_resumes(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);b=analyst(c,a,cid);out=c.build374.workflow_enqueue_source(case_id=cid,source_id=s["source_id"],identity=a,confirmation="CRAWL");c.build374.handoff_case_workflow(case_id=cid,identity=a,to_username="analyst374",note="transfer investigation context",confirmation="HANDOFF");st=c.build374.accept_case_handoff(case_id=cid,identity=b,confirmation="ACCEPT");assert st["state"]=="active" and st["current_owner"]=="analyst374" and c.job_engine_348.get(out["job"]["job_id"])["status"]=="queued"
# 37
def test_graph_navigation_requires_configured_workflow(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s,left,_=graph_fixture(c,a,cid)
        with pytest.raises(KeyError):c.build374.workflow_navigation_plan(case_id=cid,root_entity_id=left,source_ids=[s["source_id"]],identity=a)
# 38
def test_graph_navigation_budget_plan(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s,left,_=graph_fixture(c,a,cid);workflow(c,a,cid,s);p=c.build374.workflow_navigation_plan(case_id=cid,root_entity_id=left,source_ids=[s["source_id"]],identity=a);assert p["allowed"] and p["case_workflow_enforced"] and p["workflow_budget"]["allowed"]
# 39
def test_graph_navigation_budget_blocks_small_source_budget(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s,left,_=graph_fixture(c,a,cid);workflow(c,a,cid,s,source_budget=2);p=c.build374.workflow_navigation_plan(case_id=cid,root_entity_id=left,source_ids=[s["source_id"]],identity=a);assert not p["allowed"] and any("source_request_budget_exceeded" in x for x in p["reasons"])
# 40
def test_graph_navigate_tags_job(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s,left,_=graph_fixture(c,a,cid);w=workflow(c,a,cid,s);out=c.build374.workflow_navigate(case_id=cid,root_entity_id=left,source_ids=[s["source_id"]],identity=a,confirmation="NAVIGATE");r=c.job_engine_348.get(out["queued"][0]["job_id"]);p=json.loads(r["payload_json"]);assert p["phase16_case_workflow_v374"] and p["workflow_id"]==w["workflow_id"] and p["workflow_origin"]=="graph_navigation_v373"
# 41
def test_graph_navigate_paused_blocked(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s,left,_=graph_fixture(c,a,cid);workflow(c,a,cid,s);c.build374.pause_case_workflow(case_id=cid,identity=a,reason="review",confirmation="PAUSE")
        with pytest.raises(PermissionError):c.build374.workflow_navigate(case_id=cid,root_entity_id=left,source_ids=[s["source_id"]],identity=a,confirmation="NAVIGATE")
# 42
def test_invalid_jobs_detects_untagged_bypass(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);q=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]);bad=c.case_workflow_374.invalid_jobs(case_id=cid);assert any(x["job_id"]==q["job"]["job_id"] and x["reason"]=="workflow_bypass_untagged_crawl" for x in bad)
# 43
def test_opsec_cancels_untagged_bypass(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);q=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]);out=c.build374.autonomous_opsec_protect(case_id=cid);assert q["job"]["job_id"] in out["cancelled_workflow_jobs"] and c.job_engine_348.get(q["job"]["job_id"])["status"]=="cancelled"
# 44
def test_opsec_running_bypass_marks_drain(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);q=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]);job=c.crawler_production_369.claim_next(worker_id="bypass374",case_id=cid);assert job and job["job_id"]==q["job"]["job_id"];c.build374.autonomous_opsec_protect(case_id=cid);r=c.job_engine_348.get(job["job_id"]);assert r["status"]=="running" and json.loads(r["payload_json"])["workflow_pause_requested_v374"] is True
# 45
def test_ai_paused_hold(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);c.build374.pause_case_workflow(case_id=cid,identity=a,reason="review",confirmation="PAUSE");out=c.build374.run_autonomous_investigation(case_id=cid,max_ticks=1);assert out["state"]=="case_workflow_hold" and out["dossier"]["phase16_case_workflow_v374"]["research_execution_held"]
# 46
def test_ai_handoff_hold(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);analyst(c,a,cid);c.build374.handoff_case_workflow(case_id=cid,identity=a,to_username="analyst374",note="transfer investigation context",confirmation="HANDOFF");out=c.build374.run_autonomous_investigation(case_id=cid,max_ticks=1);assert out["state"]=="case_workflow_hold" and out["hold_reason"]=="workflow_handoff_pending"
# 47
def test_ai_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:s=c.ai_autonomy_374.status();assert s["case_workflow_awareness"] and s["pause_handoff_hold"] and not s["direct_workflow_mutation_authority"] and not s["automatic_scope_expansion"]
# 48
def test_opsec_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:s=c.opsec_supervisor_374.status();assert s["workflow_bypass_monitor"] and s["workflow_budget_integrity_monitor"] and not s["forced_running_worker_kill"] and not s["system_mutations"]
# 49
def test_crawler_status_increment(tmp_path):
    with ctx(tmp_path) as c:s=c.build374.crawler_status();assert s["crawler_improvement_build"]==374 and s["case_source_request_budgets"] and s["case_pause_resume"] and s["analyst_handoff_gate"]
# 50
def test_no_auto_connections_on_boot(tmp_path):
    with ctx(tmp_path) as c:s=c.build374.crawler_status();assert s["automatic_external_connections_on_boot"]==0 and s["background_workers_started_on_boot"]==0
# 51
def test_web_health(tmp_path):
    app=create_workspace_app374(base_dir=tmp_path);cl=TestClient(app);r=cl.get("/health");assert r.status_code==200 and r.json()["build"]=="374.0" and r.json()["phase16_builds_completed"]==14;app.state.context.close()
# 52
def test_workflow_status_api_requires_auth(tmp_path):
    app=create_workspace_app374(base_dir=tmp_path);cl=TestClient(app);assert cl.get("/api/cases/x/workflow374/status").status_code==401;app.state.context.close()
# 53
def test_workflow_configure_api_requires_auth(tmp_path):
    app=create_workspace_app374(base_dir=tmp_path);cl=TestClient(app);assert cl.post("/api/cases/x/workflow374/configure",json={}).status_code==401;app.state.context.close()
# 54
def test_graph_navigate_route_requires_auth(tmp_path):
    app=create_workspace_app374(base_dir=tmp_path);cl=TestClient(app);assert cl.post("/api/cases/x/graph373/navigate",json={}).status_code==401;app.state.context.close()
# 55
def test_new_modules_no_direct_network_or_subprocess_imports():
    roots=[Path("src/eagleeye/phase16/case_workflow374.py"),Path("src/eagleeye/application/build374/service.py"),Path("src/eagleeye/interfaces/web/app374.py")];bad={"requests","httpx","aiohttp","socket","ssl","urllib","subprocess"}
    for p in roots:
        tree=ast.parse(p.read_text())
        mods=set()
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):mods|={x.name.split('.')[0] for x in n.names}
            elif isinstance(n,ast.ImportFrom) and n.module:mods.add(n.module.split('.')[0])
        assert not (mods&bad),f"{p}: {mods&bad}"
# 56
def test_gate_has_no_literal_true(tmp_path):
    with ctx(tmp_path) as c:assert c.build374.active_gate_literal_true_lines()==[]
# 57
def test_truthful_release_false(tmp_path):
    with ctx(tmp_path) as c:g=c.build374.qualified_gate();assert not g["production_release_ready"] and g["external_case_workflow_validation"]=="not_run" and g["external_analyst_handoff_validation"]=="not_run"
# 58
def test_capabilities_do_not_claim_external(tmp_path):
    with ctx(tmp_path) as c:assert all(not x["states"]["externally_validated"] for x in c.build374.capabilities())
# 59
def test_registry_has_374_services(tmp_path):
    with ctx(tmp_path) as c:
        names=set(c.SERVICE_NAMES);assert {"case_workflow_374","ai_autonomy_374","opsec_supervisor_374","build374"}<=names
# 60
def test_server_points_to_app374():assert "app374 import create_workspace_app374" in Path("src/eagleeye/interfaces/web/server.py").read_text()
# 61
def test_generic_launchers_point_to_374():assert "EAGLEEYE_PRO_374_0.py" in Path("START_EAGLEEYE_PRO.sh").read_text() and "EAGLEEYE_PRO_374_0.py" in Path("START_EAGLEEYE_PRO.bat").read_text()
# 62
def test_roadmap_374_completed():
    text=Path("CRAWLER_ROADMAP_BUILD_370_TO_380.md").read_text();assert "374" in text and "completed" in text.lower() and "handoff" in text.lower()
# 63
def test_masterplan_374_actual_status():
    text=Path("PHASE_16_MASTERPLAN_BUILD_361_TO_380.md").read_text();assert "Build 374 actual status" in text and "14/20" in text
# 64
def test_workflow_status_is_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);ca=case(c,a,"A")["case_id"];cb=case(c,a,"B")["case_id"];s=source(c);workflow(c,a,ca,s)
        with pytest.raises(KeyError):c.build374.case_workflow_status(case_id=cb,identity=a)
# 65
def test_workflow_job_not_claimed_by_generic_engine(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);assert c.job_engine_348.claim(worker_id="generic374") is None
# 66
def test_workflow_no_automatic_scope_expansion(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);st=workflow(c,a,cid,s);assert st["automatic_scope_expansion"] is False and st["automatic_network_authority"] is False
