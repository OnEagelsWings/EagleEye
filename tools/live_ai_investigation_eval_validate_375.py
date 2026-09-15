from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='ee375-eval-') as d:
        with AppContext(base_dir=d,actor='validate375') as c:
            h=c.ai_crawl_planning_eval_375.run_holdout();out={"build":"375.0","code_fingerprint":c.build375.code_fingerprint(),"local_ai_planning_eval":"pass" if h["result"]=="pass" else "fail","synthetic":True,"external_network_used":False,"real_case_data_used":False,"metrics":h["metrics"],"gates":h["gates"],"external_real_case_planning_eval":"not_run","truthful_note":"Synthetic deterministic planning holdout only; this is not external model or professional analyst validation."}
    (root/'LIVE_VALIDATION_BUILD_375_AI_INVESTIGATION_EVAL.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,indent=2,sort_keys=True));return 0 if out['local_ai_planning_eval']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
