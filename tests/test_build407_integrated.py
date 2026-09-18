from __future__ import annotations
import pytest
from test_build394_integrated import admin
from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app407 import create_workspace_app407
from fastapi.testclient import TestClient

def ctx(tmp_path): return AppContext(base_dir=tmp_path)

def test_version_and_gate(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build407.version_status()['coherent']
        s=c.build407.data_fabric_status(); assert s['data_fabric_gate_pass']; assert not s['production_release_ready']

def test_adapters_seed_from_registry(tmp_path):
    with ctx(tmp_path) as c:
        rows=c.build407.adapters(); assert len(rows)>=6
        assert all(r['adapter_kind'] in {'rest_api','registry','bulk_dataset','local_mirror','crawler','archive','internal_evidence'} for r in rows)
        assert all(r['requires_go'] and r['provenance_required'] for r in rows)

def test_plan_is_review_first_and_network_silent(tmp_path):
    with ctx(tmp_path) as c:
        sid=c.build407.adapters()[0]['source_id']
        p=c.build407.plan(case_id='case-407-a',source_id=sid,operation='lookup',params={'q':'demo'})
        assert p['requires_go'] and not p['network_execution'] and not p['execution_authority']

def test_disabled_source_fails_closed(tmp_path):
    with ctx(tmp_path) as c:
        sid=c.build407.adapters()[0]['source_id']
        c.source_registry_v2_405.record_health(source_id=sid,health_state='disabled',detail='test disable',identity=admin(c))
        with pytest.raises(PermissionError): c.build407.plan(case_id='case-407-b',source_id=sid,operation='lookup')

def test_import_requires_provenance_and_is_not_evidence(tmp_path):
    with ctx(tmp_path) as c:
        sid=c.build407.adapters()[0]['source_id']
        p=c.build407.plan(case_id='case-407-c',source_id=sid,operation='import')
        with pytest.raises(ValueError): c.build407.import_result(plan_id=p['plan_id'],payload='x',media_type='text/plain',provenance={})
        r=c.build407.import_result(plan_id=p['plan_id'],payload='hello',media_type='text/plain',provenance={'retrieved_at':'2026-09-16T00:00:00Z','origin_ref':'synthetic://demo','collector':'tester'})
        assert r['provenance']['promotion_status']=='unreviewed_intake'
        assert r['provenance']['network_execution_by_build407'] is False

def test_payload_limit_fails_closed(tmp_path):
    with ctx(tmp_path) as c:
        sid=c.build407.adapters()[0]['source_id']; p=c.build407.plan(case_id='case-407-d',source_id=sid,operation='import')
        with pytest.raises(ValueError): c.build407.import_result(plan_id=p['plan_id'],payload=b'x'*(10_000_001),media_type='application/octet-stream',provenance={'retrieved_at':'x','origin_ref':'y','collector':'z'})

def test_integrity_detects_tamper(tmp_path):
    with ctx(tmp_path) as c:
        sid=c.build407.adapters()[0]['source_id']; p=c.build407.plan(case_id='case-407-e',source_id=sid,operation='import')
        r=c.build407.import_result(plan_id=p['plan_id'],payload='abc',media_type='text/plain',provenance={'retrieved_at':'x','origin_ref':'y','collector':'z'})
        assert c.connector_fabric_407.verify_integrity()['valid']
        c.db.execute("UPDATE connector_fabric_intake_407 SET media_type='tampered/type' WHERE intake_id=?",(r['intake_id'],))
        assert not c.connector_fabric_407.verify_integrity()['valid']

def test_app407_health_and_routes(tmp_path):
    app=create_workspace_app407(base_dir=tmp_path)
    try:
        client=TestClient(app); h=client.get('/health').json(); assert h['build']=='407.0'; assert h['connector_data_fabric']; assert h['data_fabric_gate_pass']; assert not h['production_release_ready']
        paths={r.path for r in app.routes}; assert '/api/build407/data-fabric/status' in paths
    finally:
        app.state.context.close()
