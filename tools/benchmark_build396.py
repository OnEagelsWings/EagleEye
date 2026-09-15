from __future__ import annotations
import hashlib, json, secrets, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tests'))
from test_build394_integrated import ctx, admin, case, setup
from test_build396_integrated import prepare_active
from eagleeye_pro.phase17.case_reconciliation396 import CONFIRM_BASELINE


def main() -> int:
    n=1000
    with tempfile.TemporaryDirectory(prefix='eagleeye396_bench_') as td:
        with ctx(Path(td)) as c:
            a=admin(c); cid=case(c,a)['case_id']; cl,h1,h2,ws,plan,*_=setup(c,a,cid); prepare_active(c,a,cid,cl,h1,h2,plan)
            b=c.build396.create_reconciliation_baseline(case_id=cid,identity=a,confirmation=CONFIRM_BASELINE)
            now='2026-09-14T12:00:00+00:00'
            for i in range(n):
                raw=f'build396-benchmark-{i}'.encode(); oid=f'obj396bench_{i:04d}_{secrets.token_hex(3)}'; sha=hashlib.sha256(raw).hexdigest()
                c.db.execute("INSERT INTO phase15_objects(object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,cid,'','canon_bench','local',oid,sha,len(raw),'application/json','review_pending','{}','bench396',now,hashlib.sha256(raw+b'r').hexdigest()))
                obj={'object_id':oid,'sha256':sha,'media_type':'application/json','security_state':'review_pending'}
                rr={'wave_number':1,'phase17_source_id':'internet_archive.metadata','canonical_source_id':'canon_bench','dispatch_id':'d'+oid,'job_id':'j'+oid,'crawl_run_id':'c'+oid,'search_run_id':'s'+oid}
                c.result_intake_389._insert_candidate(case_id=cid,session_id='bench396',result_row=rr,obj=obj,parse_run_id='p'+oid,record_index=0,candidate_type='normalized_record',normalized={'benchmark_index':i,'unrelated':'review material'},provenance={})
            before={
                'jobs':int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),
                'grants':int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),
                'promotions':int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']),
            }
            t0=time.perf_counter(); scan=c.build396.reconcile_case_state(case_id=cid,baseline_id=b['baseline_id'],identity=a); elapsed=time.perf_counter()-t0
            after={
                'jobs':int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),
                'grants':int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),
                'promotions':int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']),
            }
            recognized=sum(1 for x in scan['signals'] if x['signal_type']=='evidence_candidate')
            violations=0
            if recognized!=n: violations+=1
            if before!=after: violations+=1
            if scan['impact_count']!=0: violations+=1
            if not c.case_reconciliation_396.verify_scan(case_id=cid,scan_id=scan['scan_id'])['valid']: violations+=1
            fp=c.build396.code_fingerprint()
    payload={'build':'396.0','result':'pass' if violations==0 else 'fail','cases':n,'signals_reconciled':recognized,'violations':violations,'elapsed_seconds':round(elapsed,6),'signals_per_second':round(n/elapsed,3) if elapsed else 0,'network_requests_created':0,'crawler_jobs_created':after['jobs']-before['jobs'],'go_grants_created':after['grants']-before['grants'],'evidence_promotions_created':after['promotions']-before['promotions'],'impact_count':0,'scope':'local deterministic delta reconciliation of evidence-candidate signals only; no external execution inferred','code_fingerprint':fp}
    Path('BENCHMARK_BUILD_396_RECONCILIATION.json').write_text(json.dumps(payload,indent=2,sort_keys=True),encoding='utf-8')
    print(json.dumps(payload,indent=2,sort_keys=True))
    return 0 if violations==0 else 1

if __name__=='__main__': raise SystemExit(main())
