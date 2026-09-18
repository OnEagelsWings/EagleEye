from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from test_build394_integrated import admin
from test_build416_integrated import session
ROOT=Path(__file__).resolve().parents[1]
def test_version_and_gate(tmp_path):
 with AppContext(base_dir=tmp_path) as c: assert c.build417.version_status()['coherent']; assert c.build417.hypothesis_status()['hypothesis_gate_pass']
def test_hypothesis_counterevidence_and_alternative(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p,s=session(c,a); h=c.build417.create_hypothesis(session_id=s['session_id'],statement='Entity A controlled event B',identity=a)
  c.build417.add_hypothesis_item(hypothesis_id=h['hypothesis_id'],item_type='support',reference='claim:1',identity=a)
  c.build417.add_hypothesis_item(hypothesis_id=h['hypothesis_id'],item_type='counterevidence',reference='claim:2',identity=a)
  alt=c.build417.create_hypothesis(session_id=s['session_id'],statement='Event B occurred independently',alternative_to=h['hypothesis_id'],identity=a)
  r=c.build417.review_hypothesis(hypothesis_id=h['hypothesis_id'],identity=a); assert r['counts']['counterevidence']==1 and r['alternatives'][0]['hypothesis_id']==alt['hypothesis_id'] and not r['truth_determined']
def test_continuity_hold_blocks_hypothesis_work(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p,s=session(c,a); c.db.execute("UPDATE investigation_plan_413 SET plan_hash='tampered' WHERE plan_id=?",(p['plan_id'],))
  with pytest.raises(PermissionError): c.build417.create_hypothesis(session_id=s['session_id'],statement='blocked',identity=a)
def test_cross_session_alternative_denied(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p,s=session(c,a); h=c.build417.create_hypothesis(session_id=s['session_id'],statement='first',identity=a); p2,s2=session(c,a)
  with pytest.raises(PermissionError): c.build417.create_hypothesis(session_id=s2['session_id'],statement='second',alternative_to=h['hypothesis_id'],identity=a)
def test_integrity_detects_tamper(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p,s=session(c,a); h=c.build417.create_hypothesis(session_id=s['session_id'],statement='test hypothesis',identity=a); assert c.hypothesis_coordination_417.verify_integrity()['valid']; c.db.execute("UPDATE hypothesis_417 SET statement='tampered' WHERE hypothesis_id=?",(h['hypothesis_id'],)); assert not c.hypothesis_coordination_417.verify_integrity()['valid']
def test_human_state_and_no_forbidden_authority(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=admin(c); p,s=session(c,a); h=c.build417.create_hypothesis(session_id=s['session_id'],statement='review me',identity=a); x=c.build417.set_hypothesis_state(hypothesis_id=h['hypothesis_id'],state='accepted_by_human',identity=a); assert x['state']=='accepted_by_human'; st=c.hypothesis_coordination_417.status(); assert not any(st[k] for k in ('direct_network_authority','automatic_go_issuance','automatic_evidence_promotion','autonomous_scope_expansion','truth_determined'))
def test_app_and_launcher(tmp_path):
 app=__import__('eagleeye.interfaces.web.app417',fromlist=['create_workspace_app417']).create_workspace_app417(base_dir=tmp_path)
 try:
  h=TestClient(app).get('/health').json(); assert h['build']=='417.0' and h['hypothesis_gate_pass']; assert '/api/build417/hypotheses/status' in {r.path for r in app.routes}
 finally: app.state.context.close()
 assert 'app417 import create_workspace_app417' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
