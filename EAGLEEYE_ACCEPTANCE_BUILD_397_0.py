from __future__ import annotations
import json,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"tests"))
from eagleeye.crawler.engine import RobotsRules
from test_build394_integrated import ctx,admin,case,setup,side_counts
from test_build396_integrated import prepare_active
from eagleeye_pro.phase17.argumentative_analyst397 import CONFIRM_REVIEW

def main():
    checks={}
    with tempfile.TemporaryDirectory(prefix='e397acc_') as td:
        with ctx(Path(td)) as c:
            a=admin(c); cid=case(c,a)['case_id']; cl,h1,h2,ws,plan,*_=setup(c,a,cid); prepare_active(c,a,cid,cl,h1,h2,plan)
            checks['version']=c.build397.version_status()['coherent']; checks['schema']=c.build397.schema_metrics()['within_phase17_gate']
            checks['robots_pdf']=not RobotsRules('User-agent: *\nDisallow: /*.pdf$').allowed('/report.pdf')
            checks['robots_multi_ua']=not RobotsRules('User-agent: Other\nUser-agent: EagleEye-GovernedCrawler\nDisallow: /private/').allowed('/private/a')
            checks['robots_fail_closed']=not RobotsRules.fail_closed('503').allowed('/x')
            before=side_counts(c)
            x=c.build397.assess_argumentation(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a)
            checks['citations']=len(x['citations'])>=2 and all(z['object_sha256'] and z['candidate_record_hash'] for z in x['citations'])
            checks['support_counter']=x['support_groups']>=1 and x['contradiction_groups']>=1
            checks['stop_decision']=x['stop_decision']=='continue_discriminating_research'
            checks['integrity']=c.argumentative_analyst_397.verify_assessment(case_id=cid,assessment_id=x['assessment_id'])['valid']
            h=c.build397.assess_argumentation(case_id=cid,target_type='hypothesis',target_id=h1['hypothesis_id'],identity=a)
            checks['hypothesis_assessment']=h['target_type']=='hypothesis' and h['probability_assigned'] is False
            r=c.build397.propose_analyst_recommendation(case_id=cid,assessment_id=x['assessment_id'],identity=a,recommendation_type='human_review_only',proposal={'note':'Review cited conflict.'},rationale='Independent contradiction remains material and requires human review.')
            checks['proposal_review_only']=r['status']=='proposal_needs_review' and not r['execution_authority']
            try:c.build397.review_analyst_recommendation(case_id=cid,recommendation_id=r['recommendation_id'],identity=a,disposition='approve_for_manual_revision',rationale='x',confirmation='YES'); checks['exact_review']=False
            except PermissionError:checks['exact_review']=True
            rr=c.build397.review_analyst_recommendation(case_id=cid,recommendation_id=r['recommendation_id'],identity=a,disposition='approve_for_manual_revision',rationale='Reviewed for manual follow-up only; no automatic mutation or authority.',confirmation=CONFIRM_REVIEW)
            checks['reviewed']=rr['status']=='reviewed_for_manual_revision'
            checks['no_side_effects']=before==side_counts(c)
            st=c.argumentative_analyst_397.status(); checks['no_truth']=not st['truth_probability'] and not st['automatic_truth_acceptance']; checks['no_execution']=not st['execution_authority'] and not st['automatic_go_issuance'] and not st['automatic_live_confirmation']; checks['no_fetch']=not st['direct_network_fetch']
            fp=c.build397.code_fingerprint()
    result='pass' if all(checks.values()) else 'fail'; payload={'build':'397.0','result':result,'checks':checks,'checks_passed':sum(checks.values()),'checks_total':len(checks),'code_fingerprint':fp}; Path('ACCEPTANCE_RESULTS_BUILD_397_0.json').write_text(json.dumps(payload,indent=2,sort_keys=True)); print(json.dumps(payload,indent=2,sort_keys=True)); return 0 if result=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
