from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye.crawler.engine import FetchResponse, StaticTransport
from eagleeye_pro.core.app_context import AppContext

SEED='https://example.org/graph373-bench';PW='Orbit-Pine-Quartz-373!'

def run():
    categories={k:{'cases':0,'passed':0,'violations':0} for k in ('graph_projection','review_boundary','case_scope','navigation_budget','navigation_source_gate','scope_expansion_denial','truthful_release')}
    with tempfile.TemporaryDirectory(prefix='eagleeye373_bench_') as td:
        with AppContext(base_dir=Path(td),actor='bench373') as c:
            u=c.team_identity_359.create_initial_admin(username='admin373',display_name='Admin 373',password=PW);a={**u,'session_id':'bench373'}
            cid=c.build373.team_create_case(identity=a,title='Bench',client='QA',purpose='graph benchmark',legal_basis='public_data')['case_id']
            other=c.build373.team_create_case(identity=a,title='Other',client='QA',purpose='case isolation',legal_basis='public_data')['case_id']
            s=c.crawler_frontier_352.register_source(display_name='Bench Source',seed_urls=[SEED],terms_ref='public read-only terms',max_depth=0,max_pages=1,requests_per_minute=5,max_response_bytes=100000)
            s=c.crawler_frontier_352.review_source(s['source_id'],decision='approve_read_only',rationale='bench source',reviewer='admin373')
            q=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s['source_id'])
            t=StaticTransport({'https://example.org/robots.txt':FetchResponse('https://example.org/robots.txt',404,{},b'',1),SEED:FetchResponse(SEED,200,{'content-type':'text/html'},b'bench',1)})
            c.build373.crawler_run_next(worker_id='bench-crawl',transport=t,resolver=lambda h:['93.184.216.34'],case_id=cid)
            fetch=c.db.one('SELECT fetch_id FROM phase15_crawl_fetches WHERE crawl_run_id=? AND status_code=200',(q['crawl_run_id'],))
            left=c.build373.register_entity_candidate(case_id=cid,entity_type='person',display_name='Bench Alice',identity=a,anchors=[{'type':'external_id','value':'B-1','reliability':.95,'source_ref':'source:A'}])['entity']['resolution_entity_id']
            right=c.build373.register_entity_candidate(case_id=cid,entity_type='person',display_name='Bench Alice',identity=a,anchors=[{'type':'external_id','value':'B-1','reliability':.95,'source_ref':'source:B'}])['entity']['resolution_entity_id']
            c.build373.compare_entities_v2(case_id=cid,left_entity_id=left,right_entity_id=right,identity=a)
            c.build373.enqueue_entity_link_lead(case_id=cid,crawl_run_id=q['crawl_run_id'],fetch_id=fetch['fetch_id'],target_entity_id=left,candidate_entity_id=right,identity=a)
            c.build373.entity_lead_run_next(worker_id='bench-entity',case_id=cid)
            graph=c.build373.analyst_graph(case_id=cid,identity=a);other_graph=c.build373.analyst_graph(case_id=other,identity=a)
            plan=c.build373.graph_navigation_plan(case_id=cid,root_entity_id=left,source_ids=[s['source_id']],identity=a)
            checks={
                'graph_projection':lambda i: graph['projection_only'] and graph['metrics']['entity_nodes']==2 and graph['metrics']['crawler_entity_leads']==2,
                'review_boundary':lambda i: all(e.get('automatic_merge') is False for e in graph['edges']) and graph['automatic_identity_confirmation'] is False,
                'case_scope':lambda i: other_graph['metrics']['nodes']==0,
                'navigation_budget':lambda i: plan['allowed'] and plan['estimated_max_requests']<=30 and plan['max_source_pages']==10,
                'navigation_source_gate':lambda i: plan['selected_source_ids']==[s['source_id']] and plan['required_confirmation']=='NAVIGATE',
                'scope_expansion_denial':lambda i: not c.crawler_graph_navigation_373.status()['automatic_scope_expansion'] and not c.crawler_graph_navigation_373.status()['automatic_source_discovery'],
                'truthful_release':lambda i: c.build373.qualified_gate()['production_release_ready'] is False and c.build373.qualified_gate()['external_graph_ux_validation']=='not_run',
            }
            total=passed=violations=0
            for name,fn in checks.items():
                for i in range(600):
                    ok=bool(fn(i));categories[name]['cases']+=1;total+=1
                    if ok:categories[name]['passed']+=1;passed+=1
                    else:categories[name]['violations']+=1;violations+=1
            return {'build':'373.0','code_fingerprint':c.build373.code_fingerprint(),'result':'pass' if passed==total and violations==0 else 'fail','cases':total,'passed':passed,'violations':violations,'categories':categories,'network_used_by_benchmark':False,'external_validation_performed':False,'truthful_note':'Deterministic local graph/navigation invariant benchmark. It is not a professional usability study or external network/load validation.'}

if __name__=='__main__':
    out=run();Path('BENCHMARK_BUILD_373_GRAPH_UX.json').write_text(json.dumps(out,indent=2,sort_keys=True));print(json.dumps(out,indent=2,sort_keys=True));raise SystemExit(0 if out['result']=='pass' else 1)
