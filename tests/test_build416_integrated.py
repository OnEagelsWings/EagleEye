from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from test_build394_integrated import admin
ROOT=Path(__file__).resolve().parents[1]
def case(c,a): return c.build380.team_create_case(identity=a,title='416',client='internal',purpose='continuity',legal_basis='public_data')['case_id']
def plan(c,a,cid): return c.build413.create_investigation_plan(case_id=cid,objective='Review continuity',subquestions=['Check sources','Challenge assumptions'],identity=a)
def session(c,a,wave=False):
 cid=case(c,a); p=plan(c,a,cid); wid=''
 if wave: wid=c.build414.create_research_wave_run(plan_id=p['plan_id'],identity=a)['run_id']
 return p,c.build415.create_multi_agent_session(plan_id=p['plan_id'],wave_run_id=wid,identity=a)
def test_version_and_gate(tmp_path):
 with AppContext(base_dir=tmp_path) as c: assert c.build416.version_status()['coherent']; assert c.build416.continuity_status()['continuity_gate_pass']
def test_revalidates_each_round(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p,s=session(c,a); r=c.build416.run_multi_agent_round(session_id=s['session_id'],identity=a); assert r['continuity416']['valid'] and r['synthesis']['payload']['state']=='human_review_required'
def test_missing_identity_denied(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p,s=session(c,a)
  with pytest.raises(PermissionError): c.build416.validate_multi_agent_session(session_id=s['session_id'])
def test_plan_tamper_holds_session(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p,s=session(c,a); c.db.execute("UPDATE investigation_plan_413 SET plan_hash='tampered' WHERE plan_id=?",(p['plan_id'],))
  with pytest.raises(PermissionError): c.build416.run_multi_agent_round(session_id=s['session_id'],identity=a)
  assert c.db.one('SELECT reason FROM multi_agent_hold_416 WHERE session_id=?',(s['session_id'],))['reason']=='continuity_validation_failed'
def test_wave_tamper_holds_session(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p,s=session(c,a,True); c.db.execute("UPDATE autonomous_wave_run_414 SET record_hash='tampered' WHERE run_id=?",(s['wave_run_id'],))
  with pytest.raises(PermissionError): c.build416.run_multi_agent_round(session_id=s['session_id'],identity=a)
  assert c.db.one('SELECT 1 FROM multi_agent_hold_416 WHERE session_id=?',(s['session_id'],))
def test_orphaned_wave_holds_session(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p,s=session(c,a,True); c.db.execute('DELETE FROM autonomous_wave_run_414 WHERE run_id=?',(s['wave_run_id'],))
  with pytest.raises(PermissionError): c.build416.validate_multi_agent_session(session_id=s['session_id'],identity=a)
def test_hold_is_sticky_fail_closed(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p,s=session(c,a); c.db.execute("UPDATE investigation_plan_413 SET plan_hash='x' WHERE plan_id=?",(p['plan_id'],))
  with pytest.raises(PermissionError): c.build416.validate_multi_agent_session(session_id=s['session_id'],identity=a)
  c.db.execute('UPDATE investigation_plan_413 SET plan_hash=? WHERE plan_id=?',(p['plan_hash'],p['plan_id']))
  with pytest.raises(PermissionError,match='integrity hold'): c.build416.validate_multi_agent_session(session_id=s['session_id'],identity=a)
def test_continuity_integrity_detects_tamper(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p,s=session(c,a); c.build416.validate_multi_agent_session(session_id=s['session_id'],identity=a); assert c.multi_agent_continuity_416.verify_integrity()['valid']; c.db.execute("UPDATE multi_agent_continuity_check_416 SET result='fake'"); assert not c.multi_agent_continuity_416.verify_integrity()['valid']
def test_no_forbidden_authority(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.multi_agent_continuity_416.status(); assert not any(s[k] for k in ('direct_network_authority','automatic_go_issuance','automatic_evidence_promotion','autonomous_scope_expansion','truth_determined'))
def test_app_and_launcher(tmp_path):
 app=__import__('eagleeye.interfaces.web.app416',fromlist=['create_workspace_app416']).create_workspace_app416(base_dir=tmp_path)
 try:
  h=TestClient(app).get('/health').json(); assert h['build']=='416.0' and h['continuity_gate_pass']; assert '/api/build416/continuity/status' in {r.path for r in app.routes}
 finally: app.state.context.close()
 assert 'app416 import create_workspace_app416' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
