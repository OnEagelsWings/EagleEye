from __future__ import annotations
import hashlib,json,secrets,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.evidence_review390 import CONFIRM_ASSESS,CONFIRM_FINALIZE
from eagleeye_pro.phase17.investigation_synthesis391 import CONFIRM_CLAIM_REVIEW,CONFIRM_HYPOTHESIS_REVIEW
from eagleeye_pro.phase17.investigator_dialogue393 import CONFIRM_PROPOSAL_REVIEW,CONFIRM_KERNEL_ADMISSION

PW='Acceptance393-Secure-Vector-Z9!'

def cand(c,cid,source,norm):
    raw=json.dumps({'s':source,'n':norm},sort_keys=True).encode(); oid='a393_'+secrets.token_hex(7); sha=hashlib.sha256(raw).hexdigest(); now='2026-09-13T17:50:00+00:00'
    c.db.execute("INSERT INTO phase15_objects(object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,cid,'','canon_'+source,'local',oid,sha,len(raw),'application/json','review_pending','{}','accept393',now,hashlib.sha256(raw+b'r').hexdigest()))
    obj={'object_id':oid,'sha256':sha,'media_type':'application/json','security_state':'review_pending'}; rr={'wave_number':1,'phase17_source_id':source,'canonical_source_id':'canon_'+source,'dispatch_id':'d'+oid,'job_id':'j'+oid,'crawl_run_id':'c'+oid,'search_run_id':'s'+oid}
    out,_=c.result_intake_389._insert_candidate(case_id=cid,session_id='accept393',result_row=rr,obj=obj,parse_run_id='p'+oid,record_index=0,candidate_type='normalized_record',normalized=norm,provenance={}); return out

def upstream(c):
    return (
        int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),
        int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),
        int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']),
        int((c.db.one('SELECT COUNT(*) n FROM hypotheses_112') or {})['n']),
        int((c.db.one('SELECT COUNT(*) n FROM investigation_claim_391') or {})['n']),
        int((c.db.one('SELECT COUNT(*) n FROM investigation_hypothesis_391') or {})['n']),
        int((c.db.one('SELECT COUNT(*) n FROM reasoning_plan_392') or {})['n']),
    )

def main():
    root=Path(__file__).resolve().parent; checks={}
    with tempfile.TemporaryDirectory() as td:
        with AppContext(base_dir=td,actor='accept393') as c:
            a=c.team_identity_359.create_initial_admin(username='accept393',display_name='Challenge Reviewer',password=PW); a={**a,'session_id':'accept393'}
            cid=c.build380.team_create_case(identity=a,title='accept393',client='internal',purpose='dialogue challenge qualification',legal_basis='public_data')['case_id']; _=c.execution_authority_386
            g=cand(c,cid,'gleif.lei',{'name':'Example GmbH','status':'ACTIVE'}); s=cand(c,cid,'sec.edgar',{'name':'Example GmbH','status':'INACTIVE'})
            r=c.build390.create_corroboration_review(case_id=cid,proposition='Example GmbH is active',candidate_stances={g['candidate_id']:'supports',s['candidate_id']:'contradicts'},identity=a)
            c.build390.assess_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,confirmation=CONFIRM_ASSESS)
            c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition='contested_requires_analysis',confirmation=CONFIRM_FINALIZE)
            cl=c.build391.synthesize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a)
            cl=c.build391.review_synthesis_claim(case_id=cid,claim_id=cl['claim_id'],identity=a,disposition='contested_requires_analysis',rationale='Contradiction preserved for challenge-engine qualification.',confirmation=CONFIRM_CLAIM_REVIEW)
            h=c.build391.propose_hypothesis(case_id=cid,title='Timing explanation',statement='The contradictory observations may reflect different effective dates.',test_plan='Compare dated filings, registry history and effective dates.',claim_relations={cl['claim_id']:'test_target'},identity=a)
            h=c.build391.review_synthesis_hypothesis(case_id=cid,hypothesis_id=h['hypothesis_id'],identity=a,disposition='retain_for_testing',rationale='The explanation is testable and remains explicitly hypothetical.',confirmation=CONFIRM_HYPOTHESIS_REVIEW)
            ws=c.build392.create_case_reasoning_workspace(case_id=cid,identity=a)
            plan=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a)
            before=upstream(c)
            sess=c.build393.create_investigator_dialogue(case_id=cid,workspace_id=ws['workspace_id'],identity=a)
            weak=c.build393.challenge_reasoning(case_id=cid,session_id=sess['session_id'],prompt='Welche Annahme ist hier am schwächsten?',identity=a)
            counter=c.build393.challenge_reasoning(case_id=cid,session_id=sess['session_id'],prompt='Argumentiere gegen die Hypothese.',mode='counter_argument',target_type='hypothesis',target_id=h['hypothesis_id'],identity=a)
            fals=c.build393.challenge_reasoning(case_id=cid,session_id=sess['session_id'],prompt='Was würde diese Hypothese falsifizieren?',mode='falsification_test',target_type='hypothesis',target_id=h['hypothesis_id'],identity=a)
            red=c.build393.challenge_reasoning(case_id=cid,session_id=sess['session_id'],prompt='Red-team den Ermittlungsplan.',mode='plan_red_team',target_type='reasoning_plan',target_id=plan['plan_id'],identity=a)
            pid=fals['proposals'][0]['proposal_id']
            prop=c.build393.review_challenge_proposal(case_id=cid,proposal_id=pid,identity=a,disposition='approve_for_manual_revision',rationale='Reviewed as a manual hypothesis-test revision only; no upstream mutation authorized.',confirmation=CONFIRM_PROPOSAL_REVIEW)
            kb=c.build393.admit_challenge_to_kernel(case_id=cid,turn_id=counter['turn_id'],identity=a,confirmation=CONFIRM_KERNEL_ADMISSION)
            feed=c.build393.ai_investigator_dialogue_feed(case_id=cid,identity=a)
            after=upstream(c)
            checks={
                'version_coherent':c.build393.version_status()['coherent'],
                'schema_integrity':c.build393.schema_metrics()['within_phase17_gate'],
                'predecessor_392':c.build393.historical_build392_receipt()['valid'],
                'dialogue_session_active':sess['state']=='active_review_dialogue',
                'weakest_assumption_mode':weak['challenge_mode']=='weakest_assumption' and bool(weak['response']['challenge_points']),
                'counter_argument_mode':counter['challenge_mode']=='counter_argument' and counter['target_id']==h['hypothesis_id'],
                'falsification_mode':fals['challenge_mode']=='falsification_test' and any(x['proposal_type']=='hypothesis_test_revision' for x in fals['proposals']),
                'plan_red_team':red['challenge_mode']=='plan_red_team' and red['target_id']==plan['plan_id'],
                'proposal_reviewed_manual_only':prop['status']=='reviewed_for_manual_revision' and prop['automatic_upstream_mutation'] is False,
                'kernel_notebook_bridge':bool(kb.get('kernel_entry_id')) and kb['execution_authority'] is False,
                'turn_integrity':c.build393.verify_challenge_turn(case_id=cid,turn_id=counter['turn_id'])['valid'],
                'proposal_integrity':c.build393.verify_challenge_proposal(case_id=cid,proposal_id=pid)['valid'],
                'no_upstream_side_effects':before==after,
                'feed_boundaries':feed['truth_determined'] is False and feed['probability_assigned'] is False and feed['automatic_upstream_mutation'] is False and feed['execution_authority'] is False,
                'human_revision_review_required':c.investigator_dialogue_393.status()['human_revision_review_required'] is True,
                'no_auto_go':c.investigator_dialogue_393.status()['automatic_go_issuance'] is False,
                'no_direct_fetch':c.investigator_dialogue_393.status()['direct_network_fetch'] is False,
                'no_auto_evidence_promotion':c.investigator_dialogue_393.status()['automatic_evidence_promotion'] is False,
                'no_auto_claim_hypothesis_plan_revision':not c.investigator_dialogue_393.status()['automatic_claim_revision'] and not c.investigator_dialogue_393.status()['automatic_hypothesis_revision'] and not c.investigator_dialogue_393.status()['automatic_plan_revision'],
                'no_truth_probability':c.investigator_dialogue_393.status()['truth_probability'] is False,
            }
            fp=c.build393.code_fingerprint()
    result='pass' if all(checks.values()) else 'fail'; payload={'build':'393.0','result':result,'passed':sum(checks.values()),'total':len(checks),'checks':checks,'code_fingerprint':fp}; (root/'ACCEPTANCE_RESULTS_BUILD_393_0.json').write_text(json.dumps(payload,indent=2,sort_keys=True)); print(json.dumps(payload,indent=2)); raise SystemExit(0 if result=='pass' else 1)
if __name__=='__main__': main()
