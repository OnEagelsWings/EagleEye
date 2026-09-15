from __future__ import annotations
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent/'tests'))
from test_build394_integrated import ctx, admin, case, candidate, side_counts
from test_build396_integrated import base_case, new_corroboration
from eagleeye_pro.phase17.case_reconciliation396 import CONFIRM_BASELINE, CONFIRM_REVIEW, CONFIRM_BRANCH, CONFIRM_ADVANCE


def main() -> int:
    checks: dict[str,bool] = {}
    with tempfile.TemporaryDirectory(prefix='eagleeye396_accept_') as td:
        with ctx(Path(td)) as c:
            a=admin(c); cid=case(c,a)['case_id']; cl,h1,h2,ws,plan,*_=base_case(c,a,cid)
            checks['version_coherent']=c.build396.version_status()['coherent']
            sm=c.build396.schema_metrics(); checks['schema_gate']=sm['within_phase17_gate'] and sm['build396_tables_present'] and sm['integrity_check']=='ok'
            checks['predecessor_receipt']=c.build396.historical_build395_receipt()['valid']
            st=c.case_reconciliation_396.status(); checks['status_contract']=st['incremental_reconciliation'] and st['explicit_baseline'] and not st['execution_authority']
            try: c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation='YES'); checks['baseline_exact_confirmation']=False
            except PermissionError: checks['baseline_exact_confirmation']=True
            b=c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation=CONFIRM_BASELINE)
            checks['baseline_created']=b['signal_count']>0
            checks['baseline_integrity']=c.case_reconciliation_396.verify_baseline(case_id=cid,baseline_id=b['baseline_id'])['valid']
            s0=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a)
            checks['delta_no_change']=s0['delta_signal_count']==0 and s0['impact_count']==0
            unmatched=candidate(c,cid,'internet_archive.metadata',{'fresh':'unrelated acceptance material'})
            s1=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a)
            ux=next(x for x in s1['signals'] if x['signal_id']==unmatched['candidate_id'])
            checks['unmatched_preserved']=ux['match_state']=='unmatched_review_material' and not ux['matched_target_ids']
            exact=candidate(c,cid,'eu.ted',{'proposition':cl['proposition']})
            s2=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a)
            checks['exact_candidate_match']=any(x['source_signal_id']==exact['candidate_id'] and x['target_type']=='claim' for x in s2['impacts'])
            cr=new_corroboration(c,a,cid,cl['proposition'])
            s3=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a)
            checks['corroboration_signal_detected']=any(x['signal_type']=='corroboration_review' and x['signal_id']==cr['review_id'] for x in s3['signals'])
            checks['claim_impact']=any(x['target_type']=='claim' and x['target_id']==cl['claim_id'] for x in s3['impacts'])
            checks['hypothesis_dependency']=all(any(x['target_type']=='hypothesis' and x['target_id']==h['hypothesis_id'] for x in s3['impacts']) for h in (h1,h2))
            checks['plan_dependency']=any(x['target_type']=='reasoning_plan' and x['target_id']==plan['plan_id'] for x in s3['impacts'])
            p=c.build396.propose_reanalysis(case_id=cid,scan_id=s3['scan_id'],target_type='claim',target_id=cl['claim_id'],identity=a,rationale='Acceptance re-analysis proposal binds the active generation to newly observed analytical signals.')
            checks['proposal_review_only']=p['status']=='proposal_needs_review' and not p['execution_authority']
            try: c.build396.create_reanalysis_branch(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_BRANCH); checks['branch_requires_review']=False
            except PermissionError: checks['branch_requires_review']=True
            try: c.build396.review_reanalysis(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve',rationale='Acceptance review confirms local re-analysis only.',confirmation='YES'); checks['review_exact_confirmation']=False
            except PermissionError: checks['review_exact_confirmation']=True
            rp=c.build396.review_reanalysis(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve',rationale='Acceptance review confirms a local re-analysis branch only; no adoption or execution is authorized.',confirmation=CONFIRM_REVIEW)
            checks['review_approved']=rp['status']=='reviewed_for_reanalysis'
            before=c.build395.active_case_state(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
            try: c.build396.create_reanalysis_branch(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation='YES'); checks['branch_exact_confirmation']=False
            except PermissionError: checks['branch_exact_confirmation']=True
            br=c.build396.create_reanalysis_branch(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_BRANCH)
            after=c.build395.active_case_state(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
            checks['branch_created']=bool(br['branch_id']) and br['adopted'] is False
            checks['active_state_unchanged']=before['active_node_id']==after['active_node_id'] and before['generation']==after['generation']
            b2=c.build396.advance_reconciliation_baseline(case_id=cid,scan_id=s3['scan_id'],identity=a,confirmation=CONFIRM_ADVANCE)
            checks['baseline_advanced']=b2['previous_baseline_id']==b['baseline_id']
            s4=c.build396.reconcile_case_state(case_id=cid,baseline_id=b2['baseline_id'],identity=a)
            checks['advanced_baseline_zero_delta']=s4['delta_signal_count']==0
            checks['scan_integrity']=c.case_reconciliation_396.verify_scan(case_id=cid,scan_id=s3['scan_id'])['valid']
            before_side=side_counts(c)
            _=c.build396.reconcile_case_state(case_id=cid,baseline_id=b2['baseline_id'],identity=a)
            checks['no_execution_side_effects']=before_side==side_counts(c)
            checks['no_truth_probability']=not st['truth_probability'] and not st['automatic_truth_acceptance']
            checks['no_auto_authority']=not st['automatic_go_issuance'] and not st['automatic_live_confirmation'] and not st['execution_authority']
            checks['no_network_fetch']=not st['direct_network_fetch']
            fingerprint=c.build396.code_fingerprint()
    result='pass' if all(checks.values()) and len(checks)==28 else 'fail'
    payload={'build':'396.0','result':result,'checks':checks,'checks_passed':sum(checks.values()),'checks_total':len(checks),'code_fingerprint':fingerprint}
    Path('ACCEPTANCE_RESULTS_BUILD_396_0.json').write_text(json.dumps(payload,indent=2,sort_keys=True),encoding='utf-8')
    print(json.dumps(payload,indent=2,sort_keys=True))
    return 0 if result=='pass' else 1

if __name__=='__main__': raise SystemExit(main())
