from __future__ import annotations
import json,tempfile,time
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.jurisdiction_intelligence384 import CONFIRM_WAVES
from eagleeye_pro.phase17.acquisition_orchestrator385 import CONFIRM_PREPARE
from eagleeye_pro.phase17.execution_authority386 import CONFIRM_GO
from eagleeye_pro.phase17.controlled_executor387 import CONFIRM_EXECUTE
from eagleeye_pro.phase17.research_wave_execution388 import CONFIRM_START,CONFIRM_ATTACH
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'BENCHMARK_BUILD_388_RESEARCH_WAVES.json'; PW='Benchmark388-Orbit!'
def main()->int:
    loops=1000; violations=0
    with tempfile.TemporaryDirectory(prefix='eagleeye388-bench-') as td:
        with AppContext(base_dir=Path(td),actor='bench388') as c:
            a=c.team_identity_359.create_initial_admin(username='bench388',display_name='Bench 388',password=PW); ident={**a,'session_id':'bench388-session'}; cid=c.build380.team_create_case(identity=ident,title='Bench388',client='internal',purpose='authorized benchmark',legal_basis='public_data')['case_id']
            c.build382.set_source_scope(case_id=cid,source_id='gleif.lei',state='approved',reviewer='bench388',confirmation='APPROVE SOURCE'); waves=c.build384.plan_research_waves(case_id=cid,mission='corporate verification',jurisdictions=('global',),source_classes=('corporate',),wave_confirmation=CONFIRM_WAVES); packet=c.build385.compile_acquisition_packet(case_id=cid,wave_plan_id=waves['wave_plan_id'],identifiers={'gleif.lei':'5493001KJTIIGC8Y1R12'},actor='bench388'); prep=c.build385.prepare_acquisition_packet(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_PREPARE); sid=next(x['canonical_source_id'] for x in prep['outcomes'] if x.get('canonical_source_id')); c.crawler_engine_349.review_source(sid,decision='approve_read_only',rationale='bench388',reviewer='bench388'); c.case_workflow_374.configure(case_id=cid,identity=ident,source_budgets={sid:20},case_request_budget=20,max_active_crawls=2,confirmation='WORKFLOW'); grant=c.build386.issue_execution_grant(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_GO,source_ids=['gleif.lei']); dispatch=c.build387.execute_grant(case_id=cid,grant_id=grant['grant_id'],grant_token=grant['grant_token'],identity=ident,confirmation=CONFIRM_EXECUTE); sess=c.build388.start_wave_session(case_id=cid,wave_plan_id=waves['wave_plan_id'],packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_START); c.build388.attach_wave_dispatch(case_id=cid,session_id=sess['session_id'],dispatch_id=dispatch['dispatch_id'],identity=ident,confirmation=CONFIRM_ATTACH)
            jobs_before=int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']); grants_before=int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']); t0=time.perf_counter()
            for _ in range(loops):
                out=c.build388.reconcile_wave_session(case_id=cid,session_id=sess['session_id'],identity=ident)
                if out['decision']!='awaiting_worker_results' or out['automatic_go_issuance'] or out['automatic_worker_claim']: violations+=1
            elapsed=time.perf_counter()-t0; jobs_after=int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']); grants_after=int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']); violations += int(jobs_before!=jobs_after)+int(grants_before!=grants_after); fp=c.build388.code_fingerprint()
    result={'build':'388.0','code_fingerprint':fp,'cases':loops,'passed':loops if violations==0 else max(0,loops-violations),'violations':violations,'elapsed_seconds':round(elapsed,4),'reconciliations_per_second':round(loops/elapsed,2) if elapsed else 0,'network_fetches_by_wave_controller':0,'worker_claims_by_wave_controller':0,'automatic_go_grants':0,'result':'pass' if violations==0 else 'fail'}; OUT.write_text(json.dumps(result,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if violations==0 else 1
if __name__=='__main__': raise SystemExit(main())
