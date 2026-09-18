from pathlib import Path
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from test_build394_integrated import admin
from test_build416_integrated import session
ROOT=Path(__file__).resolve().parents[1]
def seed(c,a):
 p,s=session(c,a); h=c.build417.create_hypothesis(session_id=s['session_id'],statement='Primary hypothesis',identity=a); alt=c.build417.create_hypothesis(session_id=s['session_id'],statement='Alternative hypothesis',alternative_to=h['hypothesis_id'],identity=a); c.build418.link_evidence(hypothesis_id=h['hypothesis_id'],evidence_ref='ev:1',relation='supports',identity=a); c.build418.link_evidence(hypothesis_id=alt['hypothesis_id'],evidence_ref='ev:1',relation='contradicts',identity=a); return s,h,alt
def test_version_gate(tmp_path):
 with AppContext(base_dir=tmp_path) as c: assert c.build419.version_status()['coherent']; assert c.build419.synthesis_status()['synthesis_gate_pass']
def test_synthesis_preserves_competing_hypotheses(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); s,h,alt=seed(c,a); x=c.build419.synthesize(session_id=s['session_id'],identity=a); assert len(x['summary']['competing_hypotheses'])==2; assert x['summary']['matrix_conflicts']==1; assert not x['summary']['truth_determined']
def test_synthesis_exposes_unresolved(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p,s=session(c,a); c.build417.create_hypothesis(session_id=s['session_id'],statement='Unresolved hypothesis',identity=a); x=c.build419.synthesize(session_id=s['session_id'],identity=a); assert x['summary']['unresolved']
def test_integrity(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); s,h,alt=seed(c,a); x=c.build419.synthesize(session_id=s['session_id'],identity=a); assert c.investigation_synthesis_419.verify_integrity()['valid']; c.db.execute("UPDATE investigation_synthesis_419 SET title='tampered' WHERE synthesis_id=?",(x['synthesis_id'],)); assert not c.investigation_synthesis_419.verify_integrity()['valid']
def test_app_launcher(tmp_path):
 from eagleeye.interfaces.web.app419 import create_workspace_app419
 app=create_workspace_app419(base_dir=tmp_path)
 try:
  h=TestClient(app).get('/health').json(); assert h['build']=='419.0' and h['synthesis_gate_pass']; assert '/api/build419/multi-agent/sessions/{session_id}/syntheses' in {r.path for r in app.routes}
 finally: app.state.context.close()
 assert 'app419 import create_workspace_app419' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
