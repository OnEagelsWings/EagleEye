from __future__ import annotations
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.jurisdiction_intelligence384 import CONFIRM_WAVES
from eagleeye_pro.phase17.acquisition_orchestrator385 import CONFIRM_PREPARE
from eagleeye_pro.phase17.execution_authority386 import CONFIRM_GO
from eagleeye_pro.phase17.controlled_executor387 import CONFIRM_EXECUTE
from eagleeye_pro.phase17.research_wave_execution388 import CONFIRM_START, CONFIRM_ATTACH, CONFIRM_ADVANCE
PW='Build388-Test-Orbit!'

def ctx(tmp_path): return AppContext(base_dir=tmp_path, actor='test388')
def admin(c):
    a=c.team_identity_359.create_initial_admin(username='admin388',display_name='Admin 388',password=PW); return {**a,'session_id':'test-session-388'}
def case(c,a): return c.build380.team_create_case(identity=a,title='Build388 test',client='internal',purpose='authorized governed research-wave qualification',legal_basis='public_data')

def setup_dispatch(c,a,cid, *, add_second_wave=False):
    c.build382.set_source_scope(case_id=cid,source_id='gleif.lei',state='approved',reviewer='admin388',confirmation='APPROVE SOURCE')
    waves=c.build384.plan_research_waves(case_id=cid,mission='official corporate identifier verification',jurisdictions=('global',),source_classes=('corporate',),wave_confirmation=CONFIRM_WAVES)
    packet=c.build385.compile_acquisition_packet(case_id=cid,wave_plan_id=waves['wave_plan_id'],identifiers={'gleif.lei':'5493001KJTIIGC8Y1R12'},actor='admin388')
    if add_second_wave:
        row=c.db.one('SELECT packet_json FROM acquisition_packet_385 WHERE packet_id=?',(packet['packet_id'],)); body=json.loads(row['packet_json']); clone=dict(body['items'][0]); clone['source_id']='internet_archive.metadata'; clone['source_class']='archive'; clone['wave_number']=2; clone['ready_for_preparation']=False; clone['blockers']=['identifier_required']; body['items'].append(clone); body['packet_hash']='test388_multiwave_hash'; c.db.execute('UPDATE acquisition_packet_385 SET packet_json=?,packet_hash=? WHERE packet_id=?',(json.dumps(body,sort_keys=True,separators=(',',':')),'test388_multiwave_hash',packet['packet_id']))
        packet={**packet,'packet_hash':'test388_multiwave_hash'}
    prepared=c.build385.prepare_acquisition_packet(case_id=cid,packet_id=packet['packet_id'],identity=a,confirmation=CONFIRM_PREPARE)
    sid=next(x['canonical_source_id'] for x in prepared['outcomes'] if x.get('canonical_source_id'))
    c.crawler_engine_349.review_source(sid,decision='approve_read_only',rationale='Build 388 controlled source',reviewer='admin388')
    c.case_workflow_374.configure(case_id=cid,identity=a,source_budgets={sid:20},case_request_budget=20,max_active_crawls=2,confirmation='WORKFLOW')
    grant=c.build386.issue_execution_grant(case_id=cid,packet_id=packet['packet_id'],identity=a,confirmation=CONFIRM_GO,source_ids=['gleif.lei'],ttl_minutes=5)
    dispatch=c.build387.execute_grant(case_id=cid,grant_id=grant['grant_id'],grant_token=grant['grant_token'],identity=a,confirmation=CONFIRM_EXECUTE)
    return waves,packet,sid,dispatch

def start_and_attach(c,a,cid,waves,packet,dispatch):
    sess=c.build388.start_wave_session(case_id=cid,wave_plan_id=waves['wave_plan_id'],packet_id=packet['packet_id'],identity=a,confirmation=CONFIRM_START)
    return c.build388.attach_wave_dispatch(case_id=cid,session_id=sess['session_id'],dispatch_id=dispatch['dispatch_id'],identity=a,confirmation=CONFIRM_ATTACH)

def test_version_schema_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build388.version_status()=={'runtime_build':'388.0','schema_version':'388.0','package_version':'388.0.0','coherent':True}
        assert c.build388.schema_metrics()['within_phase17_gate']
        s=c.research_wave_execution_388.status(); assert s['sequential_wave_governance'] and not s['automatic_go_issuance'] and not s['automatic_evidence_promotion']

def test_start_requires_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; waves,packet,_sid,_dispatch=setup_dispatch(c,a,cid)
        with pytest.raises(PermissionError): c.build388.start_wave_session(case_id=cid,wave_plan_id=waves['wave_plan_id'],packet_id=packet['packet_id'],identity=a,confirmation='START')

def test_attach_and_queued_reconcile(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; waves,packet,_sid,dispatch=setup_dispatch(c,a,cid); sess=start_and_attach(c,a,cid,waves,packet,dispatch)
        out=c.build388.reconcile_wave_session(case_id=cid,session_id=sess['session_id'],identity=a)
        assert out['decision']=='awaiting_worker_results' and out['nonterminal_jobs']==1 and out['automatic_worker_claim'] is False

def test_terminal_success_returns_artifact_and_coverage(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; waves,packet,sid,dispatch=setup_dispatch(c,a,cid); sess=start_and_attach(c,a,cid,waves,packet,dispatch)
        worker='worker388'; job=c.build348.claim_job(worker_id=worker); assert job and job['job_id']==dispatch['job_ids'][0]
        c.build348.ingest_artifact(case_id=cid,content='official result',media_type='text/plain',search_run_id=job['search_run_id'],source_id=sid,security_state='review_pending',provenance={'build388_test':True})
        c.build348.complete_job(job['job_id'],{'pages_fetched':1,'pages_stored':1,'errors':0},worker_id=worker)
        out=c.build388.reconcile_wave_session(case_id=cid,session_id=sess['session_id'],identity=a)
        assert out['decision']=='session_complete'; assert out['observations'][0]['coverage_state']=='succeeded'; assert len(out['observations'][0]['object_ids'])==1
        cov=c.phase17_runtime_384.repository.coverage_report(cid,requested_source_classes=('corporate',)); assert cov.successful_or_partial_count>=1
        assert c.build388.verify_wave_session(case_id=cid,session_id=sess['session_id'])['valid']

def test_success_without_artifact_is_no_result_review(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; waves,packet,_sid,dispatch=setup_dispatch(c,a,cid); sess=start_and_attach(c,a,cid,waves,packet,dispatch)
        worker='worker388'; job=c.build348.claim_job(worker_id=worker); c.build348.complete_job(job['job_id'],{'pages_fetched':1,'pages_stored':0,'errors':0},worker_id=worker)
        out=c.build388.reconcile_wave_session(case_id=cid,session_id=sess['session_id'],identity=a); assert out['decision']=='no_result_review'; assert out['coverage']['no_result_is_nonexistence'] is False

def test_failed_job_requires_review(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; waves,packet,_sid,dispatch=setup_dispatch(c,a,cid); sess=start_and_attach(c,a,cid,waves,packet,dispatch)
        worker='worker388'; job=c.build348.claim_job(worker_id=worker); c.db.execute("UPDATE phase15_jobs SET max_attempts=1 WHERE job_id=?",(job['job_id'],)); c.build348.fail_job(job['job_id'],'simulated',worker_id=worker,retry_delay_seconds=0)
        out=c.build388.reconcile_wave_session(case_id=cid,session_id=sess['session_id'],identity=a); assert out['decision']=='human_review_required'

def test_dispatch_cannot_attach_to_wrong_packet_session(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; waves,packet,_sid,dispatch=setup_dispatch(c,a,cid)
        row=c.db.one("SELECT * FROM acquisition_packet_385 WHERE packet_id=?",(packet['packet_id'],)); other='acq385_wrongpacket388'
        c.db.execute("INSERT INTO acquisition_packet_385(packet_id,case_id,wave_plan_id,packet_hash,packet_json,identifiers_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)",(other,cid,row['wave_plan_id'],'wronghash',row['packet_json'],row['identifiers_json'],'admin388',row['created_at']))
        sess=c.build388.start_wave_session(case_id=cid,wave_plan_id=waves['wave_plan_id'],packet_id=other,identity=a,confirmation=CONFIRM_START)
        with pytest.raises(PermissionError): c.build388.attach_wave_dispatch(case_id=cid,session_id=sess['session_id'],dispatch_id=dispatch['dispatch_id'],identity=a,confirmation=CONFIRM_ATTACH)

def test_packet_mutation_blocks_reconcile(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; waves,packet,_sid,dispatch=setup_dispatch(c,a,cid); sess=start_and_attach(c,a,cid,waves,packet,dispatch); c.db.execute("UPDATE acquisition_packet_385 SET packet_hash='tampered' WHERE packet_id=?",(packet['packet_id'],))
        with pytest.raises(PermissionError,match='packet hash changed'): c.build388.reconcile_wave_session(case_id=cid,session_id=sess['session_id'],identity=a)

def test_multiwave_requires_explicit_advance_and_no_auto_go(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; waves,packet,sid,dispatch=setup_dispatch(c,a,cid,add_second_wave=True); sess=start_and_attach(c,a,cid,waves,packet,dispatch)
        worker='worker388'; job=c.build348.claim_job(worker_id=worker); c.build348.ingest_artifact(case_id=cid,content='x',search_run_id=job['search_run_id'],source_id=sid,security_state='review_pending',provenance={}); c.build348.complete_job(job['job_id'],{'pages_fetched':1,'pages_stored':1,'errors':0},worker_id=worker)
        before=int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']); out=c.build388.reconcile_wave_session(case_id=cid,session_id=sess['session_id'],identity=a); after=int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n'])
        assert out['decision']=='ready_for_next_wave_go' and before==after
        with pytest.raises(PermissionError): c.build388.advance_wave_session(case_id=cid,session_id=sess['session_id'],identity=a,confirmation='NEXT')
        adv=c.build388.advance_wave_session(case_id=cid,session_id=sess['session_id'],identity=a,confirmation=CONFIRM_ADVANCE); assert adv['current_wave']==2 and adv['decision']=='awaiting_go'; assert c.build388.verify_wave_session(case_id=cid,session_id=sess['session_id'])['valid']

def test_reconcile_idempotent_no_duplicate_coverage(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; waves,packet,sid,dispatch=setup_dispatch(c,a,cid); sess=start_and_attach(c,a,cid,waves,packet,dispatch); worker='w'; job=c.build348.claim_job(worker_id=worker); c.build348.ingest_artifact(case_id=cid,content='x',search_run_id=job['search_run_id'],source_id=sid,security_state='review_pending',provenance={}); c.build348.complete_job(job['job_id'],{'pages_stored':1},worker_id=worker)
        c.build388.reconcile_wave_session(case_id=cid,session_id=sess['session_id'],identity=a); n1=int((c.db.one('SELECT COUNT(*) n FROM source_coverage_ledger WHERE case_id=?',(cid,)) or {})['n']); c.build388.reconcile_wave_session(case_id=cid,session_id=sess['session_id'],identity=a); n2=int((c.db.one('SELECT COUNT(*) n FROM source_coverage_ledger WHERE case_id=?',(cid,)) or {})['n']); assert n1==n2

def test_web_health_and_auth(tmp_path):
    from eagleeye.interfaces.web.app388 import create_workspace_app388
    app=create_workspace_app388(base_dir=tmp_path)
    try:
        client=TestClient(app); h=client.get('/health'); assert h.status_code==200 and h.json()['build']=='388.0' and h.json()['governed_research_waves'] is True; assert client.get('/api/build388/phase17-status').status_code==401
    finally: app.state.context.close()

def test_current_launchers_server_point_388():
    root=Path(__file__).resolve().parents[1]; assert 'app388 import create_workspace_app388' in (root/'src/eagleeye/interfaces/web/server.py').read_text(); assert 'EAGLEEYE_PRO_388_0.py' in (root/'START_EAGLEEYE_PRO.bat').read_text(); assert 'EAGLEEYE_PRO_388_0.py' in (root/'START_EAGLEEYE_PRO.sh').read_text()
