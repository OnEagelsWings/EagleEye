from __future__ import annotations
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app409 import create_workspace_app409

def ctx(tmp_path): return AppContext(base_dir=tmp_path)

def _import(c,query='demo'):
    adapters=c.build407.adapters(); sids=[a['source_id'] for a in adapters[:3]]; q=c.build408.create_search(case_id='case-409',query=query,source_ids=sids)
    for i,sid in enumerate(sids):
        c.build408.import_results(search_id=q['search_id'],source_id=sid,results=[{'title':f'R{i}','snippet':f'S{i}','canonical_ref':f'https://host{i}.example/item','provenance':{'retrieved_at':'2026-09-16T00:00:00Z','collector':'tester'}}])
    return q

def test_version_gate_and_feedback(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build409.version_status()['coherent']; s=c.build409.retrieval_quality_status(); assert s['retrieval_quality_gate_pass']; assert s['feedback_checked_before_build']; assert not s['production_release_ready']

def test_empty_search_reports_gap_not_truth(tmp_path):
    with ctx(tmp_path) as c:
        q=c.build408.create_search(case_id='case-409-empty',query='demo'); a=c.build409.assess_search(q['search_id']); assert 'no_results_imported' in a['gaps']; assert not a['coverage_sufficient_for_analysis']; assert a['truth_determined'] is False and a['truth_probability'] is None

def test_diverse_results_improve_coverage(tmp_path):
    with ctx(tmp_path) as c:
        q=_import(c); a=c.build409.assess_search(q['search_id']); assert a['coverage']['observed_sources']==3; assert a['coverage']['canonical_host_count']==3; assert a['coverage']['adapter_kind_count']>=1; assert a['network_execution'] is False; assert not a['evidence_promoted']

def test_single_source_gap_detected(tmp_path):
    with ctx(tmp_path) as c:
        sid=c.build407.adapters()[0]['source_id']; q=c.build408.create_search(case_id='case-409-one',query='demo',source_ids=[sid]); c.build408.import_results(search_id=q['search_id'],source_id=sid,results=[{'title':'A','snippet':'B','canonical_ref':'https://same.example/a','provenance':{'retrieved_at':'x','collector':'y'}}]); a=c.build409.assess_search(q['search_id']); assert a['coverage']['observed_sources']==1

def test_host_concentration_gap(tmp_path):
    with ctx(tmp_path) as c:
        sids=[a['source_id'] for a in c.build407.adapters()[:2]]; q=c.build408.create_search(case_id='case-409-host',query='demo',source_ids=sids)
        for sid in sids:
            rows=[{'title':f'{sid}-{i}','snippet':'x','canonical_ref':f'https://same.example/{sid}/{i}','provenance':{'retrieved_at':'x','collector':'y'}} for i in range(3)]
            c.build408.import_results(search_id=q['search_id'],source_id=sid,results=rows)
        a=c.build409.assess_search(q['search_id']); assert 'single_canonical_host' in a['gaps']; assert 'host_concentration_high' in a['gaps']

def test_comparison_never_ranks_truth(tmp_path):
    with ctx(tmp_path) as c:
        q1=c.build408.create_search(case_id='c1',query='a'); q2=c.build408.create_search(case_id='c2',query='b'); out=c.build409.compare_searches([q1['search_id'],q2['search_id']]); assert out['truth_ranking'] is False; assert out['network_execution'] is False

def test_app409_health_and_route(tmp_path):
    app=create_workspace_app409(base_dir=tmp_path)
    try:
        c=TestClient(app); h=c.get('/health').json(); assert h['build']=='409.0'; assert h['retrieval_quality']; assert h['retrieval_quality_gate_pass']; assert not h['production_release_ready']; assert '/api/build409/retrieval-quality/status' in {r.path for r in app.routes}
    finally: app.state.context.close()
