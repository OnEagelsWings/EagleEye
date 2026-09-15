from __future__ import annotations
import hashlib, json, secrets
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.evidence_review390 import CONFIRM_ASSESS, CONFIRM_FINALIZE
from eagleeye_pro.phase17.investigation_synthesis391 import CONFIRM_CLAIM_REVIEW, CONFIRM_HYPOTHESIS_REVIEW
from eagleeye_pro.phase17.investigator_dialogue393 import CONFIRM_PROPOSAL_REVIEW, CONFIRM_KERNEL_ADMISSION
from eagleeye.interfaces.web.app393 import create_workspace_app393

PW='Build393-Secure-Vector-Z9!'

def ctx(tmp_path): return AppContext(base_dir=tmp_path,actor='test393')
def admin(c):
    a=c.team_identity_359.create_initial_admin(username='admin393',display_name='Lead Investigator',password=PW); return {**a,'session_id':'test393'}
def case(c,a): return c.build380.team_create_case(identity=a,title='Build393 test',client='internal',purpose='authorized challenge-engine qualification',legal_basis='public_data')

def candidate(c,cid,source='gleif.lei',norm=None):
    norm=norm or {'name':'Example GmbH','status':'ACTIVE'}; raw=json.dumps({'s':source,'n':norm},sort_keys=True).encode(); oid='obj393_'+secrets.token_hex(8); sha=hashlib.sha256(raw).hexdigest(); now='2026-09-13T17:35:00+00:00'
    c.db.execute("INSERT INTO phase15_objects(object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,cid,'','canon_'+source,'local',oid,sha,len(raw),'application/json','review_pending','{}','test393',now,hashlib.sha256(raw+b'r').hexdigest()))
    obj={'object_id':oid,'sha256':sha,'media_type':'application/json','security_state':'review_pending'}; result={'wave_number':1,'phase17_source_id':source,'canonical_source_id':'canon_'+source,'dispatch_id':'d'+oid,'job_id':'j'+oid,'crawl_run_id':'c'+oid,'search_run_id':'s'+oid}
    out,_=c.result_intake_389._insert_candidate(case_id=cid,session_id='sess393',result_row=result,obj=obj,parse_run_id='p'+oid,record_index=0,candidate_type='normalized_record',normalized=norm,provenance={}); return out

def finalized_review(c,a,cid,*,contradiction=False,single=False):
    g=candidate(c,cid,'gleif.lei',{'name':'Example GmbH','status':'ACTIVE'}); mapping={g['candidate_id']:'supports'}
    if not single:
        s=candidate(c,cid,'sec.edgar',{'name':'Example GmbH','status':'INACTIVE' if contradiction else 'ACTIVE'}); mapping[s['candidate_id']]='contradicts' if contradiction else 'supports'
    r=c.build390.create_corroboration_review(case_id=cid,proposition='Example GmbH is active',candidate_stances=mapping,identity=a)
    c.build390.assess_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,confirmation=CONFIRM_ASSESS)
    disp='contested_requires_analysis' if contradiction else 'ready_for_evidence_review'
    c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition=disp,confirmation=CONFIRM_FINALIZE)
    return r['review_id']

def reviewed_claim(c,a,cid,*,contradiction=False,single=False):
    rid=finalized_review(c,a,cid,contradiction=contradiction,single=single); cl=c.build391.synthesize_corroboration_review(case_id=cid,review_id=rid,identity=a)
    disp='contested_requires_analysis' if contradiction else 'ready_for_hypothesis_work'
    return c.build391.review_synthesis_claim(case_id=cid,claim_id=cl['claim_id'],identity=a,disposition=disp,rationale='Reviewed provenance, independence, counterevidence and analytical boundaries.',confirmation=CONFIRM_CLAIM_REVIEW)

def reviewed_hypothesis(c,a,cid,cl):
    h=c.build391.propose_hypothesis(case_id=cid,title='Status timing explanation',statement='Different observations may reflect different effective dates.',test_plan='Compare dated filings, registry history and effective dates.',claim_relations={cl['claim_id']:'test_target'},identity=a)
    return c.build391.review_synthesis_hypothesis(case_id=cid,hypothesis_id=h['hypothesis_id'],identity=a,disposition='retain_for_testing',rationale='Testable explanation retained as hypothesis_not_fact.',confirmation=CONFIRM_HYPOTHESIS_REVIEW)

def setup_dialogue(c,a,cid,*,contradiction=True,single=False,make_plan=False):
    cl=reviewed_claim(c,a,cid,contradiction=contradiction,single=single); h=reviewed_hypothesis(c,a,cid,cl); ws=c.build392.create_case_reasoning_workspace(case_id=cid,identity=a)
    plan=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a) if make_plan else None
    s=c.build393.create_investigator_dialogue(case_id=cid,workspace_id=ws['workspace_id'],identity=a)
    return cl,h,ws,plan,s

def upstream_counts(c):
    return {
        'jobs':int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),
        'grants':int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),
        'promotions':int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']),
        'legacy_hypotheses':int((c.db.one('SELECT COUNT(*) n FROM hypotheses_112') or {})['n']),
        'claims':int((c.db.one('SELECT COUNT(*) n FROM investigation_claim_391') or {})['n']),
        'hypotheses391':int((c.db.one('SELECT COUNT(*) n FROM investigation_hypothesis_391') or {})['n']),
        'plans392':int((c.db.one('SELECT COUNT(*) n FROM reasoning_plan_392') or {})['n']),
    }

def test_version_schema_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build393.version_status()=={'runtime_build':'393.0','schema_version':'393.0','package_version':'393.0.0','coherent':True}
        s=c.build393.schema_metrics(); assert s['within_phase17_gate'] and s['build393_tables_present']
        st=c.investigator_dialogue_393.status(); assert st['investigator_dialogue'] and st['challenge_engine'] and not st['truth_probability'] and not st['execution_authority']

def test_dialogue_session_idempotent(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws,_,s1=setup_dialogue(c,a,cid); s2=c.build393.create_investigator_dialogue(case_id=cid,workspace_id=ws['workspace_id'],identity=a); assert s1['session_id']==s2['session_id']

def test_stale_workspace_rejected_for_new_dialogue(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws,_,_=setup_dialogue(c,a,cid); _=reviewed_claim(c,a,cid,single=True)
        with pytest.raises(ValueError): c.investigator_dialogue_393.create_session(case_id=cid,workspace_id=ws['workspace_id'],identity=a)

def test_free_text_auto_routes_weakest_assumption(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,_,_,s=setup_dialogue(c,a,cid); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Welche Annahme ist hier am schwächsten?',identity=a); assert t['challenge_mode']=='weakest_assumption' and t['response']['challenge_points']

def test_counter_argument_targets_hypothesis(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,h,_,_,s=setup_dialogue(c,a,cid); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Argumentiere gegen diese Hypothese.',mode='counter_argument',target_type='hypothesis',target_id=h['hypothesis_id'],identity=a); assert t['target_id']==h['hypothesis_id'] and t['response']['questions']

def test_falsification_preserves_existing_test_plan(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,h,_,_,s=setup_dialogue(c,a,cid); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Was würde diese Hypothese falsifizieren?',mode='falsification_test',target_type='hypothesis',target_id=h['hypothesis_id'],identity=a); assert any('filings' in p['rationale'] for p in t['response']['challenge_points']); assert any(p['proposal_type']=='hypothesis_test_revision' for p in t['proposals'])

def test_blind_spot_surfaces_gaps(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,_,_,s=setup_dialogue(c,a,cid,single=True); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Was übersehen wir?',mode='blind_spot',identity=a); assert any(p['category']=='blind_spot_signal' for p in t['response']['challenge_points'])

def test_alternative_explanation_creates_prompt_not_fact(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,h,_,_,s=setup_dialogue(c,a,cid); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Welche alternative Erklärung ist denkbar?',mode='alternative_explanation',target_type='hypothesis',target_id=h['hypothesis_id'],identity=a); p=t['proposals'][0]; assert p['proposal_type']=='alternative_hypothesis_prompt' and p['status']=='proposal_needs_review' and not p['execution_authority']

def test_source_independence_attack_preserves_unresolved_as_gap(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,_,_,s=setup_dialogue(c,a,cid,single=True); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Prüfe die Quellenunabhängigkeit.',mode='source_independence_attack',identity=a); assert any('Independence' in x['statement'] or 'independent' in x['rationale'] for x in t['response']['challenge_points'])

def test_plan_red_team_uses_existing_plan_and_keeps_go_boundary(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,_,plan,s=setup_dialogue(c,a,cid,single=True,make_plan=True); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Red-team den nächsten Plan.',mode='plan_red_team',target_type='reasoning_plan',target_id=plan['plan_id'],identity=a); assert t['response']['challenge_points'] and not t['response']['execution_authority'] and not t['response']['automatic_go_issuance']

def test_invalid_target_is_rejected(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,_,_,s=setup_dialogue(c,a,cid)
        with pytest.raises(ValueError): c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Challenge this.',target_type='hypothesis',target_id='missing',identity=a)

def test_revision_review_requires_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,_,_,s=setup_dialogue(c,a,cid); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Was ist schwach?',mode='weakest_assumption',identity=a); pid=t['proposals'][0]['proposal_id']
        with pytest.raises(PermissionError): c.build393.review_challenge_proposal(case_id=cid,proposal_id=pid,identity=a,disposition='approve_for_manual_revision',rationale='Reviewed challenge proposal carefully.',confirmation='REVIEW')

def test_reviewed_revision_does_not_mutate_upstream(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,_,_,s=setup_dialogue(c,a,cid); before=upstream_counts(c); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Was ist schwach?',mode='weakest_assumption',identity=a); pid=t['proposals'][0]['proposal_id']; p=c.build393.review_challenge_proposal(case_id=cid,proposal_id=pid,identity=a,disposition='approve_for_manual_revision',rationale='Reviewed challenge proposal; upstream changes remain manual.',confirmation=CONFIRM_PROPOSAL_REVIEW); after=upstream_counts(c); assert p['status']=='reviewed_for_manual_revision' and before==after

def test_kernel_admission_requires_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,_,_,s=setup_dialogue(c,a,cid); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Challenge current reasoning.',identity=a)
        with pytest.raises(PermissionError): c.build393.admit_challenge_to_kernel(case_id=cid,turn_id=t['turn_id'],identity=a,confirmation='ADMIT')

def test_kernel_bridge_is_not_probability_or_execution_path(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,_,_,s=setup_dialogue(c,a,cid); before=upstream_counts(c); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Challenge current reasoning.',identity=a); kb=c.build393.admit_challenge_to_kernel(case_id=cid,turn_id=t['turn_id'],identity=a,confirmation=CONFIRM_KERNEL_ADMISSION); after=upstream_counts(c); assert kb['kernel_entry_id'] and not kb['execution_authority'] and before['legacy_hypotheses']==after['legacy_hypotheses'] and before['jobs']==after['jobs']

def test_turn_integrity_detects_tamper(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,_,_,s=setup_dialogue(c,a,cid); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Challenge current reasoning.',identity=a); c.db.execute("UPDATE investigator_dialogue_turn_393 SET prompt_text='tampered' WHERE turn_id=?",(t['turn_id'],)); assert not c.build393.verify_challenge_turn(case_id=cid,turn_id=t['turn_id'])['valid']

def test_proposal_integrity_detects_tamper(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,_,_,s=setup_dialogue(c,a,cid); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Challenge current reasoning.',identity=a); pid=t['proposals'][0]['proposal_id']; c.db.execute("UPDATE challenge_revision_proposal_393 SET title='tampered' WHERE proposal_id=?",(pid,)); assert not c.build393.verify_challenge_proposal(case_id=cid,proposal_id=pid)['valid']

def test_dialogue_feed_preserves_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,_,_,s=setup_dialogue(c,a,cid); _=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Was übersehen wir?',identity=a); f=c.build393.ai_investigator_dialogue_feed(case_id=cid,identity=a); assert f['dialogue_is_review_aid'] and f['counterevidence_preserved'] and not f['truth_determined'] and not f['probability_assigned'] and not f['automatic_upstream_mutation'] and not f['execution_authority']

def test_no_automatic_side_effects_across_dialogue_flow(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,_,_,s=setup_dialogue(c,a,cid); before=upstream_counts(c); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Argumentiere gegen die aktuelle Lage.',mode='counter_argument',identity=a); pid=t['proposals'][0]['proposal_id']; c.build393.review_challenge_proposal(case_id=cid,proposal_id=pid,identity=a,disposition='approve_for_manual_revision',rationale='Approved as manual revision task only.',confirmation=CONFIRM_PROPOSAL_REVIEW); after=upstream_counts(c); assert before==after

def test_response_contains_no_probability_or_confidence_fields(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,_,_,s=setup_dialogue(c,a,cid); t=c.build393.challenge_reasoning(case_id=cid,session_id=s['session_id'],prompt='Challenge current reasoning.',identity=a); raw=json.dumps(t['response'],sort_keys=True).lower(); assert 'truth_probability' not in raw and '"confidence"' not in raw and '"prior"' not in raw

def test_web_health_reports_393(tmp_path):
    app=create_workspace_app393(base_dir=tmp_path)
    try:
        client=TestClient(app); r=client.get('/health'); assert r.status_code==200; b=r.json(); assert b['build']=='393.0' and b['investigator_dialogue'] and b['challenge_engine'] and b['execution_authority'] is False
    finally:
        app.state.context.close()

def test_gate_truthful_flags(tmp_path):
    with ctx(tmp_path) as c:
        st=c.investigator_dialogue_393.status(); assert st['human_revision_review_required'] and not st['automatic_upstream_mutation'] and not st['automatic_go_issuance'] and not st['direct_network_fetch'] and not st['automatic_evidence_promotion']

def test_current_launchers_server_point_393():
    root=Path(__file__).resolve().parents[1]; server=(root/'src/eagleeye/interfaces/web/server.py').read_text(encoding='utf-8'); assert 'app393 import create_workspace_app393' in server; assert 'EAGLEEYE_PRO_393_0.py' in (root/'START_EAGLEEYE_PRO.bat').read_text(encoding='utf-8'); assert 'EAGLEEYE_PRO_393_0.py' in (root/'START_EAGLEEYE_PRO.sh').read_text(encoding='utf-8')
