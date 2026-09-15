from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eagleeye.crawler.engine import FetchResponse, StaticTransport
from eagleeye.interfaces.web.app367 import create_workspace_app367
from eagleeye_pro.core.app_context import AppContext

ADMIN_PW = "Orbit-Pine-Quartz-367!"
US_AWARD = "CONT_IDV_TMHQ10C0040_2044"
US_AWARD_2 = "CONT_AWD_EXAMPLE123_9700"
TED_NOTICE = "564613-2023"
GLEIF_LEI = "529900T8BM49AURSDO55"


def ctx(tmp_path):
    return AppContext(base_dir=tmp_path, actor="test367")


def admin(c):
    u = c.team_identity_359.create_initial_admin(username="admin367", display_name="Admin User", password=ADMIN_PW)
    return {**u, "session_id": "test-admin-367"}


def case(c, a, title="Public Money Case"):
    return c.build367.team_create_case(identity=a, title=title, client="QA", purpose="authorized public procurement and spending research", legal_basis="public_data")


def prepare(c, a, cid, connector, identifier):
    out = c.build367.prepare_public_money_source(case_id=cid, connector_key=connector, identifier=identifier, identity=a)
    assert out["source"]
    c.build367.team_review_crawler_source(identity=a, case_id=cid, source_id=out["source"]["source_id"], decision="approve_read_only", rationale="Reviewed official public read-only procurement/spending source")
    return c.db.one("SELECT s.*,p.* FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE s.source_id=?", (out["source"]["source_id"],))


def us_fixture(recipient="Example Winner Ltd") -> bytes:
    return json.dumps({
        "id": 42,
        "generated_unique_award_id": US_AWARD,
        "piid": "TMHQ10C0040",
        "category": "idv",
        "type": "IDV_B_B",
        "type_description": "INDEFINITE DELIVERY / INDEFINITE QUANTITY",
        "description": "PUBLIC PROCUREMENT OF EXAMPLE MATERIAL",
        "total_obligation": 1250000.0,
        "total_outlay": 450000.0,
        "date_signed": "2026-01-15",
        "period_of_performance": {"start_date": "2026-01-15", "end_date": "2027-01-15"},
        "recipient": {
            "recipient_name": recipient,
            "recipient_uei": "CJZ8EW1Q7JJ6",
            "parent_recipient_name": "Example Holding Ltd",
            "parent_recipient_uei": "P9T2J5V9DT32",
            "location": {"address_line1": "Sensitive Street 1", "city_name": "Secret City"},
        },
        "awarding_agency": {"toptier_agency": {"name": "Department of Example"}, "subtier_agency": {"name": "Example Procurement Agency"}},
        "funding_agency": {"toptier_agency": {"name": "Department of Example Funding"}},
        "latest_transaction_contract_data": {
            "number_of_offers_received": "3", "extent_competed_description": "FULL AND OPEN COMPETITION",
            "solicitation_procedures_description": "NEGOTIATED PROPOSAL/QUOTE", "naics": "541512",
            "naics_description": "Computer Systems Design Services", "product_or_service_code": "D302",
            "product_or_service_description": "IT AND TELECOM- SYSTEMS DEVELOPMENT",
        },
        "executive_details": {"officers": [{"name": "Sensitive Executive Person", "amount": 999999}]},
    }).encode()


def ted_fixture() -> bytes:
    return b'''<?xml version="1.0" encoding="UTF-8"?>
<Notice xmlns="urn:example:ted">
  <PublicationNumber>564613-2023</PublicationNumber>
  <NoticeIdentifier>notice-uuid-367</NoticeIdentifier>
  <ProcurementProjectName>Digital investigation platform services</ProcurementProjectName>
  <PartyName>Example Public Authority</PartyName>
  <WinnerName>Example Winner Ltd</WinnerName>
  <ItemClassificationCode>72000000</ItemClassificationCode>
  <CurrencyID>EUR</CurrencyID>
  <ValueAmount>2450000.00</ValueAmount>
  <PublicationDate>2023-09-15</PublicationDate>
  <ContactName>Sensitive Contact Person</ContactName>
  <Email>private-contact@example.org</Email>
</Notice>'''


def gleif_fixture() -> bytes:
    return json.dumps({"data":{"type":"lei-records","id":GLEIF_LEI,"attributes":{"lei":GLEIF_LEI,"entity":{"legalName":{"name":"Example Winner Ltd","language":"en"},"status":"ACTIVE","legalAddress":{"city":"Frankfurt","country":"DE"},"registeredAt":{"id":"RA000000"}}}}}).encode()


def replay_for(plan, body):
    robots = f"https://{plan['host']}/robots.txt"
    content_type = "application/xml" if plan["connector_key"] == "ted_notice_xml_v1" else "application/json"
    return StaticTransport({
        robots: FetchResponse(robots, 404, {"content-type": "text/plain"}, b"", 1),
        plan["url"]: FetchResponse(plan["url"], 200, {"content-type": content_type}, body, 2),
    })


def run_replay(c, a, cid, connector, identifier, body):
    source = prepare(c, a, cid, connector, identifier)
    plan = c.build367.public_money_source_plan(connector, identifier)
    q = c.build367.enqueue_public_money_live(case_id=cid, source_id=source["source_id"], identity=a, confirmation="LIVE")
    return c.build367.run_public_money_live_job(job_id=q["job"]["job_id"], worker_id="pm367-test", transport=replay_for(plan, body), resolver=lambda host: ["93.184.216.34"])


def run_gleif_replay(c, a, cid):
    out = c.build366.prepare_corporate_source(case_id=cid, connector_key="gleif_lei_api_v1", identifier=GLEIF_LEI, identity=a)
    c.build366.team_review_crawler_source(identity=a, case_id=cid, source_id=out["source"]["source_id"], decision="approve_read_only", rationale="Reviewed GLEIF")
    q = c.build366.enqueue_corporate_live(case_id=cid, source_id=out["source"]["source_id"], identity=a, confirmation="LIVE")
    plan = c.build366.corporate_source_plan("gleif_lei_api_v1", GLEIF_LEI)
    robots = f"https://{plan['host']}/robots.txt"
    t = StaticTransport({robots: FetchResponse(robots,404,{"content-type":"text/plain"},b"",1), plan["url"]: FetchResponse(plan["url"],200,{"content-type":"application/json"},gleif_fixture(),2)})
    return c.build366.run_corporate_live_job(job_id=q["job"]["job_id"], worker_id="corp-link-367", declared_user_agent="EagleEye Replay", transport=t, resolver=lambda host:["93.184.216.34"])


def test_version_schema(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build367.version_status() == {"runtime_build":"367.0","schema_version":"367.0","package_version":"367.0.0","coherent":True}
        m=c.build367.schema_metrics(); assert m["within_gate"] and (m["table"],m["index"],m["trigger"])==(141,128,8)


def test_no_new_per_build_data_tables(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build367.public_money_status(); assert s["new_per_build_data_tables"]==0 and not s["automatic_external_connections"]


def test_catalog_live_and_plan_only(tmp_path):
    with ctx(tmp_path) as c:
        rows={x["connector_key"]:x for x in c.build367.public_money_connector_catalog()}
        assert rows["usaspending_award_v1"]["build367_live_eligible"]
        assert rows["ted_notice_xml_v1"]["build367_live_eligible"]
        assert rows["ted_search_v3"]["plan_only"] and not rows["ted_search_v3"]["build367_live_eligible"]


def test_usaspending_plan_exact_host_get(tmp_path):
    with ctx(tmp_path) as c:
        p=c.build367.public_money_source_plan("usaspending_award_v1",US_AWARD)
        assert p["host"]=="api.usaspending.gov" and p["request_method"]=="GET" and US_AWARD in p["url"]


def test_ted_notice_plan_exact_host_get(tmp_path):
    with ctx(tmp_path) as c:
        p=c.build367.public_money_source_plan("ted_notice_xml_v1",TED_NOTICE)
        assert p["host"]=="ted.europa.eu" and p["request_method"]=="GET" and p["url"].endswith(f"/{TED_NOTICE}/xml")


def test_ted_search_is_plan_only_post(tmp_path):
    with ctx(tmp_path) as c:
        p=c.build367.public_money_source_plan("ted_search_v3","buyer-name = Example")
        assert p["request_method"]=="POST" and not p["build367_live_eligible"] and "post_search" in p["plan_only_reason"]


def test_ted_search_prepare_does_not_create_live_source(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        out=c.build367.prepare_public_money_source(case_id=cid,connector_key="ted_search_v3",identifier="buyer-name = Example",identity=a)
        assert out["state"]=="plan_only_method_not_qualified" and out["source"] is None


def test_generic_free_url_not_accepted(tmp_path):
    with ctx(tmp_path) as c:
        with pytest.raises(KeyError): c.build367.public_money_source_plan("generic_url","https://example.org/data")


def test_recipient_name_is_not_usaspending_award_id(tmp_path):
    with ctx(tmp_path) as c:
        with pytest.raises(ValueError): c.build367.public_money_source_plan("usaspending_award_v1","Example Winner Ltd")


def test_multiple_award_ids_get_distinct_sources(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        x=c.build367.prepare_public_money_source(case_id=cid,connector_key="usaspending_award_v1",identifier=US_AWARD,identity=a)
        y=c.build367.prepare_public_money_source(case_id=cid,connector_key="usaspending_award_v1",identifier=US_AWARD_2,identity=a)
        assert x["source"]["source_id"]!=y["source"]["source_id"] and x["source"]["locator"]!=y["source"]["locator"]


def test_live_enqueue_requires_explicit_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; source=prepare(c,a,cid,"usaspending_award_v1",US_AWARD)
        with pytest.raises(PermissionError): c.build367.enqueue_public_money_live(case_id=cid,source_id=source["source_id"],identity=a,confirmation="yes")


def test_live_enqueue_requires_source_review(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]
        out=c.build367.prepare_public_money_source(case_id=cid,connector_key="ted_notice_xml_v1",identifier=TED_NOTICE,identity=a)
        with pytest.raises(PermissionError): c.build367.enqueue_public_money_live(case_id=cid,source_id=out["source"]["source_id"],identity=a,confirmation="LIVE")


def test_usaspending_replay_receipt_truthful(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; out=run_replay(c,a,cid,"usaspending_award_v1",US_AWARD,us_fixture())
        r=out["receipt"]
        assert out["job"]["status"]=="succeeded" and r["http_success"] and r["parser_success"] and r["replay_or_fixture"] and not r["externally_validated"] and len(r["receipt_sha256"])==64


def test_usaspending_parser_excludes_location_and_executives_from_ai_context(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; run_replay(c,a,cid,"usaspending_award_v1",US_AWARD,us_fixture())
        text=json.dumps(c.build367.public_money_case_summary(case_id=cid),sort_keys=True)
        assert "Sensitive Street" not in text and "Sensitive Executive Person" not in text and "Example Winner Ltd" in text


def test_ted_replay_parses_safe_notice_fields(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; out=run_replay(c,a,cid,"ted_notice_xml_v1",TED_NOTICE,ted_fixture())
        assert out["receipt"]["parser_success"] and not out["receipt"]["externally_validated"]
        text=json.dumps(c.build367.public_money_case_summary(case_id=cid),sort_keys=True)
        assert "Digital investigation platform services" in text and "2450000.00" in text
        assert "Sensitive Contact Person" not in text and "private-contact@example.org" not in text


def test_receipts_are_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a,"A")["case_id"]; cb=case(c,a,"B")["case_id"]
        out=run_replay(c,a,ca,"usaspending_award_v1",US_AWARD,us_fixture())
        assert c.build367.public_money_receipts(case_id=cb)==[]
        rows=c.build367.public_money_receipts(case_id=ca); assert len(rows)==1 and rows[0]["crawl_run_id"]==out["receipt"]["crawl_run_id"]


def test_money_flow_candidate_from_usaspending(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; run_replay(c,a,cid,"usaspending_award_v1",US_AWARD,us_fixture())
        flows=c.build367.public_money_case_summary(case_id=cid)["money_flow_candidates"]
        assert any(x.get("to")=="Example Winner Ltd" and x.get("amount")==1250000.0 and x.get("currency")=="USD" for x in flows)
        assert all(x["requires_human_review"] and not x["identity_confirmed"] for x in flows)


def test_ted_money_flow_candidate_stays_hypothesis(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; run_replay(c,a,cid,"ted_notice_xml_v1",TED_NOTICE,ted_fixture())
        flows=c.build367.public_money_case_summary(case_id=cid)["money_flow_candidates"]
        assert any(x.get("publication_number")==TED_NOTICE and "Example Winner Ltd" in x.get("to_candidates",[]) for x in flows)
        assert all(x["requires_human_review"] and not x["identity_confirmed"] for x in flows)


def test_public_money_to_corporate_link_is_review_lead_only(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; run_gleif_replay(c,a,cid); run_replay(c,a,cid,"usaspending_award_v1",US_AWARD,us_fixture())
        leads=c.build367.public_money_case_summary(case_id=cid)["corporate_link_candidates"]
        assert leads and all(x["requires_human_review"] and not x["identity_confirmed"] for x in leads)


def test_ai_dossier_gets_public_money_context(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; run_replay(c,a,cid,"usaspending_award_v1",US_AWARD,us_fixture())
        c.build367.create_investigation_intake(case_id=cid,objective="Trace supported public award facts",key_questions=["What is supported?"])
        c.build367.start_investigation_go(case_id=cid,go="GO")
        out=c.build367.run_autonomous_investigation(case_id=cid,max_ticks=1)
        assert "phase16_public_money_context" in out["dossier"] and out["dossier"]["phase16_public_money_context"]["lead_review_required"]


def test_ai_has_no_direct_public_money_network_authority(tmp_path):
    with ctx(tmp_path) as c:
        assert c.ai_autonomy_367.status()["direct_public_money_network_authority"] is False


def test_opsec_cancels_tampered_public_money_job(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)["case_id"]; source=prepare(c,a,cid,"usaspending_award_v1",US_AWARD)
        q=c.build367.enqueue_public_money_live(case_id=cid,source_id=source["source_id"],identity=a,confirmation="LIVE")
        payload=json.loads(q["job"]["payload_json"]); payload["phase16_public_money_live_confirmation"]=False
        c.db.execute("UPDATE phase15_jobs SET payload_json=? WHERE job_id=?",(json.dumps(payload),q["job"]["job_id"]))
        out=c.build367.autonomous_opsec_protect(case_id=cid)
        assert q["job"]["job_id"] in out["cancelled_invalid_public_money_jobs"] and c.job_engine_348.get(q["job"]["job_id"])["status"]=="cancelled"


def test_opsec_never_mutates_system_controls(tmp_path):
    with ctx(tmp_path) as c:
        s=c.opsec_supervisor_367.status(); assert not s["system_mutations"] and not s["firewall_mutation"] and not s["os_mutation"] and not s["tor_configuration_mutation"] and not s["credential_mutation"] and not s["acl_mutation"]


def test_crawler_improvement_367(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build367.crawler_status(); assert s["crawler_improvement_build"]==367 and s["official_public_money_connector_execution"] and not s["ted_search_post_execution"] and not s["generic_free_url_execution"] and s["replay_cannot_claim_public_money_external_validation"]


def test_phase16_status_seven_of_twenty(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build367.phase16_status(); assert s["phase"]=="16" and s["build"]=="367.0" and s["builds_completed"]==7 and s["public_money"]["production_release_ready"] is False


def test_capabilities_do_not_forge_external_validation(tmp_path):
    with ctx(tmp_path) as c:
        caps={x["key"]:x for x in c.build367.capabilities()}
        assert not caps["usaspending_award_live_v367"]["states"]["externally_validated"] and not caps["ted_notice_xml_live_v367"]["states"]["externally_validated"]


def test_production_release_remains_false(tmp_path):
    with ctx(tmp_path) as c: assert c.build367.qualified_gate()["production_release_ready"] is False


def test_no_literal_true_in_gate(tmp_path):
    with ctx(tmp_path) as c: assert c.build367.active_gate_literal_true_lines()==[]


def test_new_phase16_module_has_no_direct_network_or_subprocess_imports():
    names=set()
    for p in [Path("src/eagleeye/phase16/public_money367.py"),Path("src/eagleeye/application/build367/service.py")]:
        tree=ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import): names.update(x.name.split(".")[0] for x in n.names)
            elif isinstance(n,ast.ImportFrom) and n.module: names.add(n.module.split(".")[0])
    assert not names.intersection({"requests","httpx","aiohttp","socket","subprocess"})


def test_web_health_and_public_money_auth_boundary(tmp_path):
    app=create_workspace_app367(base_dir=tmp_path/"web")
    with TestClient(app) as client:
        h=client.get("/health"); assert h.status_code==200 and h.json()["build"]=="367.0" and h.json()["phase16_builds_completed"]==7
        assert client.get("/api/build367/public-money/connectors").status_code==401
        assert client.get("/api/build367/final-status").status_code==401
