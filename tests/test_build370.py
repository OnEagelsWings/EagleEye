from __future__ import annotations

import ast
import json
import socket
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eagleeye.crawler.engine import FetchResponse
from eagleeye.interfaces.web.app370 import create_workspace_app370
from eagleeye.phase16.tor_gateway370 import (
    POLICY, TOR_JOB, Socks5TorReadOnlyTransport370, StaticTorReplayTransport370,
)
from eagleeye_pro.core.app_context import AppContext

PW="Orbit-Pine-Quartz-370!"
ONION="a"*56+".onion"
ROOT=f"http://{ONION}/"
ROBOTS=f"http://{ONION}/robots.txt"

def ctx(tmp_path): return AppContext(base_dir=tmp_path,actor="test370")
def admin(c):
    u=c.team_identity_359.create_initial_admin(username="admin370",display_name="Admin User",password=PW)
    return {**u,"session_id":"test-admin-370"}
def case(c,a,title="Tor Case"): return c.build370.team_create_case(identity=a,title=title,client="QA",purpose="authorized read-only OSINT",legal_basis="public_data")
def onion_source(c,name="Reviewed Onion"):
    s=c.crawler_frontier_352.register_source(display_name=name,seed_urls=[ROOT],terms_ref="documented public/authorized read-only terms",max_depth=0,max_pages=1,requests_per_minute=5,max_response_bytes=100000)
    return c.crawler_frontier_352.review_source(s["source_id"],decision="approve_read_only",rationale="exact read-only source reviewed",reviewer="admin370")
def clear_source(c):
    s=c.crawler_frontier_352.register_source(display_name="Clear",seed_urls=["https://example.org/"],terms_ref="terms",max_depth=0,max_pages=1)
    return c.crawler_frontier_352.review_source(s["source_id"],decision="approve_read_only",rationale="ok",reviewer="admin370")
def enable(c,a,port=9050): return c.build370.configure_tor_gateway(identity=a,confirmation="ENABLE_TOR",enabled=True,socks_host="127.0.0.1",socks_port=port)
def enqueue(c,a,cid,sid): return c.build370.enqueue_tor_crawl(case_id=cid,source_id=sid,identity=a,confirmation="TOR_LIVE")
def replay(body=b"<html><body>tor ok</body></html>"):
    return StaticTorReplayTransport370({ROBOTS:FetchResponse(ROBOTS,404,{"content-type":"text/plain"},b"",1),ROOT:FetchResponse(ROOT,200,{"content-type":"text/html","etag":"\"tor1\""},body,2)})

@contextmanager
def fake_socks_http():
    srv=socket.socket(); srv.bind(("127.0.0.1",0)); srv.listen(1); port=srv.getsockname()[1]; captured={}
    def exact(conn,n):
        b=b""
        while len(b)<n:
            x=conn.recv(n-len(b))
            if not x: raise RuntimeError("eof")
            b+=x
        return b
    def worker():
        conn,_=srv.accept()
        with conn:
            captured["greeting"]=exact(conn,3); conn.sendall(b"\x05\x02")
            av=exact(conn,1); ul=exact(conn,1)[0]; user=exact(conn,ul); pl=exact(conn,1)[0]; pw=exact(conn,pl); captured["auth"]=(av,user,pw); conn.sendall(b"\x01\x00")
            head=exact(conn,4); assert head[:4]==b"\x05\x01\x00\x03"; hl=exact(conn,1)[0]; host=exact(conn,hl).decode(); portb=int.from_bytes(exact(conn,2),"big"); captured["target"]=(host,portb); conn.sendall(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x50")
            req=b""
            while b"\r\n\r\n" not in req: req+=conn.recv(4096)
            captured["request"]=req.decode("iso-8859-1"); conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
        srv.close()
    t=threading.Thread(target=worker,daemon=True); t.start()
    try: yield port,captured
    finally: t.join(timeout=3); srv.close()

# 1
def test_version_schema(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build370.version_status()=={"runtime_build":"370.0","schema_version":"370.0","package_version":"370.0.0","coherent":True}
        m=c.build370.schema_metrics(); assert m["within_gate"] and (m["table"],m["index"],m["trigger"])==(141,128,8)
# 2
def test_phase16_ten_of_twenty(tmp_path):
    with ctx(tmp_path) as c: assert c.build370.phase16_status()["builds_completed"]==10
# 3
def test_no_boot_network_workers(tmp_path):
    with ctx(tmp_path) as c:
        s=c.tor_gateway_370.status(); assert s["automatic_external_connections_on_boot"]==0 and s["background_workers_started_on_boot"]==0
# 4
def test_gateway_disabled_default(tmp_path):
    with ctx(tmp_path) as c: assert not c.tor_gateway_370.status()["gateway_enabled"]
# 5
def test_config_requires_admin(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); a["global_role"]="analyst"
        with pytest.raises(PermissionError): enable(c,a)
# 6
def test_enable_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c)
        with pytest.raises(PermissionError): c.build370.configure_tor_gateway(identity=a,confirmation="YES",enabled=True)
# 7
def test_disable_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); enable(c,a)
        with pytest.raises(PermissionError): c.build370.configure_tor_gateway(identity=a,confirmation="NO",enabled=False)
# 8
def test_loopback_only_socks_host(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c)
        with pytest.raises(PermissionError): c.build370.configure_tor_gateway(identity=a,confirmation="ENABLE_TOR",enabled=True,socks_host="8.8.8.8")
# 9
def test_hostname_not_accepted_for_socks_host(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c)
        with pytest.raises(ValueError): c.build370.configure_tor_gateway(identity=a,confirmation="ENABLE_TOR",enabled=True,socks_host="localhost")
# 10
def test_enable_persists_existing_profile(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); enable(c,a); row=c.db.one("SELECT * FROM phase15_network_profiles WHERE profile_id='tor_read_only_v1'"); cfg=json.loads(row["config_ref"])
        assert row["runtime_execution_enabled"]==1 and cfg["policy"]==POLICY and row["system_mutation_allowed"]==0
# 11
def test_disable_gateway(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); enable(c,a); s=c.build370.configure_tor_gateway(identity=a,confirmation="DISABLE_TOR",enabled=False); assert not s["gateway_enabled"]
# 12
def test_no_controlport_newnym_or_process_authority(tmp_path):
    with ctx(tmp_path) as c:
        s=c.tor_gateway_370.status(); assert not s["control_port_authority"] and not s["newnym_authority"] and not s["torrc_mutation"] and not s["tor_process_spawn"]
# 13
def test_no_destination_credentials_forms_bypass(tmp_path):
    with ctx(tmp_path) as c:
        s=c.tor_gateway_370.status(); assert not s["destination_credentials_supported"] and not s["forms_uploads_payments_supported"] and not s["access_control_bypass_supported"]
# 14
def test_per_search_isolation_credentials_differ(tmp_path):
    with ctx(tmp_path) as c:
        x=c.tor_gateway_370.isolation_credentials("search-a"); y=c.tor_gateway_370.isolation_credentials("search-b"); assert x["username"]!=y["username"] and x["fingerprint"]!=y["fingerprint"]
# 15
def test_isolation_credentials_deterministic(tmp_path):
    with ctx(tmp_path) as c: assert c.tor_gateway_370.isolation_credentials("same")==c.tor_gateway_370.isolation_credentials("same")
# 16
def test_transport_rejects_clearnet():
    t=Socks5TorReadOnlyTransport370(socks_host="127.0.0.1",socks_port=9,isolation_username="u",isolation_password="p")
    with pytest.raises(PermissionError): t.fetch("http://example.org/")
# 17
def test_transport_rejects_write_method():
    t=Socks5TorReadOnlyTransport370(socks_host="127.0.0.1",socks_port=9,isolation_username="u",isolation_password="p")
    with pytest.raises(PermissionError): t.fetch(ROOT,method="POST")
# 18
def test_transport_rejects_credential_headers():
    t=Socks5TorReadOnlyTransport370(socks_host="127.0.0.1",socks_port=9,isolation_username="u",isolation_password="p")
    with pytest.raises(PermissionError): t.fetch(ROOT,headers={"Cookie":"x=y"})
# 19
def test_transport_rejects_nonstandard_target_port():
    t=Socks5TorReadOnlyTransport370(socks_host="127.0.0.1",socks_port=9,isolation_username="u",isolation_password="p")
    with pytest.raises(ValueError): t.fetch(f"http://{ONION}:8080/")
# 20
def test_actual_socks_contract_uses_domain_and_auth_no_local_dns():
    with fake_socks_http() as (port,cap):
        t=Socks5TorReadOnlyTransport370(socks_host="127.0.0.1",socks_port=port,isolation_username="iso-user",isolation_password="iso-pass"); r=t.fetch(ROOT)
        assert r.status==200 and r.body==b"ok" and cap["target"]==(ONION,80) and cap["auth"][1:]==(b"iso-user",b"iso-pass") and t.local_dns_used is False
# 21
def test_enqueue_requires_enabled_gateway(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=onion_source(c)
        with pytest.raises(PermissionError): enqueue(c,a,cid,s["source_id"])
# 22
def test_enqueue_requires_tor_live(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=onion_source(c); enable(c,a)
        with pytest.raises(PermissionError): c.build370.enqueue_tor_crawl(case_id=cid,source_id=s["source_id"],identity=a,confirmation="LIVE")
# 23
def test_enqueue_rejects_clearnet_source(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=clear_source(c); enable(c,a)
        with pytest.raises(PermissionError): enqueue(c,a,cid,s["source_id"])
# 24
def test_enqueue_creates_dedicated_tor_job(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=onion_source(c); enable(c,a); out=enqueue(c,a,cid,s["source_id"]); assert out["job"]["job_type"]==TOR_JOB and out["network_execution"] is False
# 25
def test_generic_worker_cannot_claim_tor_job(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=onion_source(c); enable(c,a); enqueue(c,a,cid,s["source_id"]); assert c.crawler_production_369.claim_next(worker_id="clear",case_id=cid) is None
# 26
def test_tor_worker_claims_only_tor_job(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; cs=clear_source(c); c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=cs["source_id"]); s=onion_source(c); enable(c,a); enqueue(c,a,cid,s["source_id"]); j=c.tor_gateway_370.claim_next(worker_id="tor",case_id=cid); assert j["job_type"]==TOR_JOB
# 27
def test_tor_case_backpressure_after_two_jobs(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=onion_source(c); enable(c,a); enqueue(c,a,cid,s["source_id"]); enqueue(c,a,cid,s["source_id"]); p=c.tor_gateway_370.tor_backpressure(case_id=cid); assert p["case_depth"]==2 and not p["accept_new_tor_work"]
# 28
def test_third_tor_job_blocked_by_backpressure(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=onion_source(c); enable(c,a); enqueue(c,a,cid,s["source_id"]); enqueue(c,a,cid,s["source_id"])
        with pytest.raises(RuntimeError): enqueue(c,a,cid,s["source_id"])
# 29
def test_tor_static_replay_executes_evidence_path(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=onion_source(c); enable(c,a); enqueue(c,a,cid,s["source_id"]); out=c.build370.tor_run_next(worker_id="tor370",case_id=cid,transport=replay()); summary=json.loads(out["job"]["result_json"])
        assert out["job"]["status"]=="succeeded" and summary["pages_fetched"]==1 and summary["pages_stored"]==1 and out["local_onion_dns_used"] is False
# 30
def test_tor_evidence_is_quarantined_for_review(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=onion_source(c); enable(c,a); enqueue(c,a,cid,s["source_id"]); c.build370.tor_run_next(worker_id="tor370",case_id=cid,transport=replay()); row=c.db.one("SELECT security_state FROM phase15_objects WHERE case_id=? ORDER BY created_at DESC LIMIT 1",(cid,)); assert row["security_state"]=="quarantined"
# 31
def test_search_capsule_profile_exact_tor(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=onion_source(c); enable(c,a); out=enqueue(c,a,cid,s["source_id"]); row=c.db.one("SELECT search_kind,network_profile_ref FROM phase15_search_runs WHERE search_run_id=?",(out["search_run_id"],)); assert row=={"search_kind":"darknet","network_profile_ref":"tor_read_only_v1"}
# 32
def test_lease_renewal(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=onion_source(c); enable(c,a); enqueue(c,a,cid,s["source_id"]); j=c.tor_gateway_370.claim_next(worker_id="w",case_id=cid,lease_seconds=60); old=j["lease_expires_at"]; n=c.tor_gateway_370.renew_lease(job_id=j["job_id"],worker_id="w",lease_seconds=300); assert n["lease_expires_at"]>=old
# 33
def test_expired_lease_recovery_preserves_checkpoint(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=onion_source(c); enable(c,a); out=enqueue(c,a,cid,s["source_id"]); j=c.tor_gateway_370.claim_next(worker_id="dead",case_id=cid); cp='{"frontier":["x"]}'; c.db.execute("UPDATE phase15_jobs SET lease_expires_at='2000-01-01T00:00:00+00:00',checkpoint_json=? WHERE job_id=?",(cp,j["job_id"])); r=c.tor_gateway_370.recover_expired_leases(case_id=cid); row=c.job_engine_348.get(j["job_id"]); assert j["job_id"] in r["recovered_jobs"] and row["status"]=="queued" and row["checkpoint_json"]==cp
# 34
def test_case_status_is_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a,"A")["case_id"]; cb=case(c,a,"B")["case_id"]; s=onion_source(c); enable(c,a); enqueue(c,a,ca,s["source_id"]); assert len(c.build370.tor_case_status(case_id=ca)["jobs"])==1 and c.build370.tor_case_status(case_id=cb)["jobs"]==[]
# 35
def test_opsec_cancels_tor_job_when_gateway_disabled(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; s=onion_source(c); enable(c,a); out=enqueue(c,a,cid,s["source_id"]); c.build370.configure_tor_gateway(identity=a,confirmation="DISABLE_TOR",enabled=False); p=c.build370.autonomous_opsec_protect(case_id=cid); assert out["job"]["job_id"] in p["cancelled_invalid_tor_jobs"]
# 36
def test_opsec_no_system_mutations(tmp_path):
    with ctx(tmp_path) as c:
        s=c.opsec_supervisor_370.status(); assert not any(s[k] for k in ("system_mutations","firewall_mutation","os_mutation","tor_configuration_mutation","credential_mutation","acl_mutation"))
# 37
def test_ai_has_no_tor_authority(tmp_path):
    with ctx(tmp_path) as c:
        s=c.ai_autonomy_370.status(); assert not s["direct_tor_gateway_configuration_authority"] and not s["direct_tor_job_enqueue_authority"] and not s["direct_tor_network_authority"]
# 38
def test_ai_dossier_contains_tor_context(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; c.build370.create_investigation_intake(case_id=cid,objective="Review evidence",key_questions=["What is supported?"]); c.build370.start_investigation_go(case_id=cid,go="GO"); out=c.build370.run_autonomous_investigation(case_id=cid,max_ticks=1); assert "phase16_tor_gateway_context" in out["dossier"] and out["dossier"]["tor_research_requires_explicit_human_live_confirmation"]
# 39
def test_crawler_roadmap_exact_370_to_380(tmp_path):
    with ctx(tmp_path) as c: assert [x["build"] for x in c.build370.crawler_roadmap()]==list(range(370,381))
# 40
def test_crawler_roadmap_has_increment_each_build(tmp_path):
    with ctx(tmp_path) as c: assert all(str(x["crawler_increment"]).strip() for x in c.build370.crawler_roadmap())
# 41
def test_crawler_status_continuous_program(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build370.crawler_status(); assert s["crawler_improvement_build"]==370 and s["continuous_crawler_expansion_370_380"] and s["tor_specific_job_queue"] and s["clearnet_tor_worker_separation"]
# 42
def test_masterplan_contains_all_crawler_builds():
    t=Path("PHASE_16_MASTERPLAN_BUILD_361_TO_380.md").read_text()
    assert "Crawler-Dauerprogramm Build 370–380" in t and all(f"| {b} |" in t for b in range(370,381))
# 43
def test_web_health_and_auth_boundary(tmp_path):
    app=create_workspace_app370(base_dir=tmp_path/"web")
    with TestClient(app) as client:
        h=client.get("/health"); assert h.status_code==200 and h.json()["build"]=="370.0" and h.json()["phase16_builds_completed"]==10 and h.json()["continuous_crawler_expansion_370_380"]
        assert client.get("/api/build370/final-status").status_code==401
# 44
def test_new_nontransport_modules_no_direct_network_or_subprocess_imports():
    bad={"requests","httpx","aiohttp","socket","subprocess"}; found=set()
    for p in [Path("src/eagleeye/application/build370/service.py"),Path("src/eagleeye/interfaces/web/app370.py")]:
        tree=ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import): found.update(x.name.split(".")[0] for x in n.names)
            elif isinstance(n,ast.ImportFrom) and n.module: found.add(n.module.split(".")[0])
    assert not found.intersection(bad)
# 45
def test_truthful_release_false_and_external_not_run(tmp_path):
    with ctx(tmp_path) as c:
        s=c.tor_gateway_370.status(); assert s["local_tor_daemon_validation"]=="not_run" and s["external_onion_validation"]=="not_run" and c.build370.qualified_gate()["production_release_ready"] is False
