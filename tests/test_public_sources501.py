"""Current integrated app: real adapters, exact grants and canonical candidate intake."""
import hashlib
import json
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from eagleeye.application import public_sources501 as sources
from eagleeye.infrastructure.providers import ProviderRunRequest, ProviderTransportResponse, ProviderValidationError
from eagleeye.infrastructure.providers.public_sources501 import additional_adapters
from eagleeye.interfaces.web.app500 import create_workspace_app500
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.app448 import COOKIE
from test_build471_local_ai import workspace  # noqa: F401

ws = pytest.mark.parametrize("workspace", [create_workspace_app500], indirect=True)

PAYLOADS = {
    "lobid_gnd_persons_public_501": {"member": [{"gndIdentifier": "1234567", "preferredName": "Example, Alex",
        "type": ["DifferentiatedPerson", "Person"], "variantName": ["Alex Example"],
        "professionOrOccupation": [{"label": "Autor"}], "dateOfBirth": ["DO NOT IMPORT"],
        "gender": [{"label": "DO NOT IMPORT"}], "email": "DO NOT IMPORT"}]},
    "abgeordnetenwatch_persons_public_501": {"meta": {"status": "ok"}, "data": [{
        "id": 42, "label": "Alex Example", "occupation": "Abgeordneter", "qid_wikidata": "Q123",
        "abgeordnetenwatch_url": "https://www.abgeordnetenwatch.de/profile/alex-example",
        "year_of_birth": "DO NOT IMPORT", "sex": "DO NOT IMPORT", "residence": "DO NOT IMPORT"}]},
    "hdx_catalog_public_501": {"success": True, "result": {"results": [{"id": "ds-1", "name": "example-data",
        "title": "Example open dataset", "license_title": "CC BY 4.0", "private": False,
        "resources": [{"url": "https://example.org/data.csv", "format": "CSV"}], "dataset_source": "Example Publisher"}]}},
    "crossref_topics_public_501": {"message": {"items": [{"DOI": "10.0000/example", "title": ["Example research"],
        "author": [{"given": "Alex", "family": "Example"}], "published": {"date-parts": [[2026, 10, 1]]}}]}},
    "openalex_works_public_501": {"results": [{"id": "https://openalex.org/W123456", "title": "Example research",
        "publication_date": "2026-10-01", "authorships": [{"author": {"display_name": "Alex Example"}}]}]},
    "commoncrawl_index_public_501": {"url": "https://example.org/", "timestamp": "20261001000000", "status": "200",
        "filename": "crawl-data/CC-MAIN-2026-43/segments/example/warc/example.warc.gz", "offset": "10", "length": "100"},
}


def response(url, payload):
    return ProviderTransportResponse(url, url, 200, {"Content-Type": "application/json"}, json.dumps(payload).encode())


@pytest.mark.parametrize("adapter", additional_adapters(), ids=lambda a: a.definition.provider_key)
def test_source_contracts_and_bounded_normalization(adapter):
    key = adapter.definition.provider_key
    term = "CC-MAIN-2026-43 https://example.org/" if key.startswith("commoncrawl") else "Alex Example"
    req = ProviderRunRequest("case-test", key, term, "Public source validation", "reviewer", max_results=1)
    adapter.validate_request(req)
    calls = adapter.build_requests(req)
    assert len(calls) == 1 and urlsplit(calls[0].url).hostname in adapter.definition.allowed_hosts
    items = adapter.normalize(response(calls[0].url, PAYLOADS[key]), req)
    assert len(items) == 1 and items[0].url.startswith("https://")
    assert "DO NOT IMPORT" not in json.dumps(items[0].raw_payload)
    if key == "crossref_topics_public_501":
        assert "query.bibliographic" in parse_qs(urlsplit(calls[0].url).query)
        assert "query.author" not in parse_qs(urlsplit(calls[0].url).query)
    if key == "commoncrawl_index_public_501":
        assert "index.commoncrawl.org/" in items[0].url
        assert "data.commoncrawl.org/crawl-data/" in items[0].raw_payload["archive_file_url"]
        assert not adapter.definition.supports_replay


@pytest.mark.parametrize("bad", ["https://example.org/", "CC-MAIN-2026-43 http://127.0.0.1/", "CC-MAIN-2026-43 https://example.org/*"])
def test_commoncrawl_rejects_unbounded_or_private_scope(bad):
    adapter = additional_adapters()[-1]
    with pytest.raises(ProviderValidationError):
        adapter.validate_request(ProviderRunRequest("case", adapter.definition.provider_key, bad, "Public archive lookup", "reviewer"))


def token(workspace):
    app, client, *_ = workspace
    session = app.state.context.team_identity_359.authenticate(username="qa471", password="Build471!Password_88",
        client_fingerprint=hashlib.sha256(b"testclient||testclient").hexdigest())
    client.cookies.clear()
    client.cookies.set(COOKIE, session.token)
    client.cookies.set(CSRF_COOKIE, session.csrf_token)
    return session.csrf_token


@ws
def test_current_ui_catalog_and_preparation_do_not_fetch(workspace, monkeypatch):
    app, client, user, cid, _, other, _ = workspace
    ctx = app.state.context
    network = Mock(side_effect=AssertionError("No request permitted"))
    monkeypatch.setattr(ctx.provider_collection_120.transport, "fetch", network)
    csrf = token(workspace)
    r = client.get("/workbench", params={"case_id": cid})
    assert r.status_code == 200 and "/workbench/public-sources" in r.text
    r = client.get("/workbench/public-sources", params={"case_id": cid, "kind": "person", "term": "Alex Example"})
    assert r.status_code == 200 and "GND / lobid" in r.text and "Lobbyregister" in r.text
    assert "source\" value=\"orcid" not in r.text  # Not falsely selectable as a live adapter.
    data = client.get("/api/research/public-sources", params={"case_id": cid, "kind": "person"}).json()
    assert not data["network_executed"]
    federal = client.get("/api/research/public-sources", params={"case_id": cid, "kind": "federal"}).json()
    entries = {x["id"]: x for x in federal["sources"]}
    assert {"bundesanzeiger", "unternehmensregister", "handelsregister", "dip", "bundestag_opendata", "govdata"} <= set(entries)
    assert not entries["bundesanzeiger"]["adapter_available"]
    assert "kostenpflichtig" in entries["unternehmensregister"]["terms"]
    federal_page = client.get("/workbench/public-sources", params={"case_id": cid, "kind": "federal"})
    assert federal_page.status_code == 200 and "Bundesanzeiger" in federal_page.text
    assert "Suchpaket als Entwurf anlegen" not in federal_page.text
    assert next(x for x in data["sources"] if x["id"] == "gnd")["adapter_available"]
    assert not next(x for x in data["sources"] if x["id"] == "orcid")["adapter_available"]
    r = client.post("/workbench/public-sources/prepare", data={"case_id": cid, "csrf": csrf,
        "kind": "person", "term": "Alex Example", "source": ["gnd", "abgeordnetenwatch"],
        "purpose": "Synthetic public role and authority record comparison."}, follow_redirects=False)
    assert r.status_code == 303, r.text
    assert not network.called
    assert not ctx.provider_collection_120.list_intake(cid)
    assert not ctx.provider_collection_120.list_intake(other)
    assert client.get("/workbench/public-sources", params={"case_id": "missing"}).status_code == 403
    assert client.get("/api/research/public-sources", params={"case_id": "missing"}).status_code == 403


@ws
def test_exact_approval_execution_intake_and_duplicate_prevention(workspace, monkeypatch):
    app, client, user, cid, _, other, _ = workspace
    ctx = app.state.context
    plan = sources.prepare(ctx, user, cid, "person", "Alex Example", ["gnd", "abgeordnetenwatch"],
                           "Synthetic public person comparison, without asserting shared identity.")
    plan, rows = sources.package(ctx, user, cid, plan["plan_id"])
    calls = []
    def fetch(request, **kwargs):
        calls.append(request.url)
        key = "lobid_gnd_persons_public_501" if "lobid.org" in request.url else "abgeordnetenwatch_persons_public_501"
        return response(request.url, PAYLOADS[key])
    monkeypatch.setattr(ctx.provider_collection_120.transport, "fetch", fetch)
    with pytest.raises(ValueError):
        sources.run(ctx, user, cid, plan["plan_id"], rows[0]["query_id"], "live")
    assert not calls
    with pytest.raises(ValueError, match="geändert"):
        sources.approve(ctx, user, cid, plan["plan_id"], "stale", "Exact source selection and query wording reviewed.")
    sources.approve(ctx, user, cid, plan["plan_id"], sources.snapshot(plan, rows), "Exact source selection and query wording reviewed.")
    for row in rows:
        result = sources.run(ctx, user, cid, plan["plan_id"], row["query_id"], "live")
        assert result["state"] == "completed"
    assert len(calls) == 2
    with pytest.raises(ValueError, match="already"):
        sources.run(ctx, user, cid, plan["plan_id"], rows[0]["query_id"], "live")
    assert len(calls) == 2
    intake = ctx.provider_collection_120.list_intake(cid)
    assert len(intake) == 2 and all(x["candidate_only"] and x["review_status"] == "new" for x in intake)
    assert all(x["raw_payload"].get("identity_confirmed") is False for x in intake)
    assert not ctx.provider_collection_120.list_intake(other)
    with pytest.raises(KeyError):
        sources.package(ctx, user, other, plan["plan_id"])
    page = client.get("/workbench/public-sources", params={"case_id": cid, "plan_id": plan["plan_id"]})
    assert page.status_code == 200 and "Gespeicherte Kandidaten: 1" in page.text
    csrf = token(workspace)
    data = {"case_id": cid, "csrf": csrf, "plan_id": plan["plan_id"], "intake_id": intake[0]["intake_id"],
            "confirm": "yes", "note": "Synthetic original checked; shared identity remains unconfirmed."}
    assert client.post("/workbench/public-sources/lead", data={**data, "case_id": other}).status_code == 404
    assert client.post("/workbench/public-sources/lead", data=data, follow_redirects=False).status_code == 303
    assert client.post("/workbench/public-sources/lead", data=data, follow_redirects=False).status_code == 303
    leads = ctx.db.all("SELECT * FROM research_leads_483 WHERE case_id=?", (cid,))
    assert len(leads) == 1 and leads[0]["review_state"] == "unverified_lead"
    assert intake[0]["intake_id"] in leads[0]["analyst_note"] and intake[0]["run_id"] in leads[0]["analyst_note"]
    # Queries are persisted in the canonical search table and bound to the plan.
    assert ctx.db.one("SELECT count(*) AS n FROM search_intents_114 WHERE workflow_id=?", (plan["plan_id"],))["n"] == 2


@ws
def test_no_partial_packages_for_gated_sources_or_csrf(workspace):
    app, client, user, cid, *_ = workspace
    ctx = app.state.context
    before = len(ctx.db.all("SELECT * FROM case_plans_496"))
    with pytest.raises(ValueError):
        sources.prepare(ctx, user, cid, "person", "Alex Example", ["gnd", "orcid"], "Synthetic public source test only.")
    assert len(ctx.db.all("SELECT * FROM case_plans_496")) == before
    csrf = token(workspace)
    data = {"case_id": cid, "csrf": "wrong", "kind": "person", "term": "Alex Example", "source": "gnd", "purpose": "Synthetic public source test only."}
    assert client.post("/workbench/public-sources/prepare", data=data).status_code == 403
    data.update(csrf=csrf, source="orcid")
    assert client.post("/workbench/public-sources/prepare", data=data).status_code == 409
    assert len(ctx.db.all("SELECT * FROM case_plans_496")) == before


@ws
def test_browser_grants_and_non_json_archive_without_false_replay(workspace, monkeypatch):
    app, client, user, cid, _, other, _ = workspace
    ctx = app.state.context
    csrf = token(workspace)
    plan = sources.prepare(ctx, user, cid, "url", "https://example.org/", ["common_crawl"],
                           "Check a synthetic public archive URL in a specified collection.", "CC-MAIN-2026-43")
    plan, rows = sources.package(ctx, user, cid, plan["plan_id"])
    assert client.post("/workbench/public-sources/approve", data={"case_id": cid, "csrf": csrf,
        "plan_id": plan["plan_id"], "expected_hash": sources.snapshot(plan, rows), "confirm": "yes",
        "reason": "This exact archive collection and public URL were reviewed."}, follow_redirects=False).status_code == 303
    payload = PAYLOADS["commoncrawl_index_public_501"]
    calls = []
    def fetch(request, **kwargs):
        calls.append(request.url)
        body = (json.dumps(payload) + "\n" + json.dumps({**payload, "timestamp": "20261002000000"})).encode()
        return ProviderTransportResponse(request.url, request.url, 200, {"Content-Type": "application/x-ndjson"}, body)
    monkeypatch.setattr(ctx.provider_collection_120.transport, "fetch", fetch)
    data = {"case_id": cid, "csrf": csrf, "plan_id": plan["plan_id"], "query_id": rows[0]["query_id"],
            "confirm": "yes", "mode": "live", "query": "USER CANNOT OVERRIDE THE STORED QUERY"}
    assert client.post("/workbench/public-sources/run", data={**data, "case_id": other}).status_code == 404
    assert not calls
    assert client.post("/workbench/public-sources/run", data=data, follow_redirects=False).status_code == 303
    assert len(calls) == 1
    assert "example.org" in calls[0] and "OVERRIDE" not in calls[0]
    items = ctx.provider_collection_120.list_intake(cid)
    assert len(items) == 2 and all(x["candidate_only"] for x in items)
    assert not ctx.db.all("SELECT * FROM provider_replay_fixtures_120 WHERE provider_key='commoncrawl_index_public_501'")
    assert client.post("/workbench/public-sources/run", data=data).status_code == 409
    assert len(calls) == 1


@ws
def test_source_review_permission_and_stale_query_snapshot(workspace, monkeypatch):
    app, client, user, cid, *_ = workspace
    ctx = app.state.context
    plan = sources.prepare(ctx, user, cid, "person", "Alex Example", ["gnd"], "Synthetic authority source validation only.")
    plan, rows = sources.package(ctx, user, cid, plan["plan_id"])
    original = ctx.team_governance_359.authorize
    def deny_review(*args, **kwargs):
        if kwargs.get("capability") == "source.review":
            raise PermissionError("Read-only reviewer")
        return original(*args, **kwargs)
    with monkeypatch.context() as m:
        m.setattr(ctx.team_governance_359, "authorize", deny_review)
        with pytest.raises(PermissionError):
            sources.approve(ctx, user, cid, plan["plan_id"], sources.snapshot(plan, rows), "Exact search terms and authority source reviewed.")
    old = sources.snapshot(plan, rows)
    ctx.db.execute("UPDATE search_queries_114 SET query_text='Different Example' WHERE query_id=?", (rows[0]["query_id"],))
    with pytest.raises(ValueError, match="geändert"):
        sources.approve(ctx, user, cid, plan["plan_id"], old, "Exact search terms and authority source reviewed.")
    assert ctx.db.one("SELECT state FROM case_plans_496 WHERE plan_id=?", (plan["plan_id"],))["state"] == "draft"
