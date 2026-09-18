from __future__ import annotations
import pytest
from eagleeye_pro.core.app_context import AppContext


def ctx(tmp_path): return AppContext(base_dir=tmp_path, actor='test404')

def test_version_and_gate_empty_ledger_passes(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build404.version_status()=={'runtime_build':'404.0','schema_version':'404.0','package_version':'404.0.0','coherent':True}
        g=c.build404.qualified_gate(); assert g['build_acceptance_ready'] and not g['production_release_ready']

def test_rules_encode_feedback_requirements(tmp_path):
    with ctx(tmp_path) as c:
        r=c.build404.review_rules(); keys={x['key'] for x in r['rules']}
        assert {'blocking_severity','verified_closure','regression_required','human_governed','source_traceability','feedback_cycle'} <= keys
        assert r['blocking_severities']==['P0','P1'] and not r['production_release_ready']

def test_p1_open_finding_blocks_gate(tmp_path):
    with ctx(tmp_path) as c:
        f=c.ai_review_gate_404.record_finding(source='github-codex',external_ref='PR#99:C1',title='Authorization bypass',severity='P1',description='synthetic regression finding',component='authorization')
        g=c.build404.review_gate_status(); assert g['open_blocking_count']==1 and not g['ai_review_gate_pass']
        assert g['open_blocking'][0]['finding_id']==f['finding_id']

def test_p2_open_finding_does_not_block_security_gate(tmp_path):
    with ctx(tmp_path) as c:
        c.ai_review_gate_404.record_finding(source='external-tester',external_ref='ISSUE#77',title='Minor UX confusion',severity='P2',description='synthetic feedback',component='ui')
        g=c.build404.review_gate_status(); assert g['open_blocking_count']==0 and g['ai_review_gate_pass']

def test_p1_secure_closure_requires_independent_verified_evidence(tmp_path):
    with ctx(tmp_path) as c:
        admin=c.team_identity_359.create_initial_admin(username='verify404',display_name='Verifier 404',password='Quartz-Verify-404-X91!Safe')
        verifier={**admin,'session_id':'verify404'}
        f=c.ai_review_gate_404.record_finding(source='github-codex',external_ref='PR#99:C2',title='Gate bypass',severity='P1',description='synthetic',component='holdout')
        with pytest.raises(ValueError): c.ai_review_gate_404.transition(finding_id=f['finding_id'],status='verified_closed',regression_test='made_up',fix_evidence='x',verification_evidence='y')
        c.ai_review_gate_404.transition(finding_id=f['finding_id'],status='fix_in_progress',actor='developer404')
        c.ai_review_gate_404.transition(finding_id=f['finding_id'],status='fixed_pending_verification',fix_evidence={'type':'fix','ref':'commit-abc'},actor='developer404')
        reg='tests/test_build404_integrated.py::test_p1_secure_closure_requires_independent_verified_evidence'
        x=c.ai_review_gate_404.transition(finding_id=f['finding_id'],status='verified_closed',regression_test=reg,verification_evidence={'type':'verification','ref':'ci-404-1','result':'passed','test':reg},verifier_identity=verifier)
        assert x['status']=='verified_closed' and x['verified_by']==verifier['user_id'] and x['verification_receipt']
        assert c.build404.review_gate_status()['ai_review_gate_pass']

def test_fixed_pending_verification_still_blocks(tmp_path):
    with ctx(tmp_path) as c:
        f=c.ai_review_gate_404.record_finding(source='copilot',external_ref='PR#99:C3',title='Missing state bug',severity='P1',description='synthetic',component='soak')
        c.ai_review_gate_404.transition(finding_id=f['finding_id'],status='fix_in_progress',actor='developer404')
        c.ai_review_gate_404.transition(finding_id=f['finding_id'],status='fixed_pending_verification',fix_evidence={'type':'fix','ref':'commit-def'},actor='developer404')
        assert not c.build404.review_gate_status()['ai_review_gate_pass']

def test_review_ledger_integrity_detects_tamper(tmp_path):
    with ctx(tmp_path) as c:
        f=c.ai_review_gate_404.record_finding(source='codex',external_ref='x',title='Tamper test',severity='P3',description='synthetic',component='docs')
        assert c.build404.review_integrity()['valid']
        c.db.execute("UPDATE ai_review_finding_404 SET title='tampered' WHERE finding_id=?",(f['finding_id'],))
        assert not c.build404.review_integrity()['valid']

def test_phase_status_targets_build405_feedback(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build404.phase18_status(); assert s['phase18_builds_completed']==4 and s['ai_review_gate'] and s['next_public_feedback_build']=='405.0' and not s['production_release_ready']
