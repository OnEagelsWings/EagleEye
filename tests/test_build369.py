from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eagleeye.crawler.engine import FetchResponse, StaticTransport
from eagleeye.crawler.frontier import WorkerInterrupted
from eagleeye.interfaces.web.app369 import create_workspace_app369
from eagleeye_pro.core.app_context import AppContext

ADMIN_PW="Orbit-Pine-Quartz-369!"
SEED="https://example.org/root"


def ctx(tmp_path): return AppContext(base_dir=tmp_path,actor="test369")
def admin(c):
    u=c.team_identity_359.create_initial_admin(username="admin369",display_name="Admin User",password=ADMIN_PW)
    return {**u,"session_id":"test-admin-369"}
def case(c,a,title="Crawler Production Case"): return c.build369.team_create_case(identity=a,title=title,client="QA",purpose="authorized public source monitoring",legal_basis="public_data")
def source(c,name="Public Example",seed=SEED,**kw):
    s=c.crawler_frontier_352.register_source(display_name=name,seed_urls=[seed],terms_ref="https://example.org/terms",max_depth=kw.get("max_depth",0),max_pages=kw.get("max_pages",1),requests_per_minute=kw.get("requests_per_minute",10),max_response_bytes=kw.get("max_response_bytes",100000),parser_version="html-text-links-v1")
    return c.crawler_frontier_352.review_source(s["source_id"],decision="approve_read_only",rationale="official public read-only source approved",reviewer="admin369")
def schedule(c,a,cid,sid,**kw):
    return c.build369.configure_crawler_schedule(case_id=cid,source_id=sid,identity=a,confirmation="ENABLE",interval_minutes=kw.get("interval_minutes",60),enabled=True,failure_threshold=kw.get("failure_threshold",3),max_backoff_minutes=kw.get("max_backoff_minutes",1440),case_high_watermark=kw.get("case_high_watermark",8),global_high_watermark=kw.get("global_high_watermark",64))
def transport(body=b"<html><title>Example</title><body>hello</body></html>",etag='"v1"'):
    return StaticTransport({"https://example.org/robots.txt":FetchResponse("https://example.org/robots.txt",404,{"content-type":"text/plain"},b"",1),SEED:FetchResponse(SEED,200,{"content-type":"text/html","etag":etag},body,2)})
def resolver(host): return ["93.184.216.34"]

# 1
def test_version_schema(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build369.version_status()=={"runtime_build":"369.0","schema_version":"369.0","package_version":"369.0.0","coherent":True}
        m=c.build369.schema_metrics(); assert m["within_gate"] and (m["table"],m["index"],m["trigger"])==(141,128,8)
# 2
def test_no_new_per_build_tables(tmp_path):
    with ctx(tmp_path) as c: assert c.crawler_production_369.status()["new_per_build_data_tables"]==0
# 3
def test_schedule_requires_enable_word(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c)
        with pytest.raises(PermissionError): c.build369.configure_crawler_schedule(case_id=cid,source_id=s["source_id"],identity=a,confirmation="yes",enabled=True)
# 4
def test_schedule_config_persisted_in_existing_policy(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); out=schedule(c,a,cid,s["source_id"],interval_minutes=30)
        row=c.db.one("SELECT frontier_policy_json FROM phase15_crawler_policies WHERE source_id=?",(s["source_id"],)); doc=json.loads(row["frontier_policy_json"])
        assert out["schedule"]["interval_seconds"]==1800 and doc["production369"]["case_id"]==cid and doc["production369"]["enabled"]
# 5
def test_disable_requires_disable_word(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); schedule(c,a,cid,s["source_id"])
        out=c.build369.configure_crawler_schedule(case_id=cid,source_id=s["source_id"],identity=a,confirmation="DISABLE",enabled=False)
        assert not out["schedule"]["enabled"]
# 6
def test_connector_sources_cannot_bypass_live_gate(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; prep=c.build369.prepare_reference_source(case_id=cid,connector_key="federal_register_document_v1",identifier="2026-12345",identity=a)
        c.crawler_frontier_352.review_source(prep["source"]["source_id"],decision="approve_read_only",rationale="reviewed",reviewer="admin369")
        with pytest.raises(PermissionError): schedule(c,a,cid,prep["source"]["source_id"])
# 7
def test_darknet_sources_not_recurring(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; onion="a"*56+".onion"; s=source(c,name="Onion",seed="http://"+onion+"/")
        with pytest.raises(PermissionError): schedule(c,a,cid,s["source_id"])
# 8
def test_scheduler_tick_enqueues_due_source_without_network(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); schedule(c,a,cid,s["source_id"]); out=c.build369.crawler_scheduler_tick(case_id=cid,identity=a)
        assert out["state"]=="ok" and len(out["scheduled"])==1 and out["network_execution"] is False and not out["background_worker_started"]
        payload=json.loads(out["scheduled"][0]["job"]["payload_json"]); assert payload["phase16_crawler369_scheduled"] is True
# 9
def test_scheduler_tick_deduplicates_active_source_job(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); schedule(c,a,cid,s["source_id"]); c.build369.crawler_scheduler_tick(case_id=cid,identity=a); out=c.build369.crawler_scheduler_tick(case_id=cid,identity=a)
        assert not out["scheduled"] and any(x["reason"]=="source_job_already_active" for x in out["skipped"])
# 10
def test_case_backpressure_blocks_new_schedule(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); schedule(c,a,cid,s["source_id"],case_high_watermark=1); c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]); out=c.build369.crawler_scheduler_tick(case_id=cid,identity=a)
        assert out["state"]=="backpressure_hold" and out["backpressure"]["case_backpressure"]
# 11
def test_source_health_rate_limit_opens_circuit(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); schedule(c,a,cid,s["source_id"]); c.db.execute("UPDATE phase15_crawler_policies SET source_health='rate_limited' WHERE source_id=?",(s["source_id"],)); h=c.build369.crawler_source_health(source_id=s["source_id"])
        assert h["circuit_open"] and h["circuit_reason"]=="rate_limited"
# 12
def test_scheduler_skips_open_source_circuit(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); schedule(c,a,cid,s["source_id"]); c.db.execute("UPDATE phase15_crawler_policies SET source_health='offline' WHERE source_id=?",(s["source_id"],)); out=c.build369.crawler_scheduler_tick(case_id=cid,identity=a)
        assert not out["scheduled"] and out["skipped"][0]["reason"]=="source_health_circuit_open"
# 13
def test_worker_claims_only_governed_crawl(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; c.job_engine_348.enqueue(job_type="not_crawler",payload={},case_id=cid,priority=0); s=source(c); crawl=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]); job=c.crawler_production_369.claim_next(worker_id="w369",case_id=cid)
        assert job["job_id"]==crawl["job"]["job_id"] and job["job_type"]=="governed_crawl_v1"
# 14
def test_lease_heartbeat_extends_active_lease(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); crawl=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]); job=c.crawler_production_369.claim_next(worker_id="w369",case_id=cid,lease_seconds=60); old=job["lease_expires_at"]; new=c.crawler_production_369.renew_lease(job_id=job["job_id"],worker_id="w369",lease_seconds=300)
        assert new["lease_expires_at"]>=old
# 15
def test_expired_crawler_lease_recovery_preserves_checkpoint(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); crawl=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]); jid=crawl["job"]["job_id"]
        cp=json.dumps({"policy":"phase15.frontier-resume.v352","crawl_run_id":crawl["crawl_run_id"],"frontier":[],"seen_canonical":[SEED],"seq":1,"counters":{},"inflight_url":SEED})
        c.db.execute("UPDATE phase15_jobs SET status='running',lease_owner='dead-worker',lease_expires_at='2000-01-01T00:00:00+00:00',checkpoint_json=? WHERE job_id=?",(cp,jid)); out=c.crawler_production_369.recover_expired_leases(case_id=cid); row=c.job_engine_348.get(jid)
        assert jid in out["recovered_jobs"] and row["status"]=="queued" and row["checkpoint_json"]==cp
# 16
def test_production_worker_executes_static_replay(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); schedule(c,a,cid,s["source_id"]); c.build369.crawler_scheduler_tick(case_id=cid,identity=a); out=c.build369.crawler_run_next(worker_id="prod369",transport=transport(),resolver=resolver,case_id=cid)
        assert out["job"]["status"]=="succeeded" and out["lease_heartbeat"] and out["source_health_event"]["status"]=="operational"
# 17
def test_scheduler_not_due_after_recent_success(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); schedule(c,a,cid,s["source_id"],interval_minutes=60); c.build369.crawler_scheduler_tick(case_id=cid,identity=a); c.build369.crawler_run_next(worker_id="prod369",transport=transport(),resolver=resolver,case_id=cid); out=c.build369.crawler_scheduler_tick(case_id=cid,identity=a)
        assert not out["scheduled"] and any(x["reason"]=="not_due" for x in out["skipped"])
# 18
def test_delta_second_run_uses_conditional_header(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); first=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]); t1=transport(); c.build369.crawler_run_next(worker_id="p1",transport=t1,resolver=resolver,case_id=cid)
        second=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]); t2=StaticTransport({"https://example.org/robots.txt":FetchResponse("https://example.org/robots.txt",404,{"content-type":"text/plain"},b"",1),SEED:FetchResponse(SEED,304,{"content-type":"text/html","etag":'"v1"'},b"",1)}); c.build369.crawler_run_next(worker_id="p2",transport=t2,resolver=resolver,case_id=cid)
        root=[x for x in t2.request_log if x["url"]==SEED][-1]; assert root["headers"].get("If-None-Match")== '"v1"'
        run=c.db.one("SELECT summary_json FROM phase15_crawl_runs WHERE crawl_run_id=?",(second["crawl_run_id"],)); assert json.loads(run["summary_json"])["not_modified"]==1
# 19
class InterruptOnceTransport:
    transport_kind="static_interrupt_once_v369"; externally_configured=False
    def __init__(self): self.inner=transport(); self.raised=False
    def fetch(self,url,**kw):
        if url==SEED and not self.raised:
            self.raised=True; raise WorkerInterrupted("simulated worker loss")
        return self.inner.fetch(url,**kw)

def test_frontier_resume_after_worker_interruption(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); crawl=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]); t=InterruptOnceTransport(); first=c.build369.crawler_run_next(worker_id="lost",transport=t,resolver=resolver,case_id=cid); assert first["job"]["status"]=="queued"
        second=c.build369.crawler_run_next(worker_id="resume",transport=transport(),resolver=resolver,case_id=cid); assert second["job"]["status"]=="succeeded"
        run=c.db.one("SELECT summary_json FROM phase15_crawl_runs WHERE crawl_run_id=?",(crawl["crawl_run_id"],)); assert json.loads(run["summary_json"])["resumed_from_checkpoint"] is True
# 20
def test_soak_snapshot_reports_resume_and_no_stale_lease(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); crawl=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]); t=InterruptOnceTransport(); c.build369.crawler_run_next(worker_id="lost",transport=t,resolver=resolver,case_id=cid); c.build369.crawler_run_next(worker_id="resume",transport=transport(),resolver=resolver,case_id=cid); soak=c.build369.crawler_soak_snapshot(case_id=cid)
        assert soak["runs"]==1 and soak["succeeded"]==1 and soak["resumed_from_checkpoint"]==1 and soak["stale_running_leases"]==0
# 21
def test_soak_snapshot_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a,"A")["case_id"]; cb=case(c,a,"B")["case_id"]; sa=source(c,"A source"); c.crawler_frontier_352.enqueue_crawl(case_id=ca,source_id=sa["source_id"]); c.build369.crawler_run_next(worker_id="wa",transport=transport(),resolver=resolver,case_id=ca)
        assert c.build369.crawler_soak_snapshot(case_id=ca)["runs"]==1 and c.build369.crawler_soak_snapshot(case_id=cb)["runs"]==0
# 22
def test_opsec_cancels_tampered_scheduled_job(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); schedule(c,a,cid,s["source_id"]); tick=c.build369.crawler_scheduler_tick(case_id=cid,identity=a); jid=tick["scheduled"][0]["job"]["job_id"]
        c.build369.configure_crawler_schedule(case_id=cid,source_id=s["source_id"],identity=a,confirmation="DISABLE",enabled=False); out=c.build369.autonomous_opsec_protect(case_id=cid)
        assert jid in out["cancelled_invalid_scheduled_crawls"] and c.job_engine_348.get(jid)["status"]=="cancelled"
# 23
def test_opsec_no_system_mutations(tmp_path):
    with ctx(tmp_path) as c:
        s=c.opsec_supervisor_369.status(); assert not any(s[k] for k in ("system_mutations","firewall_mutation","os_mutation","tor_configuration_mutation","credential_mutation","acl_mutation"))
# 24
def test_ai_holds_when_source_circuit_open(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); schedule(c,a,cid,s["source_id"]); c.db.execute("UPDATE phase15_crawler_policies SET source_health='rate_limited' WHERE source_id=?",(s["source_id"],)); out=c.build369.run_autonomous_investigation(case_id=cid,max_ticks=1)
        assert out["state"]=="crawler_operations_hold" and out["lead_review_required"]
# 25
def test_ai_dossier_gets_crawler_production_context(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; c.build369.create_investigation_intake(case_id=cid,objective="Review public evidence",key_questions=["What is supported?"]); c.build369.start_investigation_go(case_id=cid,go="GO"); out=c.build369.run_autonomous_investigation(case_id=cid,max_ticks=1)
        assert "phase16_crawler_production_context" in out["dossier"] and out["dossier"]["crawler_production_requires_review"]
# 26
def test_ai_has_no_scheduler_mutation_authority(tmp_path):
    with ctx(tmp_path) as c:
        s=c.ai_autonomy_369.status(); assert not s["direct_scheduler_mutation_authority"] and not s["direct_worker_lease_mutation_authority"]
# 27
def test_readiness_green_empty_case(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; r=c.build369.crawler_production_readiness(case_id=cid); assert r["ready_for_more_bounded_work"]
# 28
def test_readiness_red_under_backpressure(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); schedule(c,a,cid,s["source_id"],case_high_watermark=1); c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]); assert not c.build369.crawler_production_readiness(case_id=cid)["ready_for_more_bounded_work"]
# 29
def test_crawler_status_preserves_live_gates(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build369.crawler_status(); assert s["provider_connector_live_gates_preserved"] and not s["darknet_recurring_schedule_disabled"] is False and s["automatic_external_connections_on_boot"]==0
# 30
def test_phase16_status_nine_of_twenty(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build369.phase16_status(); assert s["phase"]=="16" and s["build"]=="369.0" and s["builds_completed"]==9
# 31
def test_production_status_no_background_worker(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build369.crawler_production_status(); assert s["background_workers_started_on_boot"]==0 and s["automatic_external_connections_on_boot"]==0
# 32
def test_production_release_false(tmp_path):
    with ctx(tmp_path) as c: assert c.build369.qualified_gate()["production_release_ready"] is False
# 33
def test_no_literal_true_in_gate(tmp_path):
    with ctx(tmp_path) as c: assert c.build369.active_gate_literal_true_lines()==[]
# 34
def test_new_modules_have_no_direct_network_or_subprocess_imports():
    names=set()
    for p in [Path("src/eagleeye/phase16/crawler_production369.py"),Path("src/eagleeye/application/build369/service.py")]:
        tree=ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import): names.update(x.name.split(".")[0] for x in n.names)
            elif isinstance(n,ast.ImportFrom) and n.module: names.add(n.module.split(".")[0])
    assert not names.intersection({"requests","httpx","aiohttp","socket","subprocess"})
# 35
def test_web_health_and_auth_boundary(tmp_path):
    app=create_workspace_app369(base_dir=tmp_path/"web")
    with TestClient(app) as client:
        h=client.get("/health"); assert h.status_code==200 and h.json()["build"]=="369.0" and h.json()["phase16_builds_completed"]==9 and h.json()["background_workers_started_on_boot"]==0
        assert client.get("/api/build369/final-status").status_code==401
# 36
def test_scheduler_tick_cap_declared(tmp_path):
    with ctx(tmp_path) as c: assert c.crawler_production_369.status()["queue_backpressure"] and c.crawler_production_369.status()["source_health_circuit_breaker"]
# 37
def test_source_health_reports_delta_metrics(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]); c.build369.crawler_run_next(worker_id="w",transport=transport(),resolver=resolver,case_id=cid); h=c.build369.crawler_source_health(source_id=s["source_id"])
        assert h["fetches"]>=1 and h["delta_new"]>=1 and not h["automatic_identity_or_fact_promotion"]
# 38
def test_source_failure_backoff_increases_interval(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); schedule(c,a,cid,s["source_id"],interval_minutes=10,failure_threshold=3)
        for i in range(2):
            cr=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]); c.db.execute("UPDATE phase15_crawl_runs SET status='failed',completed_at=? WHERE crawl_run_id=?",(f"2026-09-09T00:00:0{i}+00:00",cr["crawl_run_id"])); c.job_engine_348.cancel(cr["job"]["job_id"],actor="test369")
        h=c.build369.crawler_source_health(source_id=s["source_id"]); assert h["interval_seconds_effective"]>=2400 and not h["circuit_open"]
# 39
def test_failure_threshold_opens_circuit(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=source(c); schedule(c,a,cid,s["source_id"],failure_threshold=2)
        for i in range(2):
            cr=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s["source_id"]); c.db.execute("UPDATE phase15_crawl_runs SET status='failed',completed_at=? WHERE crawl_run_id=?",(f"2026-09-09T00:00:0{i}+00:00",cr["crawl_run_id"])); c.job_engine_348.cancel(cr["job"]["job_id"],actor="test369")
        h=c.build369.crawler_source_health(source_id=s["source_id"]); assert h["circuit_open"] and h["circuit_reason"]=="consecutive_failures"
# 40
def test_scheduler_never_changes_provider_or_firewall_policy(tmp_path):
    with ctx(tmp_path) as c:
        s=c.crawler_production_369.status(); o=c.opsec_supervisor_369.status(); assert not s["generic_connector_live_gate_bypass"] and not o["system_mutations"] and o["provider_live_gate_bypass_blocked"]
