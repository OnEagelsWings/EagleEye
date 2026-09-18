from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from test_build394_integrated import admin
ROOT=Path(__file__).resolve().parents[1]
def case(c,a): return c.build380.team_create_case(identity=a,title='415',client='internal',purpose='multi agent investigation',legal_basis='public_data')['case_id']
def plan(c,a,cid): return c.build413.create_investigation_plan(case_id=cid,objective='Establish reviewable chronology',subquestions=['Find dated records','Challenge assumptions'],identity=a)
def test_version_and_gate(tmp_path):
 with AppContext(base_dir=tmp_path) as c: assert c.build415.version_status()['coherent']; assert c.build415.multi_agent_status()['multi_agent_gate_pass']
def test_session_is_case_plan_bound(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); cid=case(c,a); p=plan(c,a,cid); s=c.build415.create_multi_agent_session(plan_id=p['plan_id'],identity=a); assert s['case_id']==cid and s['plan_hash']==p['plan_hash'] and s['state']=='analysis_only'
def test_missing_identity_denied(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p=plan(c,a,case(c,a))
  with pytest.raises(PermissionError): c.build415.create_multi_agent_session(plan_id=p['plan_id'])
def test_wave_binding_fail_closed(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p1=plan(c,a,case(c,a)); p2=plan(c,a,case(c,a)); w=c.build414.create_research_wave_run(plan_id=p1['plan_id'],identity=a)
  with pytest.raises(PermissionError): c.build415.create_multi_agent_session(plan_id=p2['plan_id'],wave_run_id=w['run_id'],identity=a)
def test_five_specialists_and_human_review_synthesis(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p=plan(c,a,case(c,a)); s=c.build415.create_multi_agent_session(plan_id=p['plan_id'],identity=a); r=c.build415.run_multi_agent_round(session_id=s['session_id'],identity=a); assert {x['agent_id'] for x in r['contributions']}=={'lead','source','temporal','relationship','challenge'}; q=r['synthesis']['payload']; assert q['state']=='human_review_required' and not q['network_execution'] and not q['automatic_go'] and not q['truth_determined']
def test_plan_tamper_blocks_round(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p=plan(c,a,case(c,a)); s=c.build415.create_multi_agent_session(plan_id=p['plan_id'],identity=a); c.db.execute("UPDATE investigation_plan_413 SET plan_hash='tampered' WHERE plan_id=?",(p['plan_id'],))
  with pytest.raises(PermissionError): c.build415.run_multi_agent_round(session_id=s['session_id'],identity=a)
def test_integrity_detects_tamper(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p=plan(c,a,case(c,a)); s=c.build415.create_multi_agent_session(plan_id=p['plan_id'],identity=a); assert c.multi_agent_investigation_415.verify_integrity()['valid']; c.db.execute("UPDATE multi_agent_session_415 SET state='active' WHERE session_id=?",(s['session_id'],)); assert not c.multi_agent_investigation_415.verify_integrity()['valid']
def test_no_forbidden_authority(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.multi_agent_investigation_415.status(); assert not any(s[k] for k in ('direct_network_authority','automatic_go_issuance','automatic_evidence_promotion','autonomous_scope_expansion','truth_determined'))
def test_app_and_launcher(tmp_path):
 app=__import__('eagleeye.interfaces.web.app415',fromlist=['create_workspace_app415']).create_workspace_app415(base_dir=tmp_path)
 try:
  h=TestClient(app).get('/health').json(); assert h['build']=='415.0' and h['multi_agent_gate_pass']; assert '/api/build415/multi-agent/sessions' in {r.path for r in app.routes}
 finally: app.state.context.close()
 assert 'app415 import create_workspace_app415' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
