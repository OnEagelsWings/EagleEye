from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.model_holdout398 import CONFIRM_FREEZE_SUITE, CONFIRM_EXTERNAL_RUN, CONFIRM_HUMAN_REVIEW
from eagleeye_pro.phase17.target_soak399 import CONFIRM_FREEZE_PLAN, CONFIRM_IMPORT_EXTERNAL, CONFIRM_REVIEW
from eagleeye.interfaces.web.app406 import create_workspace_app406

PW='Quartz-Build406-Admin-X91!Safe'
def ctx(tmp_path): return AppContext(base_dir=tmp_path,actor='test406')
def admin(c,username='admin406'):
    a=c.team_identity_359.create_initial_admin(username=username,display_name='Build 406 Lead',password=PW)
    return {**a,'session_id':'s-'+username}
def readonly(c,a):
    u=c.team_identity_359.create_user(identity=a,username='ro406',display_name='Read Only 406',global_role='read_only',password='Quartz-Readonly-406-X91!Safe')
    return {**u,'session_id':'ro406'}

def test_build406_version_and_remediation_gate(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build406.version_status()=={'runtime_build':'406.0','schema_version':'406.0','package_version':'406.0.0','coherent':True}
        r=c.build406.remediation_status(); assert r['p1_remediation_gate_pass'] and r['catalogued_mutation_surfaces']>=36 and not r['production_release_ready']

def test_qualification_mutations_are_catalogued_and_governed(tmp_path):
    with ctx(tmp_path) as c:
        keys={x['key'] for x in c.build402.authorization_matrix()['rows']}
        assert {'holdout.external_run.record','holdout.human_review.submit','soak.external_bundle.import','soak.external_session.review'} <= keys
        assert c.build402.authorization_audit()['authorization_audit_pass']

def test_read_only_cannot_record_external_holdout_or_review(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ro=readonly(c,a); s=c.model_holdout_398.create_reference_suite(); c.model_holdout_398.freeze_suite(suite_id=s['suite_id'],identity=a,confirmation=CONFIRM_FREEZE_SUITE)
        case=c.model_holdout_398._case(s['suite_id'],'H398-001'); out=c.model_holdout_398.deterministic_reference_output(case)
        with pytest.raises(PermissionError): c.model_holdout_398.record_external_model_run(suite_id=s['suite_id'],case_id='H398-001',adapter_id='x',model_id='x',output=out,execution_receipt='r',identity=ro,confirmation=CONFIRM_EXTERNAL_RUN)
        run=c.model_holdout_398.record_external_model_run(suite_id=s['suite_id'],case_id='H398-001',adapter_id='x',model_id='x',output=out,execution_receipt='r',identity=a,confirmation=CONFIRM_EXTERNAL_RUN)
        scores={k:5 for k in ('evidence_grounding','counterevidence_handling','uncertainty_handling','actionability','governance')}
        with pytest.raises(PermissionError): c.model_holdout_398.submit_human_review(run_id=run['run_id'],identity=ro,blind_review=True,scores=scores,harmful_overreach=False,notes='x',confirmation=CONFIRM_HUMAN_REVIEW)

def test_read_only_cannot_import_or_review_soak(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ro=readonly(c,a); p=c.target_soak_399.create_reference_plan(); c.target_soak_399.freeze_plan(plan_id=p['plan_id'],identity=a,confirmation=CONFIRM_FREEZE_PLAN)
        bundle={'environment':{'native_windows':True,'native_firefox':True,'native_firefox_e2e':True,'protected_firefox_profile':True},'samples':[],'recoveries':[],'started_at':'2026-01-01T00:00:00+00:00','ended_at':'2026-01-01T00:01:00+00:00','execution_receipt':'r','collector_id':'c'}
        with pytest.raises(PermissionError): c.target_soak_399.import_external_bundle(plan_id=p['plan_id'],bundle=bundle,identity=ro,confirmation=CONFIRM_IMPORT_EXTERNAL)
        sess=c.target_soak_399.import_external_bundle(plan_id=p['plan_id'],bundle=bundle,identity=a,confirmation=CONFIRM_IMPORT_EXTERNAL)
        with pytest.raises(PermissionError): c.target_soak_399.review_external_session(session_id=sess['session_id'],identity=ro,disposition='not_qualified',native_windows_verified=False,native_firefox_e2e_verified=False,recovery_verified=False,notes='x',confirmation=CONFIRM_REVIEW)

def test_blocking_review_cannot_close_with_fabricated_strings(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); f=c.ai_review_gate_404.record_finding(source='codex',external_ref='PR5',title='fabricated closure',severity='P1',description='synthetic',component='review')
        with pytest.raises(ValueError): c.ai_review_gate_404.transition(finding_id=f['finding_id'],status='verified_closed',regression_test='made_up',fix_evidence='x',verification_evidence='y',verifier_identity=a)

def test_review_ledger_tamper_blocks_build405_and_406(tmp_path):
    with ctx(tmp_path) as c:
        f=c.ai_review_gate_404.record_finding(source='codex',external_ref='PR5',title='tamper',severity='P1',description='synthetic',component='review')
        c.db.execute("UPDATE ai_review_finding_404 SET status='verified_closed',fix_evidence='x',verification_evidence='y',regression_test='z' WHERE finding_id=?",(f['finding_id'],))
        assert not c.build404.review_integrity()['valid']
        assert not c.build405.qualified_gate()['build_acceptance_ready']
        assert not c.build406.remediation_status()['p1_remediation_gate_pass']

def test_app406_startup_and_health(tmp_path):
    app=create_workspace_app406(base_dir=tmp_path); client=TestClient(app)
    h=client.get('/health'); assert h.status_code==200 and h.json()['build']=='406.0' and h.json()['feedback_remediation_406'] is True
    paths={getattr(r,'path','') for r in app.router.routes}; assert '/api/build405/source-registry/status' in paths and '/api/build406/remediation-status' in paths

def test_server_entrypoint_points_to_app406():
    from pathlib import Path
    text=Path('src/eagleeye/interfaces/web/server.py').read_text()
    assert 'app406' in text and 'create_workspace_app406 as create_workspace_app' in text
