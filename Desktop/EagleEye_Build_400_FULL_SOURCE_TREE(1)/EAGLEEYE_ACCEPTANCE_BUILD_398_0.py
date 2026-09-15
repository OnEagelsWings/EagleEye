from __future__ import annotations
import json,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'tests'))
from test_build394_integrated import ctx,admin
from eagleeye_pro.phase17.model_holdout398 import CONFIRM_FREEZE_SUITE,CONFIRM_FREEZE_BASELINE,CONFIRM_EXTERNAL_RUN,CONFIRM_HUMAN_REVIEW

def main():
    checks={}
    with tempfile.TemporaryDirectory(prefix='e398acc_') as td:
        with ctx(Path(td)) as c:
            a=admin(c); checks['version']=c.build398.version_status()['coherent']; checks['schema']=c.build398.schema_metrics()['within_phase17_gate']
            st=c.model_holdout_398.status(); checks['minimum_50']=st['bundled_fixture_cases']>=50; checks['requires_real_model']=st['external_real_model_required_for_qualification']; checks['requires_human']=st['human_review_required_for_qualification']; checks['no_network']=not st['direct_network_fetch']; checks['no_execution']=not st['execution_authority']; checks['no_auto_go']=not st['automatic_go']; checks['no_auto_evidence']=not st['automatic_evidence_promotion']; checks['no_truth_training']=not st['truth_probability_training']
            s=c.model_holdout_398.create_reference_suite(); checks['sixty_distinct']=s['case_count']==60 and len(c.db.all('SELECT case_id FROM holdout_case_398 WHERE suite_id=?',(s['suite_id'],)))==60
            try:c.model_holdout_398.freeze_suite(suite_id=s['suite_id'],identity=a,confirmation='YES'); checks['exact_freeze']=False
            except PermissionError: checks['exact_freeze']=True
            s=c.model_holdout_398.freeze_suite(suite_id=s['suite_id'],identity=a,confirmation=CONFIRM_FREEZE_SUITE); checks['frozen']=s['status']=='frozen'
            cases=[r['case_id'] for r in c.db.all('SELECT case_id FROM holdout_case_398 WHERE suite_id=? ORDER BY case_id',(s['suite_id'],))]
            runs=[c.model_holdout_398.record_deterministic_reference(suite_id=s['suite_id'],case_id=x) for x in cases]
            checks['reference_runs_60']=len(runs)==60; checks['reference_scores']=all(float(r['structural_score'])==1 for r in runs)
            b=c.model_holdout_398.freeze_internal_baseline(suite_id=s['suite_id'],identity=a,confirmation=CONFIRM_FREEZE_BASELINE); checks['baseline_frozen']=b['run_count']==60 and all(v==1 for v in b['metrics'].values())
            q=c.model_holdout_398.qualification_status(); checks['external_pending_truthful']=q['real_model_runs']==0 and q['human_reviewed_cases']==0 and not q['external_holdout_qualified']
            case=c.model_holdout_398._case(s['suite_id'],cases[0]); out=c.model_holdout_398.deterministic_reference_output(case)
            try:c.model_holdout_398.record_external_model_run(suite_id=s['suite_id'],case_id=cases[0],adapter_id='test',model_id='test',output=out,execution_receipt='x',identity=a,confirmation='YES'); checks['exact_external_import']=False
            except PermissionError: checks['exact_external_import']=True
            er=c.model_holdout_398.record_external_model_run(suite_id=s['suite_id'],case_id=cases[0],adapter_id='acceptance-test-import',model_id='fixture-model',output=out,execution_receipt='acceptance-test-only',identity=a,confirmation=CONFIRM_EXTERNAL_RUN)
            scores={k:5 for k in ('evidence_grounding','counterevidence_handling','uncertainty_handling','actionability','governance')}
            c.model_holdout_398.submit_human_review(run_id=runs[0]['run_id'],identity=a,blind_review=True,scores=scores,harmful_overreach=False,notes='reference-only review',confirmation=CONFIRM_HUMAN_REVIEW)
            q=c.model_holdout_398.qualification_status(); checks['reference_review_not_external']=q['human_reviewed_external_cases']==0 and not q['external_holdout_qualified']
            c.model_holdout_398.submit_human_review(run_id=er['run_id'],identity=a,blind_review=True,scores=scores,harmful_overreach=False,notes='external-import gate test only',confirmation=CONFIRM_HUMAN_REVIEW)
            q=c.model_holdout_398.qualification_status(); checks['one_external_case_not_enough']=q['human_reviewed_external_cases']==1 and not q['external_holdout_qualified']
            checks['integrity']=c.model_holdout_398.verify_integrity(s['suite_id'])['valid']; fp=c.build398.code_fingerprint()
    result='pass' if all(checks.values()) else 'fail'; payload={'build':'398.0','result':result,'checks':checks,'checks_passed':sum(checks.values()),'checks_total':len(checks),'external_holdout_qualified':False,'real_model_runs_in_release_evidence':0,'human_reviewed_cases_in_release_evidence':0,'code_fingerprint':fp}; Path('ACCEPTANCE_RESULTS_BUILD_398_0.json').write_text(json.dumps(payload,indent=2,sort_keys=True)); print(json.dumps(payload,indent=2,sort_keys=True)); return 0 if result=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
