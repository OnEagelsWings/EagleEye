from __future__ import annotations
import pytest
from eagleeye_pro.core.app_context import AppContext

PW='Build402-Secure-Vector-X1!'

def ctx(tmp_path): return AppContext(base_dir=tmp_path, actor='test402')
def admin(c):
    a=c.team_identity_359.create_initial_admin(username='admin402',display_name='Phase18 Lead',password=PW)
    return {**a,'session_id':'admin402'}

def test_version_and_authorization_gate(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build402.version_status()=={'runtime_build':'402.0','schema_version':'402.0','package_version':'402.0.0','coherent':True}
        g=c.build402.qualified_gate(); assert g['build_acceptance_ready'] and not g['production_release_ready']

def test_matrix_covers_high_risk_mutations(tmp_path):
    with ctx(tmp_path) as c:
        m=c.build402.authorization_matrix()
        assert m['default_deny'] and m['mutation_surfaces'] >= 30
        keys={r['key'] for r in m['rows']}
        assert {'execution.execute','evidence.promote','discussion.revision.apply','acceptance.run.global','acceptance.review.global'} <= keys
        assert all(r['capability']!='case.read' for r in m['rows'])

def test_static_governance_audit_passes(tmp_path):
    with ctx(tmp_path) as c:
        a=c.build402.authorization_audit()
        assert a['authorization_audit_pass'] and a['fail_closed'] and a['read_only_audit']
        assert all(x['pass'] for x in a['source_checks'])

def test_read_only_has_no_mutation_capability(tmp_path):
    with ctx(tmp_path) as c:
        r=c.build402.role_matrix()
        assert r['read_only_has_mutation_capability'] is False
        assert all(v is False for v in r['roles']['read_only'].values())

def test_case_role_runtime_matrix_denies_read_only_and_allows_expected_roles(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c)
        case=c.team_governance_359.create_case(identity=a,title='Auth Matrix',client='Test',purpose='Build 402',legal_basis='Synthetic validation')
        users={}
        specs=[('inv402','Investigator 402','investigator','investigator'),('analyst402','Analyst 402','reviewer','analyst'),('review402','Reviewer 402','reviewer','reviewer'),('ro402','Read Only 402','read_only','read_only')]
        for username,display,global_role,case_role in specs:
            u=c.team_identity_359.create_user(identity=a,username=username,display_name=display,password=f'Quartz-RoleMatrix-{len(users)+11}-91!SafeX',global_role=global_role)
            c.team_identity_359.assign_case(identity=a,case_id=case['case_id'],username=username,case_role=case_role,notes='402 matrix')
            users[case_role]={**u,'session_id':f's-{username}'}
        for capability in c.build402.role_matrix()['capabilities']:
            with pytest.raises(PermissionError): c.team_governance_359.authorize(users['read_only'],case_id=case['case_id'],capability=capability)
        assert c.team_governance_359.authorize(users['investigator'],case_id=case['case_id'],capability='crawler.run')['allowed']
        assert c.team_governance_359.authorize(users['analyst'],case_id=case['case_id'],capability='dossier.write')['allowed']
        assert c.team_governance_359.authorize(users['reviewer'],case_id=case['case_id'],capability='source.review')['allowed']
        assert c.team_governance_359.authorize(users['reviewer'],case_id=case['case_id'],capability='dossier.review')['allowed']

def test_global_scope_acceptance_denies_read_only(tmp_path):
    from eagleeye_pro.phase17.final_acceptance400 import CONFIRM_RUN
    with ctx(tmp_path) as c:
        a=admin(c)
        ro=c.team_identity_359.create_user(identity=a,username='readonly402',display_name='Read Only Global',password='Quartz-Global-Readonly-91!SafeX',global_role='read_only')
        with pytest.raises(PermissionError): c.build400.run_phase17_acceptance(identity={**ro,'session_id':'ro402'},confirmation=CONFIRM_RUN)

def test_access_decisions_are_hash_chained(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c)
        case=c.team_governance_359.create_case(identity=a,title='Audit Chain',client='Test',purpose='Build 402',legal_basis='Synthetic validation')
        c.team_governance_359.authorize(a,case_id=case['case_id'],capability='dossier.review')
        chain=c.team_identity_359.verify_access_chain(); assert chain['ok'] and chain['events'] >= 1

def test_feedback_cycle_still_targets_405(tmp_path):
    with ctx(tmp_path) as c:
        st=c.build402.phase18_status(); assert st['phase18_builds_completed']==2 and st['next_public_feedback_build']=='405.0' and not st['production_release_ready']
