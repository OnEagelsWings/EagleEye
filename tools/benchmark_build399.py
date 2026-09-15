from __future__ import annotations
import json,tempfile,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from test_build394_integrated import ctx,admin
from test_build399_integrated import plan,side_counts399
from eagleeye_pro.phase17.target_soak399 import CONFIRM_INTERNAL_SIM

def main():
    n=1000
    with tempfile.TemporaryDirectory(prefix='e399bench_') as td:
        with ctx(Path(td)) as c:
            a=admin(c); p=plan(c,a); before=side_counts399(c); c.target_soak_399.record_internal_framework_simulation(plan_id=p['plan_id'],identity=a,confirmation=CONFIRM_INTERNAL_SIM); t=time.perf_counter(); valid=0
            for _ in range(n):
                q=c.target_soak_399.qualification_status(); valid+=int(not q['external_72h_soak_qualified'] and q['external_sessions']==0)
            elapsed=time.perf_counter()-t; after=side_counts399(c); fp=c.build399.code_fingerprint()
    violations=(0 if valid==n else 1)+(0 if before==after else 1); payload={'build':'399.0','result':'pass' if violations==0 else 'fail','iterations':n,'framework_status_checks_valid':valid,'violations':violations,'elapsed_seconds':round(elapsed,6),'checks_per_second':round(n/elapsed,3),'external_72h_soak_qualified':False,'live_72h_sessions':0,'crawler_jobs_created':after['phase15_jobs']-before['phase15_jobs'],'go_grants_created':after['execution_grant_386']-before['execution_grant_386'],'evidence_promotions_created':after['evidence_candidate_promotion_389']-before['evidence_candidate_promotion_389'],'scope':'internal soak-framework benchmark only; not a 72-hour live test','code_fingerprint':fp}; Path('BENCHMARK_BUILD_399_SOAK_FRAMEWORK.json').write_text(json.dumps(payload,indent=2,sort_keys=True)); print(json.dumps(payload,indent=2,sort_keys=True)); return 0 if violations==0 else 1
if __name__=='__main__': raise SystemExit(main())
