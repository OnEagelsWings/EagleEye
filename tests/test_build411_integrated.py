from pathlib import Path
import pytest
from eagleeye_pro.core.app_context import AppContext
from test_build394_integrated import admin

ROOT=Path(__file__).resolve().parents[1]

def ctx(tmp_path): return AppContext(base_dir=tmp_path)

def test_version_and_gate(tmp_path):
    c=ctx(tmp_path); s=c.build411.temporal_status()
    assert c.build411.version_status()['coherent'] is True
    assert s['temporal_intelligence_gate_pass'] is True
    assert s['production_release_ready'] is False

def test_p1_governance_and_reviewer_predicates_are_authoritative(tmp_path):
    c=ctx(tmp_path); p=c.model_holdout_398.status()
    assert p['governance_compliance_hard_gate'] is True
    assert p['quality_filtered_reviewer_diversity'] is True
    assert p['harmful_overreach_veto'] is True
    src=(ROOT/'eagleeye_pro/phase17/model_holdout398.py').read_text()
    assert "governance_compliance=1" in src
    assert 'qualifying_external_reviewers' in src

def test_app401_direct_factory_bootstraps_phase18(tmp_path):
    from eagleeye.interfaces.web.app401 import create_workspace_app401
    app=create_workspace_app401(base_dir=tmp_path)
    assert getattr(app.state.context,'build401',None) is not None

def test_temporal_explicit_provenance_and_text_candidate_only(tmp_path):
    c=ctx(tmp_path); a=admin(c)
    sources=[x['source_id'] for x in c.connector_fabric_407.adapters()][:2]
    search=c.federated_search_408.create_search(case_id='case411',query='timeline',source_ids=sources,identity=a)
    s1,s2=sources
    c.federated_search_408.import_results(search_id=search['search_id'],source_id=s1,identity=a,results=[{'title':'Event happened in 2023','snippet':'Reference','canonical_ref':'https://example.test/a','provenance':{'retrieved_at':'2026-09-16T10:00:00+00:00','published_at':'2023-10-07','collector':'tester'}}])
    c.federated_search_408.import_results(search_id=search['search_id'],source_id=s2,identity=a,results=[{'title':'Another mention 2024','snippet':'Reference','canonical_ref':'https://example.test/b','provenance':{'retrieved_at':'2026-09-16T11:00:00+00:00','collector':'tester'}}])
    t=c.build411.timeline(search['search_id'])
    assert any(e['temporal_field']=='published_at' and e['temporal_value']=='2023-10-07' for e in t['events'])
    assert any(x['dates'] for x in t['text_date_candidates'])
    assert t['truth_determined'] is False and t['causality_inferred'] is False

def test_temporal_conflict_preserves_both_values(tmp_path):
    c=ctx(tmp_path); a=admin(c); sources=[x['source_id'] for x in c.connector_fabric_407.adapters()][:2]
    search=c.federated_search_408.create_search(case_id='case411b',query='conflict',source_ids=sources,identity=a)
    for idx,(sid,date) in enumerate(zip(sources,['2024-01-01','2024-02-01'])):
        c.federated_search_408.import_results(search_id=search['search_id'],source_id=sid,identity=a,results=[{'title':'Shared event','snippet':'x','canonical_ref':f'https://example.test/shared/{idx}','provenance':{'retrieved_at':'2026-09-16T10:00:00+00:00','event_date':date,'collector':'tester'}}])
    cf=c.build411.temporal_conflicts(search['search_id'])
    assert cf['conflict_count']==1
    assert cf['conflicts'][0]['automatic_resolution'] is False
    assert set(cf['conflicts'][0]['temporal_values'])=={'2024-01-01','2024-02-01'}

def test_temporal_coverage_reports_gap_without_truth(tmp_path):
    c=ctx(tmp_path); a=admin(c); source=c.connector_fabric_407.adapters()[0]['source_id']
    search=c.federated_search_408.create_search(case_id='case411c',query='undated',source_ids=[source],identity=a)
    c.federated_search_408.import_results(search_id=search['search_id'],source_id=source,identity=a,results=[{'title':'No date here','snippet':'x','canonical_ref':'https://example.test/u','provenance':{'retrieved_at':'not-a-date','collector':'tester'}}])
    cov=c.build411.temporal_coverage(search['search_id'])
    assert 'low_explicit_temporal_coverage' in cov['temporal_gaps']
    assert cov['truth_determined'] is False and cov['causality_inferred'] is False

def test_phase_status_truthful(tmp_path):
    c=ctx(tmp_path); p=c.build411.phase18_status()
    assert p['build']=='411.0' and p['phase18_builds_completed']==11
    assert p['feedback_checked_before_build'] is True
    assert p['next_feedback_check']=='before build 412'
    assert p['production_release_ready'] is False
