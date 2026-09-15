from __future__ import annotations
import hashlib, json, secrets
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.evidence_review390 import CONFIRM_ASSESS, CONFIRM_FINALIZE
from eagleeye_pro.phase17.investigation_synthesis391 import CONFIRM_CLAIM_REVIEW, CONFIRM_HYPOTHESIS_REVIEW, CONFIRM_KERNEL_ADMISSION, CONFIRM_SNAPSHOT

PW='Build391-Test-Orbit!'
def ctx(tmp_path): return AppContext(base_dir=tmp_path,actor='test391')
def admin(c):
    a=c.team_identity_359.create_initial_admin(username='admin391',display_name='Lead Analyst 391',password=PW); return {**a,'session_id':'test391'}
def case(c,a): return c.build380.team_create_case(identity=a,title='Build391 test',client='internal',purpose='authorized synthesis qualification',legal_basis='public_data')

def candidate(c,cid,source='gleif.lei',norm=None):
    norm=norm or {'name':'Example GmbH','status':'ACTIVE'}; raw=json.dumps({'s':source,'n':norm},sort_keys=True).encode(); oid='obj391_'+secrets.token_hex(8); sha=hashlib.sha256(raw).hexdigest(); now='2026-09-13T15:00:00+00:00'
    c.db.execute("INSERT INTO phase15_objects(object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,cid,'','canon_'+source,'local',oid,sha,len(raw),'application/json','review_pending','{}','test391',now,hashlib.sha256(raw+b'r').hexdigest()))
    obj={'object_id':oid,'sha256':sha,'media_type':'application/json','security_state':'review_pending'}; result={'wave_number':1,'phase17_source_id':source,'canonical_source_id':'canon_'+source,'dispatch_id':'d'+oid,'job_id':'j'+oid,'crawl_run_id':'c'+oid,'search_run_id':'s'+oid}
    out,_=c.result_intake_389._insert_candidate(case_id=cid,session_id='sess391',result_row=result,obj=obj,parse_run_id='p'+oid,record_index=0,candidate_type='normalized_record',normalized=norm,provenance={}); return out

def finalized_review(c,a,cid,*,contradiction=False):
    g=candidate(c,cid,'gleif.lei',{'name':'Example GmbH','status':'ACTIVE'}); s=candidate(c,cid,'sec.edgar',{'name':'Example GmbH','status':'INACTIVE' if contradiction else 'ACTIVE'})
    mapping={g['candidate_id']:'supports',s['candidate_id']:'contradicts' if contradiction else 'supports'}
    r=c.build390.create_corroboration_review(case_id=cid,proposition='Example GmbH is active',candidate_stances=mapping,identity=a)
    c.build390.assess_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,confirmation=CONFIRM_ASSESS)
    disp='contested_requires_analysis' if contradiction else 'ready_for_evidence_review'
    c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition=disp,confirmation=CONFIRM_FINALIZE)
    return r['review_id']

def synth_claim(c,a,cid,contradiction=False):
    rid=finalized_review(c,a,cid,contradiction=contradiction); return c.build391.synthesize_corroboration_review(case_id=cid,review_id=rid,identity=a)

def reviewed_claim(c,a,cid,contradiction=False):
    cl=synth_claim(c,a,cid,contradiction); disp='contested_requires_analysis' if contradiction else 'ready_for_hypothesis_work'
    return c.build391.review_synthesis_claim(case_id=cid,claim_id=cl['claim_id'],identity=a,disposition=disp,rationale='Reviewed source-independent structure and preserved uncertainty.',confirmation=CONFIRM_CLAIM_REVIEW)

def test_version_schema_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build391.version_status()=={'runtime_build':'391.0','schema_version':'391.0','package_version':'391.0.0','coherent':True}
        assert c.build391.schema_metrics()['within_phase17_gate']; s=c.investigation_synthesis_391.status(); assert s['candidate_claim_synthesis'] and s['counterevidence_preserved'] and not s['truth_probability']

def test_synthesis_requires_finalized_review(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; g=candidate(c,cid); r=c.build390.create_corroboration_review(case_id=cid,proposition='Draft proposition',candidate_stances={g['candidate_id']:'supports'},identity=a)
        with pytest.raises(PermissionError): c.build391.synthesize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a)

def test_multisource_claim_is_candidate_not_fact(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl=synth_claim(c,a,cid)
        assert cl['structural_state']=='multi_source_support_structure' and cl['support_groups']==2
        assert cl['epistemic_status']=='candidate_claim_not_fact' and cl['truth_determined'] is False and cl['probability_assigned'] is False and cl['verified_fact'] is False

def test_counterevidence_preserved(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl=synth_claim(c,a,cid,True)
        assert cl['contradiction_groups']==1 and cl['structural_state'].startswith('contested_') and len(cl['counterevidence_candidate_ids'])==1
        feed=c.build391.ai_investigation_synthesis_feed(case_id=cid,identity=a); assert len(feed['counterevidence'])==1

def test_claim_review_requires_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl=synth_claim(c,a,cid)
        with pytest.raises(PermissionError): c.build391.review_synthesis_claim(case_id=cid,claim_id=cl['claim_id'],identity=a,disposition='ready_for_hypothesis_work',rationale='Substantive analytical review rationale.',confirmation='REVIEW')

def test_reviewed_claim_still_not_truth(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl=reviewed_claim(c,a,cid)
        assert cl['status']=='reviewed_candidate' and cl['analyst_disposition']=='ready_for_hypothesis_work' and cl['truth_determined'] is False

def test_hypothesis_requires_reviewed_claim(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl=synth_claim(c,a,cid)
        with pytest.raises(PermissionError): c.build391.propose_hypothesis(case_id=cid,title='Operating status explanation',statement='The company remained active because filings were current.',test_plan='Check dated filings and registry changes.',claim_relations={cl['claim_id']:'supports_hypothesis'},identity=a)

def test_hypothesis_is_not_probability(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl=reviewed_claim(c,a,cid)
        h=c.build391.propose_hypothesis(case_id=cid,title='Operating status explanation',statement='The company remained active because filings were current.',test_plan='Check dated filings and registry changes.',claim_relations={cl['claim_id']:'supports_hypothesis'},identity=a)
        assert h['epistemic_status']=='hypothesis_not_fact' and h['status']=='proposal_needs_review' and h['probability_assigned'] is False and h['legacy_kernel_confidence_used'] is False
        assert 'confidence' not in h and 'prior' not in h

def test_hypothesis_review_and_kernel_admission(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl=reviewed_claim(c,a,cid); h=c.build391.propose_hypothesis(case_id=cid,title='Operating status explanation',statement='The company remained active because filings were current.',test_plan='Check dated filings and registry changes.',claim_relations={cl['claim_id']:'supports_hypothesis'},identity=a)
        with pytest.raises(PermissionError): c.build391.review_synthesis_hypothesis(case_id=cid,hypothesis_id=h['hypothesis_id'],identity=a,disposition='retain_for_testing',rationale='Testable and properly separated from fact.',confirmation='REVIEW')
        h=c.build391.review_synthesis_hypothesis(case_id=cid,hypothesis_id=h['hypothesis_id'],identity=a,disposition='retain_for_testing',rationale='Testable and properly separated from fact.',confirmation=CONFIRM_HYPOTHESIS_REVIEW)
        before=int((c.db.one('SELECT COUNT(*) n FROM hypotheses_112') or {})['n']); b=c.build391.admit_hypothesis_to_kernel(case_id=cid,hypothesis_id=h['hypothesis_id'],identity=a,confirmation=CONFIRM_KERNEL_ADMISSION); after=int((c.db.one('SELECT COUNT(*) n FROM hypotheses_112') or {})['n'])
        assert b['kernel_entry_id'] and before==after and b['legacy_kernel_confidence_used'] is False
        note=c.db.one('SELECT * FROM notebook_109 WHERE entry_id=?',(b['kernel_entry_id'],)); assert note and note['entry_type']=='phase17_hypothesis_candidate'

def test_claim_kernel_bridge_does_not_create_legacy_claim(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _=c.claim_engine_v3_80; cl=reviewed_claim(c,a,cid); before=int((c.db.one('SELECT COUNT(*) n FROM claims_v3_80') or {})['n']); b=c.build391.admit_claim_to_kernel(case_id=cid,claim_id=cl['claim_id'],identity=a,confirmation=CONFIRM_KERNEL_ADMISSION); after=int((c.db.one('SELECT COUNT(*) n FROM claims_v3_80') or {})['n'])
        assert b['kernel_entry_id'] and before==after

def test_kernel_bridge_requires_reviewed_objects(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl=synth_claim(c,a,cid)
        with pytest.raises(PermissionError): c.build391.admit_claim_to_kernel(case_id=cid,claim_id=cl['claim_id'],identity=a,confirmation=CONFIRM_KERNEL_ADMISSION)

def test_synthesis_feed_separates_epistemic_layers_and_questions(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl=reviewed_claim(c,a,cid,True); h=c.build391.propose_hypothesis(case_id=cid,title='Alternative explanation',statement='The contradictory filing reflects a timing difference.',test_plan='Compare filing effective dates and registry timestamps.',claim_relations={cl['claim_id']:'test_target'},identity=a)
        feed=c.build391.ai_investigation_synthesis_feed(case_id=cid,identity=a)
        assert feed['claims'] and feed['hypotheses'] and feed['counterevidence'] and feed['open_questions']; assert feed['epistemic_contract']['claim'].endswith('not a verified fact') and feed['truth_determined'] is False

def test_snapshot_requires_confirmation_and_is_hash_bound(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; reviewed_claim(c,a,cid)
        with pytest.raises(PermissionError): c.build391.create_synthesis_snapshot(case_id=cid,identity=a,confirmation='SNAPSHOT')
        s=c.build391.create_synthesis_snapshot(case_id=cid,identity=a,confirmation=CONFIRM_SNAPSHOT); assert s['snapshot_id'] and len(s['snapshot_hash'])==64

def test_claim_hash_tamper_detected(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl=synth_claim(c,a,cid); assert c.build391.verify_synthesis_claim(case_id=cid,claim_id=cl['claim_id'])['valid']
        c.db.execute("UPDATE investigation_claim_391 SET structural_state='tampered' WHERE claim_id=?",(cl['claim_id'],)); assert c.build391.verify_synthesis_claim(case_id=cid,claim_id=cl['claim_id'])['valid'] is False

def test_hypothesis_hash_tamper_detected(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl=reviewed_claim(c,a,cid); h=c.build391.propose_hypothesis(case_id=cid,title='Explanation',statement='A testable explanation exists here.',test_plan='Test against dated primary records.',claim_relations={cl['claim_id']:'supports_hypothesis'},identity=a); assert c.build391.verify_synthesis_hypothesis(case_id=cid,hypothesis_id=h['hypothesis_id'])['valid']
        c.db.execute("UPDATE investigation_hypothesis_391 SET statement='tampered' WHERE hypothesis_id=?",(h['hypothesis_id'],)); assert c.build391.verify_synthesis_hypothesis(case_id=cid,hypothesis_id=h['hypothesis_id'])['valid'] is False

def test_no_jobs_grants_promotions_or_identity_merge(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _=c.execution_authority_386; _=c.result_intake_389; before=(int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']))
        cl=reviewed_claim(c,a,cid); c.build391.propose_hypothesis(case_id=cid,title='Explanation',statement='A testable explanation exists here.',test_plan='Test against dated primary records.',claim_relations={cl['claim_id']:'supports_hypothesis'},identity=a); after=(int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']))
        assert before==after and c.investigation_synthesis_391.status()['automatic_identity_merge'] is False

def test_web_health_and_auth(tmp_path):
    from eagleeye.interfaces.web.app391 import create_workspace_app391
    app=create_workspace_app391(base_dir=tmp_path)
    try:
        client=TestClient(app); h=client.get('/health'); assert h.status_code==200 and h.json()['build']=='391.0' and h.json()['ai_investigation_synthesis'] is True; assert client.get('/api/build391/phase17-status').status_code==401
    finally: app.state.context.close()

def test_current_launchers_server_point_391():
    root=Path(__file__).resolve().parents[1]; assert 'app391 import create_workspace_app391' in (root/'src/eagleeye/interfaces/web/server.py').read_text(); assert 'EAGLEEYE_PRO_391_0.py' in (root/'START_EAGLEEYE_PRO.bat').read_text(); assert 'EAGLEEYE_PRO_391_0.py' in (root/'START_EAGLEEYE_PRO.sh').read_text()
