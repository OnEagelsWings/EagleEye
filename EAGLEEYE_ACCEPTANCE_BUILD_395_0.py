from __future__ import annotations
import json,tempfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'tests')]
from test_build394_integrated import ctx,admin,case,setup,side_counts
from test_build395_integrated import make_claim_version
from eagleeye_pro.phase17.case_state_graph395 import CONFIRM_REVIEW,CONFIRM_ADOPT,CONFIRM_ROLLBACK,CONFIRM_BRANCH,CONFIRM_STAGE

def main():
    checks={}
    with tempfile.TemporaryDirectory() as d:
      with ctx(Path(d)) as c:
        a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); disc=rest[-1]; v=make_claim_version(c,a,cid,cl,disc,'acceptance-v1')
        checks['version_coherent']=c.build395.version_status()['coherent']
        checks['schema_integrity']=c.build395.schema_metrics()['within_phase17_gate']
        s0=c.build395.active_case_state(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a); checks['origin_state']=s0['generation']==0 and s0['active_node_id'].startswith('origin:claim:')
        before=side_counts(c)
        br=c.build395.create_case_state_branch(case_id=cid,target_type='claim',target_id=cl['claim_id'],branch_name='Acceptance branch',identity=a,confirmation=CONFIRM_BRANCH)
        br=c.build395.stage_case_state_branch(case_id=cid,branch_id=br['branch_id'],version_id=v['version_id'],identity=a,confirmation=CONFIRM_STAGE)
        checks['branch_stage']=br['head_node_id']==v['version_id']
        checks['branch_does_not_adopt']=c.build395.active_case_state(case_id=cid,target_type='claim',target_id=cl['claim_id'])['generation']==0
        diff=c.build395.compare_case_state_nodes(case_id=cid,target_type='claim',target_id=cl['claim_id'],left_node_id=s0['active_node_id'],right_node_id=v['version_id'],identity=a)
        checks['diff_no_truth']=bool(diff['changes']) and not diff['truth_determined']
        p=c.build395.propose_case_state_adoption(case_id=cid,target_type='claim',target_id=cl['claim_id'],candidate_version_id=v['version_id'],source_branch_id=br['branch_id'],identity=a,rationale='Acceptance adoption of reviewed branch head into active case state.')
        blocked=False
        try:c.build395.apply_case_state_adoption(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_ADOPT)
        except PermissionError:blocked=True
        checks['review_required']=blocked
        c.build395.review_case_state_adoption(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve',rationale='Acceptance review approves only state-pointer adoption and no execution rights.',confirmation=CONFIRM_REVIEW)
        s1=c.build395.apply_case_state_adoption(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_ADOPT)
        checks['controlled_adoption']=s1['generation']==1 and s1['active_version_id']==v['version_id']
        rb=c.build395.propose_case_state_adoption(case_id=cid,target_type='claim',target_id=cl['claim_id'],candidate_version_id='',proposal_kind='rollback',identity=a,rationale='Acceptance rollback returns active state to immutable origin while retaining transition history.')
        c.build395.review_case_state_adoption(case_id=cid,proposal_id=rb['proposal_id'],identity=a,disposition='approve',rationale='Acceptance rollback is reviewed as a new state transition.',confirmation=CONFIRM_REVIEW)
        s2=c.build395.apply_case_state_adoption(case_id=cid,proposal_id=rb['proposal_id'],identity=a,confirmation=CONFIRM_ROLLBACK)
        checks['rollback_transition']=s2['generation']==2 and s2['active_node_id'].startswith('origin:claim:')
        hist=c.build395.case_state_history(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
        checks['append_only_history']=len(hist['transitions'])==2
        checks['side_effect_free']=before==side_counts(c)
        st=c.case_state_graph_395.status()
        checks['no_truth_probability']=not st['truth_probability']; checks['no_auto_truth']=not st['automatic_truth_acceptance']; checks['no_auto_evidence']=not st['automatic_evidence_promotion']; checks['no_auto_go']=not st['automatic_go_issuance']; checks['no_live']=not st['automatic_live_confirmation']; checks['no_execution_authority']=not st['execution_authority']; checks['no_network_fetch']=not st['direct_network_fetch']; checks['immutable_evidence_history']=st['immutable_evidence_history']
        fp=c.build395.code_fingerprint()
    out={'build':'395.0','result':'pass' if all(checks.values()) else 'fail','checks':checks,'passed':sum(bool(v) for v in checks.values()),'total':len(checks),'code_fingerprint':fp}
    (ROOT/'ACCEPTANCE_RESULTS_BUILD_395_0.json').write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(out,indent=2,sort_keys=True)); return 0 if out['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
