from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app410 import create_workspace_app410
from test_build394_integrated import admin

def ctx(tmp_path): return AppContext(base_dir=tmp_path)

def read_only(c,a):
    u=c.team_identity_359.create_user(identity=a,username='readonly410',display_name='Read Only 410',global_role='read_only',password='Quartz-Readonly-410-X9!')
    return {**u,'session_id':'ro410'}

def test_version_and_feedback_gate(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build410.version_status()['coherent']
        s=c.build410.feedback_qualification_status(); assert s['feedback_qualification_gate_pass']; assert s['public_feedback_due']; assert not s['production_release_ready']

def test_source_metadata_requires_canonical_authorized_identity(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); sid=c.build407.adapters()[0]['source_id']; row=c.source_registry_v2_405.get(sid)
        out=c.source_registry_v2_405.update_metadata(source_id=sid,capabilities=row['capabilities'],auth_mode=row['auth_mode'],rate_limit_policy=row['rate_limit_policy'],usage_policy=row['usage_policy'],provenance_class=row['provenance_class'],identity=a)
        assert out['source_id']==sid

def test_source_health_read_only_denied(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ro=read_only(c,a); sid=c.build407.adapters()[0]['source_id']
        with pytest.raises(PermissionError): c.source_registry_v2_405.record_health(source_id=sid,health_state='healthy',detail='forbidden',identity=ro)

def test_source_metadata_forged_admin_identity_denied(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ro=read_only(c,a); sid=c.build407.adapters()[0]['source_id']; row=c.source_registry_v2_405.get(sid)
        forged={**ro,'user_id':'forged-user-id','global_role':'system_administrator'}
        with pytest.raises(PermissionError): c.source_registry_v2_405.update_metadata(source_id=sid,capabilities=row['capabilities'],auth_mode=row['auth_mode'],rate_limit_policy=row['rate_limit_policy'],usage_policy=row['usage_policy'],provenance_class=row['provenance_class'],identity=forged)

def test_source_health_audit_binds_canonical_principal(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); sid=c.build407.adapters()[0]['source_id']; c.source_registry_v2_405.record_health(source_id=sid,health_state='healthy',detail='authorized',identity=a)
        h=c.db.one('SELECT actor FROM source_health_history_405 WHERE source_id=? ORDER BY id DESC LIMIT 1',(sid,)); assert h['actor']==a['username']
        assert c.source_registry_v2_405.verify_integrity()['valid']

def test_feedback_gate_includes_registry_integrity(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build410.feedback_qualification_status()['checks']['source_registry_integrity']
        sid=c.build407.adapters()[0]['source_id']; c.db.execute("UPDATE source_registry_v2_405 SET usage_policy='tampered' WHERE source_id=?",(sid,))
        assert not c.build410.feedback_qualification_status()['feedback_qualification_gate_pass']

def test_no_execution_authority_added(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build410.feedback_qualification_status(); assert s['network_execution'] is False; assert s['automatic_go'] is False; assert s['automatic_evidence_promotion'] is False

def test_app410_health_and_route(tmp_path):
    app=create_workspace_app410(base_dir=tmp_path)
    try:
        client=TestClient(app); h=client.get('/health').json(); assert h['build']=='410.0'; assert h['feedback_qualification']; assert h['feedback_qualification_gate_pass']; assert h['public_feedback_due']; assert not h['production_release_ready']
        assert '/api/build410/feedback-qualification/status' in {r.path for r in app.routes}
    finally: app.state.context.close()
