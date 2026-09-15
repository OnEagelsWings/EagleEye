from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

ROOT=Path(__file__).resolve().parents[1]

def run():
    category_pass={k:0 for k in ["federal_exact","archive_exact","plan_only","sanctions_minimization","no_fuzzy","archive_metadata_only","source_review","live_confirmation","opsec_boundary","truthful_release"]}; violations=[]
    with tempfile.TemporaryDirectory(prefix="ee368_bench_") as d:
        with AppContext(base_dir=d,actor="bench368") as c:
            fp=c.build368.code_fingerprint(); status=c.build368.reference_status(); opsec=c.opsec_supervisor_368.status()
            ofac=b"<sdnList><sdnEntry><uid>42</uid><firstName>Example</firstName><program>TEST</program><dateOfBirth>1970</dateOfBirth><address><address1>Secret</address1></address></sdnEntry></sdnList>"
            for i in range(300):
                tests=[]
                try:
                    p=c.build368.reference_source_plan("federal_register_document_v1",f"2026-{i:05d}"); tests.append(("federal_exact",p["build368_live_eligible"] and p["request_method"]=="GET"))
                except Exception: tests.append(("federal_exact",False))
                try:
                    p=c.build368.reference_source_plan("internet_archive_metadata_v1",f"item_{i}"); tests.append(("archive_exact",p["archive_payload_download"] is False))
                except Exception: tests.append(("archive_exact",False))
                plans=[c.build368.reference_source_plan("ofac_sdn_xml_v1","sdn"),c.build368.reference_source_plan("unsc_consolidated_xml_v1","consolidated"),c.build368.reference_source_plan("nara_catalog_v1",str(i+1)),c.build368.reference_source_plan("govinfo_package_v1",f"FR-2026-{i:03d}")]
                tests.append(("plan_only",all(x["plan_only"] and not x["build368_live_eligible"] for x in plans)))
                parsed=c.build368.parse_plan_only_reference(connector_key="ofac_sdn_xml_v1",body=ofac,source_url="https://sanctionslist.ofac.treas.gov/Home/SdnList"); txt=json.dumps(parsed)
                tests.append(("sanctions_minimization","Secret" not in txt and "1970" not in txt))
                tests.append(("no_fuzzy",status["sanctions_fuzzy_name_screening"] is False))
                tests.append(("archive_metadata_only",status["archive_metadata_only"] and not status["archive_content_download"]))
                tests.append(("source_review",status["human_source_review_required"]))
                tests.append(("live_confirmation",status["explicit_live_confirmation_required"]))
                tests.append(("opsec_boundary",not opsec["system_mutations"] and opsec["archive_content_download_blocked"]))
                tests.append(("truthful_release",not c.build368.qualified_gate()["production_release_ready"] and not status.get("federal_register_externally_validated",False)))
                for cat,ok in tests:
                    if ok: category_pass[cat]+=1
                    else: violations.append({"case":i,"category":cat})
    total=sum(category_pass.values())
    return {"build":"368.0","cases":3000,"category_pass":category_pass,"passed":total,"violations":len(violations),"violation_details":violations[:100],"result":"pass" if total==3000 and not violations else "fail","network_used_by_benchmark":False,"external_validation_performed":False,"code_fingerprint":fp,"truthful_scope":"Deterministic synthetic/adversarial qualification only; no external reference-source requests are made."}

if __name__=="__main__":
    r=run(); print(json.dumps(r,indent=2,sort_keys=True)); raise SystemExit(0 if r["result"]=="pass" else 1)
