from __future__ import annotations
import pytest
from test_build394_integrated import ctx, admin
from eagleeye_pro.phase17.model_holdout398 import (
    CONFIRM_FREEZE_SUITE, CONFIRM_EXTERNAL_RUN, CONFIRM_HUMAN_REVIEW,
    CONFIRM_FREEZE_BASELINE,
)


def make_suite(c,a):
    s=c.model_holdout_398.create_reference_suite()
    return c.model_holdout_398.freeze_suite(suite_id=s['suite_id'],identity=a,confirmation=CONFIRM_FREEZE_SUITE)


def test_version_schema_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build398.version_status()=={'runtime_build':'398.0','schema_version':'398.0','package_version':'398.0.0','coherent':True}
        sm=c.build398.schema_metrics(); assert sm['within_phase17_gate'] and sm['build398_tables_present'] and sm['integrity_check']=='ok'
        st=c.model_holdout_398.status(); assert st['bundled_fixture_cases']==60 and st['human_review_required_for_qualification'] and not st['execution_authority']


def test_reference_suite_has_60_distinct_cases(tmp_path):
    with ctx(tmp_path) as c:
        s=c.model_holdout_398.create_reference_suite(); assert s['case_count']==60 and s['status']=='draft'
        rows=c.db.all('SELECT case_id,domain FROM holdout_case_398 WHERE suite_id=?',(s['suite_id'],)); assert len(rows)==60 and len({r['case_id'] for r in rows})==60
        assert len({r['domain'] for r in rows})>=10


def test_freeze_requires_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); s=c.model_holdout_398.create_reference_suite()
        with pytest.raises(PermissionError): c.model_holdout_398.freeze_suite(suite_id=s['suite_id'],identity=a,confirmation='YES')
        f=c.model_holdout_398.freeze_suite(suite_id=s['suite_id'],identity=a,confirmation=CONFIRM_FREEZE_SUITE); assert f['status']=='frozen' and f['frozen_by']


def test_deterministic_reference_all_cases_and_baseline(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); s=make_suite(c,a)
        cases=c.db.all('SELECT case_id FROM holdout_case_398 WHERE suite_id=? ORDER BY case_id',(s['suite_id'],))
        runs=[c.model_holdout_398.record_deterministic_reference(suite_id=s['suite_id'],case_id=r['case_id']) for r in cases]
        assert len(runs)==60 and all(float(r['structural_score'])==1.0 for r in runs)
        b=c.model_holdout_398.freeze_internal_baseline(suite_id=s['suite_id'],identity=a,confirmation=CONFIRM_FREEZE_BASELINE)
        assert b['run_count']==60 and all(v==1.0 for v in b['metrics'].values())
        q=c.model_holdout_398.qualification_status(); assert q['internal_baseline_frozen'] and q['real_model_runs']==0 and not q['external_holdout_qualified']


def test_external_run_requires_receipt_and_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); s=make_suite(c,a); case=c.model_holdout_398._case(s['suite_id'],'H398-001'); out=c.model_holdout_398.deterministic_reference_output(case)
        with pytest.raises(PermissionError): c.model_holdout_398.record_external_model_run(suite_id=s['suite_id'],case_id='H398-001',adapter_id='adapter',model_id='model',output=out,execution_receipt='external-receipt',identity=a,confirmation='YES')
        with pytest.raises(ValueError): c.model_holdout_398.record_external_model_run(suite_id=s['suite_id'],case_id='H398-001',adapter_id='adapter',model_id='model',output=out,execution_receipt='',identity=a,confirmation=CONFIRM_EXTERNAL_RUN)
        r=c.model_holdout_398.record_external_model_run(suite_id=s['suite_id'],case_id='H398-001',adapter_id='test-import',model_id='fixture-model',output=out,execution_receipt='test-only-external-receipt',identity=a,confirmation=CONFIRM_EXTERNAL_RUN)
        assert r['run_origin']=='external_model' and r['receipt_hash']


def test_human_review_must_be_blinded_and_scored(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); s=make_suite(c,a); run=c.model_holdout_398.record_deterministic_reference(suite_id=s['suite_id'],case_id='H398-001')
        scores={k:5 for k in ('evidence_grounding','counterevidence_handling','uncertainty_handling','actionability','governance')}
        with pytest.raises(ValueError): c.model_holdout_398.submit_human_review(run_id=run['run_id'],identity=a,blind_review=False,scores=scores,harmful_overreach=False,notes='test',confirmation=CONFIRM_HUMAN_REVIEW)
        with pytest.raises(PermissionError): c.model_holdout_398.submit_human_review(run_id=run['run_id'],identity=a,blind_review=True,scores=scores,harmful_overreach=False,notes='test',confirmation='YES')
        rv=c.model_holdout_398.submit_human_review(run_id=run['run_id'],identity=a,blind_review=True,scores=scores,harmful_overreach=False,notes='blinded structural review',confirmation=CONFIRM_HUMAN_REVIEW)
        assert rv['blind_review']==1 and rv['reviewer_id']


def test_deterministic_reviews_cannot_satisfy_external_gate(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); s=make_suite(c,a); scores={k:5 for k in ('evidence_grounding','counterevidence_handling','uncertainty_handling','actionability','governance')}
        for cid in ('H398-001','H398-002'):
            r=c.model_holdout_398.record_deterministic_reference(suite_id=s['suite_id'],case_id=cid)
            c.model_holdout_398.submit_human_review(run_id=r['run_id'],identity=a,blind_review=True,scores=scores,harmful_overreach=False,notes='reference review only',confirmation=CONFIRM_HUMAN_REVIEW)
        q=c.model_holdout_398.qualification_status(); assert q['human_reviewed_cases']==2 and q['human_reviewed_external_cases']==0 and not q['external_holdout_qualified']


def test_external_gate_requires_each_case_and_two_reviewers(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); s=make_suite(c,a); reviewer2={**c.team_identity_359.create_user(identity=a,username='reviewer398b',display_name='Independent Reviewer 398',global_role='system_administrator',password='Quartz-Independent-Reviewer-398-X9!'), 'session_id':'r398b'}; scores={k:5 for k in ('evidence_grounding','counterevidence_handling','uncertainty_handling','actionability','governance')}
        cases=[r['case_id'] for r in c.db.all('SELECT case_id FROM holdout_case_398 WHERE suite_id=? ORDER BY case_id',(s['suite_id'],))]
        for i,cid in enumerate(cases):
            case=c.model_holdout_398._case(s['suite_id'],cid); out=c.model_holdout_398.deterministic_reference_output(case)
            r=c.model_holdout_398.record_external_model_run(suite_id=s['suite_id'],case_id=cid,adapter_id='gate-test-import',model_id='gate-test-model',output=out,execution_receipt=f'test-receipt-{cid}',identity=a,confirmation=CONFIRM_EXTERNAL_RUN)
            who=a if i else reviewer2
            c.model_holdout_398.submit_human_review(run_id=r['run_id'],identity=who,blind_review=True,scores=scores,harmful_overreach=False,notes='test of qualification gate only; not a real model qualification',confirmation=CONFIRM_HUMAN_REVIEW)
        q=c.model_holdout_398.qualification_status(); assert q['real_model_cases']==60 and q['human_reviewed_external_cases']==60 and q['distinct_external_run_reviewers']==2 and q['external_holdout_qualified']


def test_scoring_penalizes_bad_citations_and_truth_probability(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); s=make_suite(c,a); case=c.model_holdout_398._case(s['suite_id'],'H398-001')
        bad={'citations':['UNKNOWN'],'support_groups':99,'contradiction_groups':99,'stop_decision':'wrong','truth_probability':0.9,'execution_authority':True}
        r=c.model_holdout_398.record_external_model_run(suite_id=s['suite_id'],case_id='H398-001',adapter_id='score-test',model_id='bad-fixture',output=bad,execution_receipt='test-only',identity=a,confirmation=CONFIRM_EXTERNAL_RUN)
        assert r['citation_precision']==0.0 and r['governance_compliance']==0.0 and r['structural_score']<0.2


def test_integrity_detects_tamper(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); s=make_suite(c,a); c.model_holdout_398.record_deterministic_reference(suite_id=s['suite_id'],case_id='H398-001')
        assert c.model_holdout_398.verify_integrity(s['suite_id'])['valid']
        c.db.execute("UPDATE holdout_case_398 SET title='tampered' WHERE suite_id=? AND case_id='H398-001'",(s['suite_id'],))
        assert not c.model_holdout_398.verify_integrity(s['suite_id'])['valid']


def test_phase_status_truthful_external_pending(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build398.phase17_status(); assert s['build']=='398.0' and s['phase17_builds_completed']==18 and s['model_holdout_framework']
        assert s['real_model_runs']==0 and s['human_reviewed_cases']==0 and not s['real_model_human_holdout_qualified'] and not s['production_release_ready']
