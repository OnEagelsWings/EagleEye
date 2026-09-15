from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='ee375-accept-') as d:
        with AppContext(base_dir=d,actor='accept375') as c:
            g=c.build375.qualified_gate();checks=dict(g['checks']);checks.update({'crawler_increment_375':c.build375.crawler_status().get('crawler_improvement_build')==375,'continuous_crawler_program':bool(c.build375.crawler_status().get('continuous_crawler_expansion_370_380')),'automatic_ai_execution_false':c.build375.crawler_status().get('automatic_ai_crawl_execution') is False,'production_release_false':g.get('production_release_ready') is False,'external_ai_eval_not_claimed':g.get('external_ai_investigation_eval')=='not_run','external_real_case_not_claimed':g.get('external_real_case_planning_eval')=='not_run'});passed=sum(bool(v) for v in checks.values());out={'build':'375.0','code_fingerprint':c.build375.code_fingerprint(),'checks':checks,'passed':passed,'total':len(checks),'result':'pass' if passed==len(checks) else 'fail','build_acceptance_ready':all(bool(v) for v in g['checks'].values()),'production_release_ready':False,'schema':c.build375.schema_metrics(),'version':c.build375.version_status()}
    (root/'ACCEPTANCE_RESULTS_BUILD_375_0.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,indent=2,sort_keys=True));return 0 if out['result']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
