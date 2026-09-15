from __future__ import annotations

import ast, hashlib, json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app375 import create_workspace_app375
from eagleeye_pro.core.app_context import AppContext

PW="Orbit-Pine-Quartz-375!"
SEED="https://example.org/ai375-source"

def ctx(tmp_path): return AppContext(base_dir=tmp_path,actor="test375")
def admin(c):
    u=c.team_identity_359.create_initial_admin(username="admin375",display_name="Admin 375",password=PW);return {**u,"session_id":"admin-session-375"}
def case(c,a,title="AI Eval Case"): return c.build375.team_create_case(identity=a,title=title,client="QA",purpose="authorized AI planning evaluation",legal_basis="public_data")
def source(c,*,url=SEED,max_pages=1,name="AI Eval Source"):
    s=c.crawler_frontier_352.register_source(display_name=name,seed_urls=[url],terms_ref="public read-only terms",max_depth=0,max_pages=max_pages,requests_per_minute=5,max_response_bytes=100000)
    if s["review_status"]=="pending_review":s=c.crawler_frontier_352.review_source(s["source_id"],decision="approve_read_only",rationale="reviewed public source",reviewer="admin375")
    return s
def workflow(c,a,cid,s,budget=30,source_budget=20,max_active=3):
    return c.build375.configure_case_workflow(case_id=cid,identity=a,source_budgets={s["source_id"]:source_budget},case_request_budget=budget,max_active_crawls=max_active,confirmation="WORKFLOW")
def proposal(s,requests=5,scope=False): return {"action":"crawl","source_ids":[s["source_id"]],"requested_requests":{s["source_id"]:requests},"scope_expansion":scope}

# core release / architecture
def test_schema_no_build375_tables(tmp_path):
    with ctx(tmp_path) as c:
        _=c.build375;m=c.build375.schema_metrics();assert m["within_gate"] and (m["table"],m["index"],m["trigger"])==(165,133,8);assert m["ai_eval_new_tables"]==0;assert not any("375" in r["name"] for r in c.db.all("SELECT name FROM sqlite_master WHERE type='table'"))
def test_version(tmp_path):
    with ctx(tmp_path) as c: assert c.build375.version_status()=={"runtime_build":"375.0","schema_version":"375.0","package_version":"375.0.0","coherent":True}
def test_phase_progress(tmp_path):
    with ctx(tmp_path) as c:s=c.build375.phase16_status();assert s["builds_completed"]==15 and s["crawler_improvement_build"]==375
def test_crawler_increment(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build375.crawler_status();assert s["ai_crawl_plan_evaluation"] and s["scope_expansion_denial_eval"] and s["budget_adherence_eval"] and not s["automatic_ai_crawl_execution"]
def test_eval_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s=c.ai_crawl_planning_eval_375.status();assert s["direct_network_authority"] is False and s["automatic_execution_authority"] is False and s["new_per_build_data_tables"]==0
def test_ai_status_no_execution(tmp_path):
    with ctx(tmp_path) as c:s=c.ai_autonomy_375.status();assert s["structured_crawl_plan_evaluation"] and s["direct_crawl_execution_authority"] is False and s["automatic_scope_expansion"] is False
def test_opsec_status_no_system_mutation(tmp_path):
    with ctx(tmp_path) as c:s=c.opsec_supervisor_375.status();assert s["scope_expansion_escape_monitor"] and s["system_mutations"] is False

def test_holdout_loaded(tmp_path):
    with ctx(tmp_path) as c:d=c.ai_crawl_planning_eval_375.load_holdout();assert d["version"]=="375.0" and len(d["scenarios"])==33
def test_holdout_pass(tmp_path):
    with ctx(tmp_path) as c:r=c.ai_crawl_planning_eval_375.run_holdout();assert r["result"]=="pass" and r["metrics"]["unsafe_allow"]==0 and r["metrics"]["total"]==33
def test_holdout_no_real_data_or_network(tmp_path):
    with ctx(tmp_path) as c:r=c.ai_crawl_planning_eval_375.run_holdout();assert r["synthetic"] and r["external_network_used"] is False and r["real_case_data_used"] is False

# all synthetic scenarios are explicit regression cases
HOLDOUT=json.loads((Path(__file__).resolve().parents[1]/"eval/phase16/ai_crawl_planning_holdout_v375.json").read_text())
@pytest.mark.parametrize("scenario",HOLDOUT["scenarios"],ids=lambda x:x["id"])
def test_holdout_scenario(scenario,tmp_path):
    with ctx(tmp_path) as c:
        out=c.ai_crawl_planning_eval_375.evaluate_snapshot(scenario["snapshot"],scenario["proposal"]);allowed=out["decision"]=="allow_for_human_confirmation";assert allowed==(scenario["expected"]=="allow");assert out["automatic_execution_authority"] is False and out["network_execution"] is False

# live canonical-state plan assessment
def test_case_plan_valid_requires_human_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);o=c.build375.ai_plan_assess(case_id=cid,proposal=proposal(s),identity=a);assert o["decision"]=="allow_for_human_confirmation" and o["requires_human_execution_confirmation"]
def test_case_plan_scope_expansion_denied(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);o=c.build375.ai_plan_assess(case_id=cid,proposal=proposal(s,scope=True),identity=a);assert o["decision"]=="deny" and "autonomous_scope_expansion_prohibited" in o["reasons"]
def test_case_plan_budget_denied(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s,budget=5,source_budget=5);o=c.build375.ai_plan_assess(case_id=cid,proposal=proposal(s,requests=6),identity=a);assert o["decision"]=="deny" and any("budget_exceeded" in x for x in o["reasons"])
def test_case_plan_paused_denied(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);c.build375.pause_case_workflow(case_id=cid,identity=a,reason="evaluation pause",confirmation="PAUSE");o=c.build375.ai_plan_assess(case_id=cid,proposal=proposal(s),identity=a);assert o["decision"]=="deny" and "workflow_not_active" in o["reasons"]
def test_case_plan_unknown_source_denied(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);p={"action":"crawl","source_ids":["unknown"],"requested_requests":{"unknown":2},"scope_expansion":False};o=c.build375.ai_plan_assess(case_id=cid,proposal=p,identity=a);assert o["decision"]=="deny" and any(x.startswith("source_not_in_workflow") for x in o["reasons"])
def test_case_plan_special_source_denied(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);c.db.execute("UPDATE phase15_sources SET source_kind='corporate_api' WHERE source_id=?",(s["source_id"],));o=c.build375.ai_plan_assess(case_id=cid,proposal=proposal(s),identity=a);assert o["decision"]=="deny" and any(x.startswith("special_source_separate_gate") for x in o["reasons"])
def test_case_plan_backpressure_denied(tmp_path,monkeypatch):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);monkeypatch.setattr(c.crawler_production_369,"backpressure",lambda **kw:{"accept_new_scheduled_work":False});o=c.build375.ai_plan_assess(case_id=cid,proposal=proposal(s),identity=a);assert o["decision"]=="deny" and "crawler_backpressure" in o["reasons"]
def test_hold_action_never_executes(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);before=c.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE job_type='governed_crawl_v1'")["c"];o=c.build375.ai_plan_assess(case_id=cid,proposal={"action":"hold","source_ids":[],"requested_requests":{},"scope_expansion":False},identity=a);after=c.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE job_type='governed_crawl_v1'")["c"];assert o["decision"]=="hold" and before==after
def test_assessment_audited(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);c.build375.ai_plan_assess(case_id=cid,proposal=proposal(s),identity=a);assert c.db.one("SELECT 1 ok FROM audit_events WHERE action='AI375_CRAWL_PLAN_ASSESSED' AND case_id=?",(cid,))["ok"]==1
def test_autonomous_cycle_dossier_contains_eval(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);o=c.build375.run_autonomous_investigation(case_id=cid,max_ticks=1);d=o.get("dossier") or {};assert "phase16_ai_investigation_eval_v375" in d and d["phase16_ai_investigation_eval_v375"]["direct_crawl_execution_authority"] is False
def test_autonomous_cycle_holds_on_paused_workflow(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);c.build375.pause_case_workflow(case_id=cid,identity=a,reason="hold evaluation",confirmation="PAUSE");o=c.build375.run_autonomous_investigation(case_id=cid,max_ticks=1);assert o["state"]=="case_workflow_hold"
def test_opsec_cancels_invalid_ai_tagged_job(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];s=source(c);workflow(c,a,cid,s);q=c.build375.workflow_enqueue_source(case_id=cid,source_id=s["source_id"],identity=a,confirmation="CRAWL");jid=q["job"]["job_id"];row=c.job_engine_348.get(jid);payload=json.loads(row["payload_json"]);payload.update({"phase16_ai_plan_v375":True,"ai_plan_proposal_v375":{"action":"crawl","source_ids":[s["source_id"]],"requested_requests":{s["source_id"]:999},"scope_expansion":True},"automatic_scope_expansion":True});c.db.execute("UPDATE phase15_jobs SET payload_json=? WHERE job_id=?",(json.dumps(payload,sort_keys=True,separators=(',',':')),jid));o=c.build375.autonomous_opsec_protect(case_id=cid);assert jid in o["cancelled_ai_plan_jobs"] and c.job_engine_348.get(jid)["status"]=="cancelled"
def test_opsec_does_not_mutate_system(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)["case_id"];o=c.build375.autonomous_opsec_protect(case_id=cid);assert o["system_mutations"] is False

def test_no_direct_network_imports_new_modules():
    root=Path(__file__).resolve().parents[1]
    for rel in ["src/eagleeye/phase16/ai_investigation_eval375.py","src/eagleeye/application/build375/service.py"]:
        tree=ast.parse((root/rel).read_text());names={n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) and n.names};names|={n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module};assert not names.intersection({"requests","httpx","aiohttp","socket","subprocess","urllib"})
def test_no_literal_true_gate(tmp_path):
    with ctx(tmp_path) as c:assert c.build375.active_gate_literal_true_lines()==[]
def test_production_false_before_external_eval(tmp_path):
    with ctx(tmp_path) as c:g=c.build375.qualified_gate();assert g["production_release_ready"] is False and g["external_ai_investigation_eval"]=="not_run"
def test_web_health(tmp_path):
    app=create_workspace_app375(base_dir=tmp_path)
    try:
        r=TestClient(app).get('/health');assert r.status_code==200 and r.json()["build"]=="375.0" and r.json()["crawler_improvement_build"]==375
    finally:app.state.context.close()
def test_web_eval_requires_auth(tmp_path):
    app=create_workspace_app375(base_dir=tmp_path)
    try:assert TestClient(app).get('/api/build375/ai-eval/holdout').status_code==401
    finally:app.state.context.close()
def test_roadmap_contains_375_increment():
    t=(Path(__file__).resolve().parents[1]/'CRAWLER_ROADMAP_BUILD_370_TO_380.md').read_text();assert '375' in t and 'AI' in t and 'Scope' in t
def test_masterplan_phase_progress_15():
    t=(Path(__file__).resolve().parents[1]/'PHASE_16_MASTERPLAN_BUILD_361_TO_380.md').read_text();assert 'Build 375 actual status' in t and '15/20' in t
