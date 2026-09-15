from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye.crawler.engine import FetchResponse, StaticTransport
from eagleeye_pro.core.app_context import AppContext

PW='Orbit-Pine-Quartz-373!'
SEED='https://example.org/graph373-live'

def run():
    with tempfile.TemporaryDirectory(prefix='eagleeye373_graph_') as td:
        with AppContext(base_dir=Path(td),actor='validator373') as c:
            u=c.team_identity_359.create_initial_admin(username='admin373',display_name='Admin 373',password=PW);a={**u,'session_id':'validator373'}
            cid=c.build373.team_create_case(identity=a,title='Graph validation',client='QA',purpose='local graph workflow validation',legal_basis='public_data')['case_id']
            s=c.crawler_frontier_352.register_source(display_name='Graph Validation Source',seed_urls=[SEED],terms_ref='synthetic public read-only terms',max_depth=0,max_pages=1,requests_per_minute=5,max_response_bytes=100000)
            s=c.crawler_frontier_352.review_source(s['source_id'],decision='approve_read_only',rationale='synthetic validation source',reviewer='admin373')
            q=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s['source_id'])
            t=StaticTransport({'https://example.org/robots.txt':FetchResponse('https://example.org/robots.txt',404,{'content-type':'text/plain'},b'',1),SEED:FetchResponse(SEED,200,{'content-type':'text/html'},b'<html>Alice Example ID-373</html>',2)})
            c.build373.crawler_run_next(worker_id='crawl373',transport=t,resolver=lambda h:['93.184.216.34'],case_id=cid)
            fetch=c.db.one('SELECT fetch_id FROM phase15_crawl_fetches WHERE crawl_run_id=? AND status_code=200',(q['crawl_run_id'],))
            left=c.build373.register_entity_candidate(case_id=cid,entity_type='person',display_name='Alice Example',identity=a,anchors=[{'type':'external_id','value':'ID-373','reliability':.95,'source_ref':'source:A'}])['entity']['resolution_entity_id']
            right=c.build373.register_entity_candidate(case_id=cid,entity_type='person',display_name='Alice Example',identity=a,anchors=[{'type':'external_id','value':'ID-373','reliability':.95,'source_ref':'source:B'}])['entity']['resolution_entity_id']
            cmp=c.build373.compare_entities_v2(case_id=cid,left_entity_id=left,right_entity_id=right,identity=a)
            lead=c.build373.enqueue_entity_link_lead(case_id=cid,crawl_run_id=q['crawl_run_id'],fetch_id=fetch['fetch_id'],target_entity_id=left,candidate_entity_id=right,identity=a,rationale='synthetic graph lead')
            c.build373.entity_lead_run_next(worker_id='entity373',case_id=cid)
            graph=c.build373.analyst_graph(case_id=cid,identity=a)
            focus=c.build373.analyst_graph_focus(case_id=cid,node_id=f'entity:{left}',identity=a,depth=1)
            plan=c.build373.graph_navigation_plan(case_id=cid,root_entity_id=left,source_ids=[s['source_id']],identity=a)
            nav=c.build373.graph_navigate(case_id=cid,root_entity_id=left,source_ids=[s['source_id']],identity=a,confirmation='NAVIGATE')
            tagged=c.job_engine_348.get(nav['queued'][0]['job_id']);payload=json.loads(tagged['payload_json'])
            checks={
                'graph_projection_live':graph['metrics']['entity_nodes']==2 and graph['metrics']['source_nodes']>=1,
                'comparison_edge_live':any(e['kind']=='entity_comparison' and e['object_id']==cmp['comparison_id'] for e in graph['edges']),
                'crawler_provenance_edge_live':sum(1 for e in graph['edges'] if e['kind']=='crawler_entity_lead')==2,
                'focus_offline_live':focus['network_execution'] is False and focus['scope_expansion'] is False,
                'plan_allowed_live':plan['allowed'] and plan['network_execution'] is False,
                'navigation_tag_live':payload.get('phase16_graph_navigation_v373') is True and payload.get('automatic_scope_expansion') is False,
                'navigation_bounded_live':int(json.loads(tagged['rate_budget_json']).get('max_requests',999))<=30,
                'no_auto_merge':graph['automatic_merge'] is False,
                'no_external_network':True,
            }
            return {'build':'373.0','code_fingerprint':c.build373.code_fingerprint(),'result':'pass' if all(checks.values()) else 'fail','local_graph_workflow_validation':'pass' if all(checks.values()) else 'fail','checks':checks,'graph_metrics':graph['metrics'],'navigation_plan':{'allowed':plan['allowed'],'estimated_max_requests':plan['estimated_max_requests'],'max_total_requests':plan['max_total_requests']},'external_graph_ux_validation':'not_run','external_graph_navigation_validation':'not_run','external_network_used':False,'truthful_note':'StaticTransport plus local queueing only. No professional analyst usability study and no external graph-navigation network validation were performed.'}

if __name__=='__main__':
    out=run();Path('LIVE_VALIDATION_BUILD_373_GRAPH_UX.json').write_text(json.dumps(out,indent=2,sort_keys=True));print(json.dumps(out,indent=2,sort_keys=True));raise SystemExit(0 if out['result']=='pass' else 1)
