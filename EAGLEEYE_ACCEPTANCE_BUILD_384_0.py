import json, sqlite3
from eagleeye_pro.phase17.jurisdiction_intelligence384 import JurisdictionIntelligence384, create_reference_repository384
class Ready:
    def status_for_case(self, case_id): return {"state":"ready"}
providers={k:Ready() for k in ("operations","opsec","evidence","crawler","search","graph")}
repo=create_reference_repository384(sqlite3.connect(":memory:")); svc=JurisdictionIntelligence384(repo,providers)
p=svc.plan_waves(case_id="accept",mission="company procurement regulatory archive",source_classes=("corporate","procurement","regulatory","archive"),jurisdictions=("us",))
checks={
 "schema": repo.schema_integrity()["build384_tables_present"],
 "coverage_objectives": bool(p.coverage_objectives),
 "research_waves": bool(p.waves),
 "wave_confirmation_required": p.requires_wave_confirmation,
 "requires_go": all(w.requires_go for w in p.waves),
 "no_execution_authority": not p.execution_authority and all(not w.execution_authority for w in p.waves),
 "no_scope_expansion": not p.scope_expansion_authority,
 "network_silent": p.network_requests_created == 0,
 "registry_fingerprint": bool(p.registry_fingerprint),
 "gap_register": isinstance(p.gaps, tuple),
 "deterministic_persistence": repo.db.execute("SELECT COUNT(*) FROM research_wave_plan_384").fetchone()[0] >= 1,
 "jurisdiction_profiles": bool(repo.load_jurisdiction_profiles()),
}
result={"build":"384.0","passed":sum(checks.values()),"total":len(checks),"checks":checks,"result":"pass" if all(checks.values()) else "fail"}
print(json.dumps(result,indent=2))
