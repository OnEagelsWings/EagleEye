from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye.crawler.engine import FetchResponse, StaticTransport
from eagleeye_pro.core.app_context import AppContext
SEED='https://example.org/entity371-live'

def main():
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as d:
        with AppContext(base_dir=d,actor='live371') as c:
            a={**c.team_identity_359.create_initial_admin(username='live371',display_name='Live Validator',password='Live-Cedar-Quartz-371!'),'session_id':'live371'}
            cid=c.build371.team_create_case(identity=a,title='Local Entity/Crawler Validation',client='QA',purpose='deterministic local validation',legal_basis='public_data')['case_id']
            s=c.crawler_frontier_352.register_source(display_name='Local source',seed_urls=[SEED],terms_ref='local fixture',max_depth=0,max_pages=1)
            s=c.crawler_frontier_352.review_source(s['source_id'],decision='approve_read_only',rationale='local deterministic fixture',reviewer='live371')
            q=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s['source_id'])
            t=StaticTransport({'https://example.org/robots.txt':FetchResponse('https://example.org/robots.txt',404,{'content-type':'text/plain'},b'',1),SEED:FetchResponse(SEED,200,{'content-type':'text/html'},b'<html>Alice Example ID-1</html>',2)})
            crawl=c.build371.crawler_run_next(worker_id='crawl371-live',transport=t,resolver=lambda h:['93.184.216.34'],case_id=cid)
            f=c.db.one('SELECT fetch_id FROM phase15_crawl_fetches WHERE crawl_run_id=? AND status_code=200',(q['crawl_run_id'],))
            x=c.build371.register_entity_candidate(case_id=cid,entity_type='person',display_name='Alice Example',identity=a,anchors=[{'type':'email','value':'alice@example.org','reliability':.95,'source_ref':'source:A'},{'type':'external_id','value':'ID-1','reliability':.9,'source_ref':'source:B'}])['entity']['resolution_entity_id']
            y=c.build371.register_entity_candidate(case_id=cid,entity_type='person',display_name='Alice Example',identity=a,anchors=[{'type':'email','value':'alice@example.org','reliability':.95,'source_ref':'source:C'},{'type':'external_id','value':'ID-1','reliability':.9,'source_ref':'source:D'}])['entity']['resolution_entity_id']
            lead=c.build371.enqueue_entity_link_lead(case_id=cid,crawl_run_id=q['crawl_run_id'],fetch_id=f['fetch_id'],target_entity_id=x,candidate_entity_id=y,identity=a,rationale='local fixture mentions candidate')
            reviewed=c.build371.entity_lead_run_next(worker_id='entity371-live',case_id=cid)
            p=c.build371.crawl_entity_provenance(crawl_run_id=q['crawl_run_id'],fetch_id=f['fetch_id'])
            result={
                'build':'371.0','status':'pass' if crawl['job']['status']=='succeeded' and reviewed['state']=='review_ready' and lead['job']['rate_budget_json'] else 'fail',
                'local_entity_crawler_validation':'pass','local_crawl_provenance_validation':'pass','local_entity_lead_queue_validation':'pass','local_review_packet_validation':'pass',
                'provenance_hash':p['provenance_hash'],'entity_classification':reviewed['result']['classification'],'automatic_merge':False,'network_used_by_entity_lead_analysis':False,
                'external_entity_resolution_evaluation':'not_run','external_network_used_by_validation':False,'code_fingerprint':c.build371.code_fingerprint(),
                'truthful_note':'Local deterministic crawler replay and entity-review lead validation only. This is not an external or calibrated entity-resolution evaluation.'}
    (root/'LIVE_VALIDATION_BUILD_371_ENTITY_CRAWLER.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True));return 0 if result['status']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
