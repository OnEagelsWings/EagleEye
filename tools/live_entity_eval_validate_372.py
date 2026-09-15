from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye.crawler.engine import FetchResponse, StaticTransport
from eagleeye_pro.core.app_context import AppContext

ROOT=Path(__file__).resolve().parents[1]
CORPUS=ROOT/'eval/phase16/entity_resolution_holdout_v372.json'
PW='Orbit-Pine-Quartz-372!'

def _entity(c,a,cid,spec):
    return c.build372.register_entity_candidate(case_id=cid,entity_type='person',display_name=spec['name'],identity=a,aliases=list(spec.get('aliases') or []),anchors=list(spec.get('anchors') or []))['entity']['resolution_entity_id']

def run():
    corpus=json.loads(CORPUS.read_text())
    with tempfile.TemporaryDirectory(prefix='eagleeye372_eval_') as td:
        with AppContext(base_dir=Path(td),actor='validator372') as c:
            u=c.team_identity_359.create_initial_admin(username='admin372',display_name='Admin 372',password=PW); a={**u,'session_id':'validator372'}
            records=[]; classifications={}
            for sc in corpus['scenarios']:
                cid=c.build372.team_create_case(identity=a,title='Holdout '+sc['id'],client='QA',purpose='synthetic entity resolution holdout',legal_basis='public_data')['case_id']
                for i in range(int(sc.get('decoy_same_name_count') or 0)):
                    c.build372.register_entity_candidate(case_id=cid,entity_type='person',display_name=sc['left']['name'],identity=a,source_entity_id=f"decoy-{sc['id']}-{i}")
                left=_entity(c,a,cid,sc['left']);right=_entity(c,a,cid,sc['right'])
                out=c.build372.compare_entities_v2(case_id=cid,left_entity_id=left,right_entity_id=right,identity=a)
                rec=c.entity_resolution_eval_372.comparison_record(case_id=cid,comparison_id=out['comparison_id']);rec.update({'ground_truth':sc['ground_truth'],'cohort':sc['cohort'],'scenario_id':sc['id']});records.append(rec);classifications[sc['id']]=out['classification']
            report=c.entity_resolution_eval_372.evaluate_records(records,evaluation_name='synthetic_holdout_v372')

            cid=c.build372.team_create_case(identity=a,title='Crawler quality',client='QA',purpose='crawler source quality validation',legal_basis='public_data')['case_id']
            seed='https://example.org/source-quality'
            s=c.crawler_frontier_352.register_source(display_name='Synthetic Public Source',seed_urls=[seed],terms_ref='synthetic public read-only terms',max_depth=0,max_pages=1,requests_per_minute=5,max_response_bytes=100000)
            s=c.crawler_frontier_352.review_source(s['source_id'],decision='approve_read_only',rationale='synthetic validation source',reviewer='admin372')
            q=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s['source_id'])
            t=StaticTransport({'https://example.org/robots.txt':FetchResponse('https://example.org/robots.txt',404,{'content-type':'text/plain'},b'',1),seed:FetchResponse(seed,200,{'content-type':'text/html'},b'<html>Synthetic entity source</html>',2)})
            c.build372.crawler_run_next(worker_id='crawl372',transport=t,resolver=lambda h:['93.184.216.34'],case_id=cid)
            fetch=c.db.one('SELECT fetch_id FROM phase15_crawl_fetches WHERE crawl_run_id=? AND status_code=200',(q['crawl_run_id'],))
            x=c.build372.register_entity_candidate(case_id=cid,entity_type='person',display_name='Crawler Alice',identity=a,anchors=[{'type':'external_id','value':'CRAWL-1','reliability':.95,'source_ref':'source:A'}])['entity']['resolution_entity_id']
            y=c.build372.register_entity_candidate(case_id=cid,entity_type='person',display_name='Crawler Alice',identity=a,anchors=[{'type':'external_id','value':'CRAWL-1','reliability':.95,'source_ref':'source:B'}])['entity']['resolution_entity_id']
            lead=c.build372.enqueue_entity_link_lead(case_id=cid,crawl_run_id=q['crawl_run_id'],fetch_id=fetch['fetch_id'],target_entity_id=x,candidate_entity_id=y,identity=a,rationale='synthetic crawler entity lead')
            analyzed=c.build372.entity_lead_run_next(worker_id='entity372',case_id=cid)
            quality=c.build372.crawler_lead_quality(job_id=lead['job']['job_id'])
            contract=c.build372.source_quality_calibration_contract()
            checks={
                'holdout_gate_passed':report['gate']['passed'],
                'holdout_20_scenarios':report['metrics']['records']>=20,
                'false_link_rate_safe':report['metrics']['unsafe_false_link_rate']<=.05,
                'conflict_escape_zero':report['metrics']['strong_identifier_conflict_escape_count']==0,
                'precision_ge_090':report['metrics']['review_positive_precision']>=.90,
                'recall_ge_080':report['metrics']['same_entity_candidate_recall']>=.80,
                'crawler_lead_review_ready':analyzed['state']=='review_ready',
                'source_quality_packet':quality['review_required'] and not quality['source_quality_can_confirm_identity'],
                'source_quality_monotonic':contract['monotonic_reference_order'],
                'no_auto_merge':not quality['automatic_merge'],
                'no_external_network':True,
            }
            return {
                'build':'372.0','code_fingerprint':c.build372.code_fingerprint(),'result':'pass' if all(checks.values()) else 'fail',
                'synthetic_holdout_validation':'pass' if report['gate']['passed'] else 'fail','metrics':report['metrics'],'cohorts':report['cohorts'],'classifications':classifications,
                'crawler_source_quality_validation':'pass' if checks['source_quality_packet'] and checks['source_quality_monotonic'] else 'fail',
                'checks':checks,'external_real_world_holdout_validation':'not_run','no_external_network':True,'real_person_data_used':False,
                'truthful_note':'Deterministic synthetic holdout and static crawler transport only. This is not an external real-world false-link validation.'
            }

if __name__=='__main__':
    out=run();Path('LIVE_VALIDATION_BUILD_372_ENTITY_EVAL.json').write_text(json.dumps(out,indent=2,sort_keys=True));print(json.dumps(out,indent=2,sort_keys=True));raise SystemExit(0 if out['result']=='pass' else 1)
