from __future__ import annotations
import pytest
from test_build394_integrated import ctx,admin,case,setup,side_counts
from eagleeye_pro.phase17.discussion_revision394 import CONFIRM_REVISION_REVIEW,CONFIRM_APPLY_REVISION
from eagleeye_pro.phase17.case_state_graph395 import CONFIRM_REVIEW,CONFIRM_ADOPT,CONFIRM_ROLLBACK,CONFIRM_BRANCH,CONFIRM_STAGE

def make_claim_version(c,a,cid,cl,d,note='v1'):
    t=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Create a controlled case-state working version.',turn_type='revision_discussion',identity=a)
    p=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='claim',target_id=cl['claim_id'],patch={'analyst_note':note},rationale='Create a reviewed append-only working copy for Build 395 case-state qualification.',source_turn_id=t['turn_id'],identity=a)
    c.build394.review_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve_versioned_revision',rationale='Approved as a working-copy revision only; evidence metrics remain immutable.',confirmation=CONFIRM_REVISION_REVIEW)
    return c.build394.apply_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)

def test_version_schema_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build395.version_status()=={'runtime_build':'395.0','schema_version':'395.0','package_version':'395.0.0','coherent':True}
        s=c.build395.schema_metrics(); assert s['within_phase17_gate'] and s['build395_tables_present'] and s['integrity_check']=='ok'
        st=c.case_state_graph_395.status(); assert st['case_state_version_graph'] and st['controlled_adoption'] and not st['execution_authority']

def test_initial_state_is_origin(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*_=setup(c,a,cid)
        s=c.build395.active_case_state(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
        assert s['generation']==0 and s['active_node_id'].startswith('origin:claim:') and not s['active_version_id'] and not s['execution_authority']

def test_branch_requires_explicit_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*_=setup(c,a,cid)
        with pytest.raises(PermissionError): c.build395.create_case_state_branch(case_id=cid,target_type='claim',target_id=cl['claim_id'],branch_name='Alternative wording',identity=a,confirmation='YES')

def test_branch_staging_does_not_change_active_state(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]; v=make_claim_version(c,a,cid,cl,d)
        before=c.build395.active_case_state(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
        br=c.build395.create_case_state_branch(case_id=cid,target_type='claim',target_id=cl['claim_id'],branch_name='Branch A',identity=a,confirmation=CONFIRM_BRANCH)
        br=c.build395.stage_case_state_branch(case_id=cid,branch_id=br['branch_id'],version_id=v['version_id'],identity=a,confirmation=CONFIRM_STAGE)
        after=c.build395.active_case_state(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
        assert br['head_node_id']==v['version_id'] and before['active_node_id']==after['active_node_id'] and after['generation']==0

def test_controlled_adoption_requires_review_and_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]; v=make_claim_version(c,a,cid,cl,d)
        p=c.build395.propose_case_state_adoption(case_id=cid,target_type='claim',target_id=cl['claim_id'],candidate_version_id=v['version_id'],identity=a,rationale='Adopt the reviewed working version as the active case-state wording.')
        with pytest.raises(PermissionError): c.build395.apply_case_state_adoption(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_ADOPT)
        c.build395.review_case_state_adoption(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve',rationale='Reviewed for case-state adoption only; no execution authority is granted.',confirmation=CONFIRM_REVIEW)
        with pytest.raises(PermissionError): c.build395.apply_case_state_adoption(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation='YES')
        s=c.build395.apply_case_state_adoption(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_ADOPT)
        assert s['active_version_id']==v['version_id'] and s['generation']==1 and not s['execution_authority']

def test_branch_can_seed_adoption(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]; v=make_claim_version(c,a,cid,cl,d)
        br=c.build395.create_case_state_branch(case_id=cid,target_type='claim',target_id=cl['claim_id'],branch_name='Reviewed alternative',identity=a,confirmation=CONFIRM_BRANCH)
        br=c.build395.stage_case_state_branch(case_id=cid,branch_id=br['branch_id'],version_id=v['version_id'],identity=a,confirmation=CONFIRM_STAGE)
        p=c.build395.propose_case_state_adoption(case_id=cid,target_type='claim',target_id=cl['claim_id'],candidate_version_id=v['version_id'],source_branch_id=br['branch_id'],identity=a,rationale='Adopt the explicitly staged branch head after human review.')
        assert p['source_branch_id']==br['branch_id']

def test_stale_adoption_blocked_after_other_transition(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]; v1=make_claim_version(c,a,cid,cl,d,'v1'); v2=make_claim_version(c,a,cid,cl,d,'v2')
        p1=c.build395.propose_case_state_adoption(case_id=cid,target_type='claim',target_id=cl['claim_id'],candidate_version_id=v1['version_id'],identity=a,rationale='First candidate adoption for stale-generation qualification.')
        p2=c.build395.propose_case_state_adoption(case_id=cid,target_type='claim',target_id=cl['claim_id'],candidate_version_id=v2['version_id'],identity=a,rationale='Second candidate created against the same initial active generation.')
        for p in (p1,p2): c.build395.review_case_state_adoption(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve',rationale='Approved for controlled adoption race qualification only.',confirmation=CONFIRM_REVIEW)
        c.build395.apply_case_state_adoption(case_id=cid,proposal_id=p1['proposal_id'],identity=a,confirmation=CONFIRM_ADOPT)
        with pytest.raises(PermissionError): c.build395.apply_case_state_adoption(case_id=cid,proposal_id=p2['proposal_id'],identity=a,confirmation=CONFIRM_ADOPT)

def test_rollback_is_new_transition_not_delete(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]; v=make_claim_version(c,a,cid,cl,d)
        p=c.build395.propose_case_state_adoption(case_id=cid,target_type='claim',target_id=cl['claim_id'],candidate_version_id=v['version_id'],identity=a,rationale='Adopt version before rollback qualification.'); c.build395.review_case_state_adoption(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve',rationale='Approved for rollback qualification sequence only.',confirmation=CONFIRM_REVIEW); c.build395.apply_case_state_adoption(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_ADOPT)
        rb=c.build395.propose_case_state_adoption(case_id=cid,target_type='claim',target_id=cl['claim_id'],candidate_version_id='',proposal_kind='rollback',identity=a,rationale='Rollback active case state to immutable origin while retaining history.'); c.build395.review_case_state_adoption(case_id=cid,proposal_id=rb['proposal_id'],identity=a,disposition='approve',rationale='Approved rollback as a new state transition with preserved history.',confirmation=CONFIRM_REVIEW)
        with pytest.raises(PermissionError): c.build395.apply_case_state_adoption(case_id=cid,proposal_id=rb['proposal_id'],identity=a,confirmation=CONFIRM_ADOPT)
        s=c.build395.apply_case_state_adoption(case_id=cid,proposal_id=rb['proposal_id'],identity=a,confirmation=CONFIRM_ROLLBACK); h=c.build395.case_state_history(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
        assert s['generation']==2 and s['active_node_id'].startswith('origin:claim:') and len(h['transitions'])==2 and h['transitions'][-1]['action']=='rollback'

def test_compare_nodes_has_field_diff_without_truth_score(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]; v=make_claim_version(c,a,cid,cl,d,'changed note')
        x=c.build395.compare_case_state_nodes(case_id=cid,target_type='claim',target_id=cl['claim_id'],left_node_id=f"origin:claim:{cl['claim_id']}",right_node_id=v['version_id'],identity=a)
        assert any(z['field']=='analyst_note' for z in x['changes']) and not x['truth_determined'] and not x['execution_authority']

def test_tampered_version_rejected(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]; v=make_claim_version(c,a,cid,cl,d)
        c.db.execute("UPDATE versioned_revision_394 SET payload_json='{}' WHERE version_id=?",(v['version_id'],))
        with pytest.raises(ValueError): c.build395.propose_case_state_adoption(case_id=cid,target_type='claim',target_id=cl['claim_id'],candidate_version_id=v['version_id'],identity=a,rationale='Tampered candidate must never enter the active case-state graph.')

def test_side_effect_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]; v=make_claim_version(c,a,cid,cl,d); before=side_counts(c)
        br=c.build395.create_case_state_branch(case_id=cid,target_type='claim',target_id=cl['claim_id'],branch_name='No side effects',identity=a,confirmation=CONFIRM_BRANCH); c.build395.stage_case_state_branch(case_id=cid,branch_id=br['branch_id'],version_id=v['version_id'],identity=a,confirmation=CONFIRM_STAGE)
        p=c.build395.propose_case_state_adoption(case_id=cid,target_type='claim',target_id=cl['claim_id'],candidate_version_id=v['version_id'],identity=a,rationale='Case-state adoption must not alter execution or evidence systems.'); c.build395.review_case_state_adoption(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve',rationale='Approved for case-state pointer change only.',confirmation=CONFIRM_REVIEW); c.build395.apply_case_state_adoption(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_ADOPT)
        assert before==side_counts(c)

def test_status_and_gate_shape(tmp_path):
    with ctx(tmp_path) as c:
        st=c.build395.phase17_status(); assert st['build']=='395.0' and st['phase17_builds_completed']==15 and st['case_state_version_graph'] and not st['execution_authority']
        g=c.build395.qualified_gate(); assert g['build']=='395.0' and g['production_release_ready'] is False
