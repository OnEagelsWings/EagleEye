from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from test_build394_integrated import admin
ROOT=Path(__file__).resolve().parents[1]
def ctx(p): return AppContext(base_dir=p)
def case(c,a): return c.build380.team_create_case(identity=a,title='414',client='internal',purpose='bounded autonomous research',legal_basis='public_data')['case_id']
def plan(c,a,cid): return c.build413.create_investigation_plan(case_id=cid,objective='Resolve documented chronology',subquestions=['Find dated records','Identify gaps'],identity=a)
def test_version_gate(tmp_path):
 with ctx(tmp_path) as c: assert c.build414.version_status()['coherent']; assert c.build414.wave_status()['autonomous_research_wave_gate_pass']
def test_run_waits_for_explicit_authorization(tmp_path):
 with ctx(tmp_path) as c:
  a=admin(c); cid=case(c,a); p=plan(c,a,cid); r=c.build414.create_research_wave_run(plan_id=p['plan_id'],identity=a); assert r['state']=='awaiting_human_authorization'
  with pytest.raises(PermissionError): c.build414.advance_research_wave_run(run_id=r['run_id'],identity=a)
  with pytest.raises(PermissionError): c.build414.authorize_research_wave_run(run_id=r['run_id'],identity=a,confirmation='GO')
def test_bounded_autonomy_after_human_authorization(tmp_path):
 with ctx(tmp_path) as c:
  a=admin(c); cid=case(c,a); p=plan(c,a,cid); r=c.build414.create_research_wave_run(plan_id=p['plan_id'],identity=a,max_waves=2); r=c.build414.authorize_research_wave_run(run_id=r['run_id'],identity=a,confirmation='AUTHORIZE RESEARCH WAVES'); assert r['state']=='active'; s=c.build414.advance_research_wave_run(run_id=r['run_id'],identity=a); assert s['work']['network_execution'] is False and s['work']['remote_execution_requires_separate_go'] is True
def test_budget_stops_run(tmp_path):
 with ctx(tmp_path) as c:
  a=admin(c); cid=case(c,a); p=plan(c,a,cid); r=c.build414.create_research_wave_run(plan_id=p['plan_id'],identity=a,max_waves=1); c.build414.authorize_research_wave_run(run_id=r['run_id'],identity=a,confirmation='AUTHORIZE RESEARCH WAVES'); c.build414.advance_research_wave_run(run_id=r['run_id'],identity=a); assert c.build414.research_wave_run(r['run_id'])['state']=='completed'
def test_missing_identity_and_budget_fail_closed(tmp_path):
 with ctx(tmp_path) as c:
  a=admin(c); cid=case(c,a); p=plan(c,a,cid)
  with pytest.raises(PermissionError): c.build414.create_research_wave_run(plan_id=p['plan_id'])
  with pytest.raises(ValueError): c.build414.create_research_wave_run(plan_id=p['plan_id'],identity=a,max_waves=21)
def test_plan_tamper_forces_hold(tmp_path):
 with ctx(tmp_path) as c:
  a=admin(c); cid=case(c,a); p=plan(c,a,cid); r=c.build414.create_research_wave_run(plan_id=p['plan_id'],identity=a); c.build414.authorize_research_wave_run(run_id=r['run_id'],identity=a,confirmation='AUTHORIZE RESEARCH WAVES'); c.db.execute("UPDATE investigation_plan_413 SET plan_hash='tampered' WHERE plan_id=?",(p['plan_id'],))
  with pytest.raises(PermissionError): c.build414.advance_research_wave_run(run_id=r['run_id'],identity=a)
  assert c.build414.research_wave_run(r['run_id'])['state']=='hold'
def test_integrity_detects_run_tamper(tmp_path):
 with ctx(tmp_path) as c:
  a=admin(c); cid=case(c,a); p=plan(c,a,cid); r=c.build414.create_research_wave_run(plan_id=p['plan_id'],identity=a); assert c.autonomous_research_waves_414.verify_integrity()['valid']; c.db.execute("UPDATE autonomous_wave_run_414 SET max_waves=19 WHERE run_id=?",(r['run_id'],)); assert not c.autonomous_research_waves_414.verify_integrity()['valid']
def test_no_forbidden_authorities(tmp_path):
 with ctx(tmp_path) as c:
  s=c.autonomous_research_waves_414.status(); assert not s['direct_network_authority'] and not s['automatic_go_issuance'] and not s['automatic_evidence_promotion'] and not s['autonomous_scope_expansion'] and not s['truth_determined']
def test_app414_and_launcher(tmp_path):
 app=__import__('eagleeye.interfaces.web.app414',fromlist=['create_workspace_app414']).create_workspace_app414(base_dir=tmp_path)
 try:
  h=TestClient(app).get('/health').json(); assert h['build']=='414.0' and h['autonomous_research_wave_gate_pass']; assert '/api/build414/waves' in {r.path for r in app.routes}
 finally: app.state.context.close()
 assert 'app414 import create_workspace_app414' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
