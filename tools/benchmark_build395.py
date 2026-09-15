from __future__ import annotations
import json,tempfile,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'tests')]
from test_build394_integrated import ctx,admin,case,setup,side_counts
from test_build395_integrated import make_claim_version
from eagleeye_pro.phase17.case_state_graph395 import CONFIRM_BRANCH,CONFIRM_STAGE

def main():
  n=1000; violations=[]
  with tempfile.TemporaryDirectory() as d:
    with ctx(Path(d)) as c:
      a=admin(c); cid=case(c,a)['case_id']; cl,*rest=setup(c,a,cid); disc=rest[-1]; v=make_claim_version(c,a,cid,cl,disc,'benchmark')
      s=c.build395.active_case_state(case_id=cid,target_type='claim',target_id=cl['claim_id'],identity=a); before=side_counts(c); t=time.perf_counter()
      for i in range(n):
        if i%2==0:
          x=c.build395.compare_case_state_nodes(case_id=cid,target_type='claim',target_id=cl['claim_id'],left_node_id=s['active_node_id'],right_node_id=v['version_id'])
          if x['execution_authority'] or x['truth_determined']: violations.append(f'compare:{i}')
        else:
          x=c.build395.active_case_state(case_id=cid,target_type='claim',target_id=cl['claim_id'])
          if x['generation']!=0: violations.append(f'state:{i}')
      elapsed=time.perf_counter()-t; after=side_counts(c); violations += ([] if before==after else ['side_effect_counts_changed']); fp=c.build395.code_fingerprint()
  out={'build':'395.0','result':'pass' if not violations else 'fail','operations':n,'violations':len(violations),'violation_samples':violations[:20],'elapsed_seconds':round(elapsed,6),'operations_per_second':round(n/elapsed,3),'code_fingerprint':fp,'network_requests_created':0,'jobs_created':0,'go_grants_created':0,'evidence_promotions_created':0}
  (ROOT/'BENCHMARK_BUILD_395_CASE_STATE.json').write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(out,indent=2,sort_keys=True)); return 0 if out['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
