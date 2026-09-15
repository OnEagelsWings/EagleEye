from __future__ import annotations
from datetime import datetime,timezone,timedelta
import pytest
from test_build394_integrated import ctx,admin
from eagleeye_pro.phase17.target_soak399 import CONFIRM_FREEZE_PLAN,CONFIRM_IMPORT_EXTERNAL,CONFIRM_REVIEW,CONFIRM_INTERNAL_SIM,MIN_EXTERNAL_SAMPLES


def side_counts399(c):
    names=['phase15_jobs','execution_grant_386','evidence_candidate_promotion_389','hypotheses_112','investigation_claim_391','investigation_hypothesis_391','reasoning_plan_392']
    present={r['name'] for r in c.db.all("SELECT name FROM sqlite_master WHERE type='table'")}
    return {n:(int((c.db.one(f'SELECT COUNT(*) n FROM {n}') or {})['n']) if n in present else 0) for n in names}

def plan(c,a):
    p=c.target_soak_399.create_reference_plan(); return c.target_soak_399.freeze_plan(plan_id=p['plan_id'],identity=a,confirmation=CONFIRM_FREEZE_PLAN)

def good_bundle(*,hours=72,firefox=True,recoveries=True,compressed=False):
    start=datetime(2026,9,1,0,0,tzinfo=timezone.utc); end=start+timedelta(hours=hours)
    if compressed:
        sample_end=start+timedelta(hours=1)
        step=(sample_end-start)/(MIN_EXTERNAL_SAMPLES-1)
    else:
        step=timedelta(seconds=900)
    samples=[]
    for i in range(MIN_EXTERNAL_SAMPLES):
        t=start+step*i
        samples.append({'observed_at':t.isoformat(),'app_health':'healthy','db_integrity':'ok','firefox_probe':'pass' if firefox else 'fail','firefox_profile_ok':firefox,'crawler_health':'idle','worker_health':'idle','recovery_state':'none','critical_error':False,'details':{},'evidence_ref':f'sample-{i:03d}'})
    rec=[]
    if recoveries:
        for kind,hr in [('application_restart',24),('firefox_restart',48)]:
            a=start+timedelta(hours=hr); b=a+timedelta(seconds=45)
            rec.append({'recovery_type':kind,'started_at':a.isoformat(),'recovered_at':b.isoformat(),'before_state':'controlled_stop','after_state':'healthy','successful':True,'evidence_ref':f'{kind}-receipt','details':{}})
    return {'environment':{'native_windows':True,'native_firefox':True,'native_firefox_e2e':firefox,'protected_firefox_profile':firefox,'windows_version':'test-fixture','firefox_version':'test-fixture','target_host_pseudonym':'fixture-only'},'collector_id':'build399-test-fixture','started_at':start.isoformat(),'ended_at':end.isoformat(),'execution_receipt':'TEST FIXTURE ONLY - not external qualification evidence','samples':samples,'recoveries':rec}

def import_bundle(c,a,p,b=None):
    return c.target_soak_399.import_external_bundle(plan_id=p['plan_id'],bundle=b or good_bundle(),identity=a,confirmation=CONFIRM_IMPORT_EXTERNAL)

def qualify_review(c,a,sid):
    return c.target_soak_399.review_external_session(session_id=sid,identity=a,disposition='qualified',native_windows_verified=True,native_firefox_e2e_verified=True,recovery_verified=True,notes='Gate test fixture only; no real live qualification is claimed.',confirmation=CONFIRM_REVIEW)

def test_version_schema_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build399.version_status()=={'runtime_build':'399.0','schema_version':'399.0','package_version':'399.0.0','coherent':True}
        s=c.build399.schema_metrics(); assert s['within_phase17_gate'] and s['build399_tables_present'] and s['integrity_check']=='ok'
        st=c.target_soak_399.status(); assert st['required_soak_hours']==72 and st['minimum_external_samples']==289 and not st['simulation_can_qualify_external']

def test_plan_requires_exact_freeze(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); p=c.target_soak_399.create_reference_plan()
        with pytest.raises(PermissionError): c.target_soak_399.freeze_plan(plan_id=p['plan_id'],identity=a,confirmation='YES')
        f=c.target_soak_399.freeze_plan(plan_id=p['plan_id'],identity=a,confirmation=CONFIRM_FREEZE_PLAN); assert f['status']=='frozen' and f['required_duration_seconds']==259200

def test_internal_framework_simulation_never_qualifies(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); p=plan(c,a); s=c.target_soak_399.record_internal_framework_simulation(plan_id=p['plan_id'],identity=a,confirmation=CONFIRM_INTERNAL_SIM); q=c.target_soak_399.qualification_status(); assert s['run_origin']=='internal_framework_simulation' and q['external_sessions']==0 and not q['external_72h_soak_qualified']

def test_external_import_requires_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); p=plan(c,a)
        with pytest.raises(PermissionError): c.target_soak_399.import_external_bundle(plan_id=p['plan_id'],bundle=good_bundle(),identity=a,confirmation='YES')

def test_72h_bundle_requires_human_review(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); p=plan(c,a); s=import_bundle(c,a,p); q=c.target_soak_399.qualification_status(); assert q['external_sessions']==1 and not q['external_72h_soak_qualified'] and not q['details'][0]['checks']['human_review']

def test_perfect_test_fixture_can_exercise_gate_after_review(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); p=plan(c,a); s=import_bundle(c,a,p); qualify_review(c,a,s['session_id']); q=c.target_soak_399.qualification_status(); assert q['external_72h_soak_qualified'] and q['qualified_external_sessions']==[s['session_id']]

def test_short_duration_fails(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); p=plan(c,a); s=import_bundle(c,a,p,good_bundle(hours=71)); qualify_review(c,a,s['session_id']); q=c.target_soak_399.qualification_status(); d=q['details'][0]; assert not d['checks']['duration_72h'] and not q['external_72h_soak_qualified']

def test_missing_recovery_fails(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); p=plan(c,a); s=import_bundle(c,a,p,good_bundle(recoveries=False)); qualify_review(c,a,s['session_id']); q=c.target_soak_399.qualification_status(); assert not q['details'][0]['checks']['recovery_types'] and not q['external_72h_soak_qualified']

def test_firefox_failure_fails(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); p=plan(c,a); s=import_bundle(c,a,p,good_bundle(firefox=False)); qualify_review(c,a,s['session_id']); q=c.target_soak_399.qualification_status(); assert not q['details'][0]['checks']['native_firefox_e2e'] and not q['details'][0]['checks']['firefox_probe'] and not q['external_72h_soak_qualified']

def test_compressed_samples_fail_end_coverage(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); p=plan(c,a); s=import_bundle(c,a,p,good_bundle(compressed=True)); qualify_review(c,a,s['session_id']); q=c.target_soak_399.qualification_status(); assert not q['details'][0]['checks']['sample_end_coverage'] and not q['external_72h_soak_qualified']

def test_review_rejects_internal_simulation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); p=plan(c,a); s=c.target_soak_399.record_internal_framework_simulation(plan_id=p['plan_id'],identity=a,confirmation=CONFIRM_INTERNAL_SIM)
        with pytest.raises(ValueError): qualify_review(c,a,s['session_id'])

def test_session_integrity_detects_tamper(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); p=plan(c,a); s=import_bundle(c,a,p); assert c.target_soak_399.verify_session(s['session_id'])['valid']; c.db.execute("UPDATE soak_sample_399 SET app_health='tampered' WHERE session_id=? AND ordinal=1",(s['session_id'],)); assert not c.target_soak_399.verify_session(s['session_id'])['valid']

def test_no_execution_side_effects(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); p=plan(c,a); before=side_counts399(c); c.target_soak_399.record_internal_framework_simulation(plan_id=p['plan_id'],identity=a,confirmation=CONFIRM_INTERNAL_SIM); assert before==side_counts399(c)

def test_phase_status_live_pending(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build399.phase17_status(); assert s['build']=='399.0' and s['phase17_builds_completed']==19 and s['required_soak_hours']==72 and not s['external_72h_soak_qualified'] and not s['production_release_ready']
