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
from eagleeye_pro.phase17.research_wave_execution388 import CONFIRM_START, CONFIRM_ATTACH
from eagleeye_pro.phase17.result_intake389 import CONFIRM_PROMOTE
PW='Build389-Test-Orbit!'

def ctx(tmp_path): return AppContext(base_dir=tmp_path, actor='test389')
def admin(c):
    a=c.team_identity_359.create_initial_admin(username='admin389',display_name='Admin 389',password=PW); return {**a,'session_id':'test-session-389'}
def case(c,a): return c.build380.team_create_case(identity=a,title='Build389 test',client='internal',purpose='authorized result intake qualification',legal_basis='public_data')

def setup_terminal(c,a,cid, *, objects=1, same_record=True, quarantined=False):
    c.build382.set_source_scope(case_id=cid,source_id='gleif.lei',state='approved',reviewer='admin389',confirmation='APPROVE SOURCE')
    waves=c.build384.plan_research_waves(case_id=cid,mission='official corporate identifier verification',jurisdictions=('global',),source_classes=('corporate',),wave_confirmation=CONFIRM_WAVES)
    packet=c.build385.compile_acquisition_packet(case_id=cid,wave_plan_id=waves['wave_plan_id'],identifiers={'gleif.lei':'5493001KJTIIGC8Y1R12'},actor='admin389')
    prep=c.build385.prepare_acquisition_packet(case_id=cid,packet_id=packet['packet_id'],identity=a,confirmation=CONFIRM_PREPARE); sid=next(x['canonical_source_id'] for x in prep['outcomes'] if x.get('canonical_source_id'))
    c.crawler_engine_349.review_source(sid,decision='approve_read_only',rationale='Build389 controlled source',reviewer='admin389')
    c.case_workflow_374.configure(case_id=cid,identity=a,source_budgets={sid:20},case_request_budget=20,max_active_crawls=2,confirmation='WORKFLOW')
    grant=c.build386.issue_execution_grant(case_id=cid,packet_id=packet['packet_id'],identity=a,confirmation=CONFIRM_GO,source_ids=['gleif.lei'],ttl_minutes=5)
    dispatch=c.build387.execute_grant(case_id=cid,grant_id=grant['grant_id'],grant_token=grant['grant_token'],identity=a,confirmation=CONFIRM_EXECUTE)
    sess=c.build388.start_wave_session(case_id=cid,wave_plan_id=waves['wave_plan_id'],packet_id=packet['packet_id'],identity=a,confirmation=CONFIRM_START)
    c.build388.attach_wave_dispatch(case_id=cid,session_id=sess['session_id'],dispatch_id=dispatch['dispatch_id'],identity=a,confirmation=CONFIRM_ATTACH)
    worker='worker389'; job=c.build348.claim_job(worker_id=worker); assert job
    object_ids=[]
    for i in range(objects):
        lei='5493001KJTIIGC8Y1R12' if same_record else f'5493001KJTIIGC8Y{i:03d}'
        body={'data':[{'id':lei,'attributes':{'lei':lei,'entity':{'legalName':{'name':'Example GmbH' if same_record else f'Example {i} GmbH'},'status':'ACTIVE'}}}]}
        obj=c.build348.ingest_artifact(case_id=cid,content=json.dumps(body),media_type='application/json',search_run_id=job['search_run_id'],source_id=sid,security_state='quarantined' if quarantined else 'review_pending',provenance={'url':f'https://example.invalid/lei/{i}.json','build389_test':True})
        object_ids.append(obj['object_id'])
    c.build348.complete_job(job['job_id'],{'pages_fetched':objects,'pages_stored':objects,'errors':0},worker_id=worker)
    done=c.build388.reconcile_wave_session(case_id=cid,session_id=sess['session_id'],identity=a); assert done['terminal_jobs']==1
    return sess, sid, object_ids

def test_version_schema_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build389.version_status()=={'runtime_build':'389.0','schema_version':'389.0','package_version':'389.0.0','coherent':True}
        assert c.build389.schema_metrics()['within_phase17_gate']; s=c.result_intake_389.status(); assert s['result_normalization'] and s['ai_candidate_feed'] and not s['automatic_evidence_promotion']

def test_terminal_json_normalizes_to_candidate(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; sess,_sid,oids=setup_terminal(c,a,cid)
        out=c.build389.normalize_wave_results(case_id=cid,session_id=sess['session_id'],identity=a); assert out['candidate_count']==1
        cand=out['candidates'][0]; assert cand['normalized']['lei']=='5493001KJTIIGC8Y1R12' and cand['object_id']==oids[0] and cand['review_status']=='needs_review' and cand['truth_assigned'] is False
        assert c.build389.verify_evidence_candidate(case_id=cid,candidate_id=cand['candidate_id'])['valid']

def test_normalization_idempotent(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; sess,_,_=setup_terminal(c,a,cid)
        first=c.build389.normalize_wave_results(case_id=cid,session_id=sess['session_id'],identity=a); second=c.build389.normalize_wave_results(case_id=cid,session_id=sess['session_id'],identity=a)
        assert first['candidate_count']==1 and second['candidate_count']==0 and len(c.build389.evidence_candidates(case_id=cid,identity=a))==1

def test_exact_duplicate_is_linked_not_collapsed(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; sess,_,_=setup_terminal(c,a,cid,objects=2,same_record=True)
        out=c.build389.normalize_wave_results(case_id=cid,session_id=sess['session_id'],identity=a); assert out['candidate_count']==2 and out['duplicate_links']==1
        rows=sorted(out['candidates'],key=lambda x:x['created_at']); assert rows[1]['duplicate_of_candidate_id']==rows[0]['candidate_id']; assert len(c.build389.evidence_candidates(case_id=cid,identity=a))==2

def test_ai_feed_is_candidate_only(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; sess,_,_=setup_terminal(c,a,cid); c.build389.normalize_wave_results(case_id=cid,session_id=sess['session_id'],identity=a)
        feed=c.build389.ai_evidence_candidates(case_id=cid,identity=a); assert feed['candidate_only'] and feed['truth_assigned'] is False and feed['identity_merge_authority'] is False and feed['candidate_count']==1

def test_promotion_requires_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; sess,_,_=setup_terminal(c,a,cid); cand=c.build389.normalize_wave_results(case_id=cid,session_id=sess['session_id'],identity=a)['candidates'][0]
        with pytest.raises(PermissionError): c.build389.promote_evidence_candidate(case_id=cid,candidate_id=cand['candidate_id'],identity=a,confirmation='PROMOTE')

def test_explicit_promotion_goes_to_vault_needs_review_only(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; sess,_,_=setup_terminal(c,a,cid); cand=c.build389.normalize_wave_results(case_id=cid,session_id=sess['session_id'],identity=a)['candidates'][0]
        before=int((c.db.one('SELECT COUNT(*) n FROM evidence_items WHERE case_id=?',(cid,)) or {})['n'])
        out=c.build389.promote_evidence_candidate(case_id=cid,candidate_id=cand['candidate_id'],identity=a,confirmation=CONFIRM_PROMOTE); art=out['vault_artifact']
        assert art['review_status']=='needs_review' and out['evidence_review_required'] is True and out['automatic_truth_acceptance'] is False
        after=int((c.db.one('SELECT COUNT(*) n FROM evidence_items WHERE case_id=?',(cid,)) or {})['n']); assert before==after
        assert c.evidence_vault_50.verify_chain(art['artifact_id'])['valid']

def test_promotion_idempotent(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; sess,_,_=setup_terminal(c,a,cid); cand=c.build389.normalize_wave_results(case_id=cid,session_id=sess['session_id'],identity=a)['candidates'][0]
        one=c.build389.promote_evidence_candidate(case_id=cid,candidate_id=cand['candidate_id'],identity=a,confirmation=CONFIRM_PROMOTE); two=c.build389.promote_evidence_candidate(case_id=cid,candidate_id=cand['candidate_id'],identity=a,confirmation=CONFIRM_PROMOTE)
        assert one['vault_artifact']['artifact_id']==two['vault_artifact']['artifact_id'] and two['idempotent'] is True

def test_quarantined_object_is_not_auto_parsed_or_promoted(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; sess,_,oids=setup_terminal(c,a,cid,quarantined=True)
        out=c.build389.normalize_wave_results(case_id=cid,session_id=sess['session_id'],identity=a); cand=out['candidates'][0]; assert cand['review_status']=='blocked_quarantined' and cand['candidate_type']=='quarantined_artifact_review'
        assert not c.db.one('SELECT 1 x FROM phase15_parse_runs WHERE object_id=?',(oids[0],))
        with pytest.raises(PermissionError): c.build389.promote_evidence_candidate(case_id=cid,candidate_id=cand['candidate_id'],identity=a,confirmation=CONFIRM_PROMOTE)

def test_raw_object_hash_binding_detects_tamper_metadata(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; sess,_,oids=setup_terminal(c,a,cid); cand=c.build389.normalize_wave_results(case_id=cid,session_id=sess['session_id'],identity=a)['candidates'][0]
        c.db.execute("UPDATE evidence_candidate_389 SET object_sha256='tampered' WHERE candidate_id=?",(cand['candidate_id'],)); assert c.build389.verify_evidence_candidate(case_id=cid,candidate_id=cand['candidate_id'])['valid'] is False

def test_no_network_jobs_or_grants_created_by_normalization(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; sess,_,_=setup_terminal(c,a,cid); jb=int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']); gb=int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']); c.build389.normalize_wave_results(case_id=cid,session_id=sess['session_id'],identity=a); assert int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n'])==jb and int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n'])==gb

def test_web_health_and_auth(tmp_path):
    from eagleeye.interfaces.web.app389 import create_workspace_app389
    app=create_workspace_app389(base_dir=tmp_path)
    try:
        client=TestClient(app); h=client.get('/health'); assert h.status_code==200 and h.json()['build']=='389.0' and h.json()['result_intake_normalization'] is True; assert client.get('/api/build389/phase17-status').status_code==401
    finally: app.state.context.close()

def test_current_launchers_server_point_389():
    root=Path(__file__).resolve().parents[1]; assert 'app389 import create_workspace_app389' in (root/'src/eagleeye/interfaces/web/server.py').read_text(); assert 'EAGLEEYE_PRO_389_0.py' in (root/'START_EAGLEEYE_PRO.bat').read_text(); assert 'EAGLEEYE_PRO_389_0.py' in (root/'START_EAGLEEYE_PRO.sh').read_text()
