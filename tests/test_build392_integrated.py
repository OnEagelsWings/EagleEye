from __future__ import annotations
import hashlib, json, secrets
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.evidence_review390 import CONFIRM_ASSESS, CONFIRM_FINALIZE
from eagleeye_pro.phase17.investigation_synthesis391 import CONFIRM_CLAIM_REVIEW, CONFIRM_HYPOTHESIS_REVIEW
from eagleeye_pro.phase17.case_reasoning392 import CONFIRM_PLAN_REVIEW, CONFIRM_KERNEL_ADMISSION
from eagleeye.interfaces.web.app392 import create_workspace_app392

PW='Build392-Secure-Orbit-Z9!'

def ctx(tmp_path): return AppContext(base_dir=tmp_path,actor='test392')
def admin(c):
    a=c.team_identity_359.create_initial_admin(username='admin392',display_name='Lead Analyst',password=PW); return {**a,'session_id':'test392'}
def case(c,a): return c.build380.team_create_case(identity=a,title='Build392 test',client='internal',purpose='authorized reasoning qualification',legal_basis='public_data')

def candidate(c,cid,source='gleif.lei',norm=None):
    norm=norm or {'name':'Example GmbH','status':'ACTIVE'}; raw=json.dumps({'s':source,'n':norm},sort_keys=True).encode(); oid='obj392_'+secrets.token_hex(8); sha=hashlib.sha256(raw).hexdigest(); now='2026-09-13T16:30:00+00:00'
    c.db.execute("INSERT INTO phase15_objects(object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,cid,'','canon_'+source,'local',oid,sha,len(raw),'application/json','review_pending','{}','test392',now,hashlib.sha256(raw+b'r').hexdigest()))
    obj={'object_id':oid,'sha256':sha,'media_type':'application/json','security_state':'review_pending'}; result={'wave_number':1,'phase17_source_id':source,'canonical_source_id':'canon_'+source,'dispatch_id':'d'+oid,'job_id':'j'+oid,'crawl_run_id':'c'+oid,'search_run_id':'s'+oid}
    out,_=c.result_intake_389._insert_candidate(case_id=cid,session_id='sess392',result_row=result,obj=obj,parse_run_id='p'+oid,record_index=0,candidate_type='normalized_record',normalized=norm,provenance={}); return out

def finalized_review(c,a,cid,*,contradiction=False,single=False):
    g=candidate(c,cid,'gleif.lei',{'name':'Example GmbH','status':'ACTIVE'}); mapping={g['candidate_id']:'supports'}
    if not single:
        s=candidate(c,cid,'sec.edgar',{'name':'Example GmbH','status':'INACTIVE' if contradiction else 'ACTIVE'}); mapping[s['candidate_id']]='contradicts' if contradiction else 'supports'
    r=c.build390.create_corroboration_review(case_id=cid,proposition='Example GmbH is active',candidate_stances=mapping,identity=a)
    c.build390.assess_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,confirmation=CONFIRM_ASSESS)
    disp='contested_requires_analysis' if contradiction else 'ready_for_evidence_review'
    c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition=disp,confirmation=CONFIRM_FINALIZE)
    return r['review_id']

def reviewed_claim(c,a,cid,*,contradiction=False,single=False,disposition=None):
    rid=finalized_review(c,a,cid,contradiction=contradiction,single=single); cl=c.build391.synthesize_corroboration_review(case_id=cid,review_id=rid,identity=a)
    disp=disposition or ('contested_requires_analysis' if contradiction else 'ready_for_hypothesis_work')
    return c.build391.review_synthesis_claim(case_id=cid,claim_id=cl['claim_id'],identity=a,disposition=disp,rationale='Reviewed provenance, source independence, counterevidence and analytical limitations.',confirmation=CONFIRM_CLAIM_REVIEW)

def reviewed_hypothesis(c,a,cid,cl):
    h=c.build391.propose_hypothesis(case_id=cid,title='Status timing explanation',statement='Different observations may reflect different effective dates.',test_plan='Compare dated filings, registry history and effective dates.',claim_relations={cl['claim_id']:'test_target'},identity=a)
    return c.build391.review_synthesis_hypothesis(case_id=cid,hypothesis_id=h['hypothesis_id'],identity=a,disposition='retain_for_testing',rationale='The explanation is testable and remains explicitly hypothetical.',confirmation=CONFIRM_HYPOTHESIS_REVIEW)

def make_workspace(c,a,cid,*,contradiction=False,single=False,with_hyp=True):
    cl=reviewed_claim(c,a,cid,contradiction=contradiction,single=single)
    h=reviewed_hypothesis(c,a,cid,cl) if with_hyp else None
    ws=c.build392.create_case_reasoning_workspace(case_id=cid,identity=a)
    return cl,h,ws

def counts(c):
    return {
        'jobs':int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),
        'grants':int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),
        'promotions':int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']),
        'legacy_hypotheses':int((c.db.one('SELECT COUNT(*) n FROM hypotheses_112') or {})['n']),
    }

def test_version_schema_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build392.version_status()=={'runtime_build':'392.0','schema_version':'392.0','package_version':'392.0.0','coherent':True}
        s=c.build392.schema_metrics(); assert s['within_phase17_gate'] and s['build392_tables_present']
        st=c.case_reasoning_392.status(); assert st['case_reasoning_workspace'] and st['argument_graph'] and not st['truth_probability'] and not st['execution_authority']

def test_workspace_preserves_epistemic_layers_and_counterevidence(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,h,ws=make_workspace(c,a,cid,contradiction=True)
        assert ws['truth_determined'] is False and ws['probability_assigned'] is False
        assert ws['reasoning_state']=='contested_analysis_required'
        assert any(i['issue_type']=='counterevidence_conflict' for i in ws['issues'])
        assert ws['source_snapshot']['epistemic_contract']['claim'].startswith('Build-391')

def test_workspace_is_idempotent_for_same_snapshots(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,w1=make_workspace(c,a,cid); w2=c.build392.create_case_reasoning_workspace(case_id=cid,identity=a)
        assert w1['workspace_id']==w2['workspace_id'] and w1['record_hash']==w2['record_hash']

def test_argument_graph_links_evidence_claim_and_claim_hypothesis(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,h,ws=make_workspace(c,a,cid,contradiction=True)
        assert any(x['from_type']=='evidence_candidate' and x['to_id']==cl['claim_id'] and x['relation']=='contradicts' for x in ws['arguments'])
        assert any(x['from_type']=='claim' and x['from_id']==cl['claim_id'] and x['to_id']==h['hypothesis_id'] for x in ws['arguments'])

def test_single_group_support_creates_independent_support_gap(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws=make_workspace(c,a,cid,single=True,with_hyp=False)
        assert any(i['issue_type']=='independent_support_gap' for i in ws['issues'])

def test_failed_coverage_observation_is_preserved_as_research_gap(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl=reviewed_claim(c,a,cid); c.phase17_runtime_384.repository.record_coverage(case_id=cid,source_id='gleif.lei',state='failed',evidence_ref='worker:test392',detail='simulated connector failure')
        ws=c.build392.create_case_reasoning_workspace(case_id=cid,identity=a)
        assert any(i['issue_type']=='research_gap' and 'failed_or_blocked' in i['title'] for i in ws['issues'])
        assert ws['coverage_snapshot']['no_result_is_nonexistence'] is False

def test_plan_proposal_has_no_execution_authority(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws=make_workspace(c,a,cid,single=True); before=counts(c); p=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a); after=counts(c)
        assert p['plan_status']=='proposal_needs_review' and p['execution_authority'] is False and p['automatic_go_issuance'] is False
        assert any(x['requires_go'] for x in p['actions']) and all(not x['execution_authority'] for x in p['actions'])
        assert before==after

def test_plan_priority_orders_high_before_medium(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws=make_workspace(c,a,cid,contradiction=True); p=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a)
        ranks={'critical':0,'high':1,'medium':2,'low':3}; seq=[ranks[x['priority']] for x in p['actions']]; assert seq==sorted(seq)

def test_plan_review_requires_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws=make_workspace(c,a,cid); p=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a)
        with pytest.raises(PermissionError): c.build392.review_reasoning_plan(case_id=cid,plan_id=p['plan_id'],identity=a,disposition='approve_for_investigator_review',rationale='Reviewed priorities and boundaries carefully.',confirmation='REVIEW')

def test_reviewed_plan_still_has_no_go_or_execution_authority(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws=make_workspace(c,a,cid,single=True); p=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a); before=counts(c)
        p=c.build392.review_reasoning_plan(case_id=cid,plan_id=p['plan_id'],identity=a,disposition='approve_for_investigator_review',rationale='Reviewed evidence gaps, priorities and authorization boundaries.',confirmation=CONFIRM_PLAN_REVIEW); after=counts(c)
        assert p['plan_status']=='reviewed_plan' and p['analyst_disposition']=='approve_for_investigator_review' and not p['execution_authority']; assert before==after

def test_kernel_bridge_requires_reviewed_plan(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws=make_workspace(c,a,cid); p=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a)
        with pytest.raises(PermissionError): c.build392.admit_reasoning_plan_to_kernel(case_id=cid,plan_id=p['plan_id'],identity=a,confirmation=CONFIRM_KERNEL_ADMISSION)

def test_kernel_bridge_uses_notebook_not_legacy_probability_path(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws=make_workspace(c,a,cid); p=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a); p=c.build392.review_reasoning_plan(case_id=cid,plan_id=p['plan_id'],identity=a,disposition='approve_for_investigator_review',rationale='Reviewed reasoning plan and retained human execution boundaries.',confirmation=CONFIRM_PLAN_REVIEW); before=counts(c)
        kb=c.build392.admit_reasoning_plan_to_kernel(case_id=cid,plan_id=p['plan_id'],identity=a,confirmation=CONFIRM_KERNEL_ADMISSION); after=counts(c)
        assert kb['kernel_entry_id'] and kb['execution_authority'] is False and kb['automatic_go_issuance'] is False; assert before['legacy_hypotheses']==after['legacy_hypotheses']

def test_workspace_becomes_stale_when_synthesis_changes(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws=make_workspace(c,a,cid,with_hyp=False); assert not c.build392.verify_case_reasoning_workspace(case_id=cid,workspace_id=ws['workspace_id'])['stale']
        _=reviewed_claim(c,a,cid,single=True)
        assert c.build392.verify_case_reasoning_workspace(case_id=cid,workspace_id=ws['workspace_id'])['stale']

def test_workspace_integrity_detects_tamper(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws=make_workspace(c,a,cid); iid=ws['issues'][0]['issue_id']; c.db.execute("UPDATE reasoning_issue_392 SET rationale='tampered' WHERE issue_id=?",(iid,))
        assert not c.build392.verify_case_reasoning_workspace(case_id=cid,workspace_id=ws['workspace_id'])['valid']

def test_plan_integrity_detects_tamper(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws=make_workspace(c,a,cid); p=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a); aid=p['actions'][0]['action_id']; c.db.execute("UPDATE reasoning_plan_action_392 SET title='tampered' WHERE action_id=?",(aid,))
        assert not c.build392.verify_reasoning_plan(case_id=cid,plan_id=p['plan_id'])['valid']

def test_ai_reasoning_feed_preserves_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws=make_workspace(c,a,cid); _=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a); f=c.build392.ai_case_reasoning_feed(case_id=cid,identity=a)
        assert f['argumentative_reasoning'] and f['counterevidence_preserved'] and f['epistemic_layers_preserved']; assert not f['truth_determined'] and not f['probability_assigned'] and not f['execution_authority'] and not f['automatic_go_issuance']

def test_no_automatic_side_effects_across_reasoning_flow(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl=reviewed_claim(c,a,cid,single=True); before=counts(c); ws=c.build392.create_case_reasoning_workspace(case_id=cid,identity=a); p=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a); p=c.build392.review_reasoning_plan(case_id=cid,plan_id=p['plan_id'],identity=a,disposition='approve_for_investigator_review',rationale='Reviewed the plan without authorizing external execution.',confirmation=CONFIRM_PLAN_REVIEW); after=counts(c)
        assert before==after

def test_workspace_no_probability_or_confidence_fields(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws=make_workspace(c,a,cid); raw=json.dumps(ws,sort_keys=True).lower(); assert 'truth_probability' not in raw and '"confidence"' not in raw and '"prior"' not in raw

def test_plan_is_idempotent_per_workspace(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,_,ws=make_workspace(c,a,cid); p1=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a); p2=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a); assert p1['plan_id']==p2['plan_id'] and p1['plan_hash']==p2['plan_hash']

def test_web_health_reports_392(tmp_path):
    app=create_workspace_app392(base_dir=tmp_path)
    try:
        client=TestClient(app); r=client.get('/health'); assert r.status_code==200; body=r.json(); assert body['build']=='392.0' and body['case_reasoning_workspace'] and body['execution_authority'] is False
    finally:
        app.state.context.close()

def test_gate_truthful_flags(tmp_path):
    with ctx(tmp_path) as c:
        st=c.case_reasoning_392.status(); assert st['human_plan_review_required'] and not st['automatic_go_issuance'] and not st['direct_network_fetch'] and not st['automatic_identity_merge'] and not st['automatic_evidence_promotion']


def test_current_launchers_server_point_392():
    root=Path(__file__).resolve().parents[1]; server=(root/'src/eagleeye/interfaces/web/server.py').read_text(encoding='utf-8'); assert 'app392 import create_workspace_app392' in server; assert 'EAGLEEYE_PRO_392_0.py' in (root/'START_EAGLEEYE_PRO.bat').read_text(encoding='utf-8'); assert 'EAGLEEYE_PRO_392_0.py' in (root/'START_EAGLEEYE_PRO.sh').read_text(encoding='utf-8')
