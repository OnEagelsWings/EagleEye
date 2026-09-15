from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parent

def read(name):
    try:return json.loads((ROOT/name).read_text())
    except Exception:return {}

def run():
    with tempfile.TemporaryDirectory(prefix='eagleeye373_accept_') as td:
        with AppContext(base_dir=Path(td),actor='accept373') as c:
            _=c.build373;gate=c.build373.qualified_gate();m=c.build373.schema_metrics();v=c.build373.version_status();live=read('LIVE_VALIDATION_BUILD_373_GRAPH_UX.json');bench=read('BENCHMARK_BUILD_373_GRAPH_UX.json');ev=read('BUILD_373_TEST_EVIDENCE.json')
            checks={
                'version_coherent':v['coherent'],
                'schema_within_gate':m['within_gate'],
                'schema_165_133_8':(m['table'],m['index'],m['trigger'])==(165,133,8),
                'no_build373_tables':m['graph_projection_new_tables']==0 and m['graph_navigation_new_tables']==0,
                'tests_58_58':ev.get('tests')=={'passed':58,'total':58},
                'regression_functional_54':(ev.get('regression_build372') or {}).get('passed')==54,
                'benchmark_4200':bench.get('cases')==4200 and bench.get('passed')==4200 and bench.get('violations')==0,
                'local_graph_validation':live.get('local_graph_workflow_validation')=='pass',
                'graph_projection_live':(live.get('checks') or {}).get('graph_projection_live') is True,
                'crawler_edges_live':(live.get('checks') or {}).get('crawler_provenance_edge_live') is True,
                'focus_offline':(live.get('checks') or {}).get('focus_offline_live') is True,
                'navigation_plan_live':(live.get('checks') or {}).get('plan_allowed_live') is True,
                'navigation_tag_live':(live.get('checks') or {}).get('navigation_tag_live') is True,
                'navigation_bounded':(live.get('checks') or {}).get('navigation_bounded_live') is True,
                'external_graph_ux_not_run':live.get('external_graph_ux_validation')=='not_run',
                'external_graph_nav_not_run':live.get('external_graph_navigation_validation')=='not_run',
                'no_external_network':live.get('external_network_used') is False,
                'no_auto_merge':c.analyst_graph_373.status()['automatic_merge'] is False,
                'no_auto_scope':c.crawler_graph_navigation_373.status()['automatic_scope_expansion'] is False,
                'crawler_increment_373':c.build373.crawler_status()['crawler_improvement_build']==373,
                'continuous_crawler':c.build373.crawler_status()['continuous_crawler_expansion_370_380'],
                'gate_acceptance':gate['build_acceptance_ready'],
                'production_false':gate['production_release_ready'] is False,
            }
            return {'build':'373.0','result':'pass' if all(checks.values()) else 'fail','checks':checks,'passed':sum(bool(x) for x in checks.values()),'total':len(checks),'build_acceptance_ready':all(checks.values()),'production_release_ready':False,'schema':m,'version':v,'code_fingerprint':c.build373.code_fingerprint(),'external_graph_ux_validation':'not_run','external_graph_navigation_validation':'not_run'}

if __name__=='__main__':
    out=run();Path('ACCEPTANCE_RESULTS_BUILD_373_0.json').write_text(json.dumps(out,indent=2,sort_keys=True));print(json.dumps(out,indent=2,sort_keys=True));raise SystemExit(0 if out['result']=='pass' else 1)
