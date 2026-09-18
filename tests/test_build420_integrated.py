from pathlib import Path
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from test_build394_integrated import admin
ROOT=Path(__file__).resolve().parents[1]
def test_version_and_phase18_gate(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  assert c.build420.version_status()['coherent']; s=c.build420.qualification_status(); assert not s['phase18_gate_pass']; assert not s['checks']['passing_qualification_run']; assert not s['production_release_ready']
def test_qualification_runs_fail_closed_and_persists(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); q=c.build420.qualify_phase18(identity=a); assert q['report']['qualification_result'] in {'pass','hold'}; assert q['report']['production_release_ready'] is False; assert c.phase18_qualification_420.verify_integrity()['valid']; assert c.build420.qualification_status()['phase18_gate_pass']==(q['report']['qualification_result']=='pass')
def test_qualification_integrity_tamper(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); q=c.build420.qualify_phase18(identity=a); c.db.execute("UPDATE phase18_qualification_run_420 SET result='tampered' WHERE qualification_id=?",(q['qualification_id'],)); assert not c.phase18_qualification_420.verify_integrity()['valid']
def test_no_forbidden_authority(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.phase18_qualification_420.status(); assert not any(s[k] for k in ('direct_network_authority','automatic_go_issuance','automatic_evidence_promotion','autonomous_scope_expansion','truth_determined'))
def test_app_launcher(tmp_path):
 from eagleeye.interfaces.web.app420 import create_workspace_app420
 app=create_workspace_app420(base_dir=tmp_path)
 try:
  h=TestClient(app).get('/health').json(); assert h['build']=='420.0' and h['phase18_complete']; assert not h['phase18_gate_pass']; assert not h['production_release_ready']; assert '/api/build420/qualification/run' in {r.path for r in app.routes}
 finally: app.state.context.close()
 assert 'app420 import create_workspace_app420' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()

def test_non_admin_cannot_run_global_qualification(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  import pytest
  with pytest.raises(PermissionError): c.build420.qualify_phase18(identity={'user_id':'reader','roles':['viewer']})
