from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eagleeye.crawler.engine import FetchResponse, StaticTransport
from eagleeye.interfaces.web.app366 import create_workspace_app366
from eagleeye_pro.core.app_context import AppContext

ADMIN_PW = "Orbit-Pine-Quartz-366!"
GLEIF_LEI = "529900T8BM49AURSDO55"
GLEIF_LEI_2 = "5493001KJTIIGC8Y1R12"
SEC_CIK = "320193"


def ctx(tmp_path):
    return AppContext(base_dir=tmp_path, actor="test366")


def admin(c):
    u = c.team_identity_359.create_initial_admin(username="admin366", display_name="Admin User", password=ADMIN_PW)
    return {**u, "session_id": "test-admin-366"}


def case(c, a, title="Corporate Case"):
    return c.build366.team_create_case(identity=a, title=title, client="QA", purpose="authorized public corporate research", legal_basis="public_data")


def prepare(c, a, cid, connector, identifier):
    out = c.build366.prepare_corporate_source(case_id=cid, connector_key=connector, identifier=identifier, identity=a)
    assert out["source"]
    c.build366.team_review_crawler_source(identity=a, case_id=cid, source_id=out["source"]["source_id"], decision="approve_read_only", rationale="Reviewed official public read-only corporate API")
    return c.db.one("SELECT s.*,p.* FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE s.source_id=?", (out["source"]["source_id"],))


def gleif_fixture():
    return json.dumps({
        "data": {
            "type": "lei-records",
            "id": GLEIF_LEI,
            "attributes": {
                "lei": GLEIF_LEI,
                "entity": {
                    "legalName": {"name": "Example AG", "language": "en"},
                    "status": "ACTIVE",
                    "legalAddress": {"city": "Frankfurt", "country": "DE"},
                    "headquartersAddress": {"city": "Frankfurt", "country": "DE"},
                    "registeredAt": {"id": "RA000000"},
                },
            },
        }
    }).encode()


def sec_fixture():
    return json.dumps({
        "cik": "320193",
        "entityType": "operating",
        "sic": "3571",
        "sicDescription": "Electronic Computers",
        "name": "Example Public Corp",
        "ein": "12-3456789",
        "tickers": ["EXM"],
        "exchanges": ["Nasdaq"],
        "addresses": {"business": {"street1": "Sensitive Address", "city": "Cupertino"}},
        "filings": {"recent": {"form": ["10-K", "8-K"], "accessionNumber": ["0001", "0002"], "filingDate": ["2026-01-01", "2026-02-01"]}},
    }).encode()


def replay_for(plan, body, *, user_agent="EagleEye Replay"):
    robots = f"https://{plan['host']}/robots.txt"
    transport = StaticTransport({
        robots: FetchResponse(robots, 404, {"content-type": "text/plain"}, b"", 1),
        plan["url"]: FetchResponse(plan["url"], 200, {"content-type": "application/json"}, body, 2),
    })
    transport.user_agent = user_agent
    return transport


def run_replay(c, a, cid, connector, identifier, body, *, user_agent="EagleEye Replay"):
    source = prepare(c, a, cid, connector, identifier)
    plan = c.build366.corporate_source_plan(connector, identifier)
    q = c.build366.enqueue_corporate_live(case_id=cid, source_id=source["source_id"], identity=a, confirmation="LIVE")
    transport = replay_for(plan, body, user_agent=user_agent)
    out = c.build366.run_corporate_live_job(job_id=q["job"]["job_id"], worker_id="corp366-test", declared_user_agent=user_agent, transport=transport, resolver=lambda host: ["93.184.216.34"])
    return out


def test_version_schema(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build366.version_status() == {"runtime_build": "366.0", "schema_version": "366.0", "package_version": "366.0.0", "coherent": True}
        m = c.build366.schema_metrics()
        assert m["within_gate"] and (m["table"], m["index"], m["trigger"]) == (141, 128, 8)


def test_no_new_per_build_data_tables(tmp_path):
    with ctx(tmp_path) as c:
        s = c.build366.corporate_status()
        assert s["new_per_build_data_tables"] == 0
        assert not s["automatic_external_connections"]


def test_catalog_truthfully_separates_live_and_plan_only(tmp_path):
    with ctx(tmp_path) as c:
        rows = {x["connector_key"]: x for x in c.build366.connector_catalog()}
        assert rows["gleif_lei_api_v1"]["build366_live_eligible"]
        assert rows["sec_edgar_submissions_v1"]["build366_live_eligible"]
        assert rows["companies_house_company_v1"]["plan_only"] and not rows["companies_house_company_v1"]["build366_live_eligible"]


def test_gleif_plan_exact_host_and_read_only(tmp_path):
    with ctx(tmp_path) as c:
        p = c.build366.corporate_source_plan("gleif_lei_api_v1", GLEIF_LEI)
        assert p["host"] == "api.gleif.org" and p["url"].endswith(GLEIF_LEI)
        assert p["explicit_live_confirmation_required"] and not p["automatic_external_connection"]


def test_sec_plan_exact_host_and_declared_ua(tmp_path):
    with ctx(tmp_path) as c:
        p = c.build366.corporate_source_plan("sec_edgar_submissions_v1", SEC_CIK)
        assert p["host"] == "data.sec.gov" and p["url"].endswith("CIK0000320193.json")
        assert p["requires_declared_user_agent"]


def test_person_name_is_not_a_live_query_type(tmp_path):
    with ctx(tmp_path) as c:
        s = c.build366.corporate_status()
        assert not s["person_name_live_lookup_supported"]
        with pytest.raises(ValueError):
            c.build366.corporate_source_plan("sec_edgar_submissions_v1", "Example Person")


def test_multiple_identifiers_same_provider_get_distinct_sources(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        x = c.build366.prepare_corporate_source(case_id=cid, connector_key="gleif_lei_api_v1", identifier=GLEIF_LEI, identity=a)
        y = c.build366.prepare_corporate_source(case_id=cid, connector_key="gleif_lei_api_v1", identifier=GLEIF_LEI_2, identity=a)
        assert x["source"]["source_id"] != y["source"]["source_id"]
        assert x["source"]["locator"] != y["source"]["locator"]


def test_companies_house_remains_plan_only(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        out = c.build366.prepare_corporate_source(case_id=cid, connector_key="companies_house_company_v1", identifier="00000006", identity=a)
        assert out["state"] == "plan_only_auth_required" and out["source"] is None


def test_live_enqueue_requires_explicit_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        source = prepare(c, a, cid, "gleif_lei_api_v1", GLEIF_LEI)
        with pytest.raises(PermissionError):
            c.build366.enqueue_corporate_live(case_id=cid, source_id=source["source_id"], identity=a, confirmation="yes")


def test_live_enqueue_requires_source_review(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        out = c.build366.prepare_corporate_source(case_id=cid, connector_key="gleif_lei_api_v1", identifier=GLEIF_LEI, identity=a)
        with pytest.raises(PermissionError):
            c.build366.enqueue_corporate_live(case_id=cid, source_id=out["source"]["source_id"], identity=a, confirmation="LIVE")


def test_gleif_replay_executes_parse_and_receipt_without_external_claim(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        out = run_replay(c, a, cid, "gleif_lei_api_v1", GLEIF_LEI, gleif_fixture())
        r = out["receipt"]
        assert out["job"]["status"] == "succeeded"
        assert r["parser_success"] and r["http_success"]
        assert r["replay_or_fixture"] and not r["externally_validated"]
        assert r["objects"] and len(r["objects"][0]["sha256"]) == 64
        assert len(r["receipt_sha256"]) == 64


def test_sec_replay_requires_contact_user_agent(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        source = prepare(c, a, cid, "sec_edgar_submissions_v1", SEC_CIK)
        plan = c.build366.corporate_source_plan("sec_edgar_submissions_v1", SEC_CIK)
        q = c.build366.enqueue_corporate_live(case_id=cid, source_id=source["source_id"], identity=a, confirmation="LIVE")
        t = replay_for(plan, sec_fixture(), user_agent="invalid")
        with pytest.raises(PermissionError):
            c.build366.run_corporate_live_job(job_id=q["job"]["job_id"], worker_id="w", declared_user_agent="invalid", transport=t, resolver=lambda host: ["93.184.216.34"])


def test_sec_replay_parses_with_declared_contact_ua(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        ua = "EagleEye/366 qa@example.org"
        out = run_replay(c, a, cid, "sec_edgar_submissions_v1", SEC_CIK, sec_fixture(), user_agent=ua)
        assert out["job"]["status"] == "succeeded" and out["receipt"]["parser_success"]
        assert not out["receipt"]["externally_validated"]


def test_receipt_is_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); ca = case(c, a, "A")["case_id"]; cb = case(c, a, "B")["case_id"]
        out = run_replay(c, a, ca, "gleif_lei_api_v1", GLEIF_LEI, gleif_fixture())
        assert c.build366.corporate_receipts(case_id=cb) == []
        rows = c.build366.corporate_receipts(case_id=ca)
        assert len(rows) == 1 and rows[0]["crawl_run_id"] == out["receipt"]["crawl_run_id"]


def test_ai_context_excludes_address_and_ein(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        ua = "EagleEye/366 qa@example.org"
        run_replay(c, a, cid, "sec_edgar_submissions_v1", SEC_CIK, sec_fixture(), user_agent=ua)
        summary = c.build366.corporate_case_summary(case_id=cid)
        text = json.dumps(summary, sort_keys=True)
        assert "Sensitive Address" not in text and "12-3456789" not in text
        assert "Example Public Corp" in text and summary["address_fields_in_ai_context"] is False


def test_ai_dossier_gets_corporate_context(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        run_replay(c, a, cid, "gleif_lei_api_v1", GLEIF_LEI, gleif_fixture())
        c.build366.create_investigation_intake(case_id=cid, objective="Research company facts", key_questions=["What is supported?"])
        c.build366.start_investigation_go(case_id=cid, go="GO")
        out = c.build366.run_autonomous_investigation(case_id=cid, max_ticks=1)
        assert "phase16_corporate_data_context" in out["dossier"]
        assert out["dossier"]["phase16_corporate_data_context"]["lead_review_required"]


def test_ai_has_no_direct_connector_network_authority(tmp_path):
    with ctx(tmp_path) as c:
        assert c.ai_autonomy_366.status()["direct_connector_network_authority"] is False


def test_opsec_cancels_tampered_corporate_job(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        source = prepare(c, a, cid, "gleif_lei_api_v1", GLEIF_LEI)
        q = c.build366.enqueue_corporate_live(case_id=cid, source_id=source["source_id"], identity=a, confirmation="LIVE")
        payload = json.loads(q["job"]["payload_json"])
        payload["phase16_corporate_live_confirmation"] = False
        c.db.execute("UPDATE phase15_jobs SET payload_json=? WHERE job_id=?", (json.dumps(payload), q["job"]["job_id"]))
        out = c.build366.autonomous_opsec_protect(case_id=cid)
        assert q["job"]["job_id"] in out["cancelled_invalid_corporate_jobs"]
        assert c.job_engine_348.get(q["job"]["job_id"])["status"] == "cancelled"


def test_opsec_never_mutates_system_controls(tmp_path):
    with ctx(tmp_path) as c:
        s = c.opsec_supervisor_366.status()
        assert not s["system_mutations"] and not s["firewall_mutation"] and not s["os_mutation"] and not s["tor_configuration_mutation"] and not s["credential_mutation"] and not s["acl_mutation"]


def test_crawler_improvement_366(tmp_path):
    with ctx(tmp_path) as c:
        s = c.build366.crawler_status()
        assert s["crawler_improvement_build"] == 366
        assert s["official_corporate_connector_execution"] and s["replay_cannot_claim_external_validation"]
        assert not s["authenticated_connector_live_execution"]


def test_phase16_status_six_of_twenty(tmp_path):
    with ctx(tmp_path) as c:
        s = c.build366.phase16_status()
        assert s["phase"] == "16" and s["build"] == "366.0" and s["builds_completed"] == 6
        assert s["corporate_live_data"]["production_release_ready"] is False


def test_capabilities_do_not_forge_external_validation(tmp_path):
    with ctx(tmp_path) as c:
        caps = {x["key"]: x for x in c.build366.capabilities()}
        assert not caps["gleif_live_connector_v366"]["states"]["externally_validated"]
        assert not caps["sec_edgar_live_connector_v366"]["states"]["externally_validated"]


def test_production_release_remains_false(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build366.qualified_gate()["production_release_ready"] is False


def test_no_literal_true_in_gate(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build366.active_gate_literal_true_lines() == []


def test_new_phase16_module_has_no_requests_httpx_subprocess_imports():
    names = set()
    for p in [Path("src/eagleeye/phase16/corporate_data366.py"), Path("src/eagleeye/application/build366/service.py")]:
        tree = ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                names.update(x.name.split(".")[0] for x in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module:
                names.add(n.module.split(".")[0])
    assert not names.intersection({"requests", "httpx", "aiohttp", "subprocess"})


def test_web_health_and_corporate_auth_boundary(tmp_path):
    app = create_workspace_app366(base_dir=tmp_path / "web")
    with TestClient(app) as client:
        h = client.get("/health")
        assert h.status_code == 200 and h.json()["build"] == "366.0" and h.json()["phase16_builds_completed"] == 6
        assert client.get("/api/build366/corporate/connectors").status_code == 401
        assert client.get("/api/build366/final-status").status_code == 401
