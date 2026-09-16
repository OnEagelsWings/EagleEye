from __future__ import annotations
import pytest
from eagleeye_pro.core.app_context import AppContext

def ctx(tmp_path): return AppContext(base_dir=tmp_path)

def test_version_and_gate(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build405.version_status()['coherent']
        g=c.build405.qualified_gate(); assert g['build_acceptance_ready'] and not g['production_release_ready']

def test_registry_v2_seeds_governed_sources(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build405.source_registry_status(); assert s['sources']>=6 and s['metadata_complete']==s['sources']
        assert not s['network_execution'] and not s['automatic_live_enablement']

def test_metadata_has_required_policy_fields(tmp_path):
    with ctx(tmp_path) as c:
        for row in c.build405.sources():
            assert row['capabilities'] and row['auth_mode'] and row['rate_limit_policy'] and row['usage_policy'] and row['provenance_class']
            assert row['health_state']=='unknown'

def test_invalid_metadata_fails_closed(tmp_path):
    with ctx(tmp_path) as c:
        sid=c.build405.sources()[0]['source_id']
        with pytest.raises(ValueError): c.source_registry_v2_405.update_metadata(source_id=sid,capabilities=['registry'],auth_mode='password_in_url',rate_limit_policy='respect provider',usage_policy='public terms',provenance_class='primary_public')
        with pytest.raises(ValueError): c.source_registry_v2_405.update_metadata(source_id=sid,capabilities=['registry'],auth_mode='none',rate_limit_policy='',usage_policy='public terms',provenance_class='primary_public')
        with pytest.raises(KeyError): c.source_registry_v2_405.update_metadata(source_id='unknown.source',capabilities=['x'],auth_mode='none',rate_limit_policy='n/a',usage_policy='public',provenance_class='primary_public')

def test_health_is_observation_not_execution_authority(tmp_path):
    with ctx(tmp_path) as c:
        sid=c.build405.sources()[0]['source_id']
        out=c.source_registry_v2_405.record_health(source_id=sid,health_state='healthy',detail='manual/test observation')
        assert out['health_state']=='healthy'
        s=c.build405.source_registry_status(); assert s['health_counts']['healthy']==1 and not s['network_execution'] and not s['automatic_live_enablement']

def test_integrity_detects_metadata_tamper(tmp_path):
    with ctx(tmp_path) as c:
        sid=c.build405.sources()[0]['source_id']; assert c.build405.source_registry_integrity()['valid']
        c.db.execute("UPDATE source_registry_v2_405 SET usage_policy='tampered' WHERE source_id=?",(sid,))
        assert not c.build405.source_registry_integrity()['valid']

def test_feedback_cycle_marked_complete(tmp_path):
    with ctx(tmp_path) as c:
        st=c.build405.phase18_status(); assert st['phase18_builds_completed']==5 and st['five_build_feedback_cycle_complete'] and st['public_feedback_due']
