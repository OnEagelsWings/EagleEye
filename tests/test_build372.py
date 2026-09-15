from __future__ import annotations
import ast, json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from eagleeye.crawler.engine import FetchResponse, StaticTransport
from eagleeye.interfaces.web.app372 import create_workspace_app372
from eagleeye_pro.core.app_context import AppContext

PW='Orbit-Pine-Quartz-372!';SEED='https://example.org/entity372-source'
def ctx(tmp_path): return AppContext(base_dir=tmp_path,actor='test372')
def admin(c):
    u=c.team_identity_359.create_initial_admin(username='admin372',display_name='Admin 372',password=PW);return {**u,'session_id':'admin-session-372'}
def case(c,a,title='Eval Case'): return c.build372.team_create_case(identity=a,title=title,client='QA',purpose='authorized entity resolution evaluation',legal_basis='public_data')
def ent(c,a,cid,name='Alice Example',email='alice@example.test',external='ID-1',refs=('source:A','source:B'),aliases=None):
    anchors=[]
    if email:anchors.append({'type':'email','value':email,'reliability':.95,'source_ref':refs[0]})
    if external:anchors.append({'type':'external_id','value':external,'reliability':.9,'source_ref':refs[1]})
    return c.build372.register_entity_candidate(case_id=cid,entity_type='person',display_name=name,identity=a,aliases=aliases or [],anchors=anchors)['entity']['resolution_entity_id']
def source_and_crawl(c,a,cid):
    s=c.crawler_frontier_352.register_source(display_name='Entity Eval Source',seed_urls=[SEED],terms_ref='public read-only terms',max_depth=0,max_pages=1,requests_per_minute=5,max_response_bytes=100000)
    s=c.crawler_frontier_352.review_source(s['source_id'],decision='approve_read_only',rationale='reviewed public source',reviewer='admin372')
    q=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s['source_id'])
    t=StaticTransport({'https://example.org/robots.txt':FetchResponse('https://example.org/robots.txt',404,{'content-type':'text/plain'},b'',1),SEED:FetchResponse(SEED,200,{'content-type':'text/html'},b'<html>Alice Example ID-1</html>',2)})
    out=c.build372.crawler_run_next(worker_id='crawl372',transport=t,resolver=lambda h:['93.184.216.34'],case_id=cid)
    fetch=c.db.one('SELECT fetch_id FROM phase15_crawl_fetches WHERE crawl_run_id=? AND status_code=200',(q['crawl_run_id'],))
    return s,q['crawl_run_id'],fetch['fetch_id'],out
def comparison(c,a,cid,left=None,right=None):
    left=left or ent(c,a,cid);right=right or ent(c,a,cid,refs=('source:C','source:D'))
    return c.build372.compare_entities_v2(case_id=cid,left_entity_id=left,right_entity_id=right,identity=a)
def good_records():
    rows=[]
    for i in range(6):rows.append({'comparison_id':f's{i}','case_id':'x','classification':'possible_review_candidate','prediction':'review_positive','evidence_weight':.7,'strong_identifier_conflict_veto':False,'common_name_count':1,'ground_truth':'same_entity','cohort':'same'})
    for i in range(8):rows.append({'comparison_id':f'd{i}','case_id':'x','classification':'likely_distinct','prediction':'distinct','evidence_weight':0,'strong_identifier_conflict_veto':True,'common_name_count':4 if i<2 else 1,'ground_truth':'distinct','cohort':'distinct'})
    for i in range(3):rows.append({'comparison_id':f'a{i}','case_id':'x','classification':'insufficient','prediction':'defer','evidence_weight':.2,'strong_identifier_conflict_veto':False,'common_name_count':1,'ground_truth':'ambiguous','cohort':'ambiguous'})
    return rows

# 1
def test_lazy_baseline_then_active_schema(tmp_path):
    with ctx(tmp_path) as c:
        row=c.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' GROUP BY type");assert int(row[0]['c'])==141
        _=c.build372
        m=c.build372.schema_metrics();assert m['within_gate'] and (m['table'],m['index'],m['trigger'])==(165,133,8) and m['build372_specific_tables_added']==0
# 2
def test_version_schema(tmp_path):
    with ctx(tmp_path) as c:assert c.build372.version_status()=={'runtime_build':'372.0','schema_version':'372.0','package_version':'372.0.0','coherent':True}
# 3
def test_phase_progress(tmp_path):
    with ctx(tmp_path) as c:assert c.build372.phase16_status()['builds_completed']==12
# 4
def test_eval_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s=c.entity_resolution_eval_372.status();assert s['offline_holdout_evaluation'] and not s['automatic_threshold_change'] and not s['score_is_probability'] and not s['automatic_merge'] and not s['network_execution']
# 5
def test_source_quality_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s=c.crawler_source_quality_372.status();assert s['source_quality_calibration'] and not s['score_is_identity_probability'] and not s['automatic_identity_confirmation'] and not s['automatic_merge'] and s['new_per_build_data_tables']==0
# 6
def test_source_quality_monotonic(tmp_path):
    with ctx(tmp_path) as c:assert c.build372.source_quality_calibration_contract()['monotonic_reference_order']
# 7
def test_source_quality_degraded_penalty(tmp_path):
    with ctx(tmp_path) as c:
        q=c.crawler_source_quality_372;good=q.score_snapshot({'source_kind':'public_web','review_status':'approved_read_only','hash_verified':True,'http_success':True,'source_health':'healthy','terms_ref_present':True});bad=q.score_snapshot({'source_kind':'public_web','review_status':'approved_read_only','hash_verified':True,'http_success':False,'source_health':'degraded','terms_ref_present':True,'degraded':True});assert good['quality_score']>bad['quality_score']
# 8
def test_source_quality_replay_penalty(tmp_path):
    with ctx(tmp_path) as c:
        q=c.crawler_source_quality_372;a=q.score_snapshot({'source_kind':'official_register','review_status':'approved_read_only','hash_verified':True,'http_success':True,'source_health':'healthy','terms_ref_present':True});b=q.score_snapshot({'source_kind':'official_register','review_status':'approved_read_only','hash_verified':True,'http_success':True,'source_health':'healthy','terms_ref_present':True,'replay_or_fixture':True});assert a['quality_score']>b['quality_score'] and 'replay_or_fixture_not_external_validation' in b['penalties']
# 9
def test_source_quality_never_identity_probability(tmp_path):
    with ctx(tmp_path) as c:
        q=c.crawler_source_quality_372.score_snapshot({'source_kind':'official_register'});assert not q['score_is_identity_probability'] and not q['can_confirm_identity'] and not q['can_skip_human_review']
# 10
def test_evaluate_records_empty_rejected(tmp_path):
    with ctx(tmp_path) as c:
        with pytest.raises(ValueError):c.entity_resolution_eval_372.evaluate_records([])
# 11
def test_evaluate_records_good_gate(tmp_path):
    with ctx(tmp_path) as c:
        r=c.entity_resolution_eval_372.evaluate_records(good_records());assert r['gate']['passed'] and r['metrics']['unsafe_false_link_rate']==0 and r['metrics']['review_positive_precision']==1
# 12
def test_evaluate_records_detects_false_link(tmp_path):
    rows=good_records();rows.append({'comparison_id':'bad','case_id':'x','classification':'possible_review_candidate','prediction':'review_positive','evidence_weight':.7,'strong_identifier_conflict_veto':False,'common_name_count':4,'ground_truth':'distinct','cohort':'common'})
    with ctx(tmp_path) as c:
        r=c.entity_resolution_eval_372.evaluate_records(rows);assert r['metrics']['unsafe_false_link_count']==1 and r['metrics']['unsafe_false_link_rate']>0
# 13
def test_evaluate_records_detects_conflict_escape(tmp_path):
    rows=good_records();rows.append({'comparison_id':'escape','case_id':'x','classification':'insufficient','prediction':'defer','evidence_weight':0,'strong_identifier_conflict_veto':True,'common_name_count':1,'ground_truth':'distinct','cohort':'conflict'})
    with ctx(tmp_path) as c:assert c.entity_resolution_eval_372.evaluate_records(rows)['metrics']['strong_identifier_conflict_escape_count']==1
# 14
def test_evaluate_records_common_name_metric(tmp_path):
    rows=good_records();rows.append({'comparison_id':'commonbad','case_id':'x','classification':'possible_review_candidate','prediction':'review_positive','evidence_weight':.7,'strong_identifier_conflict_veto':False,'common_name_count':5,'ground_truth':'distinct','cohort':'common'})
    with ctx(tmp_path) as c:assert c.entity_resolution_eval_372.evaluate_records(rows)['metrics']['common_name_false_link_rate']>0
# 15
def test_evaluate_records_false_distinct(tmp_path):
    rows=good_records();rows.append({'comparison_id':'fd','case_id':'x','classification':'likely_distinct','prediction':'distinct','evidence_weight':0,'strong_identifier_conflict_veto':True,'common_name_count':1,'ground_truth':'same_entity','cohort':'same'})
    with ctx(tmp_path) as c:assert c.entity_resolution_eval_372.evaluate_records(rows)['metrics']['false_distinct_count']==1
# 16
def test_wilson_interval_present(tmp_path):
    with ctx(tmp_path) as c:
        w=c.entity_resolution_eval_372.evaluate_records(good_records())['metrics']['unsafe_false_link_wilson95'];assert 0<=w['low']<=w['high']<=1
# 17
def test_evaluation_does_not_mutate_thresholds(tmp_path):
    with ctx(tmp_path) as c:
        r=c.entity_resolution_eval_372.evaluate_records(good_records());assert not r['automatic_threshold_change'] and not r['production_scorer_mutated']
# 18
def test_invalid_ground_truth_rejected(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];o=comparison(c,a,cid)
        with pytest.raises(ValueError):c.build372.evaluate_labeled_entity_comparisons(case_id=cid,labeled=[{'comparison_id':o['comparison_id'],'ground_truth':'maybe'}],identity=a)
# 19
def test_labeled_evaluation_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);ca=case(c,a,'A')['case_id'];cb=case(c,a,'B')['case_id'];o=comparison(c,a,ca)
        with pytest.raises(PermissionError):c.build372.evaluate_labeled_entity_comparisons(case_id=cb,labeled=[{'comparison_id':o['comparison_id'],'ground_truth':'same_entity'}],identity=a)
# 20
def test_comparison_record_score_not_probability(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];o=comparison(c,a,cid);r=c.build372.comparison_eval_record(case_id=cid,comparison_id=o['comparison_id']);assert not r['score_is_probability'] and r['review_required']
# 21
def test_actual_labeled_evaluation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];labels=[]
        for i in range(6):
            x=ent(c,a,cid,name=f'Same {i}',email=f's{i}@example.test',external='');y=ent(c,a,cid,name=f'Same {i}',email=f's{i}@example.test',external='',refs=('source:C','source:D'));o=c.build372.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a);labels.append({'comparison_id':o['comparison_id'],'ground_truth':'same_entity','cohort':'same'})
        for i in range(6):
            x=ent(c,a,cid,name=f'Distinct {i}',email=f'a{i}@example.test',external='');y=ent(c,a,cid,name=f'Distinct {i}',email=f'b{i}@example.test',external='',refs=('source:C','source:D'));o=c.build372.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a);labels.append({'comparison_id':o['comparison_id'],'ground_truth':'distinct','cohort':'conflict'})
        r=c.build372.evaluate_labeled_entity_comparisons(case_id=cid,labeled=labels,identity=a);assert r['metrics']['unsafe_false_link_rate']==0 and r['metrics']['strong_identifier_conflict_escape_count']==0
# 22
def test_provenance_source_quality_actual(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,fid,_=source_and_crawl(c,a,cid);q=c.build372.crawler_source_quality(crawl_run_id=run,fetch_id=fid);assert q['case_id']==cid and q['quality']['quality_band'] in {'high','medium','low','very_low'} and not q['used_for_auto_identity_decision']
# 23
def test_lead_quality_packet_actual(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,fid,_=source_and_crawl(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));lead=c.build372.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);c.build372.entity_lead_run_next(worker_id='w372',case_id=cid);p=c.build372.crawler_lead_quality(job_id=lead['job']['job_id']);assert p['review_required'] and not p['source_quality_can_confirm_identity'] and not p['automatic_merge']
# 24
def test_lead_quality_rejects_wrong_job_type(tmp_path):
    with ctx(tmp_path) as c:
        j=c.job_engine_348.enqueue(job_type='other',payload={},case_id='case-x')
        with pytest.raises(ValueError):c.build372.crawler_lead_quality(job_id=j['job_id'])
# 25
def test_source_quality_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);ca=case(c,a,'A')['case_id'];cb=case(c,a,'B')['case_id'];_,run,fid,_=source_and_crawl(c,a,ca);x=ent(c,a,ca);y=ent(c,a,ca,refs=('source:C','source:D'));c.build372.enqueue_entity_link_lead(case_id=ca,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);assert c.build372.crawler_source_quality_case(case_id=ca)['lead_count']==1 and c.build372.crawler_source_quality_case(case_id=cb)['lead_count']==0
# 26
def test_source_quality_does_not_change_job_payload(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,fid,_=source_and_crawl(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));lead=c.build372.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);before=c.job_engine_348.get(lead['job']['job_id'])['payload_json'];c.build372.crawler_lead_quality(job_id=lead['job']['job_id']);after=c.job_engine_348.get(lead['job']['job_id'])['payload_json'];assert before==after
# 27
def test_source_quality_no_network_authority(tmp_path):
    with ctx(tmp_path) as c:assert c.build372.crawler_status()['lead_source_quality_annotation'] and not c.build372.crawler_status()['source_quality_can_skip_review']
# 28
def test_ai_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s=c.ai_autonomy_372.status();assert s['entity_eval_awareness'] and s['source_quality_awareness'] and not s['automatic_threshold_tuning'] and not s['automatic_entity_merge']
# 29
def test_ai_dossier_eval_context(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];c.build372.create_investigation_intake(case_id=cid,objective='Evaluate entity carefully',key_questions=['Identity?']);c.build372.start_investigation_go(case_id=cid,go='GO');o=c.build372.run_autonomous_investigation(case_id=cid,max_ticks=1);assert 'phase16_entity_eval_v372' in o['dossier'] and not o['dossier']['phase16_entity_eval_v372']['automatic_threshold_tuning']
# 30
def test_opsec_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s=c.opsec_supervisor_372.status();assert s['entity_eval_boundary_monitor'] and not s['automatic_threshold_mutation'] and not s['automatic_merge_authority'] and not s['system_mutations']
# 31
def test_opsec_detects_succeeded_boundary_violation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,fid,_=source_and_crawl(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));lead=c.build372.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);c.build372.entity_lead_run_next(worker_id='w',case_id=cid);c.db.execute("UPDATE phase15_jobs SET result_json=? WHERE job_id=?",(json.dumps({'automatic_merge':True,'identity_confirmed':True}),lead['job']['job_id']));r=c.build372.autonomous_opsec_protect(case_id=cid);assert lead['job']['job_id'] in r['entity_eval_boundary_violations']
# 32
def test_opsec_cancels_queued_boundary_violation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,fid,_=source_and_crawl(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));lead=c.build372.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);p=json.loads(lead['job']['payload_json']);p['automatic_merge']=True;c.db.execute('UPDATE phase15_jobs SET payload_json=? WHERE job_id=?',(json.dumps(p),lead['job']['job_id']));r=c.build372.autonomous_opsec_protect(case_id=cid);assert lead['job']['job_id'] in r['entity_eval_boundary_violations'] and c.job_engine_348.get(lead['job']['job_id'])['status']=='cancelled'
# 33
def test_crawler_status_increment(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build372.crawler_status();assert s['crawler_improvement_build']==372 and s['false_link_calibration'] and s['source_quality_calibration'] and s['lead_source_quality_annotation']
# 34
def test_crawler_program_still_continuous(tmp_path):
    with ctx(tmp_path) as c:assert c.build372.crawler_status()['continuous_crawler_expansion_370_380']
# 35
def test_build371_no_auto_merge_preserved(tmp_path):
    with ctx(tmp_path) as c:assert not c.entity_resolution_v2_371.status()['automatic_merge']
# 36
def test_tor_boundaries_preserved(tmp_path):
    with ctx(tmp_path) as c:
        s=c.tor_gateway_370.status();assert not s['control_port_authority'] and not s['newnym_authority'] and not s['torrc_mutation']
# 37
def test_web_health_and_auth(tmp_path):
    app=create_workspace_app372(base_dir=tmp_path/'web')
    with TestClient(app) as client:
        h=client.get('/health');assert h.status_code==200 and h.json()['build']=='372.0' and h.json()['phase16_builds_completed']==12 and h.json()['source_quality_calibration'];assert client.get('/api/build372/final-status').status_code==401
# 38
def test_eval_api_requires_auth(tmp_path):
    app=create_workspace_app372(base_dir=tmp_path/'web')
    with TestClient(app) as client:assert client.post('/api/cases/nope/entity372/evaluate',json={'labeled':[]}).status_code==401
# 39
def test_source_quality_api_requires_auth(tmp_path):
    app=create_workspace_app372(base_dir=tmp_path/'web')
    with TestClient(app) as client:assert client.get('/api/cases/nope/entity372/source-quality').status_code==401
# 40
def test_new_modules_no_direct_network_or_subprocess_imports():
    bad={'requests','httpx','aiohttp','socket','subprocess'};found=set()
    for p in [Path('src/eagleeye/phase16/entity_resolution_eval372.py'),Path('src/eagleeye/application/build372/service.py'),Path('src/eagleeye/interfaces/web/app372.py')]:
        tree=ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):found.update(x.name.split('.')[0] for x in n.names)
            elif isinstance(n,ast.ImportFrom) and n.module:found.add(n.module.split('.')[0])
    assert not found.intersection(bad)
# 41
def test_build_gate_has_no_literal_true(tmp_path):
    with ctx(tmp_path) as c:assert c.build372.active_gate_literal_true_lines()==[]
# 42
def test_truthful_release_false(tmp_path):
    with ctx(tmp_path) as c:assert c.build372.qualified_gate()['production_release_ready'] is False and c.build372.qualified_gate()['external_real_world_holdout_validation']=='not_run'
# 43
def test_capabilities_do_not_claim_external_validation(tmp_path):
    with ctx(tmp_path) as c:assert not any(x['states']['externally_validated'] for x in c.build372.capabilities())
# 44
def test_corpus_is_synthetic_and_20_scenarios():
    c=json.loads(Path('eval/phase16/entity_resolution_holdout_v372.json').read_text());assert c['synthetic'] and len(c['scenarios'])==20
# 45
def test_corpus_contains_required_cohorts():
    c=json.loads(Path('eval/phase16/entity_resolution_holdout_v372.json').read_text());coh={x['cohort'] for x in c['scenarios']};assert {'strong_conflict_distinct','common_name_distinct','ambiguous_defer','name_variant_same'}.issubset(coh)
# 46
def test_corpus_uses_example_test_for_emails():
    c=json.loads(Path('eval/phase16/entity_resolution_holdout_v372.json').read_text());vals=[]
    for sc in c['scenarios']:
        for side in ('left','right'):
            for a in sc[side].get('anchors',[]):
                if a['type']=='email':vals.append(a['value'])
    assert vals and all(v.endswith('@example.test') for v in vals)
# 47
def test_roadmap_372_completed():
    t=Path('CRAWLER_ROADMAP_BUILD_370_TO_380.md').read_text().lower();assert '| 372 |' in t and 'completed' in next(line for line in t.splitlines() if line.startswith('| 372 |')) and 'source-quality' in t
# 48
def test_masterplan_372_actual_status():
    t=Path('PHASE_16_MASTERPLAN_BUILD_361_TO_380.md').read_text().lower();assert 'build 372 actual status' in t and '12/20' in t
# 49
def test_registry_has_372_services(tmp_path):
    with ctx(tmp_path) as c:
        for name in ('entity_resolution_eval_372','crawler_source_quality_372','ai_autonomy_372','opsec_supervisor_372','build372'):assert name in c.SERVICE_NAMES
# 50
def test_score_is_review_weight_not_probability(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];o=comparison(c,a,cid);assert o['v2']['score_is_probability'] is False and c.build372.comparison_eval_record(case_id=cid,comparison_id=o['comparison_id'])['score_is_probability'] is False
# 51
def test_review_workflow_still_required(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];o=comparison(c,a,cid);assert o['state']=='needs_review' and o['v2']['review_required']
# 52
def test_source_quality_cannot_skip_review(tmp_path):
    with ctx(tmp_path) as c:
        q=c.crawler_source_quality_372.score_snapshot({'source_kind':'official_register','review_status':'approved_read_only','hash_verified':True,'http_success':True,'source_health':'healthy','terms_ref_present':True});assert q['quality_score']==100 and not q['can_skip_human_review']
# 53
def test_evaluation_id_deterministic(tmp_path):
    with ctx(tmp_path) as c:
        a=c.entity_resolution_eval_372.evaluate_records(good_records(),evaluation_name='x');b=c.entity_resolution_eval_372.evaluate_records(good_records(),evaluation_name='x');assert a['evaluation_id']==b['evaluation_id']
# 54
def test_evaluation_records_preserve_no_merge(tmp_path):
    with ctx(tmp_path) as c:assert all(not r.get('automatic_merge',False) for r in c.entity_resolution_eval_372.evaluate_records(good_records())['records'])
# 55
def test_phase_status_reports_eval_and_crawler(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build372.phase16_status();assert s['entity_resolution_evaluation']['false_link_metrics'] and s['crawler_source_quality']['source_quality_calibration'] and s['crawler_improvement_build']==372
