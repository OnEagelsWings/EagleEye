from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

CASES=4600

def main():
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='ee375-bench-') as d:
        with AppContext(base_dir=d,actor='bench375') as c:
            hold=c.ai_crawl_planning_eval_375.load_holdout()['scenarios'];viol=0;passed=0;cats={k:{'cases':0,'passed':0,'violations':0} for k in ['allow','scope','budget','workflow','backpressure','special','source','hold','caps','truthfulness']}
            for i in range(CASES):
                sc=hold[i%len(hold)];out=c.ai_crawl_planning_eval_375.evaluate_snapshot(sc['snapshot'],sc['proposal']);allowed=out['decision']=='allow_for_human_confirmation';ok=(allowed==(sc['expected']=='allow')) and out['network_execution'] is False and out['automatic_execution_authority'] is False
                tags=set(sc.get('tags') or []);cat='allow' if sc['expected']=='allow' else ('scope' if 'scope_expansion' in tags else 'budget' if 'budget' in tags else 'workflow' if 'workflow_state' in tags else 'backpressure' if 'backpressure' in tags else 'special' if 'special_gate' in tags else 'hold' if 'hold' in tags else 'source')
                if i%17==0:cat='caps';ok=ok and c.ai_crawl_planning_eval_375.status()['max_ai_plan_requests']==60
                if i%23==0:cat='truthfulness';ok=ok and c.build375.qualified_gate()['production_release_ready'] is False
                cats[cat]['cases']+=1;cats[cat]['passed']+=int(ok);cats[cat]['violations']+=int(not ok);passed+=int(ok);viol+=int(not ok)
            out={'build':'375.0','code_fingerprint':c.build375.code_fingerprint(),'cases':CASES,'passed':passed,'violations':viol,'result':'pass' if passed==CASES and viol==0 else 'fail','categories':cats,'network_used_by_benchmark':False,'external_validation_performed':False}
    (root/'BENCHMARK_BUILD_375_AI_INVESTIGATION_EVAL.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,indent=2,sort_keys=True));return 0 if out['result']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
