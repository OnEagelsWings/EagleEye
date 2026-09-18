from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from test_build394_integrated import admin

ROOT=Path(__file__).resolve().parents[1]

def ctx(tmp_path): return AppContext(base_dir=tmp_path)

def _search_with_graph(c,a,case_id='case412'):
    source=c.connector_fabric_407.adapters()[0]['source_id']
    search=c.federated_search_408.create_search(case_id=case_id,query='explicit relationship graph',source_ids=[source],identity=a)
    prov={
        'retrieved_at':'2026-09-17T10:00:00+00:00','collector':'tester',
        'structured_entities':[
            {'entity_id':'person:alice','entity_type':'person','label':'Alice Example'},
            {'entity_id':'company:acme','entity_type':'organization','label':'Acme GmbH'},
            {'entity_id':'place:berlin','entity_type':'place','label':'Berlin'},
        ],
        'structured_relationships':[
            {'subject_id':'person:alice','predicate':'director_of','object_id':'company:acme','assertion_ref':'registry-row-1'},
            {'subject_id':'company:acme','predicate':'registered_in','object_id':'place:berlin','assertion_ref':'registry-row-2'},
        ],
    }
    c.federated_search_408.import_results(search_id=search['search_id'],source_id=source,identity=a,results=[{'title':'Registry extract','snippet':'Alice and Acme are mentioned together.','canonical_ref':'https://example.test/registry/1','provenance':prov}])
    return search

def test_version_and_relationship_gate(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build412.version_status()['coherent'] is True
        s=c.build412.relationship_status(); assert s['relationship_intelligence_gate_pass'] is True
        assert s['production_release_ready'] is False

def test_inactive_registry_identity_is_denied(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); sid=c.source_registry_v2_405.list_sources()[0]['source_id']; row=c.source_registry_v2_405.get(sid)
        c.db.execute('UPDATE phase15_team_users SET active=0 WHERE user_id=?',(a['user_id'],))
        with pytest.raises(PermissionError,match='inactive'):
            c.source_registry_v2_405.update_metadata(source_id=sid,capabilities=row['capabilities'],auth_mode=row['auth_mode'],rate_limit_policy=row['rate_limit_policy'],usage_policy=row['usage_policy'],provenance_class=row['provenance_class'],identity=a)

def test_registry_integrity_detects_deleted_row_and_orphan_history(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); sid=c.source_registry_v2_405.list_sources()[0]['source_id']
        c.source_registry_v2_405.record_health(source_id=sid,health_state='healthy',detail='authorized observation',identity=a)
        c.db.execute('DELETE FROM source_registry_v2_405 WHERE source_id=?',(sid,))
        integ=c.source_registry_v2_405.verify_integrity()
        assert integ['valid'] is False and integ['registry_reconciled'] is False
        reasons={x['reason'] for x in integ['violations']}; assert 'missing_registry_row' in reasons and 'orphaned_history' in reasons

def test_explicit_structured_relationships_become_graph_edges(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); search=_search_with_graph(c,a)
        g=c.build412.relationship_graph(search['search_id'])
        assert g['node_count']==3 and g['edge_count']==2
        assert all(e['relationship_inferred'] is False for e in g['edges'])
        assert all(e['assertions'][0]['basis']=='explicit_structured_provenance' for e in g['edges'])
        assert g['truth_determined'] is False and g['automatic_evidence_promotion'] is False

def test_text_cooccurrence_does_not_create_relationship(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); source=c.connector_fabric_407.adapters()[0]['source_id']
        search=c.federated_search_408.create_search(case_id='case412text',query='text only',source_ids=[source],identity=a)
        c.federated_search_408.import_results(search_id=search['search_id'],source_id=source,identity=a,results=[{'title':'Alice Example works at Acme GmbH','snippet':'Alice Example and Acme GmbH appear together.','canonical_ref':'https://example.test/text','provenance':{'retrieved_at':'2026-09-17T10:00:00+00:00','collector':'tester'}}])
        g=c.build412.relationship_graph(search['search_id'])
        assert g['node_count']==0 and g['edge_count']==0
        assert g['unstructured_result_ids'] and g['text_cooccurrence_relationships'] is False

def test_unresolved_relationship_endpoint_fails_closed(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); source=c.connector_fabric_407.adapters()[0]['source_id']
        search=c.federated_search_408.create_search(case_id='case412bad',query='bad endpoint',source_ids=[source],identity=a)
        prov={'retrieved_at':'2026-09-17T10:00:00+00:00','collector':'tester','structured_entities':[{'entity_id':'person:alice','entity_type':'person','label':'Alice'}],'structured_relationships':[{'subject_id':'person:alice','predicate':'director_of','object_id':'company:missing'}]}
        c.federated_search_408.import_results(search_id=search['search_id'],source_id=source,identity=a,results=[{'title':'Partial record','snippet':'x','canonical_ref':'https://example.test/partial','provenance':prov}])
        g=c.build412.relationship_graph(search['search_id'])
        assert g['edge_count']==0
        assert any(x['reason']=='unresolved_endpoint' for x in g['malformed_or_unresolved'])

def test_neighborhood_and_paths_use_only_explicit_edges(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); search=_search_with_graph(c,a,'case412paths')
        n=c.build412.neighborhood(search['search_id'],'company:acme')
        assert set(n['neighbor_ids'])=={'person:alice','place:berlin'}
        p=c.build412.relationship_paths(search['search_id'],'person:alice','place:berlin',4)
        assert p['path_count']==1 and p['paths'][0]['explicit_edge_count']==2
        assert p['derived_only_from_explicit_edges'] is True and p['relationship_inference_performed'] is False

def test_app412_health_and_routes(tmp_path):
    app=__import__('eagleeye.interfaces.web.app412',fromlist=['create_workspace_app412']).create_workspace_app412(base_dir=tmp_path)
    try:
        client=TestClient(app); h=client.get('/health').json()
        assert h['build']=='412.0' and h['relationship_intelligence_gate_pass'] and h['registry_remediation_gate_pass']
        assert h['network_execution_on_boot'] is False and h['production_release_ready'] is False
        paths={r.path for r in app.routes}; assert '/api/build412/relationships/status' in paths
    finally: app.state.context.close()
