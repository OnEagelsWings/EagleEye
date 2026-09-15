from __future__ import annotations
import json,tempfile,time
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.final_acceptance400 import CONFIRM_RUN
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as d:
    with AppContext(base_dir=Path(d),actor='benchmark400') as c:
        a=c.team_identity_359.create_initial_admin(username='bench400',display_name='Performance User',password='Build400-Perf-Z9!');a={**a,'session_id':'bench'}
        n=500;viol=0;t=time.perf_counter()
        for _ in range(n):
            r=c.build400.run_phase17_acceptance(identity=a,confirmation=CONFIRM_RUN)
            if not r['internal_acceptance'] or r['production_release_ready'] or r['passed_steps']!=19:viol+=1
        elapsed=time.perf_counter()-t
        out={'build':'400.0','code_fingerprint':c.build400.code_fingerprint(),'result':'pass' if viol==0 else 'fail','runs':n,'violations':viol,'elapsed_seconds':elapsed,'runs_per_second':n/elapsed if elapsed else 0,'automatic_go':0,'automatic_live':0,'network_fetches':0,'production_releases':0}
ROOT.joinpath('BENCHMARK_BUILD_400_FINAL_ACCEPTANCE.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
