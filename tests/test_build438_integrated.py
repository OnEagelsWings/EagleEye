from pathlib import Path
import runpy
from eagleeye_pro.core.app_context import AppContext

ROOT=Path(__file__).resolve().parents[1]

def ident(c):
    if c.team_identity_359.bootstrap_required():
        return c.team_identity_359.create_initial_admin(username='analyst',display_name='Analyst Fixture',password='SecureFixturePassword!2026')
    return c.team_identity_359.public_user('analyst')

def case(c,title='Fusion 438'):
    return c.build438.team_create_case(identity=ident(c),title=title,client='QA',purpose='authorized temporal relationship fusion',legal_basis='public_data')

def test_case_selftest_is_provenance_first_and_non_inferential(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i=ident(c);cid=case(c)['case_id'];r=c.build438.run_temporal_relationship_case_selftest(identity=i,case_id=cid)
        assert r['result']=='PASS';assert all(r['checks'].values())
        tl=c.build438.fused_timeline_438(cid,True);g=c.build438.fused_relationship_graph_438(cid,True)
        assert tl['event_count']>=2;assert tl['causality_inferred'] is False
        assert g['text_cooccurrence_relationships'] is False;assert g['automatic_relationship_inference'] is False
        assert c.build438.fusion_groups_438(cid)['group_count']>=2

def test_reviewed_same_entity_link_fuses_view_without_merge(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        admin=ident(c);cid=case(c,'Reviewed fusion')['case_id'];base=c.build437.run_entity_resolution_case_selftest(identity=admin,case_id=cid)
        cmp=base['comparison_packet']['comparison'];canonical=cmp['left_entity_id']
        p=c.build437.propose_same_entity_437(identity=admin,case_id=cid,comparison_id=cmp['comparison_id'],canonical_entity_id=canonical)
        c.team_governance_359.create_user(identity=admin,username='reviewer438',display_name='Reviewer 438',global_role='reviewer',password='Cedar!Orbit!Quartz!438')
        c.team_governance_359.assign_case_role(identity=admin,case_id=cid,username='reviewer438',case_role='reviewer',notes='independent Build 438 review')
        reviewer=c.team_identity_359.public_user('reviewer438')
        out=c.build437.review_same_entity_437(identity=reviewer,case_id=cid,proposal_id=p['proposal_id'],approve=True,reason='Independent source review supports a non-destructive same-entity link')
        assert out['state']=='approved' and out['destructive_merge'] is False
        groups=c.build438.fusion_groups_438(cid)
        assert groups['reviewed_same_entity_links']==1
        assert any(len(x['member_entity_ids'])==2 for x in groups['groups'])
        assert c.db.one('SELECT COUNT(*) n FROM resolution_entities_115 WHERE case_id=?',(cid,))['n']==2
        assert groups['destructive_merge'] is False


def test_reviewed_same_entity_link_survives_build437_resync(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        admin=ident(c);cid=case(c,'Reviewed fusion resync')['case_id'];base=c.build437.run_entity_resolution_case_selftest(identity=admin,case_id=cid)
        cmp=base['comparison_packet']['comparison'];canonical=cmp['left_entity_id']
        p=c.build437.propose_same_entity_437(identity=admin,case_id=cid,comparison_id=cmp['comparison_id'],canonical_entity_id=canonical)
        c.team_governance_359.create_user(identity=admin,username='reviewer438sync',display_name='Reviewer 438 Sync',global_role='reviewer',password='Cedar!Orbit!Quartz!438Sync')
        c.team_governance_359.assign_case_role(identity=admin,case_id=cid,username='reviewer438sync',case_role='reviewer',notes='independent Build 438 resync review')
        reviewer=c.team_identity_359.public_user('reviewer438sync')
        out=c.build437.review_same_entity_437(identity=reviewer,case_id=cid,proposal_id=p['proposal_id'],approve=True,reason='Independent review confirms a non-destructive same-entity link before resync')
        assert out['state']=='approved'
        before=c.build438.fusion_groups_438(cid)
        assert before['reviewed_same_entity_links']==1 and any(len(x['member_entity_ids'])==2 for x in before['groups'])
        c.build437.sync_cross_source_entities(identity=admin,case_id=cid,include_fixtures=True,min_name_similarity=.8)
        state=c.db.one('SELECT state FROM resolution_comparisons_115 WHERE comparison_id=?',(cmp['comparison_id'],))
        assert state['state']=='approved_same'
        after=c.build438.fusion_groups_438(cid)
        assert after['reviewed_same_entity_links']==1 and any(len(x['member_entity_ids'])==2 for x in after['groups'])
        assert after['destructive_merge'] is False

def test_explicit_organization_relation_becomes_edge_only(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i=ident(c);cid=case(c,'Explicit relationships')['case_id']
        src=c.build421.register_source(identity=i,name='Relationship 438 source',source_type='website',base_url='https://rel438.example.org',capabilities=['public_pages'])
        ev=c.build422.record_event(identity=i,case_id=cid,source_id=src['source_id'],target='https://rel438.example.org/record',method='manual_import')
        content=c.build423.ingest_content(identity=i,event_id=ev['event_id'],content='Alpha Foundation is a partner of Beta Network.')
        a=c.organization_intelligence_433.create_subject(identity=i,case_id=cid,display_name='Alpha Foundation',organization_type='foundation',jurisdiction='DE')
        b=c.organization_intelligence_433.create_subject(identity=i,case_id=cid,display_name='Beta Network',organization_type='network',jurisdiction='DE')
        c.organization_intelligence_433.record_observation(identity=i,case_id=cid,subject_id=a['subject_id'],source_id=src['source_id'],event_id=ev['event_id'],content_id=content['content_id'],observed_name='Alpha Foundation',observed_at='2026-09-20T10:00:00Z')
        c.organization_intelligence_433.record_observation(identity=i,case_id=cid,subject_id=b['subject_id'],source_id=src['source_id'],event_id=ev['event_id'],content_id=content['content_id'],observed_name='Beta Network',observed_at='2026-09-20T10:00:00Z')
        c.organization_intelligence_433.record_relation(identity=i,case_id=cid,source_subject_id=a['subject_id'],target_subject_id=b['subject_id'],relation_type='partner',source_id=src['source_id'],event_id=ev['event_id'],content_id=content['content_id'],source_span='partner of')
        c.build437.sync_cross_source_entities(identity=i,case_id=cid)
        g=c.build438.fused_relationship_graph_438(cid)
        assert g['edge_count']==1;edge=g['edges'][0]
        assert edge['relation_type']=='partner';assert edge['source_asserted_only'];assert edge['relationship_inferred'] is False
        assert g['text_cooccurrence_relationships'] is False and g['truth_determined'] is False

def test_machine_news_event_stays_candidate_and_does_not_create_causality(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i=ident(c);cid=case(c,'News candidate time')['case_id']
        s=c.build421.register_source(identity=i,name='News 438',source_type='news',base_url='https://news438.example.org',capabilities=['articles'])
        e=c.build422.record_event(identity=i,case_id=cid,source_id=s['source_id'],target='https://news438.example.org/a',method='http')
        o=c.build423.ingest_content(identity=i,event_id=e['event_id'],content='Alice Example appeared at an event.')
        n=c.build429.ingest_news_item(identity=i,case_id=cid,source_id=s['source_id'],event_id=e['event_id'],content_id=o['content_id'],canonical_url='https://news438.example.org/a',title='Example event',published_at='2026-09-25T10:00:00Z',external_id='n438',connector_kind='rss')
        c.build430.record_news_extraction(identity=i,news_item_id=n['news_item_id'],extractor='fixture',extractor_version='1',entities=[{'label':'Alice Example','kind':'person','confidence':.8,'source_span':'Alice Example'}],events=[{'label':'Example meeting','event_type':'meeting','time':'2026-09-24T09:30:00Z','location':'Berlin','confidence':.7,'source_span':'appeared at an event'}])
        c.build437.sync_cross_source_entities(identity=i,case_id=cid)
        tl=c.build438.fused_timeline_438(cid)
        candidates=[x for x in tl['events'] if x['semantic_kind']=='news_extracted_event_candidate']
        assert len(candidates)==1 and candidates[0]['machine_extracted_candidate']
        assert candidates[0]['truth_determined'] is False and candidates[0]['causality_inferred'] is False
        assert tl['machine_extracted_events_candidate_only'] and tl['causality_inferred'] is False

def test_fusion_run_tamper_fails_integrity(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i=ident(c);cid=case(c,'Tamper 438')['case_id'];r=c.build438.run_temporal_relationship_case_selftest(identity=i,case_id=cid)
        run_id=r['fusion_run']['run_id'];c.db.execute('UPDATE phase19_fusion_run_438 SET timeline_events=999 WHERE run_id=?',(run_id,))
        assert c.temporal_relationship_438.verify_integrity()['valid'] is False

def test_case_isolation(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i=ident(c);ca=case(c,'A438')['case_id'];cb=case(c,'B438')['case_id']
        c.build438.run_temporal_relationship_case_selftest(identity=i,case_id=ca);c.build438.run_temporal_relationship_case_selftest(identity=i,case_id=cb)
        ga=c.build438.fusion_groups_438(ca);gb=c.build438.fusion_groups_438(cb)
        assert ga['groups'] and gb['groups']
        assert not ({e['resolution_entity_id'] for g in ga['groups'] for e in g['entities']} & {e['resolution_entity_id'] for g in gb['groups'] for e in g['entities']})

def test_contract_and_launcher(tmp_path,monkeypatch):
    with AppContext(base_dir=tmp_path) as c:
        s=c.build438.temporal_relationship_status_438()
        assert s['version_coherent'];assert s['phase19_builds_completed']==18;assert s['temporal_relationship_fusion']
        assert s['reviewed_identity_links_fused_non_destructively'];assert s['provenance_preserved'];assert s['explicit_source_relationships_only']
        assert s['text_cooccurrence_relationships'] is False;assert s['automatic_identity_confirmation'] is False
        assert s['automatic_relationship_inference'] is False;assert s['causality_inferred'] is False;assert s['network_execution'] is False
        assert s['production_release_ready'] is False
    import eagleeye.interfaces.web.app438 as appmod
    calls=[];monkeypatch.setattr(appmod,'create_workspace_app438',lambda *a,**k:calls.append((a,k)))
    ns=runpy.run_path(str(ROOT/'EAGLEEYE_PRO_438_0.py'),run_name='__mp_main__');assert calls==[];assert ns['app'] is None
    assert 'app440 import create_workspace_app440' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
    assert (ROOT/'BUILD_438_CASE_TEST.md').exists();assert (ROOT/'README_BUILD_438_0.md').exists()
    readme=(ROOT/'README.md').read_text();assert 'EAGLEEYE_PRO_440_0.py' in readme and 'test_build440_integrated.py' in readme
