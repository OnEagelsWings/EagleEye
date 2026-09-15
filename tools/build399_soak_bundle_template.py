from __future__ import annotations
import argparse,json
from pathlib import Path
from eagleeye_pro.phase17.target_soak399 import REQUIRED_DURATION_SECONDS,DEFAULT_SAMPLE_INTERVAL_SECONDS,MIN_EXTERNAL_SAMPLES,REQUIRED_RECOVERY_TYPES

def template():
    return {
      'schema':'phase17.target-soak-evidence-bundle.v399',
      'instructions':{
        'required_duration_seconds':REQUIRED_DURATION_SECONDS,
        'sample_interval_seconds':DEFAULT_SAMPLE_INTERVAL_SECONDS,
        'minimum_samples':MIN_EXTERNAL_SAMPLES,
        'required_recovery_types':list(REQUIRED_RECOVERY_TYPES),
        'note':'Populate this bundle from the real target environment. Do not mark native_firefox_e2e true without actual native Firefox end-to-end evidence.'
      },
      'environment':{
        'native_windows':False,'native_firefox':False,'native_firefox_e2e':False,'protected_firefox_profile':False,
        'windows_version':'','firefox_version':'','firefox_profile_id':'','target_host_pseudonym':'','eagleeye_build':'399.0'
      },
      'collector_id':'','started_at':'','ended_at':'','execution_receipt':'','samples':[],
      'recoveries':[
        {'recovery_type':'application_restart','started_at':'','recovered_at':'','before_state':'','after_state':'','successful':False,'evidence_ref':'','details':{}},
        {'recovery_type':'firefox_restart','started_at':'','recovered_at':'','before_state':'','after_state':'','successful':False,'evidence_ref':'','details':{}}
      ]
    }
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('-o','--output',default='BUILD_399_TARGET_SOAK_BUNDLE_TEMPLATE.json'); a=ap.parse_args(); p=Path(a.output); p.write_text(json.dumps(template(),indent=2,sort_keys=True)); print(p)
if __name__=='__main__': main()
