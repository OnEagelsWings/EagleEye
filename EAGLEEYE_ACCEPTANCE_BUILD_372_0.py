from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

ROOT=Path(__file__).resolve().parent

def read(name):
    try:return json.loads((ROOT/name).read_text())
    except Exception:return {}

def run():
    with tempfile.TemporaryDirectory(prefix='eagleeye372_accept_') as td:
        with AppContext(base_dir=Path(td),actor='accept372') as c:
            _=c.build372
            gate=c.build372.qualified_gate();m=c.build372.schema_metrics();v=c.build372.version_status();hold=read('LIVE_VALIDATION_BUILD_372_ENTITY_EVAL.json');bench=read('BENCHMARK_BUILD_372_ENTITY_EVAL.json');ev=read('BUILD_372_TEST_EVIDENCE.json')
            checks={
                'version_coherent':v['coherent'],
                'schema_within_gate':m['within_gate'],
                'schema_165_133_8':(m['table'],m['index'],m['trigger'])==(165,133,8),
                'no_build372_tables':m['build372_specific_tables_added']==0,
                'tests_55_55':ev.get('tests')=={'passed':55,'total':55},
                'regression_functional_47':(ev.get('regression_build371') or {}).get('passed')==47,
                'benchmark_4000':bench.get('cases')==4000 and bench.get('passed')==4000 and bench.get('violations')==0,
                'holdout_pass':hold.get('synthetic_holdout_validation')=='pass',
                'holdout_20':int((hold.get('metrics') or {}).get('records',0))>=20,
                'false_link_safe':float((hold.get('metrics') or {}).get('unsafe_false_link_rate',1))<=.05,
                'conflict_escape_zero':int((hold.get('metrics') or {}).get('strong_identifier_conflict_escape_count',1))==0,
                'precision_ge_090':float((hold.get('metrics') or {}).get('review_positive_precision',0))>=.90,
                'recall_ge_080':float((hold.get('metrics') or {}).get('same_entity_candidate_recall',0))>=.80,
                'source_quality_pass':hold.get('crawler_source_quality_validation')=='pass',
                'external_real_world_not_run':hold.get('external_real_world_holdout_validation')=='not_run',
                'no_real_person_data':hold.get('real_person_data_used') is False,
                'no_auto_threshold':c.entity_resolution_eval_372.status()['automatic_threshold_change'] is False,
                'no_auto_merge':c.entity_resolution_eval_372.status()['automatic_merge'] is False,
                'crawler_increment_372':c.build372.crawler_status()['crawler_improvement_build']==372,
                'continuous_crawler':c.build372.crawler_status()['continuous_crawler_expansion_370_380'],
                'gate_acceptance':gate['build_acceptance_ready'],
                'production_false':gate['production_release_ready'] is False,
            }
            return {'build':'372.0','result':'pass' if all(checks.values()) else 'fail','checks':checks,'passed':sum(bool(x) for x in checks.values()),'total':len(checks),'build_acceptance_ready':all(checks.values()),'production_release_ready':False,'schema':m,'version':v,'code_fingerprint':c.build372.code_fingerprint(),'external_real_world_holdout_validation':'not_run'}

if __name__=='__main__':
    out=run();Path('ACCEPTANCE_RESULTS_BUILD_372_0.json').write_text(json.dumps(out,indent=2,sort_keys=True));print(json.dumps(out,indent=2,sort_keys=True));raise SystemExit(0 if out['result']=='pass' else 1)
