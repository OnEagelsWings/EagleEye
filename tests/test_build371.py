from __future__ import annotations
import ast, json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from eagleeye.crawler.engine import FetchResponse, StaticTransport
from eagleeye.interfaces.web.app371 import create_workspace_app371
from eagleeye.phase16.entity_resolution371 import LEAD_JOB, POLICY
from eagleeye_pro.core.app_context import AppContext

PW='Orbit-Pine-Quartz-371!'; RPW='Review-Cedar-Quartz-371!'; SEED='https://example.org/entity-source'
def ctx(tmp_path): return AppContext(base_dir=tmp_path,actor='test371')
def admin(c):
    u=c.team_identity_359.create_initial_admin(username='admin371',display_name='Admin 371',password=PW); return {**u,'session_id':'admin-session-371'}
def case(c,a,title='Entity Case'): return c.build371.team_create_case(identity=a,title=title,client='QA',purpose='authorized entity resolution',legal_basis='public_data')
def reviewer(c,a,cid):
    u=c.team_identity_359.create_user(identity=a,username='reviewer371',display_name='Reviewer 371',global_role='reviewer',password=RPW); c.team_identity_359.assign_case(identity=a,case_id=cid,username=u['username'],case_role='reviewer'); return {**u,'session_id':'review-session-371'}
def ent(c,a,cid,name='Alice Example',email='alice@example.org',external='ID-1',refs=('source:A','source:B')):
    anchors=[]
    if email: anchors.append({'type':'email','value':email,'reliability':.95,'source_ref':refs[0]})
    if external: anchors.append({'type':'external_id','value':external,'reliability':.9,'source_ref':refs[1]})
    return c.build371.register_entity_candidate(case_id=cid,entity_type='person',display_name=name,identity=a,anchors=anchors)['entity']['resolution_entity_id']
def source_and_crawl(c,a,cid):
    s=c.crawler_frontier_352.register_source(display_name='Entity Source',seed_urls=[SEED],terms_ref='public read-only terms',max_depth=0,max_pages=1,requests_per_minute=5,max_response_bytes=100000)
    s=c.crawler_frontier_352.review_source(s['source_id'],decision='approve_read_only',rationale='reviewed public source',reviewer='admin371')
    q=c.crawler_frontier_352.enqueue_crawl(case_id=cid,source_id=s['source_id'])
    t=StaticTransport({'https://example.org/robots.txt':FetchResponse('https://example.org/robots.txt',404,{'content-type':'text/plain'},b'',1),SEED:FetchResponse(SEED,200,{'content-type':'text/html'},b'<html>Alice Example ID-1</html>',2)})
    out=c.build371.crawler_run_next(worker_id='crawl371',transport=t,resolver=lambda h:['93.184.216.34'],case_id=cid)
    fetch=c.db.one('SELECT fetch_id FROM phase15_crawl_fetches WHERE crawl_run_id=? AND status_code=200',(q['crawl_run_id'],))
    return s,q['crawl_run_id'],fetch['fetch_id'],out

# 1
def test_version_schema(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build371.version_status()=={'runtime_build':'371.0','schema_version':'371.0','package_version':'371.0.0','coherent':True}
        m=c.build371.schema_metrics(); assert m['within_gate'] and (m['table'],m['index'],m['trigger'])==(165,133,8) and m['build371_specific_tables_added']==0
# 2
def test_phase_progress(tmp_path):
    with ctx(tmp_path) as c: assert c.build371.phase16_status()['builds_completed']==11
# 3
def test_no_new_tables(tmp_path):
    with ctx(tmp_path) as c: assert c.crawler_entity_link_371.status()['new_per_build_data_tables']==0
# 4
def test_entity_v2_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s=c.entity_resolution_v2_371.status(); assert s['entity_resolution_v2'] and not s['score_is_probability'] and not s['automatic_merge'] and not s['automatic_identity_confirmation']
# 5
def test_register_candidate_only(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];o=c.build371.register_entity_candidate(case_id=cid,entity_type='person',display_name='Alice Example',identity=a); assert o['candidate_only'] and not o['identity_confirmed']
# 6
def test_cross_case_compare_blocked(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);ca=case(c,a,'A')['case_id'];cb=case(c,a,'B')['case_id'];x=ent(c,a,ca);y=ent(c,a,cb)
        with pytest.raises(PermissionError): c.build371.compare_entities_v2(case_id=ca,left_entity_id=x,right_entity_id=y,identity=a)
# 7
def test_strong_independent_candidate(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];x=ent(c,a,cid,refs=('source:A','source:B'));y=ent(c,a,cid,refs=('source:C','source:D'));o=c.build371.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a); assert o['classification']=='strong_review_candidate' and o['v2']['independent_source_count']>=2
# 8
def test_score_not_probability(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));o=c.build371.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a); assert o['v2']['score_is_probability'] is False
# 9
def test_email_conflict_veto(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];x=ent(c,a,cid,email='a@example.org',external='');y=ent(c,a,cid,email='b@example.org',external='');o=c.build371.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a); assert o['classification']=='likely_distinct' and o['v2']['strong_identifier_conflict_veto']
# 10
def test_external_id_conflict_veto(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];x=ent(c,a,cid,email='',external='X1');y=ent(c,a,cid,email='',external='X2');o=c.build371.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a); assert o['classification']=='likely_distinct'
# 11
def test_birth_year_conflict_penalty(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];x=c.build371.register_entity_candidate(case_id=cid,entity_type='person',display_name='Alex Doe',identity=a,anchors=[{'type':'birth_year','value':'1980','source_ref':'source:A'}])['entity']['resolution_entity_id'];y=c.build371.register_entity_candidate(case_id=cid,entity_type='person',display_name='Alex Doe',identity=a,anchors=[{'type':'birth_year','value':'1990','source_ref':'source:B'}])['entity']['resolution_entity_id'];o=c.build371.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a); assert o['v2']['conflicts'][0]['type']=='birth_year' and o['v2']['evidence_weight']<.7
# 12
def test_common_name_penalty(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];ids=[c.build371.register_entity_candidate(case_id=cid,entity_type='person',display_name='John Smith',identity=a)['entity']['resolution_entity_id'] for _ in range(4)];o=c.build371.compare_entities_v2(case_id=cid,left_entity_id=ids[0],right_entity_id=ids[1],identity=a); assert o['v2']['common_name_count']==4 and o['v2']['common_name_penalty']>0
# 13
def test_independent_sources_bonus(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];x=ent(c,a,cid,refs=('source:A','source:B'));y=ent(c,a,cid,refs=('source:C','source:D'));o=c.build371.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a); assert len(o['v2']['independent_source_families'])>=4
# 14
def test_comparison_persisted_needs_review(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));o=c.build371.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a);row=c.db.one('SELECT state FROM resolution_comparisons_115 WHERE comparison_id=?',(o['comparison_id'],));assert row['state']=='needs_review'
# 15
def test_event_chain_remains_valid(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));c.build371.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a);assert c.entity_resolution_115.verify_event_chain(cid)['valid']
# 16
def test_weak_candidate_cannot_propose_merge(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];x=c.build371.register_entity_candidate(case_id=cid,entity_type='person',display_name='Alice A',identity=a)['entity']['resolution_entity_id'];y=c.build371.register_entity_candidate(case_id=cid,entity_type='person',display_name='Bob B',identity=a)['entity']['resolution_entity_id'];o=c.build371.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a)
        with pytest.raises(ValueError):c.build371.propose_same_entity(case_id=cid,comparison_id=o['comparison_id'],canonical_entity_id=x,identity=a)
# 17
def test_human_proposal_only(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));o=c.build371.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a);p=c.build371.propose_same_entity(case_id=cid,comparison_id=o['comparison_id'],canonical_entity_id=x,identity=a);assert p['state']=='pending' and not p['automatic_merge']
# 18
def test_same_requester_cannot_review(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));o=c.build371.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a);p=c.build371.propose_same_entity(case_id=cid,comparison_id=o['comparison_id'],canonical_entity_id=x,identity=a)
        with pytest.raises(PermissionError):c.build371.review_same_entity(case_id=cid,proposal_id=p['proposal_id'],identity=a,approve=True,reason='Independent review supports same entity')
# 19
def test_independent_review_creates_non_destructive_link(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];r=reviewer(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));o=c.build371.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a);p=c.build371.propose_same_entity(case_id=cid,comparison_id=o['comparison_id'],canonical_entity_id=x,identity=a);v=c.build371.review_same_entity(case_id=cid,proposal_id=p['proposal_id'],identity=r,approve=True,reason='Independent evidence review supports a non-destructive same-entity link');assert v['state']=='approved' and not v['destructive_merge'];assert c.db.one('SELECT COUNT(*) c FROM resolution_entities_115 WHERE case_id=?',(cid,))['c']==2
# 20
def test_rejected_review_marks_distinct(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];r=reviewer(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));o=c.build371.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a);p=c.build371.propose_same_entity(case_id=cid,comparison_id=o['comparison_id'],canonical_entity_id=x,identity=a);v=c.build371.review_same_entity(case_id=cid,proposal_id=p['proposal_id'],identity=r,approve=False,reason='Independent review finds insufficient evidence for same entity');assert v['state']=='rejected'
# 21
def test_crawl_provenance_hash(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];s,run,fid,_=source_and_crawl(c,a,cid);p=c.build371.crawl_entity_provenance(crawl_run_id=run,fetch_id=fid);assert p['source_id']==s['source_id'] and len(p['provenance_hash'])==64 and p['fetch_count']==1
# 22
def test_crawl_provenance_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,_,_=source_and_crawl(c,a,cid);p=c.build371.crawl_entity_provenance(crawl_run_id=run);assert p['case_id']==cid
# 23
def test_lead_enqueue_uses_canonical_job_ledger(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,fid,_=source_and_crawl(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));o=c.build371.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a,rationale='crawler source mentions candidate');assert o['job']['job_type']==LEAD_JOB and not o['network_execution'];assert c.db.one('SELECT job_type FROM phase15_jobs WHERE job_id=?',(o['job']['job_id'],))['job_type']==LEAD_JOB
# 24
def test_lead_deduplicates(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,fid,_=source_and_crawl(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));a1=c.build371.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);a2=c.build371.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);assert a1['job']['job_id']==a2['job']['job_id'] and a2['job']['deduplicated']
# 25
def test_cross_case_lead_blocked(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);ca=case(c,a,'A')['case_id'];cb=case(c,a,'B')['case_id'];_,run,fid,_=source_and_crawl(c,a,ca);x=ent(c,a,ca);y=ent(c,a,cb)
        with pytest.raises(PermissionError):c.build371.enqueue_entity_link_lead(case_id=ca,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a)
# 26
def test_lead_rejects_same_entity(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,fid,_=source_and_crawl(c,a,cid);x=ent(c,a,cid)
        with pytest.raises(ValueError):c.build371.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=x,identity=a)
# 27
def test_generic_crawler_worker_does_not_claim_entity_lead(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,fid,_=source_and_crawl(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));c.build371.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);assert c.crawler_production_369.claim_next(worker_id='crawler',case_id=cid) is None
# 28
def test_entity_lead_worker_claims_only_lead(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];c.job_engine_348.enqueue(job_type='other',payload={},case_id=cid,priority=0);_,run,fid,_=source_and_crawl(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));c.build371.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);j=c.crawler_entity_link_371.claim_next(worker_id='entity-worker',case_id=cid);assert j['job_type']==LEAD_JOB
# 29
def test_lead_worker_produces_review_packet(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,fid,_=source_and_crawl(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));c.build371.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);o=c.build371.entity_lead_run_next(worker_id='entity-worker',case_id=cid);assert o['state']=='review_ready' and o['result']['review_required'] and not o['result']['automatic_merge']
# 30
def test_lead_worker_no_network_budget(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,fid,_=source_and_crawl(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));o=c.build371.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);rate=json.loads(o['job']['rate_budget_json']);assert rate['max_requests']==0
# 31
def test_provenance_tamper_fails_worker(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,fid,_=source_and_crawl(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));o=c.build371.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);p=json.loads(o['job']['payload_json']);p['provenance_hash']='0'*64;c.db.execute('UPDATE phase15_jobs SET payload_json=? WHERE job_id=?',(json.dumps(p),o['job']['job_id']));r=c.build371.entity_lead_run_next(worker_id='w',case_id=cid);assert r['state']=='failed'
# 32
def test_opsec_cancels_tampered_lead(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,fid,_=source_and_crawl(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));o=c.build371.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);p=json.loads(o['job']['payload_json']);p['lead_only']=False;c.db.execute('UPDATE phase15_jobs SET payload_json=? WHERE job_id=?',(json.dumps(p),o['job']['job_id']));r=c.build371.autonomous_opsec_protect(case_id=cid);assert o['job']['job_id'] in r['cancelled_invalid_entity_lead_jobs']
# 33
def test_opsec_no_merge_authority(tmp_path):
    with ctx(tmp_path) as c:
        s=c.opsec_supervisor_371.status();assert not s['automatic_merge_authority'] and not s['system_mutations']
# 34
def test_ai_no_merge_authority(tmp_path):
    with ctx(tmp_path) as c:
        s=c.ai_autonomy_371.status();assert not s['automatic_entity_merge'] and not s['direct_merge_approval_authority'] and not s['direct_entity_lead_enqueue_authority']
# 35
def test_ai_dossier_entity_context(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));c.build371.compare_entities_v2(case_id=cid,left_entity_id=x,right_entity_id=y,identity=a);c.build371.create_investigation_intake(case_id=cid,objective='Resolve identity carefully',key_questions=['Same entity?']);c.build371.start_investigation_go(case_id=cid,go='GO');o=c.build371.run_autonomous_investigation(case_id=cid,max_ticks=1);assert 'phase16_entity_resolution_v2' in o['dossier'] and o['dossier']['entity_resolution_review_required']
# 36
def test_crawler_status_increment(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build371.crawler_status();assert s['crawler_improvement_build']==371 and s['entity_linked_crawl_provenance'] and s['source_to_entity_lead_queue'] and not s['entity_lead_auto_merge']
# 37
def test_crawler_program_still_continuous(tmp_path):
    with ctx(tmp_path) as c:assert c.build371.crawler_status()['continuous_crawler_expansion_370_380']
# 38
def test_tor_boundaries_preserved(tmp_path):
    with ctx(tmp_path) as c:
        s=c.tor_gateway_370.status();assert not s['control_port_authority'] and not s['newnym_authority'] and not s['torrc_mutation']
# 39
def test_case_status_is_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);ca=case(c,a,'A')['case_id'];cb=case(c,a,'B')['case_id'];ent(c,a,ca);assert c.build371.entity_case_status(case_id=ca)['entities']==1 and c.build371.entity_case_status(case_id=cb)['entities']==0
# 40
def test_entity_lead_status_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);ca=case(c,a,'A')['case_id'];cb=case(c,a,'B')['case_id'];_,run,fid,_=source_and_crawl(c,a,ca);x=ent(c,a,ca);y=ent(c,a,ca,refs=('source:C','source:D'));c.build371.enqueue_entity_link_lead(case_id=ca,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);assert len(c.build371.entity_lead_case_status(case_id=ca)['lead_jobs'])==1 and c.build371.entity_lead_case_status(case_id=cb)['lead_jobs']==[]
# 41
def test_expired_lead_lease_recovery(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);cid=case(c,a)['case_id'];_,run,fid,_=source_and_crawl(c,a,cid);x=ent(c,a,cid);y=ent(c,a,cid,refs=('source:C','source:D'));o=c.build371.enqueue_entity_link_lead(case_id=cid,crawl_run_id=run,fetch_id=fid,target_entity_id=x,candidate_entity_id=y,identity=a);j=c.crawler_entity_link_371.claim_next(worker_id='dead',case_id=cid);c.db.execute("UPDATE phase15_jobs SET lease_expires_at='2000-01-01T00:00:00+00:00',checkpoint_json='{""step"":1}' WHERE job_id=?",(j['job_id'],));r=c.build371.entity_lead_recover_expired_leases(case_id=cid);assert j['job_id'] in r['recovered_jobs'] and c.job_engine_348.get(j['job_id'])['status']=='queued'
# 42
def test_web_health_and_auth(tmp_path):
    app=create_workspace_app371(base_dir=tmp_path/'web')
    with TestClient(app) as client:
        h=client.get('/health');assert h.status_code==200 and h.json()['build']=='371.0' and h.json()['phase16_builds_completed']==11 and h.json()['entity_linked_crawl_provenance'];assert client.get('/api/build371/final-status').status_code==401
# 43
def test_new_modules_no_direct_network_or_subprocess_imports():
    bad={'requests','httpx','aiohttp','socket','subprocess'};found=set()
    for p in [Path('src/eagleeye/phase16/entity_resolution371.py'),Path('src/eagleeye/application/build371/service.py'),Path('src/eagleeye/interfaces/web/app371.py')]:
        tree=ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):found.update(x.name.split('.')[0] for x in n.names)
            elif isinstance(n,ast.ImportFrom) and n.module:found.add(n.module.split('.')[0])
    assert not found.intersection(bad)
# 44
def test_build_gate_has_no_literal_true(tmp_path):
    with ctx(tmp_path) as c:assert c.build371.active_gate_literal_true_lines()==[]
# 45
def test_truthful_release_false(tmp_path):
    with ctx(tmp_path) as c:assert c.build371.qualified_gate()['production_release_ready'] is False and c.build371.qualified_gate()['entity_resolution_external_evaluation']=='scheduled_build_372'
# 46
def test_masterplan_crawler_371_increment():
    t=Path('PHASE_16_MASTERPLAN_BUILD_361_TO_380.md').read_text();assert '| 371 |' in t and 'entity-linked crawl provenance' in t.lower()
# 47
def test_roadmap_371_increment():
    t=Path('CRAWLER_ROADMAP_BUILD_370_TO_380.md').read_text().lower();assert '371' in t and 'entity' in t and 'auto-merge' in t
# 48
def test_phase_status_reports_v2_and_crawler(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build371.phase16_status();assert s['entity_resolution_v2']['entity_resolution_v2'] and s['crawler_entity_linkage']['source_to_entity_lead_queue']
