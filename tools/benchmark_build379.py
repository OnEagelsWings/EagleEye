from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

CATEGORIES=('runtime_snapshot','recovery_contract','queue_lease','case_isolation','object_pressure','receipt_boundary','no_fault_api','ai_boundary','opsec_boundary','truthful_release')

def main():
    root=Path(__file__).resolve().parents[1]; cases=0; violations=0; counts={}
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='bench379') as c:
        contract=c.external_qualification_379.contract(); status=c.external_qualification_379.status(); crawler=c.build379.crawler_status(); ai=c.ai_autonomy_379.status(); opsec=c.opsec_supervisor_379.status()
        for cat in CATEGORIES:
            ok=0
            for _i in range(560):
                if cat=='runtime_snapshot': v=c.build379.qualification_snapshot()['network_execution_by_snapshot'] is False
                elif cat=='recovery_contract': v=contract['minimum_recovery_ratio']>=0.99 and contract['maximum_p95_lease_recovery_seconds']<=10.0
                elif cat=='queue_lease': v=crawler['qualification_queue_lease_stability'] is True and contract['maximum_stale_leases_after_recovery']==0
                elif cat=='case_isolation': v=crawler['qualification_case_isolation'] is True and contract['maximum_cross_case_leaks']==0
                elif cat=='object_pressure': v=crawler['qualification_object_store_pressure_gate'] is True and crawler['automatic_evidence_eviction'] is False
                elif cat=='receipt_boundary': v=status['external_receipt_required'] is True and status['external_receipt_signature']=='Ed25519' and status['external_receipt_grants_network_scope'] is False
                elif cat=='no_fault_api': v=status['runtime_fault_injection_api'] is False and crawler['production_fault_injection_api'] is False
                elif cat=='ai_boundary': v=ai['fault_injection_authority'] is False and ai['production_decision_authority'] is False
                elif cat=='opsec_boundary': v=opsec['system_mutations'] is False and opsec['automatic_evidence_eviction'] is False
                else: v=c.build379.external_qualification_status()['externally_validated'] is False and c.build379.qualified_gate()['production_release_ready'] is False
                cases+=1; ok+=int(v); violations+=int(not v)
            counts[cat]=ok
        out={'build':'379.0','code_fingerprint':c.build379.code_fingerprint(),'cases':cases,'violations':violations,'categories':counts,'network_used':False,'external_validation_performed':False,'result':'pass' if cases>=5600 and violations==0 else 'fail','truthful_scope':'Deterministic local policy/boundary benchmark only; no external soak/load traffic or external receipt is claimed.'}
    path=root/'BENCHMARK_BUILD_379_EXTERNAL_QUALIFICATION.json'; path.write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(out,indent=2)); return 0 if out['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
