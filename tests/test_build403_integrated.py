from __future__ import annotations
import pytest
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.final_acceptance400 import CONFIRM_RUN

PW='Build403-Secure-Vector-X1!'
def ctx(tmp_path): return AppContext(base_dir=tmp_path, actor='test403')
def admin(c):
    a=c.team_identity_359.create_initial_admin(username='admin403',display_name='Phase18 Lead',password=PW)
    return {**a,'session_id':'admin403'}

def test_version_and_gate(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build403.version_status()=={'runtime_build':'403.0','schema_version':'403.0','package_version':'403.0.0','coherent':True}
        g=c.build403.qualified_gate(); assert g['build_acceptance_ready'] and not g['production_release_ready']

def test_catalog_has_required_negative_categories(tmp_path):
    with ctx(tmp_path) as c:
        x=c.build403.negative_path_catalog(); assert x['scenario_count']>=15 and x['default_fail_closed']
        cats=set(x['categories']); assert {'missing_record','authorization','confirmation','invalid_state','duplicate_mutation','abuse','scope_manipulation','integrity'} <= cats

def test_contract_audit_passes(tmp_path):
    with ctx(tmp_path) as c:
        a=c.build403.negative_path_audit(); assert a['contract_audit_pass'] and a['fail_closed'] and all(a['checks'].values())

def test_missing_records_are_structured(tmp_path):
    with ctx(tmp_path) as c:
        p=c.build403.negative_path_runtime_probes(); assert p['runtime_probe_pass'] and p['mutation_free']
        assert c.target_soak_399.verify_session('no-such-session')=={'valid':False,'violations':['missing_session']}
        assert c.phase17_final_acceptance_400.verify('no-such-run')=={'valid':False,'violations':['missing_run']}

def test_wrong_confirmation_fails_closed_before_mutation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c)
        with pytest.raises(PermissionError): c.phase17_final_acceptance_400.run_acceptance(identity=a,confirmation='YES')
        assert not c.db.one('SELECT 1 FROM phase17_acceptance_run_400 LIMIT 1')

def test_read_only_global_scope_bypass_denied(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ro=c.team_identity_359.create_user(identity=a,username='readonly403',display_name='Read Only 403',password='Quartz-403-Readonly-91!SafeX',global_role='read_only')
        with pytest.raises(PermissionError): c.phase17_final_acceptance_400.run_acceptance(identity={**ro,'session_id':'ro403'},case_id='',confirmation=CONFIRM_RUN)

def test_holdout_contracts_include_codex_bypasses(tmp_path):
    with ctx(tmp_path) as c:
        checks=c.build403.negative_path_audit()['checks']
        assert checks['holdout_governance_hard_veto'] and checks['holdout_quality_reviewer_diversity'] and checks['holdout_harmful_overreach_veto']

def test_phase_status_targets_405_feedback(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build403.phase18_status(); assert s['phase18_builds_completed']==3 and s['negative_path_framework'] and s['next_public_feedback_build']=='405.0' and not s['production_release_ready']
