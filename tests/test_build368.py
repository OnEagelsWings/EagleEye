from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eagleeye.crawler.engine import FetchResponse, StaticTransport
from eagleeye.interfaces.web.app368 import create_workspace_app368
from eagleeye_pro.core.app_context import AppContext

ADMIN_PW="Orbit-Pine-Quartz-368!"
FED_DOC="2026-12345"
ARCHIVE_ID="eagleeye-public-example"


def ctx(tmp_path): return AppContext(base_dir=tmp_path,actor="test368")
def admin(c):
    u=c.team_identity_359.create_initial_admin(username="admin368",display_name="Admin User",password=ADMIN_PW)
    return {**u,"session_id":"test-admin-368"}
def case(c,a,title="Reference Case"): return c.build368.team_create_case(identity=a,title=title,client="QA",purpose="authorized legal government archive research",legal_basis="public_data")

def prepare(c,a,cid,connector,identifier):
    out=c.build368.prepare_reference_source(case_id=cid,connector_key=connector,identifier=identifier,identity=a); assert out["source"]
    c.build368.team_review_crawler_source(identity=a,case_id=cid,source_id=out["source"]["source_id"],decision="approve_read_only",rationale="Reviewed official public read-only reference source")
    return c.db.one("SELECT s.*,p.* FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE s.source_id=?",(out["source"]["source_id"],))

def federal_fixture():
    return json.dumps({"document_number":FED_DOC,"title":"Cybersecurity Records Rule","type":"Rule","abstract":"A public legal notice.","publication_date":"2026-08-15","agencies":[{"name":"Example Agency"}],"html_url":"https://www.federalregister.gov/documents/2026/08/15/2026-12345/example","pdf_url":"https://www.govinfo.gov/content/pkg/FR-2026-08-15/pdf/2026-12345.pdf","regulation_id_numbers":["1234-AA01"],"docket_ids":["EX-2026-1"],"contact":"Sensitive Contact Person","email":"private@example.org"}).encode()

def archive_fixture():
    return json.dumps({"metadata":{"identifier":ARCHIVE_ID,"title":"Public historical collection","creator":"Public Institution","date":"1984","description":"Historical public metadata","mediatype":"texts","collection":["opensource"],"subject":["history"],"language":"eng","publicdate":"2020-01-01","addeddate":"2020-01-01","uploader":"private@example.org"},"item_size":123456,"files":[{"name":"payload.pdf","sha1":"secret-file-list"}]}).encode()

def ofac_fixture():
    return b'''<sdnList><sdnEntry><uid>123</uid><firstName>Example</firstName><lastName>Entity</lastName><program>TEST</program><dateOfBirth>1970-01-01</dateOfBirth><address><address1>Sensitive Street</address1></address><idList><id><idNumber>PASSPORT-SECRET</idNumber></id></idList></sdnEntry></sdnList>'''

def un_fixture():
    return b'''<CONSOLIDATED_LIST><INDIVIDUAL><DATAID>UN123</DATAID><FIRST_NAME>Example Name</FIRST_NAME><UN_LIST_TYPE>Test List</UN_LIST_TYPE><LISTED_ON>2026-01-01</LISTED_ON><INDIVIDUAL_DATE_OF_BIRTH><DATE>1970-01-01</DATE></INDIVIDUAL_DATE_OF_BIRTH><INDIVIDUAL_ADDRESS><STREET>Sensitive Street</STREET></INDIVIDUAL_ADDRESS></INDIVIDUAL></CONSOLIDATED_LIST>'''

def replay_for(plan,body):
    robots=f"https://{plan['host']}/robots.txt"
    return StaticTransport({robots:FetchResponse(robots,404,{"content-type":"text/plain"},b"",1),plan["url"]:FetchResponse(plan["url"],200,{"content-type":"application/json"},body,2)})

def run_replay(c,a,cid,connector,identifier,body):
    source=prepare(c,a,cid,connector,identifier); plan=c.build368.reference_source_plan(connector,identifier)
    q=c.build368.enqueue_reference_live(case_id=cid,source_id=source["source_id"],identity=a,confirmation="LIVE")
    return c.build368.run_reference_live_job(job_id=q["job"]["job_id"],worker_id="ref368-test",transport=replay_for(plan,body),resolver=lambda host:["93.184.216.34"])

# 1
def test_version_schema(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build368.version_status()=={"runtime_build":"368.0","schema_version":"368.0","package_version":"368.0.0","coherent":True}
        m=c.build368.schema_metrics(); assert m["within_gate"] and (m["table"],m["index"],m["trigger"])==(141,128,8)
# 2
def test_no_new_per_build_tables(tmp_path):
    with ctx(tmp_path) as c: assert c.build368.reference_status()["new_per_build_data_tables"]==0
# 3
def test_catalog_has_two_live_four_plan(tmp_path):
    with ctx(tmp_path) as c:
        rows={x["connector_key"]:x for x in c.build368.reference_connector_catalog()}; assert sum(bool(x["build368_live_eligible"]) for x in rows.values())==2 and sum(bool(x["plan_only"]) for x in rows.values())==4
# 4
def test_federal_plan_exact_get(tmp_path):
    with ctx(tmp_path) as c:
        p=c.build368.reference_source_plan("federal_register_document_v1",FED_DOC); assert p["host"]=="www.federalregister.gov" and p["request_method"]=="GET" and p["url"].endswith(FED_DOC+".json")
# 5
def test_archive_plan_exact_metadata_only(tmp_path):
    with ctx(tmp_path) as c:
        p=c.build368.reference_source_plan("internet_archive_metadata_v1",ARCHIVE_ID); assert p["host"]=="archive.org" and p["url"].endswith("/metadata/"+ARCHIVE_ID) and p["archive_payload_download"] is False
# 6
def test_federal_identifier_is_exact(tmp_path):
    with ctx(tmp_path) as c:
        with pytest.raises(ValueError): c.build368.reference_source_plan("federal_register_document_v1","cybersecurity")
# 7
def test_archive_identifier_rejects_url(tmp_path):
    with ctx(tmp_path) as c:
        with pytest.raises(ValueError): c.build368.reference_source_plan("internet_archive_metadata_v1","https://archive.org/details/x")
# 8
def test_generic_free_url_not_accepted(tmp_path):
    with ctx(tmp_path) as c:
        with pytest.raises(KeyError): c.build368.reference_source_plan("generic_url","https://example.org")
# 9
def test_ofac_plan_only(tmp_path):
    with ctx(tmp_path) as c:
        p=c.build368.reference_source_plan("ofac_sdn_xml_v1","sdn"); assert p["plan_only"] and not p["build368_live_eligible"]
# 10
def test_unsc_plan_only(tmp_path):
    with ctx(tmp_path) as c: assert c.build368.reference_source_plan("unsc_consolidated_xml_v1","consolidated")["plan_only"]
# 11
def test_nara_plan_only_api_key(tmp_path):
    with ctx(tmp_path) as c:
        p=c.build368.reference_source_plan("nara_catalog_v1","123456"); assert p["plan_only"] and p["auth_type"]=="api_key" and "cache" in p["plan_only_reason"]
# 12
def test_govinfo_plan_only_api_key(tmp_path):
    with ctx(tmp_path) as c:
        p=c.build368.reference_source_plan("govinfo_package_v1","FR-2026-09-01"); assert p["plan_only"] and p["auth_type"]=="api_key"
# 13
def test_prepare_plan_only_never_creates_source(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; out=c.build368.prepare_reference_source(case_id=cid,connector_key="nara_catalog_v1",identifier="123456",identity=a); assert out["source"] is None and out["state"]=="plan_only_policy"
# 14
def test_live_enqueue_requires_live_word(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; src=prepare(c,a,cid,"federal_register_document_v1",FED_DOC)
        with pytest.raises(PermissionError): c.build368.enqueue_reference_live(case_id=cid,source_id=src["source_id"],identity=a,confirmation="yes")
# 15
def test_live_enqueue_requires_review(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; out=c.build368.prepare_reference_source(case_id=cid,connector_key="internet_archive_metadata_v1",identifier=ARCHIVE_ID,identity=a)
        with pytest.raises(PermissionError): c.build368.enqueue_reference_live(case_id=cid,source_id=out["source"]["source_id"],identity=a,confirmation="LIVE")
# 16
def test_federal_replay_receipt_truthful(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; out=run_replay(c,a,cid,"federal_register_document_v1",FED_DOC,federal_fixture()); r=out["receipt"]
        assert out["job"]["status"]=="succeeded" and r["http_success"] and r["parser_success"] and r["replay_or_fixture"] and not r["externally_validated"] and len(r["receipt_sha256"])==64
# 17
def test_archive_replay_receipt_truthful(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; r=run_replay(c,a,cid,"internet_archive_metadata_v1",ARCHIVE_ID,archive_fixture())["receipt"]; assert r["parser_success"] and r["replay_or_fixture"] and not r["externally_validated"]
# 18
def test_federal_ai_context_excludes_contact(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; run_replay(c,a,cid,"federal_register_document_v1",FED_DOC,federal_fixture()); text=json.dumps(c.build368.reference_case_summary(case_id=cid),sort_keys=True)
        assert "Cybersecurity Records Rule" in text and "Sensitive Contact Person" not in text and "private@example.org" not in text
# 19
def test_archive_ai_context_excludes_files_and_uploader(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; run_replay(c,a,cid,"internet_archive_metadata_v1",ARCHIVE_ID,archive_fixture()); text=json.dumps(c.build368.reference_case_summary(case_id=cid),sort_keys=True)
        assert "Public historical collection" in text and "payload.pdf" not in text and "private@example.org" not in text and "secret-file-list" not in text
# 20
def test_receipts_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a,"A")["case_id"]; cb=case(c,a,"B")["case_id"]; run_replay(c,a,ca,"federal_register_document_v1",FED_DOC,federal_fixture()); assert c.build368.reference_receipts(case_id=cb)==[] and len(c.build368.reference_receipts(case_id=ca))==1
# 21
def test_ofac_parser_is_reference_minimized(tmp_path):
    with ctx(tmp_path) as c:
        out=c.build368.parse_plan_only_reference(connector_key="ofac_sdn_xml_v1",body=ofac_fixture(),source_url="https://sanctionslist.ofac.treas.gov/Home/SdnList"); text=json.dumps(out,sort_keys=True)
        assert "123" in text and "Sensitive Street" not in text and "PASSPORT-SECRET" not in text and "1970-01-01" not in text and not out["identity_confirmed"]
# 22
def test_unsc_parser_is_reference_minimized(tmp_path):
    with ctx(tmp_path) as c:
        out=c.build368.parse_plan_only_reference(connector_key="unsc_consolidated_xml_v1",body=un_fixture(),source_url="https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list"); text=json.dumps(out,sort_keys=True)
        assert "UN123" in text and "Sensitive Street" not in text and "1970-01-01" not in text
# 23
def test_no_fuzzy_sanctions_screening(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build368.reference_status(); assert not s["sanctions_fuzzy_name_screening"] and not s["sanctions_adverse_decision_support"]
# 24
def test_archive_content_download_disabled(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build368.reference_status(); assert s["archive_metadata_only"] and not s["archive_content_download"]
# 25
def test_ai_dossier_gets_reference_context(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; run_replay(c,a,cid,"federal_register_document_v1",FED_DOC,federal_fixture()); c.build368.create_investigation_intake(case_id=cid,objective="Review public legal record",key_questions=["What is supported?"]); c.build368.start_investigation_go(case_id=cid,go="GO"); out=c.build368.run_autonomous_investigation(case_id=cid,max_ticks=1)
        assert "phase16_reference_intelligence_context" in out["dossier"] and out["dossier"]["reference_intelligence_requires_review"]
# 26
def test_ai_no_direct_reference_network_authority(tmp_path):
    with ctx(tmp_path) as c:
        s=c.ai_autonomy_368.status(); assert not s["direct_reference_network_authority"] and not s["archive_content_download_authority"]
# 27
def test_opsec_cancels_tampered_reference_job(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; src=prepare(c,a,cid,"federal_register_document_v1",FED_DOC); q=c.build368.enqueue_reference_live(case_id=cid,source_id=src["source_id"],identity=a,confirmation="LIVE"); payload=json.loads(q["job"]["payload_json"]); payload["phase16_reference_live_confirmation"]=False; c.db.execute("UPDATE phase15_jobs SET payload_json=? WHERE job_id=?",(json.dumps(payload),q["job"]["job_id"])); out=c.build368.autonomous_opsec_protect(case_id=cid); assert q["job"]["job_id"] in out["cancelled_invalid_reference_jobs"] and c.job_engine_348.get(q["job"]["job_id"])["status"]=="cancelled"
# 28
def test_opsec_no_system_mutations(tmp_path):
    with ctx(tmp_path) as c:
        s=c.opsec_supervisor_368.status(); assert not any(s[k] for k in ("system_mutations","firewall_mutation","os_mutation","tor_configuration_mutation","credential_mutation","acl_mutation"))
# 29
def test_crawler_improvement_368(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build368.crawler_status(); assert s["crawler_improvement_build"]==368 and s["official_reference_connector_execution"] and not s["generic_free_url_execution"] and not s["archive_content_download"] and s["replay_cannot_claim_reference_external_validation"]
# 30
def test_phase16_status_eight_of_twenty(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build368.phase16_status(); assert s["phase"]=="16" and s["build"]=="368.0" and s["builds_completed"]==8
# 31
def test_capabilities_do_not_forge_external_validation(tmp_path):
    with ctx(tmp_path) as c:
        caps={x["key"]:x for x in c.build368.capabilities()}; assert not caps["federal_register_live_v368"]["states"]["externally_validated"] and not caps["internet_archive_metadata_live_v368"]["states"]["externally_validated"]
# 32
def test_production_release_false(tmp_path):
    with ctx(tmp_path) as c: assert c.build368.qualified_gate()["production_release_ready"] is False
# 33
def test_no_literal_true_in_gate(tmp_path):
    with ctx(tmp_path) as c: assert c.build368.active_gate_literal_true_lines()==[]
# 34
def test_new_modules_have_no_direct_network_or_subprocess_imports():
    names=set()
    for p in [Path("src/eagleeye/phase16/reference_intel368.py"),Path("src/eagleeye/application/build368/service.py")]:
        tree=ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import): names.update(x.name.split(".")[0] for x in n.names)
            elif isinstance(n,ast.ImportFrom) and n.module: names.add(n.module.split(".")[0])
    assert not names.intersection({"requests","httpx","aiohttp","socket","subprocess"})
# 35
def test_web_health_and_auth_boundary(tmp_path):
    app=create_workspace_app368(base_dir=tmp_path/"web")
    with TestClient(app) as client:
        h=client.get("/health"); assert h.status_code==200 and h.json()["build"]=="368.0" and h.json()["phase16_builds_completed"]==8 and not h.json()["archive_content_download"]
        assert client.get("/api/build368/reference/connectors").status_code==401 and client.get("/api/build368/final-status").status_code==401
