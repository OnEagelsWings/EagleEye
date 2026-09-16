from __future__ import annotations

from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase18.bootstrap410 import install_phase18_410
from eagleeye.interfaces.web.app410 import create_workspace_app410


def test_feedback_bootstrap_installs_410(tmp_path):
    with AppContext(base_dir=tmp_path) as raw:
        ctx=install_phase18_410(raw)
        assert ctx.build410.feedback_qualification_status()['build']=='410.0'
        assert ctx.build410.feedback_qualification_status()['production_release_ready'] is False


def test_feedback_app_health_is_410(tmp_path):
    app=create_workspace_app410(base_dir=tmp_path)
    with TestClient(app) as client:
        health=client.get('/health').json()
    assert health['ok'] is True
    assert health['build']=='410.0'
    assert health['feedback_qualification'] is True
    assert health['production_release_ready'] is False


def test_source_registry_rejects_forged_identity(tmp_path):
    with AppContext(base_dir=tmp_path) as raw:
        ctx=install_phase18_410(raw)
        sources=ctx.source_registry_v2_405.list_sources()
        assert sources
        forged={'username':'admin','user_id':'forged','global_role':'system_administrator'}
        try:
            ctx.source_registry_v2_405.record_health(source_id=sources[0]['source_id'],health_state='healthy',detail='forged',identity=forged)
        except (PermissionError, KeyError):
            pass
        else:
            raise AssertionError('forged identity must be rejected')


def test_410_has_no_execution_authority(tmp_path):
    with AppContext(base_dir=tmp_path) as raw:
        ctx=install_phase18_410(raw)
        q=ctx.build410.feedback_qualification_status()
        assert q['network_execution'] is False
        assert q['automatic_go'] is False
        assert q['automatic_evidence_promotion'] is False
