from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from test_build394_integrated import admin
from test_build416_integrated import session
ROOT=Path(__file__).resolve().parents[1]
def setup_h(c,a):
 p,s=session(c,a); h=c.build417.create_hypothesis(session_id=s['session_id'],statement='Primary working hypothesis',identity=a); return s,h
def test_version_gate(tmp_path):
 with AppContext(base_dir=tmp_path) as c: assert c.build418.version_status()['coherent']; assert c.build418.matrix_status()['matrix_gate_pass']
def test_matrix_support_counterevidence_and_gap(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); s,h=setup_h(c,a); c.build418.link_evidence(hypothesis_id=h['hypothesis_id'],evidence_ref='ev:1',relation='supports',identity=a); m=c.build418.reasoning_matrix(session_id=s['session_id'],identity=a); assert m['hypotheses'][0]['coverage']['supports']==1; assert m['gaps'][0]['reason']=='no_counterevidence_link'
  c.build418.link_evidence(hypothesis_id=h['hypothesis_id'],evidence_ref='ev:2',relation='contradicts',identity=a); assert c.build418.reasoning_matrix(session_id=s['session_id'],identity=a)['gaps']==[]
def test_cross_hypothesis_conflict(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); s,h=setup_h(c,a); alt=c.build417.create_hypothesis(session_id=s['session_id'],statement='Alternative working hypothesis',alternative_to=h['hypothesis_id'],identity=a); c.build418.link_evidence(hypothesis_id=h['hypothesis_id'],evidence_ref='ev:x',relation='supports',identity=a); c.build418.link_evidence(hypothesis_id=alt['hypothesis_id'],evidence_ref='ev:x',relation='contradicts',identity=a); assert c.build418.reasoning_matrix(session_id=s['session_id'],identity=a)['conflicts']
def test_bad_payloads_and_no_truth(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); s,h=setup_h(c,a)
  with pytest.raises(ValueError): c.build418.link_evidence(hypothesis_id=h['hypothesis_id'],evidence_ref=None,relation='supports',identity=a)
  with pytest.raises(ValueError): c.build418.link_evidence(hypothesis_id=h['hypothesis_id'],evidence_ref='ev',relation='supports',confidence=2,identity=a)
  m=c.build418.reasoning_matrix(session_id=s['session_id'],identity=a); assert not m['truth_determined'] and not m['automatic_evidence_promotion']
def test_integrity_tamper(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); s,h=setup_h(c,a); x=c.build418.link_evidence(hypothesis_id=h['hypothesis_id'],evidence_ref='ev',relation='supports',identity=a); assert c.evidence_hypothesis_matrix_418.verify_integrity()['valid']; c.db.execute("UPDATE evidence_hypothesis_link_418 SET relation='contradicts' WHERE link_id=?",(x['link_id'],)); assert not c.evidence_hypothesis_matrix_418.verify_integrity()['valid']
def test_app_launcher(tmp_path):
 from eagleeye.interfaces.web.app418 import create_workspace_app418
 app=create_workspace_app418(base_dir=tmp_path)
 try:
  h=TestClient(app).get('/health').json(); assert h['build']=='418.0' and h['matrix_gate_pass']; assert '/api/build418/multi-agent/sessions/{session_id}/matrix' in {r.path for r in app.routes}
 finally: app.state.context.close()
 assert 'app418 import create_workspace_app418' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
