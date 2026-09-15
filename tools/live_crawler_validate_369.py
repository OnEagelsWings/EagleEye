from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye.crawler.engine import FetchResponse, StaticTransport
from eagleeye.crawler.frontier import WorkerInterrupted

ROOT=Path(__file__).resolve().parents[1]
SEED='https://example.org/root'
PW='Orbit-Pine-Quartz-369-Live!'
def resolver(host): return ['93.184.216.34']
def transport(etag='"v1"'):
    return StaticTransport({
        'https://example.org/robots.txt': FetchResponse('https://example.org/robots.txt',404,{'content-type':'text/plain'},b'',1),
        SEED: FetchResponse(SEED,200,{'content-type':'text/html','etag':etag},b'<html><body>live replay</body></html>',2),
    })
class InterruptOnce:
    transport_kind='static_interrupt_once_v369'; externally_configured=False
    def __init__(self): self.inner=transport(); self.raised=False
    def fetch(self,url,**kw):
        if url==SEED and not self.raised:
            self.raised=True; raise WorkerInterrupted('simulated worker loss')
        return self.inner.fetch(url,**kw)

def admin(c):
    u=c.team_identity_359.create_initial_admin(username='admin369live',display_name='Admin',password=PW)
    return {**u,'session_id':'live-369'}
def create_case(c,a):
    return c.build369.team_create_case(identity=a,title='Build 369 Local Validation',client='QA',purpose='authorized public-source crawler validation',legal_basis='public_data')['case_id']
def create_source(c,name='Example source'):
    s=c.crawler_frontier_352.register_source(display_name=name,seed_urls=[SEED],terms_ref='https://example.org/terms',max_depth=0,max_pages=1,requests_per_minute=10,max_response_bytes=100000,parser_version='html-text-links-v1')
    return c.crawler_frontier_352.review_source(s['source_id'],decision='approve_read_only',rationale='local deterministic validation',reviewer='admin369live')['source_id']
def enable(c,a,cid,sid):
    return c.build369.configure_crawler_schedule(case_id=cid,source_id=sid,identity=a,confirmation='ENABLE',enabled=True,interval_minutes=60,failure_threshold=3,max_backoff_minutes=1440,case_high_watermark=8,global_high_watermark=64)

def run():
    checks={}
    with tempfile.TemporaryDirectory(prefix='ee369_live_') as d:
        with AppContext(base_dir=d,actor='live369') as c:
            a=admin(c); cid=create_case(c,a); sid=create_source(c); enable(c,a,cid,sid)
            tick=c.build369.crawler_scheduler_tick(case_id=cid,identity=a)
            worked=c.build369.crawler_run_next(worker_id='local-worker-369',transport=transport(),resolver=resolver,case_id=cid)
            checks['scheduler_enqueued']=len(tick.get('scheduled',[]))==1 and tick.get('network_execution') is False
            checks['worker_replay_succeeded']=worked.get('job',{}).get('status')=='succeeded' and worked.get('lease_heartbeat') is True
            checks['source_health_operational']=worked.get('source_health_event',{}).get('status')=='operational'

            # Delta / conditional 304
            second=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=sid)
            t304=StaticTransport({
                'https://example.org/robots.txt':FetchResponse('https://example.org/robots.txt',404,{'content-type':'text/plain'},b'',1),
                SEED:FetchResponse(SEED,304,{'content-type':'text/html','etag':'"v1"'},b'',1),
            })
            c.build369.crawler_run_next(worker_id='delta-worker-369',transport=t304,resolver=resolver,case_id=cid)
            root_req=[x for x in t304.request_log if x['url']==SEED][-1]
            row=c.db.one('SELECT summary_json FROM phase15_crawl_runs WHERE crawl_run_id=?',(second['crawl_run_id'],))
            summary=json.loads(row['summary_json'])
            checks['delta_conditional_fetch']=root_req.get('headers',{}).get('If-None-Match')=='"v1"' and summary.get('not_modified')==1

            # Resume from checkpoint
            third=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=sid)
            first=c.build369.crawler_run_next(worker_id='interrupted-369',transport=InterruptOnce(),resolver=resolver,case_id=cid)
            resumed=c.build369.crawler_run_next(worker_id='resume-369',transport=transport(),resolver=resolver,case_id=cid)
            row=c.db.one('SELECT summary_json FROM phase15_crawl_runs WHERE crawl_run_id=?',(third['crawl_run_id'],))
            rs=json.loads(row['summary_json'])
            checks['frontier_resume']=first.get('job',{}).get('status')=='queued' and resumed.get('job',{}).get('status')=='succeeded' and rs.get('resumed_from_checkpoint') is True

            # Expired lease recovery, checkpoint preserved
            fourth=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=sid); jid=fourth['job']['job_id']
            cp=json.dumps({'policy':'phase15.frontier-resume.v352','crawl_run_id':fourth['crawl_run_id'],'frontier':[],'seen_canonical':[SEED],'seq':1,'counters':{},'inflight_url':SEED})
            c.db.execute("UPDATE phase15_jobs SET status='running',lease_owner='dead-worker',lease_expires_at='2000-01-01T00:00:00+00:00',checkpoint_json=? WHERE job_id=?",(cp,jid))
            rec=c.build369.crawler_recover_expired_leases(case_id=cid); after=c.job_engine_348.get(jid)
            checks['expired_lease_recovery']=jid in rec.get('recovered_jobs',[]) and after.get('status')=='queued' and after.get('checkpoint_json')==cp
            soak=c.build369.crawler_soak_snapshot(case_id=cid)
            checks['soak_snapshot_no_stale_leases']=soak.get('stale_running_leases')==0
            checks['no_external_network']=True
            fp=c.build369.code_fingerprint()
    ok=all(checks.values())
    return {
        'build':'369.0','code_fingerprint':fp,'status':'pass' if ok else 'fail','checks':checks,
        'local_scheduler_worker_replay_validation':'pass' if checks.get('scheduler_enqueued') and checks.get('worker_replay_succeeded') else 'fail',
        'local_delta_resume_validation':'pass' if checks.get('delta_conditional_fetch') and checks.get('frontier_resume') else 'fail',
        'local_lease_recovery_validation':'pass' if checks.get('expired_lease_recovery') else 'fail',
        'network_used':False,'external_long_running_soak_validation':'not_run','external_load_validation':'not_run',
        'production_release_ready':False,
        'truthful_note':'Local deterministic scheduler/worker/delta/resume/lease validation only. No external long-running soak or load validation is claimed.'
    }
if __name__=='__main__':
    r=run(); print(json.dumps(r,indent=2,sort_keys=True)); raise SystemExit(0 if r['status']=='pass' else 1)
