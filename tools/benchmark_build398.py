from __future__ import annotations
import json,tempfile,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from test_build394_integrated import ctx,admin
from eagleeye_pro.phase17.model_holdout398 import CONFIRM_FREEZE_SUITE,CONFIRM_FREEZE_BASELINE

def main():
    with tempfile.TemporaryDirectory(prefix='e398bench_') as td:
        with ctx(Path(td)) as c:
            a=admin(c); s=c.model_holdout_398.create_reference_suite(); s=c.model_holdout_398.freeze_suite(suite_id=s['suite_id'],identity=a,confirmation=CONFIRM_FREEZE_SUITE); cases=[r['case_id'] for r in c.db.all('SELECT case_id FROM holdout_case_398 WHERE suite_id=? ORDER BY case_id',(s['suite_id'],))]
            t=time.perf_counter(); runs=[c.model_holdout_398.record_deterministic_reference(suite_id=s['suite_id'],case_id=x) for x in cases]; elapsed=time.perf_counter()-t
            b=c.model_holdout_398.freeze_internal_baseline(suite_id=s['suite_id'],identity=a,confirmation=CONFIRM_FREEZE_BASELINE); integ=c.model_holdout_398.verify_integrity(s['suite_id']); q=c.model_holdout_398.qualification_status(); fp=c.build398.code_fingerprint()
    violations=0
    violations += int(len(runs)!=60 or any(float(r['structural_score'])!=1.0 for r in runs)); violations += int(not integ['valid']); violations += int(q['external_holdout_qualified'] or q['real_model_runs']!=0 or q['human_reviewed_cases']!=0); violations += int(any(v!=1.0 for v in b['metrics'].values()))
    payload={'build':'398.0','result':'pass' if violations==0 else 'fail','cases':60,'deterministic_reference_runs':len(runs),'violations':violations,'elapsed_seconds':round(elapsed,6),'reference_runs_per_second':round(len(runs)/elapsed,3),'baseline_metrics':b['metrics'],'real_model_runs':0,'human_reviewed_cases':0,'external_holdout_qualified':False,'scope':'internal deterministic structural baseline only; not a real-model or human-reviewed qualification','code_fingerprint':fp}; Path('BENCHMARK_BUILD_398_HOLDOUT.json').write_text(json.dumps(payload,indent=2,sort_keys=True)); print(json.dumps(payload,indent=2,sort_keys=True)); return 0 if violations==0 else 1
if __name__=='__main__': raise SystemExit(main())
