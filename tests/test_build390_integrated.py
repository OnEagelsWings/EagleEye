from __future__ import annotations
import hashlib, json, secrets
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.evidence_review390 import CONFIRM_ASSESS, CONFIRM_FINALIZE, CONFIRM_INDEPENDENCE

PW='Build390-Test-Orbit!'

def ctx(tmp_path): return AppContext(base_dir=tmp_path, actor='test390')
def admin(c):
    a=c.team_identity_359.create_initial_admin(username='admin390',display_name='Admin 390',password=PW); return {**a,'session_id':'test-session-390'}
def case(c,a): return c.build380.team_create_case(identity=a,title='Build390 test',client='internal',purpose='authorized evidence review qualification',legal_basis='public_data')

def candidate(c, case_id, *, phase17_source_id='gleif.lei', normalized=None, review_status='needs_review'):
    normalized = normalized or {'name':'Example GmbH','status':'ACTIVE'}
    raw=json.dumps({'source':phase17_source_id,'normalized':normalized},sort_keys=True).encode()
    oid='obj390_'+secrets.token_hex(8); sha=hashlib.sha256(raw).hexdigest(); now='2026-09-13T10:00:00+00:00'
    c.db.execute("INSERT INTO phase15_objects(object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (oid,case_id,'','canon_'+phase17_source_id,'local','objects/'+oid,sha,len(raw),'application/json','review_pending',json.dumps({'source_url':'https://example.invalid/'+oid}),'test390',now,hashlib.sha256(raw+b'row').hexdigest()))
    obj={'object_id':oid,'sha256':sha,'media_type':'application/json','security_state':'review_pending','provenance_json':json.dumps({'source_url':'https://example.invalid/'+oid})}
    result={'wave_number':1,'phase17_source_id':phase17_source_id,'canonical_source_id':'canon_'+phase17_source_id,'dispatch_id':'disp_'+oid,'job_id':'job_'+oid,'crawl_run_id':'crawl_'+oid,'search_run_id':'search_'+oid}
    cand,_=c.result_intake_389._insert_candidate(case_id=case_id,session_id='sess390',result_row=result,obj=obj,parse_run_id='parse_'+oid,record_index=0,candidate_type='normalized_record',normalized=normalized,provenance={'source_url':'https://example.invalid/'+oid,'object_id':oid},review_status=review_status)
    return cand

def review(c,a,cid, mapping, proposition='Example GmbH is active'):
    return c.build390.create_corroboration_review(case_id=cid,proposition=proposition,candidate_stances=mapping,identity=a)

def assess(c,a,cid,rid):
    return c.build390.assess_corroboration_review(case_id=cid,review_id=rid,identity=a,confirmation=CONFIRM_ASSESS)

def test_version_schema_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build390.version_status()=={'runtime_build':'390.0','schema_version':'390.0','package_version':'390.0.0','coherent':True}
        assert c.build390.schema_metrics()['within_phase17_gate']
        s=c.evidence_review_390.status(); assert s['source_independence_profiles'] and s['duplicate_aware'] and s['mirror_aware'] and not s['automatic_truth_acceptance']

def test_archive_profile_not_countable_by_default(tmp_path):
    with ctx(tmp_path) as c:
        p=next(x for x in c.build390.source_independence_profiles() if x['phase17_source_id']=='internet_archive.metadata')
        assert p['countable_default'] is False and p['source_role']=='archive_mirror'

def test_same_source_exact_duplicates_count_once(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; one=candidate(c,cid); two=candidate(c,cid)
        r=review(c,a,cid,{one['candidate_id']:'supports',two['candidate_id']:'supports'}); out=assess(c,a,cid,r['review_id'])
        assert out['support_groups']==1 and out['exact_duplicate_links']==1 and out['assessment_state']=='single_independence_group'
        assert out['truth_determined'] is False and out['probability_assigned'] is False

def test_distinct_primary_publishers_count_as_two_groups(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; one=candidate(c,cid,phase17_source_id='gleif.lei'); two=candidate(c,cid,phase17_source_id='sec.edgar')
        r=review(c,a,cid,{one['candidate_id']:'supports',two['candidate_id']:'supports'}); out=assess(c,a,cid,r['review_id'])
        assert out['support_groups']==2 and out['assessment_state']=='multi_group_support'
        assert set(out['support_group_ids'])=={'publisher:gleif.org','publisher:sec.gov'}

def test_archive_mirror_does_not_add_independent_support(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; one=candidate(c,cid,phase17_source_id='gleif.lei'); arc=candidate(c,cid,phase17_source_id='internet_archive.metadata')
        r=review(c,a,cid,{one['candidate_id']:'supports',arc['candidate_id']:'supports'}); out=assess(c,a,cid,r['review_id'])
        assert out['support_groups']==1 and out['non_countable_observations']==1 and out['assessment_state']=='single_independence_group'

def test_contradiction_is_preserved_not_averaged_away(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; one=candidate(c,cid,phase17_source_id='gleif.lei'); two=candidate(c,cid,phase17_source_id='sec.edgar',normalized={'name':'Example GmbH','status':'INACTIVE'})
        r=review(c,a,cid,{one['candidate_id']:'supports',two['candidate_id']:'contradicts'}); out=assess(c,a,cid,r['review_id'])
        assert out['support_groups']==1 and out['contradiction_groups']==1 and out['assessment_state']=='contested_single_support_group'

def test_unknown_origin_fails_closed(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; one=candidate(c,cid,phase17_source_id='custom.unknown')
        r=review(c,a,cid,{one['candidate_id']:'supports'}); out=assess(c,a,cid,r['review_id'])
        assert out['support_groups']==0 and out['unresolved_observations']==1 and out['assessment_state']=='independence_unresolved'

def test_candidate_integrity_tamper_blocks_assessment_state(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; one=candidate(c,cid)
        r=review(c,a,cid,{one['candidate_id']:'supports'}); c.db.execute("UPDATE evidence_candidate_389 SET object_sha256='tampered' WHERE candidate_id=?",(one['candidate_id'],))
        out=assess(c,a,cid,r['review_id']); assert out['invalid_candidates']==1 and out['assessment_state']=='integrity_review_required' and out['support_groups']==0

def test_independence_override_requires_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; arc=candidate(c,cid,phase17_source_id='internet_archive.metadata')
        with pytest.raises(PermissionError):
            c.build390.review_source_independence(case_id=cid,candidate_id=arc['candidate_id'],identity=a,source_family='originpublisher',independence_group='origin:publisher.example',origin_key='https://publisher.example/doc',countable=True,rationale='Reviewed original publisher provenance',confirmation='REVIEW')

def test_reviewed_archive_origin_can_be_counted_without_truth_promotion(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; one=candidate(c,cid,phase17_source_id='gleif.lei'); arc=candidate(c,cid,phase17_source_id='internet_archive.metadata')
        ov=c.build390.review_source_independence(case_id=cid,candidate_id=arc['candidate_id'],identity=a,source_family='originpublisher',independence_group='origin:publisher.example',origin_key='https://publisher.example/doc',countable=True,rationale='Reviewed original publisher provenance',confirmation=CONFIRM_INDEPENDENCE)
        assert ov['countable'] and ov['truth_assigned'] is False
        r=review(c,a,cid,{one['candidate_id']:'supports',arc['candidate_id']:'supports'}); out=assess(c,a,cid,r['review_id']); assert out['support_groups']==2 and out['truth_determined'] is False

def test_finalize_requires_assessment_and_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; one=candidate(c,cid); r=review(c,a,cid,{one['candidate_id']:'supports'})
        with pytest.raises(PermissionError): c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition='needs_more_evidence',confirmation=CONFIRM_FINALIZE)
        out=assess(c,a,cid,r['review_id']); assert out['assessment_id']
        with pytest.raises(PermissionError): c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition='needs_more_evidence',confirmation='FINALIZE')
        fin=c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition='needs_more_evidence',confirmation=CONFIRM_FINALIZE); assert fin['status']=='finalized' and fin['truth_determined'] is False

def test_no_jobs_grants_or_evidence_promotions_created(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; one=candidate(c,cid); two=candidate(c,cid,phase17_source_id='sec.edgar')
        before=(int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']))
        r=review(c,a,cid,{one['candidate_id']:'supports',two['candidate_id']:'supports'}); assess(c,a,cid,r['review_id'])
        after=(int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']))
        assert before==after

def test_ai_feed_is_review_only(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; one=candidate(c,cid); r=review(c,a,cid,{one['candidate_id']:'supports'}); assess(c,a,cid,r['review_id'])
        feed=c.build390.ai_corroboration_feed(case_id=cid,identity=a); assert feed['candidate_review_only'] and feed['truth_determined'] is False and feed['probability_assigned'] is False and feed['automatic_evidence_promotion'] is False and feed['review_count']==1

def test_assessment_hash_verification_detects_tamper(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; one=candidate(c,cid); r=review(c,a,cid,{one['candidate_id']:'supports'}); out=assess(c,a,cid,r['review_id']); assert c.build390.verify_corroboration_assessment(case_id=cid,assessment_id=out['assessment_id'])['valid']
        c.db.execute("UPDATE corroboration_assessment_390 SET assessment_state='tampered' WHERE assessment_id=?",(out['assessment_id'],)); assert c.build390.verify_corroboration_assessment(case_id=cid,assessment_id=out['assessment_id'])['valid'] is False

def test_web_health_and_auth(tmp_path):
    from eagleeye.interfaces.web.app390 import create_workspace_app390
    app=create_workspace_app390(base_dir=tmp_path)
    try:
        client=TestClient(app); h=client.get('/health'); assert h.status_code==200 and h.json()['build']=='390.0' and h.json()['evidence_review_corroboration'] is True; assert client.get('/api/build390/phase17-status').status_code==401
    finally: app.state.context.close()

def test_current_launchers_server_point_390():
    root=Path(__file__).resolve().parents[1]; assert 'app390 import create_workspace_app390' in (root/'src/eagleeye/interfaces/web/server.py').read_text(); assert 'EAGLEEYE_PRO_390_0.py' in (root/'START_EAGLEEYE_PRO.bat').read_text(); assert 'EAGLEEYE_PRO_390_0.py' in (root/'START_EAGLEEYE_PRO.sh').read_text()
