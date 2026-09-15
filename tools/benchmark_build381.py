#!/usr/bin/env python3
import json, os, sys
ROOT=os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT,'src'))
from eagleeye.phase17.investigation_control381 import InvestigationControlPlane381, default_registry

base={
'evidence': {'state':'ready'}, 'crawler': {'state':'ready'}, 'operations': {'state':'ready'},
'opsec': {'state':'ready'}, 'graph': {'state':'ready'}, 'search': {'state':'degraded'},
'image': {'state':'not_validated'}, 'ai': {'state':'ready'}}
violations=[]
cases=2000
for i in range(cases):
    providers={k:dict(v) for k,v in base.items()}
    should_hold = i % 10 in {0,1,2}
    if i % 10 == 0: providers['opsec']={'state':'hold'}
    if i % 10 == 1: providers['operations']={'state':'ready','circuit_open':True}
    if i % 10 == 2: providers.pop('crawler')
    cp=InvestigationControlPlane381(default_registry(),providers)
    snap=cp.snapshot(f'CASE-{i:05d}')
    if should_hold == snap.research_ready:
        violations.append({'case':i,'reason':'hold_semantics'})
        continue
    if snap.network_requests_created or snap.mutations_performed:
        violations.append({'case':i,'reason':'side_effect'})
        continue
    if snap.research_ready:
        plan=cp.plan_research(case_id=f'CASE-{i:05d}',mission='regulated source planning',jurisdictions=['US'],entity_types=['company'])
        if plan.execution_authority or plan.scope_expansion_authority or plan.network_requests_created:
            violations.append({'case':i,'reason':'authority_boundary'})
result={'build':'381.0','cases':cases,'violations':len(violations),'result':'pass' if not violations else 'fail',
        'network_used':False,'mutations_performed':0,'truthful_scope':'Deterministic network-silent Build-381 control-plane/source-registry benchmark.'}
print(json.dumps(result,indent=2,sort_keys=True))
if violations: sys.exit(1)
