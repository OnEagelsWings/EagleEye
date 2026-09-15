from __future__ import annotations
import pytest
from test_build394_integrated import ctx, admin, case, setup, candidate, reviewed_claim, side_counts
from test_build395_integrated import make_claim_version
from eagleeye_pro.phase17.evidence_review390 import CONFIRM_ASSESS, CONFIRM_FINALIZE
from eagleeye_pro.phase17.case_reconciliation396 import CONFIRM_BASELINE, CONFIRM_REVIEW, CONFIRM_BRANCH, CONFIRM_ADVANCE
from eagleeye_pro.phase17.case_state_graph395 import CONFIRM_REVIEW as CONFIRM_STATE_REVIEW, CONFIRM_ADOPT


def prepare_active(c,a,cid,cl,h1,h2,plan):
    c.build395.active_case_state(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
    c.build395.active_case_state(case_id=cid,target_type='hypothesis',target_id=h1['hypothesis_id'],identity=a)
    c.build395.active_case_state(case_id=cid,target_type='hypothesis',target_id=h2['hypothesis_id'],identity=a)
    if plan:
        c.build395.active_case_state(case_id=cid,target_type='reasoning_plan',target_id=plan['plan_id'],identity=a)


def new_corroboration(c,a,cid,proposition):
    x=candidate(c,cid,'us.federal_register',{'fresh':'signal-a'})
    y=candidate(c,cid,'usaspending.awards',{'fresh':'signal-b'})
    r=c.build390.create_corroboration_review(case_id=cid,proposition=proposition,candidate_stances={x['candidate_id']:'supports',y['candidate_id']:'context'},identity=a)
    c.build390.assess_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,confirmation=CONFIRM_ASSESS)
    c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition='ready_for_evidence_review',confirmation=CONFIRM_FINALIZE)
    return r


def base_case(c,a,cid):
    cl,h1,h2,ws,plan,d393,d394=setup(c,a,cid)
    prepare_active(c,a,cid,cl,h1,h2,plan)
    return cl,h1,h2,ws,plan,d393,d394


def test_version_schema_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build396.version_status()=={'runtime_build':'396.0','schema_version':'396.0','package_version':'396.0.0','coherent':True}
        s=c.build396.schema_metrics(); assert s['within_phase17_gate'] and s['build396_tables_present'] and s['integrity_check']=='ok'
        st=c.case_reconciliation_396.status(); assert st['incremental_reconciliation'] and st['explicit_baseline'] and not st['execution_authority']


def test_baseline_requires_explicit_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; base_case(c,a,cid)
        with pytest.raises(PermissionError): c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation='YES')


def test_baseline_is_explicit_and_integrity_bound(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; base_case(c,a,cid)
        b=c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation=CONFIRM_BASELINE)
        assert b['signal_count']>=1 and c.case_reconciliation_396.verify_baseline(case_id=cid,baseline_id=b['baseline_id'])['valid']


def test_no_change_scan_has_no_impacts(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; base_case(c,a,cid)
        b=c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation=CONFIRM_BASELINE)
        s=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a)
        assert s['delta_signal_count']==0 and s['impact_count']==0 and s['scan_state']=='no_change'


def test_new_exact_corroboration_impacts_claim_hypothesis_and_plan(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,h1,h2,ws,plan,*_=base_case(c,a,cid)
        b=c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation=CONFIRM_BASELINE)
        new_corroboration(c,a,cid,cl['proposition'])
        s=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a)
        targets={(x['target_type'],x['target_id']) for x in s['impacts']}
        assert ('claim',cl['claim_id']) in targets and ('hypothesis',h1['hypothesis_id']) in targets and ('hypothesis',h2['hypothesis_id']) in targets
        assert any(t=='reasoning_plan' for t,_ in targets)


def test_unmatched_candidate_is_review_material_not_forced_match(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; base_case(c,a,cid)
        b=c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation=CONFIRM_BASELINE)
        candidate(c,cid,'internet_archive.metadata',{'completely':'unrelated material'})
        s=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a)
        x=next(z for z in s['signals'] if z['signal_type']=='evidence_candidate')
        assert x['match_state']=='unmatched_review_material' and not x['matched_target_ids']


def test_exact_candidate_proposition_can_match_conservatively(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*_=base_case(c,a,cid)
        b=c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation=CONFIRM_BASELINE)
        candidate(c,cid,'eu.ted',{'proposition':cl['proposition']})
        s=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a)
        assert any(x['target_type']=='claim' and x['target_id']==cl['claim_id'] for x in s['impacts'])


def test_reanalysis_proposal_requires_impact(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*_=base_case(c,a,cid)
        b=c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation=CONFIRM_BASELINE)
        s=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a)
        with pytest.raises(ValueError): c.build396.propose_reanalysis(case_id=cid,scan_id=s['scan_id'],target_type='claim',target_id=cl['claim_id'],identity=a,rationale='No impact exists, so this proposal must fail closed.')


def test_reviewed_proposal_can_create_branch_but_not_adopt(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*_=base_case(c,a,cid)
        before=c.build395.active_case_state(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
        b=c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation=CONFIRM_BASELINE); new_corroboration(c,a,cid,cl['proposition']); s=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a)
        p=c.build396.propose_reanalysis(case_id=cid,scan_id=s['scan_id'],target_type='claim',target_id=cl['claim_id'],identity=a,rationale='New finalized corroboration changes the review context for the active claim.')
        with pytest.raises(PermissionError): c.build396.create_reanalysis_branch(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_BRANCH)
        c.build396.review_reanalysis(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve',rationale='Re-analysis is warranted; branch creation must not adopt or mutate active state.',confirmation=CONFIRM_REVIEW)
        br=c.build396.create_reanalysis_branch(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_BRANCH)
        after=c.build395.active_case_state(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
        assert br['branch_id'] and not br['adopted'] and before['active_node_id']==after['active_node_id'] and before['generation']==after['generation']


def test_stale_generation_blocks_branch_creation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=base_case(c,a,cid); d=rest[-1]
        b=c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation=CONFIRM_BASELINE); new_corroboration(c,a,cid,cl['proposition']); s=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a)
        p=c.build396.propose_reanalysis(case_id=cid,scan_id=s['scan_id'],target_type='claim',target_id=cl['claim_id'],identity=a,rationale='Capture re-analysis against the current claim generation before a concurrent state transition.')
        c.build396.review_reanalysis(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve',rationale='Approved only for stale-generation branch qualification.',confirmation=CONFIRM_REVIEW)
        v=make_claim_version(c,a,cid,cl,d,'new active generation')
        ap=c.build395.propose_case_state_adoption(case_id=cid,target_type='claim',target_id=cl['claim_id'],candidate_version_id=v['version_id'],identity=a,rationale='Advance active state to force re-analysis proposal staleness.')
        c.build395.review_case_state_adoption(case_id=cid,proposal_id=ap['proposal_id'],identity=a,disposition='approve',rationale='Approved solely to test stale-generation protection.',confirmation=CONFIRM_STATE_REVIEW)
        c.build395.apply_case_state_adoption(case_id=cid,proposal_id=ap['proposal_id'],identity=a,confirmation=CONFIRM_ADOPT)
        with pytest.raises(PermissionError): c.build396.create_reanalysis_branch(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_BRANCH)


def test_advance_baseline_consumes_current_signal_inventory(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*_=base_case(c,a,cid)
        b=c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation=CONFIRM_BASELINE); new_corroboration(c,a,cid,cl['proposition']); s=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a)
        b2=c.build396.advance_reconciliation_baseline(case_id=cid,scan_id=s['scan_id'],identity=a,confirmation=CONFIRM_ADVANCE)
        s2=c.build396.reconcile_case_state(case_id=cid,baseline_id=b2['baseline_id'],identity=a)
        assert b2['previous_baseline_id']==b['baseline_id'] and s2['delta_signal_count']==0


def test_tampered_baseline_detected(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; base_case(c,a,cid)
        b=c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation=CONFIRM_BASELINE)
        c.db.execute("UPDATE reconciliation_baseline_396 SET baseline_hash='tampered' WHERE baseline_id=?",(b['baseline_id'],))
        assert not c.case_reconciliation_396.verify_baseline(case_id=cid,baseline_id=b['baseline_id'])['valid']


def test_tampered_scan_detected(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; base_case(c,a,cid)
        b=c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation=CONFIRM_BASELINE); s=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a)
        c.db.execute("UPDATE reconciliation_scan_396 SET scan_state='tampered' WHERE scan_id=?",(s['scan_id'],))
        assert not c.case_reconciliation_396.verify_scan(case_id=cid,scan_id=s['scan_id'])['valid']


def test_side_effect_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*_=base_case(c,a,cid); before=side_counts(c)
        b=c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation=CONFIRM_BASELINE); new_corroboration(c,a,cid,cl['proposition']); s=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a)
        p=c.build396.propose_reanalysis(case_id=cid,scan_id=s['scan_id'],target_type='claim',target_id=cl['claim_id'],identity=a,rationale='Local re-analysis must remain isolated from execution and evidence-promotion systems.')
        c.build396.review_reanalysis(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve',rationale='Approved for a local working branch only; no collection or evidence action.',confirmation=CONFIRM_REVIEW)
        c.build396.create_reanalysis_branch(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_BRANCH)
        assert before==side_counts(c)


def test_status_and_gate_shape(tmp_path):
    with ctx(tmp_path) as c:
        st=c.build396.phase17_status(); assert st['build']=='396.0' and st['phase17_builds_completed']==16 and st['incremental_reconciliation'] and not st['execution_authority']
        g=c.build396.qualified_gate(); assert g['build']=='396.0' and g['production_release_ready'] is False
