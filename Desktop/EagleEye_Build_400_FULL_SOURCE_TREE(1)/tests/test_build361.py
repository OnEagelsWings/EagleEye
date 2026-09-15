from __future__ import annotations
import ast,tempfile
from pathlib import Path
import pytest
from eagleeye_pro.core.app_context import AppContext

def ctx(tmp_path): return AppContext(base_dir=tmp_path)
def case(c,title='P16'):
    return c.cases.create_case(title=title,client='QA',purpose='phase16 test',legal_basis='authorized public-source test')

def test_version_schema(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build361.version_status()=={'runtime_build':'361.0','schema_version':'361.0','package_version':'361.0.0','coherent':True}
        m=c.build361.schema_metrics(); assert m['within_gate'] and (m['table'],m['index'],m['trigger'])==(141,128,8)
def test_phase16_targets_declared(tmp_path):
    with ctx(tmp_path) as c:
        m=c.build361.validation_matrix(); assert len(m)>=13 and all(x['status']=='not_run' and not x['externally_validated'] for x in m)
def test_go_required_for_autonomy(tmp_path):
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']; r=c.build361.run_autonomous_investigation(case_id=cid); assert r['state']=='go_required' and r['ticks']==0
def test_go_autonomy_produces_review_dossier(tmp_path):
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']; c.build361.create_investigation_intake(case_id=cid,objective='Research public facts',key_questions=['What is supported?']); c.build361.start_investigation_go(case_id=cid,go='GO')
        r=c.build361.run_autonomous_investigation(case_id=cid,max_ticks=2); assert r['state'] in {'review_ready','in_progress'}; assert r['dossier']['phase16_review_state']=='ready_for_lead_review'; assert r['dossier']['release_authority']=='human_case_lead_only'
def test_ai_never_direct_network(tmp_path):
    with ctx(tmp_path) as c: assert c.ai_autonomy_361.status()['direct_network_client'] is False
def test_opsec_supervisor_status(tmp_path):
    with ctx(tmp_path) as c:
        s=c.opsec_supervisor_361.status(); assert s['autonomous_defensive_supervision'] and not s['can_change_firewall'] and not s['can_change_tor_config']
def test_opsec_cancels_job_bound_to_blocked_search(tmp_path):
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']; cap=c.build361.create_clearnet_capsule(case_id=cid,egress_hosts=['example.org']); sr=cap['search_run_id']
        c.db.execute("INSERT INTO phase15_jobs(job_id,idempotency_key,job_type,case_id,search_run_id,status,priority,attempts,max_attempts,available_at,lease_owner,lease_expires_at,payload_json,resource_budget_json,rate_budget_json,checkpoint_json,result_json,error_text,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('job361x','idem361x','test',cid,sr,'queued',1,0,1,'2000-01-01T00:00:00+00:00','','','{}','{}','{}','{}','{}','', '2000-01-01T00:00:00+00:00','2000-01-01T00:00:00+00:00','x'))
        c.db.execute("INSERT INTO phase15_security_events(security_event_id,case_id,search_run_id,event_type,disposition,severity,policy_version,evidence_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",('sec361x',cid,sr,'test','block','high','test','{}','2000-01-01T00:00:00+00:00'))
        out=c.build361.autonomous_opsec_protect(case_id=cid); assert 'job361x' in out['jobs_defensively_stopped']; assert c.db.one("SELECT status FROM phase15_jobs WHERE job_id='job361x'")['status']=='cancelled'
def test_opsec_does_not_mutate_system(tmp_path):
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']; assert c.build361.autonomous_opsec_protect(case_id=cid)['system_mutations'] is False
def test_validation_receipt_is_truthful(tmp_path):
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']; r=c.build361.record_validation_receipt(case_id=cid,target_key='gleif_live',status='contract_only',evidence={'fixture':1},external=False); assert not r['external_validation'] and r['evidence_hash']
def test_unknown_validation_target_rejected(tmp_path):
    with ctx(tmp_path) as c:
        cid=case(c)['case_id']
        with pytest.raises(ValueError): c.build361.record_validation_receipt(case_id=cid,target_key='fake',status='pass',evidence={})
def test_crawler_marks_361(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build361.crawler_status(); assert s['crawler_improvement_build']==361 and s['opsec_supervisor_monitors_crawler']
def test_connectors_exist_but_not_external_claim(tmp_path):
    with ctx(tmp_path) as c:
        keys={x['connector_key'] for x in c.build361.connector_manifests()}; assert {'gleif_lei_api_v1','sec_edgar_submissions_v1','companies_house_company_v1'}<=keys
        assert all(not x['states']['externally_validated'] for x in c.build361.capabilities())
def test_gleif_plan_is_bounded(tmp_path):
    with ctx(tmp_path) as c:
        p=c.build361.connector_source_plan('gleif_lei_api_v1','529900T8BM49AURSDO55'); assert p['host']=='api.gleif.org' and not p['live_fetch_automatically_started']
def test_sec_plan_requires_declared_ua(tmp_path):
    with ctx(tmp_path) as c:
        p=c.build361.connector_source_plan('sec_edgar_submissions_v1','320193'); assert p['requires_declared_user_agent']
def test_companies_house_auth_remains_plan_only(tmp_path):
    with ctx(tmp_path) as c:
        p=c.build361.connector_source_plan('companies_house_company_v1','00000006'); assert p['auth_type']!='none'
def test_production_false(tmp_path):
    with ctx(tmp_path) as c: assert c.build361.qualified_gate()['production_release_ready'] is False
def test_phase16_status_truthful(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build361.phase16_status(); assert s['phase']=='16' and s['build']=='361.0' and not s['production_release_ready']
def test_no_literal_true_in_gate(tmp_path):
    with ctx(tmp_path) as c: assert c.build361.active_gate_literal_true_lines()==[]
def test_new_modules_no_network_or_subprocess_imports():
    names=set()
    for p in [Path('src/eagleeye/phase16/baseline361.py'),Path('src/eagleeye/application/build361/service.py')]:
        tr=ast.parse(p.read_text())
        for n in ast.walk(tr):
            if isinstance(n,ast.Import): names.update(x.name.split('.')[0] for x in n.names)
            elif isinstance(n,ast.ImportFrom) and n.module:names.add(n.module.split('.')[0])
    assert not names.intersection({'requests','httpx','aiohttp','urllib','socket','subprocess'})

def test_web_health_and_phase16_auth_boundary(tmp_path):
    from fastapi.testclient import TestClient
    from eagleeye.interfaces.web.app361 import create_workspace_app361
    app=create_workspace_app361(base_dir=tmp_path/'web')
    with TestClient(app) as client:
        h=client.get('/health'); assert h.status_code==200 and h.json()['build']=='361.0'
        assert client.get('/api/build361/phase16-status').status_code==401
