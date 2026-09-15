from __future__ import annotations
import json
from pathlib import Path
import pytest
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.final_acceptance400 import CONFIRM_RUN,CONFIRM_REVIEW

PW='Build400-Secure-Vector-Z9!'
def ctx(tmp_path):return AppContext(base_dir=tmp_path,actor='test400')
def admin(c):
    a=c.team_identity_359.create_initial_admin(username='admin400',display_name='Phase17 Lead',password=PW)
    return {**a,'session_id':'test400'}
def counts(c):
    names=['phase15_jobs','execution_grant_386','evidence_candidate_promotion_389','hypotheses_112','investigation_claim_391','investigation_hypothesis_391','reasoning_plan_392']
    present={r['name'] for r in c.db.all("SELECT name FROM sqlite_master WHERE type='table'")}
    return {n:(int((c.db.one(f'SELECT COUNT(*) n FROM {n}') or {})['n']) if n in present else 0) for n in names}

def test_version_schema_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build400.version_status()=={'runtime_build':'400.0','schema_version':'400.0','package_version':'400.0.0','coherent':True}
        s=c.build400.schema_metrics();assert s['within_phase17_gate'] and s['build400_tables_present'] and s['integrity_check']=='ok'
        st=c.phase17_final_acceptance_400.status();assert st['phase17_builds_completed']==20 and not st['production_release_ready'] and not st['execution_authority']

def test_exact_run_confirmation_required(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c)
        with pytest.raises(PermissionError):c.build400.run_phase17_acceptance(identity=a,confirmation='YES')

def test_internal_acceptance_covers_all_19_predecessor_stages(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);r=c.build400.run_phase17_acceptance(identity=a,confirmation=CONFIRM_RUN)
        assert r['internal_acceptance'] and r['passed_steps']==19 and r['total_steps']==19
        assert [x['ordinal'] for x in r['steps']]==list(range(1,20))
        assert all(x['status']=='pass' for x in r['steps'])

def test_external_gaps_remain_visible_and_production_false(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);r=c.build400.run_phase17_acceptance(identity=a,confirmation=CONFIRM_RUN)
        assert not r['external_holdout_qualified'] and not r['external_soak_qualified'] and not r['production_release_ready']
        assert 'build398_real_model_human_holdout_pending' in r['blockers'] and 'build399_real_72h_windows_firefox_soak_pending' in r['blockers']

def test_internal_acceptance_is_phase18_entry_ready_not_production_release(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);r=c.build400.run_phase17_acceptance(identity=a,confirmation=CONFIRM_RUN)
        assert r['phase18_entry_ready'] and r['professional_pilot_ready'] and not r['production_release_ready']

def test_review_requires_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);r=c.build400.run_phase17_acceptance(identity=a,confirmation=CONFIRM_RUN)
        with pytest.raises(PermissionError):c.build400.review_phase17_acceptance(run_id=r['run_id'],identity=a,disposition='accept_internal_phase17',rationale='test',confirmation='YES')
        rr=c.build400.review_phase17_acceptance(run_id=r['run_id'],identity=a,disposition='accept_internal_phase17',rationale='Internal Phase 17 accepted; external production qualification remains pending.',confirmation=CONFIRM_REVIEW)
        assert rr['review']['disposition']=='accept_internal_phase17'

def test_export_requires_review_and_writes_json_markdown_docx(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);r=c.build400.run_phase17_acceptance(identity=a,confirmation=CONFIRM_RUN)
        with pytest.raises(PermissionError):c.build400.export_phase17_acceptance(run_id=r['run_id'],outdir=tmp_path/'reports')
        c.build400.review_phase17_acceptance(run_id=r['run_id'],identity=a,disposition='accept_internal_phase17',rationale='Accepted for Phase 18 entry only.',confirmation=CONFIRM_REVIEW)
        out=c.build400.export_phase17_acceptance(run_id=r['run_id'],outdir=tmp_path/'reports')
        assert Path(out['json']).is_file() and Path(out['markdown']).is_file() and Path(out['docx']).is_file()
        data=json.loads(Path(out['json']).read_text());assert data['truthful_scope']['production_release_ready'] is False

def test_hash_verification_and_tamper_detection(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);r=c.build400.run_phase17_acceptance(identity=a,confirmation=CONFIRM_RUN);assert c.build400.verify_phase17_acceptance(r['run_id'])['valid']
        c.db.execute("UPDATE phase17_acceptance_step_400 SET status='fail' WHERE run_id=? AND ordinal=1",(r['run_id'],))
        assert not c.build400.verify_phase17_acceptance(r['run_id'])['valid']

def test_acceptance_has_no_execution_side_effects(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);before=counts(c);r=c.build400.run_phase17_acceptance(identity=a,confirmation=CONFIRM_RUN);c.build400.review_phase17_acceptance(run_id=r['run_id'],identity=a,disposition='accept_internal_phase17',rationale='No execution authority.',confirmation=CONFIRM_REVIEW);after=counts(c);assert before==after

def test_status_after_review_marks_internal_phase17_only(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c);r=c.build400.run_phase17_acceptance(identity=a,confirmation=CONFIRM_RUN);c.build400.review_phase17_acceptance(run_id=r['run_id'],identity=a,disposition='accept_internal_phase17',rationale='Phase 18 entry approved.',confirmation=CONFIRM_REVIEW);st=c.build400.phase17_status();assert st['phase17_internal_acceptance'] and st['phase18_entry_ready'] and not st['production_release_ready']

def test_server_and_launchers_point_to_400():
    root=Path(__file__).resolve().parents[1]
    assert 'app400' in (root/'src/eagleeye/interfaces/web/server.py').read_text()
    assert 'EAGLEEYE_PRO_400_0.py' in (root/'START_EAGLEEYE_PRO.sh').read_text()
    assert 'EAGLEEYE_PRO_400_0.py' in (root/'START_EAGLEEYE_PRO.bat').read_text()
