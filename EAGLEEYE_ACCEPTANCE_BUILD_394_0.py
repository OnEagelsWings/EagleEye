from __future__ import annotations
import hashlib, json, secrets, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.evidence_review390 import CONFIRM_ASSESS, CONFIRM_FINALIZE
from eagleeye_pro.phase17.investigation_synthesis391 import CONFIRM_CLAIM_REVIEW, CONFIRM_HYPOTHESIS_REVIEW
from eagleeye_pro.phase17.investigator_dialogue393 import CONFIRM_PROPOSAL_REVIEW
from eagleeye_pro.phase17.discussion_revision394 import CONFIRM_REVISION_REVIEW, CONFIRM_APPLY_REVISION, CONFIRM_KERNEL_ADMISSION

PW='Acceptance394-Secure-Vector-Z9!'

def cand(c,cid,source,norm):
    raw=json.dumps({'s':source,'n':norm},sort_keys=True).encode(); oid='a394_'+secrets.token_hex(7); sha=hashlib.sha256(raw).hexdigest(); now='2026-09-13T22:00:00+00:00'
    c.db.execute("INSERT INTO phase15_objects(object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,cid,'','canon_'+source,'local',oid,sha,len(raw),'application/json','review_pending','{}','accept394',now,hashlib.sha256(raw+b'r').hexdigest()))
    obj={'object_id':oid,'sha256':sha,'media_type':'application/json','security_state':'review_pending'}; rr={'wave_number':1,'phase17_source_id':source,'canonical_source_id':'canon_'+source,'dispatch_id':'d'+oid,'job_id':'j'+oid,'crawl_run_id':'c'+oid,'search_run_id':'s'+oid}
    out,_=c.result_intake_389._insert_candidate(case_id=cid,session_id='accept394',result_row=rr,obj=obj,parse_run_id='p'+oid,record_index=0,candidate_type='normalized_record',normalized=norm,provenance={}); return out

def counts(c):
    names=['phase15_jobs','execution_grant_386','evidence_candidate_promotion_389','hypotheses_112','investigation_claim_391','investigation_hypothesis_391','reasoning_plan_392']
    return {n:int((c.db.one(f'SELECT COUNT(*) n FROM {n}') or {})['n']) for n in names}

def main():
    root=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as td:
        with AppContext(base_dir=td,actor='accept394') as c:
            a=c.team_identity_359.create_initial_admin(username='accept394',display_name='Discussion Acceptance',password=PW); a={**a,'session_id':'accept394'}
            cid=c.build380.team_create_case(identity=a,title='accept394',client='internal',purpose='discussion revision acceptance',legal_basis='public_data')['case_id']
            g=cand(c,cid,'gleif.lei',{'entity':'Example GmbH','status':'ACTIVE'}); s=cand(c,cid,'sec.edgar',{'entity':'Example GmbH','status':'INACTIVE'})
            r=c.build390.create_corroboration_review(case_id=cid,proposition='Example GmbH status differs across reviewed sources',candidate_stances={g['candidate_id']:'supports',s['candidate_id']:'contradicts'},identity=a)
            c.build390.assess_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,confirmation=CONFIRM_ASSESS); c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition='contested_requires_analysis',confirmation=CONFIRM_FINALIZE)
            cl=c.build391.synthesize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a); cl=c.build391.review_synthesis_claim(case_id=cid,claim_id=cl['claim_id'],identity=a,disposition='contested_requires_analysis',rationale='Acceptance review preserves contradictory independent observations and uncertainty.',confirmation=CONFIRM_CLAIM_REVIEW)
            h1=c.build391.propose_hypothesis(case_id=cid,title='Timing explanation',statement='The observations may refer to different effective dates.',test_plan='Compare dated filings and registry history.',claim_relations={cl['claim_id']:'test_target'},identity=a); h1=c.build391.review_synthesis_hypothesis(case_id=cid,hypothesis_id=h1['hypothesis_id'],identity=a,disposition='retain_for_testing',rationale='Retained as a falsifiable timing hypothesis, not a fact.',confirmation=CONFIRM_HYPOTHESIS_REVIEW)
            h2=c.build391.propose_hypothesis(case_id=cid,title='Scope explanation',statement='The observations may refer to different legal-entity scopes.',test_plan='Resolve identifiers and compare entity scope.',claim_relations={cl['claim_id']:'test_target'},identity=a); h2=c.build391.review_synthesis_hypothesis(case_id=cid,hypothesis_id=h2['hypothesis_id'],identity=a,disposition='retain_for_testing',rationale='Retained as a competing scope hypothesis, not a fact.',confirmation=CONFIRM_HYPOTHESIS_REVIEW)
            ws=c.build392.create_case_reasoning_workspace(case_id=cid,identity=a); plan=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a)
            d393=c.build393.create_investigator_dialogue(case_id=cid,workspace_id=ws['workspace_id'],identity=a)
            challenge=c.build393.challenge_reasoning(case_id=cid,session_id=d393['session_id'],prompt='What would falsify the timing hypothesis?',mode='falsification_test',target_type='hypothesis',target_id=h1['hypothesis_id'],identity=a)
            cp=next(x for x in challenge['proposals'] if x['proposal_type']=='hypothesis_test_revision')
            c.build393.review_challenge_proposal(case_id=cid,proposal_id=cp['proposal_id'],identity=a,disposition='approve_for_manual_revision',rationale='Reviewed as a manual falsification-test revision only.',confirmation=CONFIRM_PROPOSAL_REVIEW)
            before=counts(c)
            d=c.build394.create_investigator_discussion(case_id=cid,dialogue_session_id=d393['session_id'],identity=a)
            t1=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Argue for the timing explanation while preserving counterevidence.',turn_type='argument',identity=a)
            t2=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt='Now state the strongest counterargument and discriminating test.',turn_type='counterargument',parent_turn_id=t1['turn_id'],identity=a)
            comp=c.build394.compare_discussion_hypotheses(case_id=cid,discussion_id=d['discussion_id'],hypothesis_ids=[h1['hypothesis_id'],h2['hypothesis_id']],identity=a)
            original_claim_hash=c.build391.synthesis_claim(case_id=cid,claim_id=cl['claim_id'])['record_hash']; original_hyp_hash=c.build391.synthesis_hypothesis(case_id=cid,hypothesis_id=h1['hypothesis_id'])['record_hash']; original_plan_hash=c.build392.reasoning_plan(case_id=cid,plan_id=plan['plan_id'])['plan_hash']
            p1=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='claim',target_id=cl['claim_id'],patch={'scope_note':'Limited to the reviewed reporting interval.','analyst_note':'Counterevidence remains unresolved.'},rationale='Discussion narrowed the claim scope while preserving evidence-derived metrics.',source_turn_id=t2['turn_id'],identity=a)
            c.build394.review_versioned_revision(case_id=cid,proposal_id=p1['proposal_id'],identity=a,disposition='approve_versioned_revision',rationale='Approved as append-only working-copy revision; upstream claim remains unchanged.',confirmation=CONFIRM_REVISION_REVIEW); v1=c.build394.apply_versioned_revision(case_id=cid,proposal_id=p1['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)
            p2=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='hypothesis',target_id=h1['hypothesis_id'],patch={'test_plan':'Compare dated filings and registry history; identify a dated observation that would contradict the timing explanation.'},rationale='Reviewed Build-393 challenge refined the hypothesis falsification path.',source_challenge_proposal_id=cp['proposal_id'],identity=a)
            c.build394.review_versioned_revision(case_id=cid,proposal_id=p2['proposal_id'],identity=a,disposition='approve_versioned_revision',rationale='Approved as versioned test-plan refinement; hypothesis remains hypothesis_not_fact.',confirmation=CONFIRM_REVISION_REVIEW); v2=c.build394.apply_versioned_revision(case_id=cid,proposal_id=p2['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)
            order=[x['action_id'] for x in reversed(plan['actions'])]
            p3=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='reasoning_plan',target_id=plan['plan_id'],patch={'action_order':order,'sequence_note':'Review sequence changed; no new action or authority added.'},rationale='Discussion changed only the review ordering of the existing bounded plan.',source_turn_id=t2['turn_id'],identity=a)
            c.build394.review_versioned_revision(case_id=cid,proposal_id=p3['proposal_id'],identity=a,disposition='approve_versioned_revision',rationale='Approved because it preserves all existing actions and GO boundaries.',confirmation=CONFIRM_REVISION_REVIEW); v3=c.build394.apply_versioned_revision(case_id=cid,proposal_id=p3['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)
            kb=c.build394.admit_versioned_revision_to_kernel(case_id=cid,version_id=v2['version_id'],identity=a,confirmation=CONFIRM_KERNEL_ADMISSION)
            after=counts(c); feed=c.build394.ai_investigator_discussion_feed(case_id=cid,identity=a); status=c.investigator_discussion_394.status()
            checks={
                'version_coherent':c.build394.version_status()['coherent'],
                'schema_integrity':c.build394.schema_metrics()['within_phase17_gate'],
                'predecessor_393':c.build394.historical_build393_receipt()['valid'],
                'multi_turn_chain':t2['parent_turn_id']==t1['turn_id'] and t2['ordinal']==2,
                'side_by_side_hypotheses':len(comp['comparison']['hypotheses'])==2 and comp['comparison']['winner_selected'] is False,
                'shared_claim_not_double_counted':bool(comp['comparison']['shared_claims']),
                'claim_version_created':v1['version_number']==1 and v1['epistemic_status']=='versioned_investigation_working_copy_not_fact',
                'reviewed_dialogue_seeded_hypothesis_version':v2['version_number']==1 and p2['source_challenge_proposal_id']==cp['proposal_id'],
                'plan_version_preserves_actions':set(order)=={x['action_id'] for x in v3['payload']['actions']},
                'upstream_claim_unchanged':c.build391.synthesis_claim(case_id=cid,claim_id=cl['claim_id'])['record_hash']==original_claim_hash,
                'upstream_hypothesis_unchanged':c.build391.synthesis_hypothesis(case_id=cid,hypothesis_id=h1['hypothesis_id'])['record_hash']==original_hyp_hash,
                'upstream_plan_unchanged':c.build392.reasoning_plan(case_id=cid,plan_id=plan['plan_id'])['plan_hash']==original_plan_hash,
                'no_execution_side_effects':before==after,
                'kernel_notebook_only':bool(kb.get('kernel_entry_id')) and kb['execution_authority'] is False,
                'version_integrity':all(c.build394.verify_versioned_revision(case_id=cid,version_id=v['version_id'])['valid'] for v in (v1,v2,v3)),
                'discussion_integrity':c.build394.verify_investigator_discussion(case_id=cid,discussion_id=d['discussion_id'])['valid'],
                'feed_boundaries':feed['truth_determined'] is False and feed['probability_assigned'] is False and feed['execution_authority'] is False,
                'evidence_metrics_immutable':status['evidence_derived_metrics_editable'] is False,
                'append_only_lineage':status['append_only_revision_lineage'] is True and status['immutable_upstream_objects'] is True,
                'no_auto_go_live_fetch':not status['automatic_go_issuance'] and not status['automatic_live_confirmation'] and not status['direct_network_fetch'],
                'no_auto_evidence_promotion':not status['automatic_evidence_promotion'],
                'no_truth_probability':not status['truth_probability'] and not status['automatic_truth_acceptance'],
            }
            fp=c.build394.code_fingerprint()
    result='pass' if all(checks.values()) else 'fail'
    payload={'build':'394.0','result':result,'passed':sum(checks.values()),'total':len(checks),'checks':checks,'code_fingerprint':fp}
    (root/'ACCEPTANCE_RESULTS_BUILD_394_0.json').write_text(json.dumps(payload,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(payload,indent=2)); raise SystemExit(0 if result=='pass' else 1)

if __name__=='__main__': main()
