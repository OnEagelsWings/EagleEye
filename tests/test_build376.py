from __future__ import annotations

import ast, hashlib, json
from pathlib import Path
from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app376 import create_workspace_app376
from eagleeye_pro.core.app_context import AppContext

PW='Orbit-Pine-Quartz-376!'
SEED='https://example.org/dossier376-source'

def ctx(tmp_path): return AppContext(base_dir=tmp_path,actor='test376')
def admin(c):
    u=c.team_identity_359.create_initial_admin(username='admin376',display_name='Admin 376',password=PW);return {**u,'session_id':'admin-session-376'}
def case(c,a,title='Dossier vNext Case'): return c.build376.team_create_case(identity=a,title=title,client='QA',purpose='authorized dossier coverage evaluation',legal_basis='public_data')
def source(c,*,url=SEED,max_pages=1,name='Dossier Source'):
    s=c.crawler_frontier_352.register_source(display_name=name,seed_urls=[url],terms_ref='public read-only terms',max_depth=0,max_pages=max_pages,requests_per_minute=5,max_response_bytes=100000)
    if s['review_status']=='pending_review':s=c.crawler_frontier_352.review_source(s['source_id'],decision='approve_read_only',rationale='reviewed public source',reviewer='admin376')
    return s
def workflow(c,a,cid,s,budget=30,source_budget=20): return c.build376.configure_case_workflow(case_id=cid,identity=a,source_budgets={s['source_id']:source_budget},case_request_budget=budget,max_active_crawls=3,confirmation='WORKFLOW')
def run(c,cid,s,*,rid='run376',status='succeeded',at='2026-09-09T12:00:00+00:00',fetch=True):
    sr='sr_'+rid
    c.db.execute("INSERT INTO phase15_search_runs(search_run_id,case_id,task_id,search_kind,state,opsec_state,network_profile_ref,workspace_ref,policy_version,created_by,created_at,completed_at,summary_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(sr,cid,None,'crawler','completed','green',None,None,'test376','test376',at,at,'{}'))
    c.db.execute("INSERT INTO phase15_crawl_runs(crawl_run_id,case_id,source_id,search_run_id,status,pages_fetched,pages_stored,bytes_fetched,started_at,completed_at,created_at,summary_json,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(rid,cid,s['source_id'],sr,status,1 if status=='succeeded' else 0,1 if status=='succeeded' else 0,100 if status=='succeeded' else 0,at,at,at,json.dumps({'transport_kind':'static_replay_v1'}),'h'*64))
    if fetch:
        c.db.execute("INSERT INTO phase15_crawl_fetches(fetch_id,crawl_run_id,url,depth,status_code,content_type,content_sha256,size_bytes,elapsed_ms,disposition,reason,object_id,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('f_'+rid,rid,SEED,0,200 if status=='succeeded' else 500,'text/html','a'*64,100,1,'stored_review_pending','','',at,'b'*64))
    return rid

def test_schema_no_build376_tables(tmp_path):
    with ctx(tmp_path) as c:
        _=c.build376;m=c.build376.schema_metrics();assert m['within_gate'] and (m['table'],m['index'],m['trigger'])==(165,133,8);assert m['dossier_vnext_new_tables']==0;assert not any('376' in r['name'] for r in c.db.all("SELECT name FROM sqlite_master WHERE type='table'"))
def test_version(tmp_path):
    with ctx(tmp_path) as c: assert c.build376.version_status()=={'runtime_build':'376.0','schema_version':'376.0','package_version':'376.0.0','coherent':True}
def test_phase_progress(tmp_path):
    with ctx(tmp_path) as c:s=c.build376.phase16_status();assert s['builds_completed']==16 and s['crawler_improvement_build']==376
def test_crawler_increment(tmp_path):
    with ctx(tmp_path) as c:s=c.build376.crawler_status();assert s['dossier_source_coverage'] and s['negative_evidence_semantics'] and s['stale_source_metrics'] and not s['automatic_gap_crawl']
def test_dossier_status_semantics(tmp_path):
    with ctx(tmp_path) as c:s=c.dossier_vnext_376.status();assert s['coverage_is_truth_probability'] is False and s['absence_is_nonexistence'] is False and s['automatic_crawl_from_gap'] is False
def test_ai_status_no_gap_execution(tmp_path):
    with ctx(tmp_path) as c:s=c.ai_autonomy_376.status();assert s['dossier_vnext_awareness'] and s['automatic_gap_closure'] is False and s['direct_crawl_execution_authority'] is False
def test_opsec_status(tmp_path):
    with ctx(tmp_path) as c:s=c.opsec_supervisor_376.status();assert s['absence_observation_integrity_monitor'] and s['auto_gap_crawl_block'] and s['system_mutations'] is False

def test_empty_case_coverage_not_truth(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];o=c.build376.dossier_coverage(case_id=cid);assert o['expected_sources']==0 and o['recent_coverage_ratio']==0 and o['coverage_is_truth_probability'] is False
def test_workflow_source_not_attempted_gap(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);o=c.build376.dossier_coverage(case_id=cid,as_of='2026-09-09T15:00:00+00:00');assert o['counts']['not_attempted']==1 and o['open_research_gaps'][0]['gap_type']=='not_attempted'
def test_recent_success_covered(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);run(c,cid,s);o=c.build376.dossier_coverage(case_id=cid,as_of='2026-09-09T15:00:00+00:00');assert o['counts']['covered_recent']==1 and not o['entries'][0]['stale']
def test_stale_success_exposed_as_gap(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);run(c,cid,s,at='2026-08-01T12:00:00+00:00');o=c.build376.dossier_coverage(case_id=cid,as_of='2026-09-09T15:00:00+00:00');assert o['counts']['covered_stale']==1 and o['entries'][0]['stale'] and o['open_research_gaps'][0]['gap_type']=='stale_evidence'
def test_failed_attempt_is_not_negative_evidence(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);run(c,cid,s,status='failed');o=c.build376.dossier_packet(case_id=cid);assert o['source_coverage']['counts']['attempted_failed']==1 and not o['negative_evidence']['bounded_absence_observations']
def test_freshness_thresholds():
    from eagleeye.phase16.dossier_vnext376 import DossierVNext376
    assert DossierVNext376.freshness_threshold_hours('public_web')==168 and DossierVNext376.freshness_threshold_hours('government_register')==720 and DossierVNext376.freshness_threshold_hours('web_archive')==2160

def test_absence_requires_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);rid=run(c,cid,s)
        try:c.build376.record_absence_observation(case_id=cid,source_id=s['source_id'],crawl_run_id=rid,query_scope='exact identifier lookup',observation='No matching record observed',identity=a,confirmation='NO')
        except PermissionError:pass
        else:raise AssertionError('confirmation required')
def test_absence_requires_succeeded_run(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);rid=run(c,cid,s,status='failed')
        try:c.build376.record_absence_observation(case_id=cid,source_id=s['source_id'],crawl_run_id=rid,query_scope='exact identifier lookup',observation='No matching record observed',identity=a,confirmation='RECORD')
        except PermissionError:pass
        else:raise AssertionError('successful run required')
def test_absence_requires_successful_fetch(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);rid=run(c,cid,s,fetch=False)
        try:c.build376.record_absence_observation(case_id=cid,source_id=s['source_id'],crawl_run_id=rid,query_scope='exact identifier lookup',observation='No matching record observed',identity=a,confirmation='RECORD')
        except PermissionError:pass
        else:raise AssertionError('successful fetch required')
def test_absence_record_never_nonexistence(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);rid=run(c,cid,s);o=c.build376.record_absence_observation(case_id=cid,source_id=s['source_id'],crawl_run_id=rid,query_scope='exact identifier lookup',observation='No matching record observed in bounded response',identity=a,confirmation='RECORD');assert o['counterevidence'] is False and o['nonexistence_inferred'] is False and o['network_execution'] is False
def test_absence_visible_in_packet(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);rid=run(c,cid,s);c.build376.record_absence_observation(case_id=cid,source_id=s['source_id'],crawl_run_id=rid,query_scope='exact identifier lookup',observation='No matching record observed in bounded response',identity=a,confirmation='RECORD');p=c.build376.dossier_packet(case_id=cid);assert len(p['negative_evidence']['bounded_absence_observations'])==1 and p['negative_evidence']['absence_is_nonexistence'] is False
def test_tampered_absence_excluded(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);rid=run(c,cid,s);o=c.build376.record_absence_observation(case_id=cid,source_id=s['source_id'],crawl_run_id=rid,query_scope='exact identifier lookup',observation='No matching record observed in bounded response',identity=a,confirmation='RECORD');row=c.job_engine_348.get(o['job_id']);p=json.loads(row['payload_json']);p['observation']='tampered conclusion';c.db.execute('UPDATE phase15_jobs SET payload_json=? WHERE job_id=?',(json.dumps(p,sort_keys=True,separators=(",",":")),o['job_id']));items=c.build376.absence_observations(case_id=cid);assert items[0]['integrity_valid'] is False and items[0]['usable_in_dossier'] is False
def test_opsec_reports_tampered_absence(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);rid=run(c,cid,s);o=c.build376.record_absence_observation(case_id=cid,source_id=s['source_id'],crawl_run_id=rid,query_scope='exact identifier lookup',observation='No matching record observed in bounded response',identity=a,confirmation='RECORD');row=c.job_engine_348.get(o['job_id']);p=json.loads(row['payload_json']);p['counterevidence']=True;c.db.execute('UPDATE phase15_jobs SET payload_json=? WHERE job_id=?',(json.dumps(p),o['job_id']));r=c.build376.autonomous_opsec_protect(case_id=cid);assert o['job_id'] in r['invalid_absence_observations']
def test_opsec_cancels_auto_gap_crawl(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);q=c.build376.workflow_enqueue_source(case_id=cid,source_id=s['source_id'],identity=a,confirmation='CRAWL');jid=q['job']['job_id'];row=c.job_engine_348.get(jid);p=json.loads(row['payload_json']);p['automatic_gap_closure']=True;c.db.execute('UPDATE phase15_jobs SET payload_json=? WHERE job_id=?',(json.dumps(p),jid));r=c.build376.autonomous_opsec_protect(case_id=cid);assert jid in r['cancelled_gap_jobs'] and c.job_engine_348.get(jid)['status']=='cancelled'
def test_opsec_no_system_mutation(tmp_path):
    with ctx(tmp_path) as c:a=admin(c);cid=case(c,a)['case_id'];assert c.build376.autonomous_opsec_protect(case_id=cid)['system_mutations'] is False

def test_enrich_dossier_adds_sections(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);d=c.dossier_vnext_376.enrich_dossier(case_id=cid,dossier={'metrics':{},'uncertainties':[]});assert 'phase16_dossier_vnext_v376' in d and d['research_gap_review_required'] and any('truth probability' in x for x in d['uncertainties'])
def test_build_vnext_report_uses_existing_report_table(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);d=c.dossier_vnext_376.build_vnext_report(case_id=cid,base_dossier={'case_id':cid,'executive_summary':'test','facts':[],'hypotheses':[],'counterevidence_and_conflicts':[],'open_questions':[],'metrics':{},'uncertainties':[],'provenance_annex':[]});assert d['dossier_version']=='v376' and c.db.one("SELECT report_id FROM professional_reports WHERE report_id=?",(d['report_id'],))
def test_report_idempotent_for_same_content(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);base={'case_id':cid,'executive_summary':'test','facts':[],'hypotheses':[],'counterevidence_and_conflicts':[],'open_questions':[],'metrics':{},'uncertainties':[],'provenance_annex':[]};a1=c.dossier_vnext_376.build_vnext_report(case_id=cid,base_dossier=base);a2=c.dossier_vnext_376.build_vnext_report(case_id=cid,base_dossier=base);assert a1['report_id']==a2['report_id']
def test_autonomous_cycle_contains_vnext(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);o=c.build376.run_autonomous_investigation(case_id=cid,max_ticks=1);assert 'phase16_dossier_vnext_v376' in (o.get('dossier') or {})
def test_no_auto_jobs_from_coverage(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s=source(c);workflow(c,a,cid,s);before=c.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE job_type IN ('governed_crawl_v1','governed_tor_crawl_v370')")['c'];c.build376.dossier_packet(case_id=cid);after=c.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE job_type IN ('governed_crawl_v1','governed_tor_crawl_v370')")['c'];assert before==after

def test_no_direct_network_imports_new_modules():
    root=Path(__file__).resolve().parents[1]
    for rel in ['src/eagleeye/phase16/dossier_vnext376.py','src/eagleeye/application/build376/service.py']:
        tree=ast.parse((root/rel).read_text());names={n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) and n.names};names|={n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module};assert not names.intersection({'requests','httpx','aiohttp','socket','subprocess','urllib'})
def test_no_literal_true_gate(tmp_path):
    with ctx(tmp_path) as c:assert c.build376.active_gate_literal_true_lines()==[]
def test_production_false_before_external_eval(tmp_path):
    with ctx(tmp_path) as c:g=c.build376.qualified_gate();assert g['production_release_ready'] is False and g['external_dossier_validation']=='not_run'
def test_web_health(tmp_path):
    app=create_workspace_app376(base_dir=tmp_path)
    try:r=TestClient(app).get('/health');assert r.status_code==200 and r.json()['build']=='376.0' and r.json()['crawler_improvement_build']==376
    finally:app.state.context.close()
def test_web_coverage_requires_auth(tmp_path):
    app=create_workspace_app376(base_dir=tmp_path)
    try:assert TestClient(app).get('/api/cases/x/dossier376/coverage').status_code==401
    finally:app.state.context.close()
def test_roadmap_contains_376_increment():
    t=(Path(__file__).resolve().parents[1]/'CRAWLER_ROADMAP_BUILD_370_TO_380.md').read_text();assert '376' in t and 'coverage' in t.lower() and 'stale' in t.lower()
def test_masterplan_phase_progress_16():
    t=(Path(__file__).resolve().parents[1]/'PHASE_16_MASTERPLAN_BUILD_361_TO_380.md').read_text();assert 'Build 376 actual status' in t and '16/20' in t
