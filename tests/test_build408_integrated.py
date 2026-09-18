from __future__ import annotations
import pytest
from test_build394_integrated import admin
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app408 import create_workspace_app408

def ctx(tmp_path): return AppContext(base_dir=tmp_path)

def test_version_and_gate(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build408.version_status()['coherent']
        s=c.build408.federated_search_status(); assert s['federated_search_gate_pass']; assert not s['production_release_ready']

def test_feedback_checked_and_p2_health_history_integrity(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build408.federated_search_status(); assert s['feedback_checked_before_build']; assert s['checks']['source_health_history_integrity']

def test_health_history_update_tamper_detected(tmp_path):
    with ctx(tmp_path) as c:
        sid=c.build407.adapters()[0]['source_id']; c.source_registry_v2_405.record_health(source_id=sid,health_state='healthy',detail='ok',identity=admin(c))
        assert c.source_registry_v2_405.verify_integrity()['valid']
        row=c.db.one('SELECT id FROM source_health_history_405 WHERE source_id=? ORDER BY id DESC LIMIT 1',(sid,))
        c.db.execute("UPDATE source_health_history_405 SET health_detail='tampered' WHERE id=?",(row['id'],))
        x=c.source_registry_v2_405.verify_integrity(); assert not x['valid']; assert not x['health_history_valid']

def test_health_history_delete_tamper_detected(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); sid=c.build407.adapters()[0]['source_id']; c.source_registry_v2_405.record_health(source_id=sid,health_state='healthy',detail='first',identity=a); c.source_registry_v2_405.record_health(source_id=sid,health_state='degraded',detail='second',identity=a)
        assert c.source_registry_v2_405.verify_integrity()['valid']
        row=c.db.one('SELECT id FROM source_health_history_405 WHERE source_id=? ORDER BY id LIMIT 1',(sid,)); c.db.execute('DELETE FROM source_health_history_405 WHERE id=?',(row['id'],))
        x=c.source_registry_v2_405.verify_integrity(); assert not x['valid']; assert any(v['reason']=='anchor_mismatch' for v in x['health_history_violations'])

def test_search_plan_is_federated_but_network_silent(tmp_path):
    with ctx(tmp_path) as c:
        q=c.build408.create_search(case_id='case-408-a',query='Example person company relationship')
        assert len(q['source_plan'])>=6
        assert not q['network_execution'] and not q['automatic_go']
        assert all(p['network_execution'] is False for p in q['source_plan'])

def test_disabled_source_excluded(tmp_path):
    with ctx(tmp_path) as c:
        sid=c.build407.adapters()[0]['source_id']; c.source_registry_v2_405.record_health(source_id=sid,health_state='disabled',detail='disabled for test',identity=admin(c))
        q=c.build408.create_search(case_id='case-408-b',query='demo')
        assert sid not in {p['source_id'] for p in q['source_plan']}
        with pytest.raises(ValueError): c.build408.create_search(case_id='case-408-b',query='demo',source_ids=[sid])

def test_import_normalizes_dedupes_and_never_promotes(tmp_path):
    with ctx(tmp_path) as c:
        sid=c.build407.adapters()[0]['source_id']; q=c.build408.create_search(case_id='case-408-c',query='demo',source_ids=[sid])
        rows=[{'title':'Alpha','snippet':'Example','canonical_ref':'https://example.invalid/a','provenance':{'retrieved_at':'2026-09-16T00:00:00Z','collector':'tester'}},{'title':'Alpha duplicate','snippet':'Other','canonical_ref':'https://example.invalid/a','provenance':{'retrieved_at':'2026-09-16T00:00:00Z','collector':'tester'}}]
        out=c.build408.import_results(search_id=q['search_id'],source_id=sid,results=rows)
        assert len(out)==1; assert out[0]['provenance']['promotion_status']=='search_result_unreviewed'; assert out[0]['provenance']['network_execution_by_build408'] is False

def test_import_requires_provenance(tmp_path):
    with ctx(tmp_path) as c:
        sid=c.build407.adapters()[0]['source_id']; q=c.build408.create_search(case_id='case-408-d',query='demo',source_ids=[sid])
        with pytest.raises(ValueError): c.build408.import_results(search_id=q['search_id'],source_id=sid,results=[{'title':'x','snippet':'y','provenance':{}}])

def test_federated_integrity_detects_tamper(tmp_path):
    with ctx(tmp_path) as c:
        sid=c.build407.adapters()[0]['source_id']; q=c.build408.create_search(case_id='case-408-e',query='demo',source_ids=[sid]); out=c.build408.import_results(search_id=q['search_id'],source_id=sid,results=[{'title':'x','snippet':'y','provenance':{'retrieved_at':'x','collector':'z'}}])
        assert c.federated_search_408.verify_integrity()['valid']; c.db.execute("UPDATE federated_search_result_408 SET title='tampered' WHERE result_id=?",(out[0]['result_id'],)); assert not c.federated_search_408.verify_integrity()['valid']

def test_app408_health_and_route(tmp_path):
    app=create_workspace_app408(base_dir=tmp_path)
    try:
        c=TestClient(app); h=c.get('/health').json(); assert h['build']=='408.0'; assert h['federated_search']; assert h['federated_search_gate_pass']; assert h['source_health_history_integrity']; assert not h['production_release_ready']
        assert '/api/build408/federated-search/status' in {r.path for r in app.routes}
    finally: app.state.context.close()
