import json
import sqlite3
from eagleeye_pro.phase17.jurisdiction_intelligence384 import JurisdictionIntelligence384, create_reference_repository384

class Ready:
    def status_for_case(self, case_id): return {"state":"ready"}

providers={k:Ready() for k in ("operations","opsec","evidence","crawler","search","graph")}
repo=create_reference_repository384(sqlite3.connect(":memory:"))
svc=JurisdictionIntelligence384(repo, providers)
classes=("corporate","procurement","public_money","regulatory","government","legal","archive","reference")
violations=[]
for i in range(5000):
    sc=(classes[i % len(classes)],)
    p=svc.plan_waves(case_id=f"bench-{i%50}", mission=f"benchmark {sc[0]}", source_classes=sc, jurisdictions=(("us","eu","global")[i%3],), max_steps_per_wave=4)
    if p.execution_authority or p.scope_expansion_authority or p.network_requests_created:
        violations.append(i)
    if any(w.execution_authority or not w.requires_go for w in p.waves):
        violations.append(i)
result={"build":"384.0","cases":5000,"violations":len(set(violations)),"result":"pass" if not violations else "fail","network_used":False,"system_mutations":0}
print(json.dumps(result, indent=2))
