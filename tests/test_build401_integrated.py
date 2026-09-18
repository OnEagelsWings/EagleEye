from __future__ import annotations
import pytest
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.final_acceptance400 import CONFIRM_RUN, CONFIRM_REVIEW
from eagleeye_pro.phase17.model_holdout398 import CONFIRM_FREEZE_SUITE, CONFIRM_EXTERNAL_RUN, CONFIRM_HUMAN_REVIEW

PW='Build401-Secure-Vector-X1!'
def ctx(tmp_path): return AppContext(base_dir=tmp_path, actor='test401')
def admin(c):
    a=c.team_identity_359.create_initial_admin(username='admin401',display_name='Phase18 Lead',password=PW)
    return {**a,'session_id':'test401'}

def test_version_and_gate(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build401.version_status()=={'runtime_build':'401.0','schema_version':'401.0','package_version':'401.0.0','coherent':True}
        g=c.build401.security_gate(); assert g['security_gate_pass'] and g['fail_closed'] and g['read_only'] and not g['production_release_ready']

def test_missing_soak_session_is_structured(tmp_path):
    with ctx(tmp_path) as c:
        assert c.target_soak_399.verify_session('does-not-exist')=={'valid':False,'violations':['missing_session']}

def test_needs_remediation_cannot_open_phase18(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); run=c.build400.run_phase17_acceptance(identity=a,confirmation=CONFIRM_RUN)
        c.build400.review_phase17_acceptance(run_id=run['run_id'],identity=a,disposition='needs_remediation',rationale='negative-path regression',confirmation=CONFIRM_REVIEW)
        st=c.build400.phase17_status(); assert not st['phase18_entry_ready'] and not st['production_release_ready']

def test_global_read_only_cannot_mutate_final_acceptance(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c)
        ro=c.team_identity_359.create_user(username='readonly401',display_name='Read Only',password='Quartz-Vector-91!Safe',global_role='read_only',identity=a)
        identity={**ro,'session_id':'ro401'}
        with pytest.raises(PermissionError): c.build400.run_phase17_acceptance(identity=identity,confirmation=CONFIRM_RUN)

def _prepare_holdout(c,a):
    s=c.model_holdout_398.create_reference_suite(); c.model_holdout_398.freeze_suite(suite_id=s['suite_id'],identity=a,confirmation=CONFIRM_FREEZE_SUITE)
    return s

def test_governance_violation_is_hard_holdout_veto(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); s=_prepare_holdout(c,a); scores={k:5 for k in ('evidence_grounding','counterevidence_handling','uncertainty_handling','actionability','governance')}
        for i,row in enumerate(c.db.all('SELECT case_id FROM holdout_case_398 WHERE suite_id=? ORDER BY case_id',(s['suite_id'],))):
            cid=row['case_id']; case=c.model_holdout_398._case(s['suite_id'],cid); out=c.model_holdout_398.deterministic_reference_output(case); out['execution_authority']=True
            r=c.model_holdout_398.record_external_model_run(suite_id=s['suite_id'],case_id=cid,adapter_id='401-test',model_id='unsafe-authority',output=out,execution_receipt=f'r-{cid}',identity=a,confirmation=CONFIRM_EXTERNAL_RUN)
            assert r['structural_score']>=0.8 and r['governance_compliance']==0
            who=a if i else {**c.team_identity_359.create_user(identity=a,username='reviewer401b',display_name='Independent Reviewer 401',global_role='system_administrator',password='Quartz-Independent-Reviewer-401-X9!'), 'session_id':'r401b'}
            c.model_holdout_398.submit_human_review(run_id=r['run_id'],identity=who,blind_review=True,scores=scores,harmful_overreach=False,notes='high-score but unsafe authority',confirmation=CONFIRM_HUMAN_REVIEW)
        q=c.model_holdout_398.qualification_status(); assert q['quality_external_model_cases']==0 and not q['external_holdout_qualified']

def test_two_reviewers_must_both_have_qualifying_reviews(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); s=_prepare_holdout(c,a); good={k:5 for k in ('evidence_grounding','counterevidence_handling','uncertainty_handling','actionability','governance')}; bad={k:1 for k in good}
        runs=[]
        for row in c.db.all('SELECT case_id FROM holdout_case_398 WHERE suite_id=? ORDER BY case_id',(s['suite_id'],)):
            cid=row['case_id']; case=c.model_holdout_398._case(s['suite_id'],cid); out=c.model_holdout_398.deterministic_reference_output(case)
            r=c.model_holdout_398.record_external_model_run(suite_id=s['suite_id'],case_id=cid,adapter_id='401-test',model_id='safe',output=out,execution_receipt=f'r-{cid}',identity=a,confirmation=CONFIRM_EXTERNAL_RUN);runs.append(r)
            c.model_holdout_398.submit_human_review(run_id=r['run_id'],identity=a,blind_review=True,scores=good,harmful_overreach=False,notes='qualifying',confirmation=CONFIRM_HUMAN_REVIEW)
        reviewer2={**c.team_identity_359.create_user(identity=a,username='reviewer401c',display_name='Independent Reviewer 401 C',global_role='system_administrator',password='Quartz-Independent-Reviewer-401-C9!'), 'session_id':'r401c'}
        c.model_holdout_398.submit_human_review(run_id=runs[0]['run_id'],identity=reviewer2,blind_review=True,scores=bad,harmful_overreach=False,notes='non-qualifying reviewer',confirmation=CONFIRM_HUMAN_REVIEW)
        q=c.model_holdout_398.qualification_status(); assert q['distinct_external_run_reviewers']==2 and q['distinct_qualifying_external_reviewers']==1 and not q['external_holdout_qualified']

def test_feedback_cycle_is_five_builds(tmp_path):
    with ctx(tmp_path) as c:
        g=c.build401.security_gate(); assert g['feedback_cycle']=={'builds':[401,402,403,404,405],'publish_after_build':405}
