from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='accept379') as c:
        gate=c.build379.qualified_gate(); schema=c.build379.schema_metrics(); qual=c.external_qualification_379.status(); crawler=c.build379.crawler_status(); ai=c.ai_autonomy_379.status(); opsec=c.opsec_supervisor_379.status(); ext=c.build379.external_qualification_status()
        checks={
            'build_acceptance_ready':gate['build_acceptance_ready'],
            'version_coherent':c.build379.version_status()['coherent'],
            'schema_within_gate':schema['within_gate'],
            'no_new_tables':schema['external_qualification_new_tables']==0,
            'local_prequalification_pass':gate['local_prequalification']=='pass',
            'external_validation_not_run':gate['external_qualification']=='not_run' and ext['externally_validated'] is False,
            'signed_receipt_required':qual['external_receipt_required'] and qual['external_receipt_signature']=='Ed25519',
            'fingerprint_binding':qual['external_receipt_fingerprint_bound'],
            'receipt_no_network_scope':qual['external_receipt_grants_network_scope'] is False,
            'no_runtime_fault_api':qual['runtime_fault_injection_api'] is False and crawler['production_fault_injection_api'] is False,
            'recovery_slo':crawler['qualification_recovery_slo_measurement'],
            'queue_lease_stability':crawler['qualification_queue_lease_stability'],
            'case_isolation':crawler['qualification_case_isolation'],
            'object_store_pressure':crawler['qualification_object_store_pressure_gate'],
            'no_auto_eviction':crawler['automatic_evidence_eviction'] is False,
            'ai_boundary':ai['fault_injection_authority'] is False and ai['production_decision_authority'] is False,
            'opsec_boundary':opsec['system_mutations'] is False and opsec['production_fault_injection_authority'] is False,
            'production_false_build380_required':gate['production_release_ready'] is False and gate['build380_final_decision_required'] is True,
        }
        out={'build':'379.0','code_fingerprint':c.build379.code_fingerprint(),'checks':checks,'passed':sum(bool(x) for x in checks.values()),'total':len(checks),'result':'pass' if all(checks.values()) else 'fail','build_acceptance_ready':all(checks.values()),'production_release_ready':False,'external_qualification_validated':False}
    (root/'ACCEPTANCE_RESULTS_BUILD_379_0.json').write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(out,indent=2)); return 0 if out['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
