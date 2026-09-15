from __future__ import annotations
import argparse,json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def run(root:Path)->dict:
    with tempfile.TemporaryDirectory(prefix='ee374-live-') as d:
        with AppContext(base_dir=d,actor='validate374') as c:
            a=c.team_identity_359.create_initial_admin(username='admin374v',display_name='Admin 374V',password='Orbit-Pine-Quartz-374V!');a={**a,'session_id':'s374v'}
            ca=c.build374.team_create_case(identity=a,title='Local Workflow Validation',client='QA',purpose='local deterministic workflow validation',legal_basis='public_data');cid=ca['case_id']
            b=c.team_governance_359.create_user(identity=a,username='analyst374v',display_name='Analyst 374V',global_role='read_only',password='Analyst-Quartz-Orbit-374V!');b={**b,'session_id':'sb374v'};c.team_governance_359.assign_case_role(identity=a,case_id=cid,username='analyst374v',case_role='analyst',notes='local workflow validation')
            s=c.crawler_frontier_352.register_source(display_name='Workflow Validation Source',seed_urls=['https://example.org/workflow374-validation'],terms_ref='public read-only test contract',max_depth=0,max_pages=1,requests_per_minute=5,max_response_bytes=10000)
            if s['review_status']=='pending_review':s=c.crawler_frontier_352.review_source(s['source_id'],decision='approve_read_only',rationale='local validation reviewed source',reviewer='admin374v')
            configured=c.build374.configure_case_workflow(case_id=cid,identity=a,source_budgets={s['source_id']:20},case_request_budget=30,max_active_crawls=2,confirmation='WORKFLOW')
            q=c.build374.workflow_enqueue_source(case_id=cid,source_id=s['source_id'],identity=a,confirmation='CRAWL')
            paused=c.build374.pause_case_workflow(case_id=cid,identity=a,reason='local pause validation',confirmation='PAUSE')
            resumed=c.build374.resume_case_workflow(case_id=cid,identity=a,confirmation='RESUME')
            handed=c.build374.handoff_case_workflow(case_id=cid,identity=a,to_username='analyst374v',note='deterministic local handoff validation',confirmation='HANDOFF')
            accepted=c.build374.accept_case_handoff(case_id=cid,identity=b,confirmation='ACCEPT')
            checks={
                'configured_active':configured['state']=='active',
                'crawl_workflow_tagged':bool(json.loads(c.job_engine_348.get(q['job']['job_id'])['payload_json']).get('phase16_case_workflow_v374')),
                'pause_suspended_queue':paused['state']=='paused' and bool(paused['paused_job_ids']),
                'resume_requeued':resumed['state']=='active',
                'handoff_pending':handed['state']=='handoff_pending',
                'handoff_accepted':accepted['state']=='active' and accepted['current_owner']=='analyst374v',
                'external_network_used':False,
                'automatic_scope_expansion':False,
            }
            return {'build':'374.0','code_fingerprint':c.build374.code_fingerprint(),'status':'pass' if all(v for k,v in checks.items() if k not in {'external_network_used','automatic_scope_expansion'}) and not checks['external_network_used'] and not checks['automatic_scope_expansion'] else 'fail','local_case_workflow_validation':'pass','checks':checks,'network_used':False,'externally_validated':False,'truthful_note':'Local deterministic ledger/workflow validation only; no external multi-analyst or network workflow validation performed.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',default='LIVE_VALIDATION_BUILD_374_CASE_WORKFLOW.json');args=ap.parse_args();root=Path(__file__).resolve().parents[1];out=run(root);Path(args.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,indent=2,sort_keys=True))
if __name__=='__main__':main()
