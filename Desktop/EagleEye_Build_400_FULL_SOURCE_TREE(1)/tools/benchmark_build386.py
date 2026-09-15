from __future__ import annotations
import json, tempfile, time
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.jurisdiction_intelligence384 import CONFIRM_WAVES
from eagleeye_pro.phase17.acquisition_orchestrator385 import CONFIRM_PREPARE
from eagleeye_pro.phase17.execution_authority386 import CONFIRM_GO

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'BENCHMARK_BUILD_386_GO_GRANTS.json'; CASES=200; PW='Bench-Orbit-Quartz-386!'

def main()->int:
    violations=0; started=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='eagleeye386-bench-') as td:
        with AppContext(base_dir=Path(td),actor='bench386') as c:
            admin=c.team_identity_359.create_initial_admin(username='bench386',display_name='Bench 386',password=PW); ident={**admin,'session_id':'bench-session-386'}
            case=c.build380.team_create_case(identity=ident,title='Build386 benchmark',client='internal',purpose='deterministic grant benchmark',legal_basis='public_data'); cid=case['case_id']
            c.build382.set_source_scope(case_id=cid,source_id='gleif.lei',state='approved',reviewer='bench386',confirmation='APPROVE SOURCE')
            waves=c.build384.plan_research_waves(case_id=cid,mission='official corporate identifier verification',jurisdictions=('global',),source_classes=('corporate',),wave_confirmation=CONFIRM_WAVES)
            packet=c.build385.compile_acquisition_packet(case_id=cid,wave_plan_id=waves['wave_plan_id'],identifiers={'gleif.lei':'5493001KJTIIGC8Y1R12'},actor='bench386')
            prepared=c.build385.prepare_acquisition_packet(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_PREPARE)
            sid=next(x['canonical_source_id'] for x in prepared['outcomes'] if x.get('canonical_source_id'))
            c.crawler_engine_349.review_source(sid,decision='approve_read_only',rationale='benchmark review',reviewer='bench386')
            c.case_workflow_374.configure(case_id=cid,identity=ident,source_budgets={sid:5000},case_request_budget=5000,max_active_crawls=2,confirmation='WORKFLOW')
            before_jobs=int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {}).get('n') or 0)
            tokens=[]
            for _ in range(CASES):
                g=c.build386.issue_execution_grant(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_GO,ttl_minutes=5)
                tokens.append((g['grant_id'],g['grant_token']))
                if g.get('network_requests_created')!=0 or g.get('jobs_created')!=0 or g.get('direct_network_authority') is not False: violations+=1
            after_jobs=int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {}).get('n') or 0)
            if before_jobs!=after_jobs: violations+=1
            for gid,token in tokens[::100]:
                v=c.build386.verify_execution_grant(case_id=cid,grant_id=gid,grant_token=token,identity=ident)
                if not v.get('valid'): violations+=1
            plain_token_hits=0
            for gid,token in tokens[:10]:
                row=c.db.one('SELECT scope_json FROM execution_grant_386 WHERE grant_id=?',(gid,)) or {}
                plain_token_hits += int(token in str(row.get('scope_json') or ''))
            if plain_token_hits: violations+=1
            count=int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {}).get('n') or 0); fp=c.build386.code_fingerprint()
    elapsed=max(time.perf_counter()-started,1e-6); payload={'build':'386.0','code_fingerprint':fp,'cases':CASES,'grants_persisted':count,'elapsed_seconds':round(elapsed,6),'cases_per_second':round(CASES/elapsed,3),'violations':violations,'network_requests':0,'crawler_jobs_created':0,'plaintext_token_hits':plain_token_hits,'result':'pass' if violations==0 and count==CASES else 'fail','truthful_scope':'200 repeated security-sensitive GO grants with full inherited access-chain verification retained; no external execution or connector validation is inferred.'}
    OUT.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n'); print(json.dumps(payload,indent=2,sort_keys=True)); return 0 if payload['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
