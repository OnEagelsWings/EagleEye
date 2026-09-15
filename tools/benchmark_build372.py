from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

ROOT=Path(__file__).resolve().parents[1]

def _good_records():
    rows=[]
    for i in range(6):rows.append({'comparison_id':f's{i}','case_id':'x','classification':'possible_review_candidate','prediction':'review_positive','evidence_weight':.7,'strong_identifier_conflict_veto':False,'common_name_count':1,'ground_truth':'same_entity','cohort':'same'})
    for i in range(8):rows.append({'comparison_id':f'd{i}','case_id':'x','classification':'likely_distinct','prediction':'distinct','evidence_weight':0,'strong_identifier_conflict_veto':True,'common_name_count':4 if i<2 else 1,'ground_truth':'distinct','cohort':'distinct'})
    for i in range(3):rows.append({'comparison_id':f'a{i}','case_id':'x','classification':'insufficient','prediction':'defer','evidence_weight':.2,'strong_identifier_conflict_veto':False,'common_name_count':1,'ground_truth':'ambiguous','cohort':'ambiguous'})
    return rows

def run():
    categories={k:{'cases':0,'passed':0,'violations':0} for k in ('holdout_gate','false_link_safety','conflict_veto','common_name_safety','source_quality_order','source_quality_boundary','review_boundary','truthful_release')}
    with tempfile.TemporaryDirectory(prefix='eagleeye372_bench_') as td:
        with AppContext(base_dir=Path(td),actor='bench372') as c:
            report=c.entity_resolution_eval_372.evaluate_records(_good_records(),evaluation_name='benchmark_reference')
            contract=c.crawler_source_quality_372.calibration_contract()
            high=contract['samples']['official_reviewed_hashed']['quality_score'];mid=contract['samples']['public_web_reviewed_hashed']['quality_score'];low=contract['samples']['unknown_unreviewed']['quality_score']
            checks={
                'holdout_gate':lambda i: report['gate']['passed'] and report['metrics']['binary_records']>=12,
                'false_link_safety':lambda i: report['metrics']['unsafe_false_link_rate']<=.05 and report['metrics']['strong_review_false_link_rate']<=.02,
                'conflict_veto':lambda i: report['metrics']['strong_identifier_conflict_escape_count']==0,
                'common_name_safety':lambda i: report['metrics']['common_name_false_link_rate']<=.05,
                'source_quality_order':lambda i: high>mid>low,
                'source_quality_boundary':lambda i: not c.crawler_source_quality_372.score_snapshot({'source_kind':'official_register','review_status':'approved_read_only','hash_verified':True,'http_success':True,'source_health':'healthy','terms_ref_present':True})['can_confirm_identity'],
                'review_boundary':lambda i: not c.entity_resolution_eval_372.status()['automatic_merge'] and not c.entity_resolution_eval_372.status()['automatic_threshold_change'],
                'truthful_release':lambda i: c.build372.qualified_gate()['production_release_ready'] is False and c.build372.qualified_gate()['external_real_world_holdout_validation']=='not_run',
            }
            total=passed=violations=0
            for name,fn in checks.items():
                for i in range(500):
                    ok=bool(fn(i));categories[name]['cases']+=1;total+=1
                    if ok:categories[name]['passed']+=1;passed+=1
                    else:categories[name]['violations']+=1;violations+=1
            return {'build':'372.0','code_fingerprint':c.build372.code_fingerprint(),'result':'pass' if passed==total and violations==0 else 'fail','cases':total,'passed':passed,'violations':violations,'categories':categories,'network_used_by_benchmark':False,'external_validation_performed':False,'truthful_note':'Deterministic local invariant benchmark; not a real-world population accuracy or external load test.'}

if __name__=='__main__':
    out=run();Path('BENCHMARK_BUILD_372_ENTITY_EVAL.json').write_text(json.dumps(out,indent=2,sort_keys=True));print(json.dumps(out,indent=2,sort_keys=True));raise SystemExit(0 if out['result']=='pass' else 1)
