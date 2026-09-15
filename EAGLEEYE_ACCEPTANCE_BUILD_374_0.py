from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='ee374-accept-') as d:
        with AppContext(base_dir=d,actor='accept374') as c:
            g=c.build374.qualified_gate();checks=dict(g['checks']);checks.update({'crawler_increment_374':c.build374.crawler_status().get('crawler_improvement_build')==374,'continuous_crawler_program':bool(c.build374.crawler_status().get('continuous_crawler_expansion_370_380')),'production_release_false':g.get('production_release_ready') is False,'external_workflow_not_claimed':g.get('external_case_workflow_validation')=='not_run','external_handoff_not_claimed':g.get('external_analyst_handoff_validation')=='not_run'})
            passed=sum(bool(v) for v in checks.values());out={'build':'374.0','code_fingerprint':c.build374.code_fingerprint(),'checks':checks,'passed':passed,'total':len(checks),'result':'pass' if passed==len(checks) else 'fail','build_acceptance_ready':all(bool(v) for v in g['checks'].values()),'production_release_ready':False,'schema':c.build374.schema_metrics(),'version':c.build374.version_status()}
    (root/'ACCEPTANCE_RESULTS_BUILD_374_0.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,indent=2,sort_keys=True));return 0 if out['result']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
