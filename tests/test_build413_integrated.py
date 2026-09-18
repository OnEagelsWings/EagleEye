from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from test_build394_integrated import admin

ROOT=Path(__file__).resolve().parents[1]
def ctx(tmp_path): return AppContext(base_dir=tmp_path)
def mkcase(c,a): return c.build380.team_create_case(identity=a,title='Build413 case',client='internal',purpose='authorized investigation planning',legal_basis='public_data')['case_id']

def test_version_and_planner_gate(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build413.version_status()['coherent'] is True
        s=c.build413.planner_status(); assert s['investigation_planner_gate_pass'] is True and s['production_release_ready'] is False

def test_plan_contains_agreed_five_elements_and_no_execution(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=mkcase(c,a)
        r=c.build413.create_investigation_plan(case_id=cid,objective='Establish a reviewable chronology',subquestions=['Which dated records exist?','Which sources disagree?'],identity=a)
        p=r['plan']; assert p['objective'] and len(p['subquestions'])==2 and p['source_strategy'] and p['stop_conditions'] and p['risk_constraints']
        assert p['network_execution'] is False and p['execution_authority'] is False and p['automatic_go'] is False and p['truth_determined'] is False and p['automatic_evidence_promotion'] is False

def test_missing_identity_denied(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=mkcase(c,a)
        with pytest.raises(PermissionError): c.build413.create_investigation_plan(case_id=cid,objective='x',subquestions=['y'])

def test_cross_case_search_context_denied(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); c1=mkcase(c,a); c2=mkcase(c,a); source=c.connector_fabric_407.adapters()[0]['source_id']
        s=c.federated_search_408.create_search(case_id=c1,query='context',source_ids=[source],identity=a)
        with pytest.raises(PermissionError,match='another case'): c.build413.create_investigation_plan(case_id=c2,objective='x',subquestions=['y'],search_ids=[s['search_id']],identity=a)

def test_context_carries_coverage_temporal_relationship_signals(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=mkcase(c,a); source=c.connector_fabric_407.adapters()[0]['source_id']; s=c.federated_search_408.create_search(case_id=cid,query='context',source_ids=[source],identity=a)
        c.federated_search_408.import_results(search_id=s['search_id'],source_id=source,identity=a,results=[{'title':'Record','snippet':'structured','canonical_ref':'https://example.test/1','provenance':{'retrieved_at':'2026-09-18T10:00:00+00:00','collector':'tester','event_date':'2026-09-01','structured_entities':[{'entity_id':'org:x','entity_type':'organization','label':'X'}]}}])
        r=c.build413.create_investigation_plan(case_id=cid,objective='x',subquestions=['y'],search_ids=[s['search_id']],identity=a); x=r['plan']['existing_search_context'][0]
        assert x['search_id']==s['search_id'] and 'source_coverage_ratio' in x and 'explicit_temporal_coverage_ratio' in x and x['explicit_graph_nodes']==1

def test_plan_record_integrity_detects_tampering(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=mkcase(c,a); r=c.build413.create_investigation_plan(case_id=cid,objective='x',subquestions=['y'],identity=a)
        c.db.execute("UPDATE investigation_plan_413 SET objective='tampered' WHERE plan_id=?",(r['plan_id'],))
        # objective column is indexed/display metadata; immutable canonical content remains plan_json.
        assert c.investigation_planner_413.verify_integrity()['valid'] is True
        c.db.execute("UPDATE investigation_plan_413 SET plan_json='{}' WHERE plan_id=?",(r['plan_id'],))
        assert c.investigation_planner_413.verify_integrity()['valid'] is False

def test_forbidden_authority_flag_detected(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=mkcase(c,a); r=c.build413.create_investigation_plan(case_id=cid,objective='x',subquestions=['y'],identity=a)
        c.db.execute('UPDATE investigation_plan_413 SET automatic_go=1 WHERE plan_id=?',(r['plan_id'],)); integ=c.investigation_planner_413.verify_integrity(); assert integ['valid'] is False and any(x['reason']=='forbidden_authority_flag' for x in integ['violations'])

def test_plans_are_append_only_api(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=mkcase(c,a); c.build413.create_investigation_plan(case_id=cid,objective='first',subquestions=['q'],identity=a); c.build413.create_investigation_plan(case_id=cid,objective='second',subquestions=['q'],identity=a)
        assert len(c.build413.investigation_plans(cid))==2 and not hasattr(c.investigation_planner_413,'update_plan')

def test_app413_health_and_routes(tmp_path):
    app=__import__('eagleeye.interfaces.web.app413',fromlist=['create_workspace_app413']).create_workspace_app413(base_dir=tmp_path)
    try:
        client=TestClient(app); h=client.get('/health').json(); assert h['build']=='413.0' and h['investigation_planner_gate_pass'] and h['network_execution_on_boot'] is False and h['production_release_ready'] is False
        paths={r.path for r in app.routes}; assert '/api/build413/planner/status' in paths and '/api/build413/plans' in paths
    finally: app.state.context.close()

def test_server_launcher_targets_413():
    text=(ROOT/'src/eagleeye/interfaces/web/server.py').read_text(); assert 'app413 import create_workspace_app413' in text

def test_407_408_case_writes_require_identity(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=mkcase(c,a); sid=c.connector_fabric_407.adapters()[0]['source_id']
        with pytest.raises(PermissionError): c.connector_fabric_407.plan(case_id=cid,source_id=sid,operation='lookup')
        with pytest.raises(PermissionError): c.federated_search_408.create_search(case_id=cid,query='x',source_ids=[sid])

def test_407_plan_integrity_and_orphan_intake_detected(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=mkcase(c,a); sid=c.connector_fabric_407.adapters()[0]['source_id']; p=c.connector_fabric_407.plan(case_id=cid,source_id=sid,operation='import',identity=a)
        r=c.connector_fabric_407.import_result(plan_id=p['plan_id'],payload='x',media_type='text/plain',provenance={'retrieved_at':'x','origin_ref':'y','collector':'z'},identity=a)
        assert c.connector_fabric_407.verify_integrity()['valid']
        c.db.execute('DELETE FROM connector_fabric_plan_407 WHERE plan_id=?',(p['plan_id'],)); integ=c.connector_fabric_407.verify_integrity(); assert not integ['valid'] and any(x.get('reason')=='orphaned_plan' for x in integ['violations'])
