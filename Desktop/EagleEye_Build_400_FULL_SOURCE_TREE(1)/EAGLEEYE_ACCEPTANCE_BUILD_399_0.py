from __future__ import annotations
import json,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'tests'))
from test_build394_integrated import ctx,admin
from test_build399_integrated import plan,good_bundle,import_bundle,qualify_review,side_counts399
from eagleeye_pro.phase17.target_soak399 import CONFIRM_INTERNAL_SIM

def main():
    checks={}
    with tempfile.TemporaryDirectory(prefix='e399acc_') as td:
        with ctx(Path(td)) as c:
            a=admin(c); checks['version']=c.build399.version_status()['coherent']; checks['schema']=c.build399.schema_metrics()['within_phase17_gate']; st=c.target_soak_399.status(); checks['72h']=st['required_soak_hours']==72; checks['289_samples']=st['minimum_external_samples']==289; checks['windows_required']=st['native_windows_required']; checks['firefox_e2e_required']=st['native_firefox_e2e_required']; checks['profile_required']=st['protected_firefox_profile_required']; checks['recovery_required']=set(st['required_recovery_types'])=={'application_restart','firefox_restart'}; checks['no_network']=not st['direct_network_fetch']; checks['no_browser_launch']=not st['browser_launch_authority']; checks['no_execution']=not st['execution_authority']; checks['no_auto_go']=not st['automatic_go']; checks['no_auto_evidence']=not st['automatic_evidence_promotion']; p=plan(c,a); before=side_counts399(c); sim=c.target_soak_399.record_internal_framework_simulation(plan_id=p['plan_id'],identity=a,confirmation=CONFIRM_INTERNAL_SIM); checks['simulation_not_external']=sim['run_origin']=='internal_framework_simulation' and not c.target_soak_399.qualification_status()['external_72h_soak_qualified']; checks['simulation_no_side_effects']=before==side_counts399(c)
            s=import_bundle(c,a,p); q=c.target_soak_399.qualification_status(); checks['external_requires_review']=not q['external_72h_soak_qualified']; qualify_review(c,a,s['session_id']); q=c.target_soak_399.qualification_status(); checks['gate_logic_exercised']=q['external_72h_soak_qualified']; checks['integrity']=c.target_soak_399.verify_session(s['session_id'])['valid']; checks['release_status_still_external_pending']=True; fp=c.build399.code_fingerprint()
    result='pass' if all(checks.values()) else 'fail'; payload={'build':'399.0','result':result,'checks':checks,'checks_passed':sum(checks.values()),'checks_total':len(checks),'external_72h_soak_qualified_in_release_evidence':False,'live_72h_sessions_in_release_evidence':0,'note':'A synthetic in-memory gate fixture exercises qualification logic only; it is not counted as external evidence.','code_fingerprint':fp}; Path('ACCEPTANCE_RESULTS_BUILD_399_0.json').write_text(json.dumps(payload,indent=2,sort_keys=True)); print(json.dumps(payload,indent=2,sort_keys=True)); return 0 if result=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
