from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

CATEGORIES=('phase_completion','pilot_telemetry','pilot_slo','production_slo_boundary','decision_taxonomy','external_matrix','restricted_scope','ai_boundary','opsec_boundary','truthful_current_state')

def main():
    root=Path(__file__).resolve().parents[1]; cases=0; violations=0; counts={}
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='bench380') as c:
        for cat in CATEGORIES:
            ok=0
            for _i in range(600):
                if cat=='phase_completion': v=c.professional_pilot_380.status()['phase16_builds_completed']==20
                elif cat=='pilot_telemetry': v=c.build380.pilot_telemetry()['network_execution_by_telemetry'] is False
                elif cat=='pilot_slo': v=c.build380.final_crawler_slo_gate()['pilot_slo_gate_pass'] is True
                elif cat=='production_slo_boundary': v=c.build380.final_crawler_slo_gate()['production_slo_gate_pass'] is False
                elif cat=='decision_taxonomy': v=c.professional_pilot_380.classify(local_ready=True,external_qualified=False)=='professional_pilot_only'
                elif cat=='external_matrix': v=c.build380.external_validation_matrix()['build379_independent_operational_qualification']=='not_run'
                elif cat=='restricted_scope': v='automatic_identity_merge' in c.professional_pilot_380.restricted_scope()['kept_disabled_or_separately_gated']
                elif cat=='ai_boundary': v=c.ai_autonomy_380.status()['production_decision_authority'] is False
                elif cat=='opsec_boundary': v=c.opsec_supervisor_380.status()['system_mutations'] is False and c.opsec_supervisor_380.status()['production_override_authority'] is False
                else: v=c.professional_pilot_380.current_decision(local_ready=True)['decision']=='professional_pilot_only'
                cases+=1; ok+=int(v); violations+=int(not v)
            counts[cat]=ok
        out={'build':'380.0','code_fingerprint':c.build380.code_fingerprint(),'cases':cases,'violations':violations,'categories':counts,'network_used':False,'external_validation_performed':False,'result':'pass' if cases>=6000 and violations==0 else 'fail','truthful_scope':'Deterministic local final-decision/boundary benchmark only. Independent production qualification is not claimed.'}
    (root/'BENCHMARK_BUILD_380_FINAL_DECISION.json').write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(out,indent=2)); return 0 if out['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
