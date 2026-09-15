from __future__ import annotations
import json,tempfile,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from test_build394_integrated import ctx,admin,case,setup,side_counts
from test_build396_integrated import prepare_active

def main():
    n=1000
    with tempfile.TemporaryDirectory(prefix='e397bench_') as td:
        with ctx(Path(td)) as c:
            a=admin(c); cid=case(c,a)['case_id']; cl,h1,h2,ws,plan,*_=setup(c,a,cid); prepare_active(c,a,cid,cl,h1,h2,plan); before=side_counts(c); t=time.perf_counter(); valid=0
            for _ in range(n):
                x=c.build397.assess_argumentation(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a); valid += int(c.argumentative_analyst_397.verify_assessment(case_id=cid,assessment_id=x['assessment_id'])['valid'])
            elapsed=time.perf_counter()-t; after=side_counts(c); violations=(0 if valid==n else 1)+(0 if before==after else 1); fp=c.build397.code_fingerprint()
    payload={'build':'397.0','result':'pass' if violations==0 else 'fail','cases':n,'assessments_valid':valid,'violations':violations,'elapsed_seconds':round(elapsed,6),'assessments_per_second':round(n/elapsed,3),'crawler_jobs_created':after['phase15_jobs']-before['phase15_jobs'],'go_grants_created':after['execution_grant_386']-before['execution_grant_386'],'evidence_promotions_created':after['evidence_candidate_promotion_389']-before['evidence_candidate_promotion_389'],'truth_probability_assignments':0,'scope':'local deterministic argumentative analyst assessment; no external model qualification inferred','code_fingerprint':fp}; Path('BENCHMARK_BUILD_397_ANALYST.json').write_text(json.dumps(payload,indent=2,sort_keys=True)); print(json.dumps(payload,indent=2,sort_keys=True)); return 0 if violations==0 else 1
if __name__=='__main__':raise SystemExit(main())
