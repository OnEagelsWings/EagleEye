from __future__ import annotations
import hashlib, json, secrets
import pytest
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.evidence_review390 import CONFIRM_ASSESS, CONFIRM_FINALIZE
from eagleeye_pro.phase17.investigation_synthesis391 import CONFIRM_CLAIM_REVIEW, CONFIRM_HYPOTHESIS_REVIEW
from eagleeye_pro.phase17.discussion_revision394 import CONFIRM_REVISION_REVIEW, CONFIRM_APPLY_REVISION, CONFIRM_KERNEL_ADMISSION
from eagleeye_pro.phase17.investigator_dialogue393 import CONFIRM_PROPOSAL_REVIEW

PW='Build394-Secure-Vector-Z9!'

def ctx(tmp_path): return AppContext(base_dir=tmp_path, actor='test394')
def admin(c):
    a=c.team_identity_359.create_initial_admin(username='admin394',display_name='Lead Investigator',password=PW)
    return {**a,'session_id':'test394'}
def case(c,a): return c.build380.team_create_case(identity=a,title='Build394 test',client='internal',purpose='authorized discussion and revision qualification',legal_basis='public_data')

def candidate(c,cid,source,norm):
    raw=json.dumps({'s':source,'n':norm},sort_keys=True).encode(); oid='obj394_'+secrets.token_hex(8); sha=hashlib.sha256(raw).hexdigest(); now='2026-09-13T21:45:00+00:00'
    c.db.execute("INSERT INTO phase15_objects(object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,cid,'','canon_'+source,'local',oid,sha,len(raw),'application/json','review_pending','{}','test394',now,hashlib.sha256(raw+b'r').hexdigest()))
    obj={'object_id':oid,'sha256':sha,'media_type':'application/json','security_state':'review_pending'}
    rr={'wave_number':1,'phase17_source_id':source,'canonical_source_id':'canon_'+source,'dispatch_id':'d'+oid,'job_id':'j'+oid,'crawl_run_id':'c'+oid,'search_run_id':'s'+oid}
    out,_=c.result_intake_389._insert_candidate(case_id=cid,session_id='sess394',result_row=rr,obj=obj,parse_run_id='p'+oid,record_index=0,candidate_type='normalized_record',normalized=norm,provenance={})
    return out

def reviewed_claim(c,a,cid,proposition='Example GmbH status is disputed'):
    g=candidate(c,cid,'gleif.lei',{'name':'Example GmbH','status':'ACTIVE'})
    s=candidate(c,cid,'sec.edgar',{'name':'Example GmbH','status':'INACTIVE'})
    r=c.build390.create_corroboration_review(case_id=cid,proposition=proposition,candidate_stances={g['candidate_id']:'supports',s['candidate_id']:'contradicts'},identity=a)
    c.build390.assess_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,confirmation=CONFIRM_ASSESS)
    c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition='contested_requires_analysis',confirmation=CONFIRM_FINALIZE)
    cl=c.build391.synthesize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a)
    return c.build391.review_synthesis_claim(case_id=cid,claim_id=cl['claim_id'],identity=a,disposition='contested_requires_analysis',rationale='Reviewed provenance, independence and contradiction; retained as a contested candidate claim.',confirmation=CONFIRM_CLAIM_REVIEW)

def reviewed_hypothesis(c,a,cid,cl,title,statement,test_plan):
    h=c.build391.propose_hypothesis(case_id=cid,title=title,statement=statement,test_plan=test_plan,claim_relations={cl['claim_id']:'test_target'},identity=a)
    return c.build391.review_synthesis_hypothesis(case_id=cid,hypothesis_id=h['hypothesis_id'],identity=a,disposition='retain_for_testing',rationale='Retained for discriminating tests only; hypothesis remains non-factual.',confirmation=CONFIRM_HYPOTHESIS_REVIEW)

def setup(c,a,cid,make_plan=True):
    cl=reviewed_claim(c,a,cid)
    h1=reviewed_hypothesis(c,a,cid,cl,'Timing explanation','The conflicting records may reflect different effective dates.','Compare dated filings and registry history.')
    h2=reviewed_hypothesis(c,a,cid,cl,'Entity-scope explanation','The records may describe different legal entities or reporting scopes.','Resolve identifiers and compare legal-entity scope.')
    ws=c.build392.create_case_reasoning_workspace(case_id=cid,identity=a)
    plan=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a) if make_plan else None
    d393=c.build393.create_investigator_dialogue(case_id=cid,workspace_id=ws['workspace_id'],identity=a)
    d394=c.build394.create_investigator_discussion(case_id=cid,dialogue_session_id=d393['session_id'],identity=a)
    return cl,h1,h2,ws,plan,d393,d394

def side_counts(c):
    names=['phase15_jobs','execution_grant_386','evidence_candidate_promotion_389','hypotheses_112','investigation_claim_391','investigation_hypothesis_391','reasoning_plan_392']
    return {n:int((c.db.one(f'SELECT COUNT(*) n FROM {n}') or {})['n']) for n in names}

def test_version_schema_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build394.version_status()=={'runtime_build':'394.0','schema_version':'394.0','package_version':'394.0.0','coherent':True}
        s=c.build394.schema_metrics(); assert s['within_phase17_gate'] and s['build394_tables_present'] and s['integrity_check']=='ok'
        st=c.investigator_discussion_394.status(); assert st['multi_turn_discussion'] and st['append_only_revision_lineage'] and not st['truth_probability'] and not st['execution_authority']

def test_discussion_session_idempotent(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; *_,d393,d1=setup(c,a,cid); d2=c.build394.create_investigator_discussion(case_id=cid,dialogue_session_id=d393['session_id'],identity=a); assert d1['discussion_id']==d2['discussion_id']

def test_multi_turn_parent_chain(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; *_,d=setup(c,a,cid); t1=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='State the strongest argument for the timing explanation.',turn_type='argument',identity=a); t2=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Now give the strongest counterargument.',turn_type='counterargument',parent_turn_id=t1['turn_id'],identity=a); assert t2['parent_turn_id']==t1['turn_id'] and t2['ordinal']==2 and t2['response']['counterevidence_context']

def test_invalid_parent_other_discussion_rejected(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid1=case(c,a)['case_id']; *_,d1=setup(c,a,cid1); t=c.build394.discuss_case(case_id=cid1,discussion_id=d1['discussion_id'],prompt='First thread.',identity=a)
        cid2=case(c,a)['case_id']; *_,d2=setup(c,a,cid2)
        with pytest.raises((ValueError,KeyError)): c.build394.discuss_case(case_id=cid2,discussion_id=d2['discussion_id'],prompt='Wrong parent.',parent_turn_id=t['turn_id'],identity=a)

def test_hypothesis_side_by_side_comparison_no_winner(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,h1,h2,*rest=setup(c,a,cid); d=rest[-1]
        comp=c.build394.compare_discussion_hypotheses(case_id=cid,discussion_id=d['discussion_id'],hypothesis_ids=[h1['hypothesis_id'],h2['hypothesis_id']],identity=a)
        assert len(comp['comparison']['hypotheses'])==2 and comp['comparison']['winner_selected'] is False and comp['comparison']['probability_assigned'] is False
        assert comp['comparison']['shared_claims']

def test_comparison_rejects_hypothesis_outside_workspace(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,h1,_,_,_,_,d=setup(c,a,cid); h3=reviewed_hypothesis(c,a,cid,cl,'Late hypothesis','A later hypothesis added after workspace creation.','Test after refreshing the workspace.')
        with pytest.raises(ValueError): c.build394.compare_discussion_hypotheses(case_id=cid,discussion_id=d['discussion_id'],hypothesis_ids=[h1['hypothesis_id'],h3['hypothesis_id']],identity=a)

def test_claim_revision_requires_review_and_is_versioned(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]; t=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Narrow the claim wording to the observed reporting period.',turn_type='revision_discussion',identity=a)
        original=c.build391.synthesis_claim(case_id=cid,claim_id=cl['claim_id'],identity=a); original_hash=original['record_hash']
        p=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='claim',target_id=cl['claim_id'],patch={'proposition':'Example GmbH status is disputed in the observed reporting period.','scope_note':'Limited to the reviewed reporting interval.'},rationale='The dialogue identified an overly broad temporal scope that should be narrowed.',source_turn_id=t['turn_id'],identity=a)
        with pytest.raises(PermissionError): c.build394.apply_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)
        c.build394.review_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve_versioned_revision',rationale='Revision narrows wording without changing evidence-derived corroboration metrics.',confirmation=CONFIRM_REVISION_REVIEW)
        v=c.build394.apply_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)
        assert v['version_number']==1 and v['payload']['proposition'].endswith('reporting period.') and not v['upstream_overwritten']
        assert c.build391.synthesis_claim(case_id=cid,claim_id=cl['claim_id'],identity=a)['record_hash']==original_hash

def test_evidence_derived_claim_metrics_cannot_be_patched(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]; t=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Try to change support count.',identity=a)
        with pytest.raises(ValueError): c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='claim',target_id=cl['claim_id'],patch={'support_groups':99},rationale='This intentionally attempts to mutate an evidence-derived metric and must fail.',source_turn_id=t['turn_id'],identity=a)

def test_hypothesis_version_preserves_upstream(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; _,h1,_,*rest=setup(c,a,cid); d=rest[-1]; t=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Strengthen the discriminating test.',turn_type='revision_discussion',identity=a)
        old=c.build391.synthesis_hypothesis(case_id=cid,hypothesis_id=h1['hypothesis_id'],identity=a); oh=old['record_hash']
        p=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='hypothesis',target_id=h1['hypothesis_id'],patch={'test_plan':'Compare dated filings and registry history, then test whether the status change aligns with a documented effective date.','analyst_note':'Discriminating temporal test.'},rationale='The discussion refined the falsification path without promoting the hypothesis to fact.',source_turn_id=t['turn_id'],identity=a)
        c.build394.review_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve_versioned_revision',rationale='The revised test remains falsifiable and preserves hypothesis_not_fact status.',confirmation=CONFIRM_REVISION_REVIEW)
        v=c.build394.apply_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)
        assert v['payload']['revision_metadata']['versioned_working_copy'] and c.build391.synthesis_hypothesis(case_id=cid,hypothesis_id=h1['hypothesis_id'],identity=a)['record_hash']==oh

def test_reasoning_plan_reorder_existing_actions_only(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; *vals,plan,d393,d=setup(c,a,cid); assert plan and len(plan['actions'])>=1
        t=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Discuss plan sequencing.',turn_type='revision_discussion',identity=a)
        order=[x['action_id'] for x in reversed(plan['actions'])]
        p=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='reasoning_plan',target_id=plan['plan_id'],patch={'action_order':order,'sequence_note':'Sequence revised for review; GO boundaries unchanged.'},rationale='The discussion suggested a different review order while preserving every existing action.',source_turn_id=t['turn_id'],identity=a)
        c.build394.review_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve_versioned_revision',rationale='Only ordering and notes change; no action or authority is added.',confirmation=CONFIRM_REVISION_REVIEW)
        v=c.build394.apply_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)
        assert [x['action_id'] for x in v['payload']['actions']]==order and all(not x['execution_authority'] for x in v['payload']['actions'])

def test_reasoning_plan_cannot_add_action(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; *vals,plan,d393,d=setup(c,a,cid); t=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Attempt unauthorized action insertion.',identity=a)
        bad=[x['action_id'] for x in plan['actions']]+['invented-action']
        with pytest.raises(ValueError): c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='reasoning_plan',target_id=plan['plan_id'],patch={'action_order':bad},rationale='This must fail because revisioning cannot invent new plan actions.',source_turn_id=t['turn_id'],identity=a)

def test_revision_lineage_second_version(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]
        def make(text):
            t=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Revision discussion '+text,turn_type='revision_discussion',identity=a)
            p=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='claim',target_id=cl['claim_id'],patch={'analyst_note':text},rationale='A reviewed analyst note is being added as a new append-only version.',source_turn_id=t['turn_id'],identity=a)
            c.build394.review_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve_versioned_revision',rationale='Approved as append-only working-copy revision with unchanged evidence metrics.',confirmation=CONFIRM_REVISION_REVIEW)
            return c.build394.apply_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)
        v1=make('First note'); v2=make('Second note'); assert v1['version_number']==1 and v2['version_number']==2 and v2['parent_version_id']==v1['version_id']

def test_stale_revision_proposal_blocked_after_new_version(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]
        t1=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Proposal A.',identity=a); t2=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Proposal B.',identity=a)
        p1=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='claim',target_id=cl['claim_id'],patch={'analyst_note':'A'},rationale='First concurrent revision proposal for append-only lineage testing.',source_turn_id=t1['turn_id'],identity=a)
        p2=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='claim',target_id=cl['claim_id'],patch={'analyst_note':'B'},rationale='Second concurrent revision proposal should become stale after A applies.',source_turn_id=t2['turn_id'],identity=a)
        for p in (p1,p2): c.build394.review_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve_versioned_revision',rationale='Approved for lineage conflict test; no upstream mutation.',confirmation=CONFIRM_REVISION_REVIEW)
        c.build394.apply_versioned_revision(case_id=cid,proposal_id=p1['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)
        with pytest.raises(PermissionError): c.build394.apply_versioned_revision(case_id=cid,proposal_id=p2['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)

def test_rejected_revision_cannot_apply(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]; t=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Reject this revision.',identity=a)
        p=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='claim',target_id=cl['claim_id'],patch={'analyst_note':'Rejected'},rationale='A deliberately rejected revision should never materialize.',source_turn_id=t['turn_id'],identity=a)
        c.build394.review_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='rejected',rationale='Rejected because the proposed note adds no investigative value.',confirmation=CONFIRM_REVISION_REVIEW)
        with pytest.raises(PermissionError): c.build394.apply_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)

def test_kernel_bridge_is_not_legacy_hypothesis(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]; t=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Version for kernel note.',identity=a)
        before=int((c.db.one('SELECT COUNT(*) n FROM hypotheses_112') or {})['n'])
        p=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='claim',target_id=cl['claim_id'],patch={'analyst_note':'Kernel notebook version.'},rationale='Reviewed working-copy revision intended for notebook visibility only.',source_turn_id=t['turn_id'],identity=a)
        c.build394.review_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve_versioned_revision',rationale='Approved as a notebook-visible working copy, not a factual finding.',confirmation=CONFIRM_REVISION_REVIEW)
        v=c.build394.apply_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)
        b=c.build394.admit_versioned_revision_to_kernel(case_id=cid,version_id=v['version_id'],identity=a,confirmation=CONFIRM_KERNEL_ADMISSION)
        after=int((c.db.one('SELECT COUNT(*) n FROM hypotheses_112') or {})['n']); assert b['kernel_entry_id'] and before==after and not b['execution_authority']

def test_side_effect_counts_unchanged_by_discussion_and_revision(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]; before=side_counts(c)
        t=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Discuss a wording revision.',identity=a)
        p=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='claim',target_id=cl['claim_id'],patch={'analyst_note':'No execution side effects.'},rationale='A local versioning-only change must not alter execution or evidence state.',source_turn_id=t['turn_id'],identity=a)
        c.build394.review_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve_versioned_revision',rationale='Approved as local append-only working version only.',confirmation=CONFIRM_REVISION_REVIEW)
        c.build394.apply_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)
        after=side_counts(c); assert before==after

def test_tampered_version_detected(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); d=rest[-1]; t=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Create a version for integrity test.',identity=a)
        p=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='claim',target_id=cl['claim_id'],patch={'analyst_note':'Integrity test.'},rationale='Create a valid version and then simulate payload tampering.',source_turn_id=t['turn_id'],identity=a)
        c.build394.review_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve_versioned_revision',rationale='Approved only for hash-integrity qualification.',confirmation=CONFIRM_REVISION_REVIEW); v=c.build394.apply_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)
        assert c.build394.verify_versioned_revision(case_id=cid,version_id=v['version_id'])['valid']
        c.db.execute("UPDATE versioned_revision_394 SET payload_json=? WHERE version_id=?",('{}',v['version_id']))
        assert not c.build394.verify_versioned_revision(case_id=cid,version_id=v['version_id'])['valid']

def test_discussion_becomes_stale_if_source_dialogue_changes(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,h1,h2,ws,plan,d393,d=setup(c,a,cid)
        assert c.build394.verify_investigator_discussion(case_id=cid,discussion_id=d['discussion_id'])['valid']
        c.build393.challenge_reasoning(case_id=cid,session_id=d393['session_id'],prompt='Add a new challenge after Build-394 discussion starts.',mode='general_challenge',identity=a)
        assert c.build394.verify_investigator_discussion(case_id=cid,discussion_id=d['discussion_id'])['stale']
        with pytest.raises(ValueError): c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='This old discussion is stale.',identity=a)

def test_ai_feed_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; *_,d=setup(c,a,cid); feed=c.build394.ai_investigator_discussion_feed(case_id=cid,identity=a)
        assert feed['multi_turn_discussion'] and feed['versioned_revision_lineage'] and not feed['truth_determined'] and not feed['probability_assigned'] and not feed['execution_authority'] and feed['network_requests_created']==0


def test_reviewed_build393_proposal_can_seed_versioned_revision(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']
        cl=reviewed_claim(c,a,cid)
        h1=reviewed_hypothesis(c,a,cid,cl,'Timing explanation','The conflicting records may reflect different effective dates.','Compare dated filings and registry history.')
        _=reviewed_hypothesis(c,a,cid,cl,'Entity-scope explanation','The records may describe different legal entities or reporting scopes.','Resolve identifiers and compare legal-entity scope.')
        ws=c.build392.create_case_reasoning_workspace(case_id=cid,identity=a)
        d393=c.build393.create_investigator_dialogue(case_id=cid,workspace_id=ws['workspace_id'],identity=a)
        turn=c.build393.challenge_reasoning(case_id=cid,session_id=d393['session_id'],prompt='What would falsify this hypothesis?',mode='falsification_test',target_type='hypothesis',target_id=h1['hypothesis_id'],identity=a)
        p393=next(p for p in turn['proposals'] if p['proposal_type']=='hypothesis_test_revision')
        c.build393.review_challenge_proposal(case_id=cid,proposal_id=p393['proposal_id'],identity=a,disposition='approve_for_manual_revision',rationale='Reviewed as a manual test-plan revision only; no upstream mutation is authorized.',confirmation=CONFIRM_PROPOSAL_REVIEW)
        d394=c.build394.create_investigator_discussion(case_id=cid,dialogue_session_id=d393['session_id'],identity=a)
        p=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d394['discussion_id'],target_type='hypothesis',target_id=h1['hypothesis_id'],patch={'test_plan':'Compare dated filings, registry history and effective dates; identify an observation that would contradict the timing explanation.'},rationale='The reviewed Build-393 falsification challenge is materialized as a versioned working-copy test-plan revision.',source_challenge_proposal_id=p393['proposal_id'],identity=a)
        c.build394.review_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve_versioned_revision',rationale='The revision is traceable to a reviewed dialogue result and remains hypothesis_not_fact.',confirmation=CONFIRM_REVISION_REVIEW)
        v=c.build394.apply_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)
        assert v['version_number']==1 and v['target_type']=='hypothesis' and 'contradict' in v['payload']['test_plan']

def test_build394_phase_status_and_gate_shape(tmp_path):
    with ctx(tmp_path) as c:
        st=c.build394.phase17_status(); assert st['build']=='394.0' and st['phase17_builds_completed']==14 and st['append_only_upstream'] and not st['execution_authority']
        gate=c.build394.qualified_gate(); assert gate['build']=='394.0' and gate['production_release_ready'] is False
