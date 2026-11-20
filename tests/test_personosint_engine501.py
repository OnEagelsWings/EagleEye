"""PersonOSINT als Recherche-Motor der Fallakte: Quellen laufen über den freigegebenen EagleEye-Providerweg."""
import json
from urllib.parse import urlsplit

import pytest

from eagleeye.application import public_sources501 as sources
from eagleeye.infrastructure.providers import ProviderRunRequest, ProviderTransportResponse, ProviderValidationError
from eagleeye.infrastructure.providers.adapters import default_adapters
from eagleeye.infrastructure.providers.personosint_bridge import BRIDGED, EXCLUDED, personosint_adapters
from eagleeye.interfaces.web.app500 import create_workspace_app500
from test_build471_local_ai import workspace  # noqa: F401

ws = pytest.mark.parametrize("workspace", [create_workspace_app500], indirect=True)
FORBIDDEN_HEADERS = {"authorization", "cookie", "x-api-key", "api-key", "proxy-authorization"}


def reply(url, status=200, payload=None, body=None):
    data = body if body is not None else (json.dumps(payload).encode() if payload is not None else b"")
    return ProviderTransportResponse(url, url, status, {"Content-Type": "application/json"}, data)


def test_bridge_registers_every_bridged_source_once_and_documents_the_rest():
    adapters = personosint_adapters()
    assert [a.source.key for a in adapters] == list(BRIDGED)
    keys = [a.definition.provider_key for a in default_adapters()]
    assert len(keys) == len(set(keys))
    assert all(a.definition.provider_key in keys for a in adapters)
    assert not set(BRIDGED) & set(EXCLUDED)
    # Lizenz- oder schlüsselpflichtige Quellen laufen nicht automatisch.
    assert {"orcid", "opencorporates", "companies_house", "opensanctions"} <= set(EXCLUDED)
    # Jeder Katalogeintrag des Motors zeigt auf einen registrierten Provider.
    for entry in sources.PERSONOSINT_SOURCES:
        assert entry.provider in keys


@pytest.mark.parametrize("adapter", personosint_adapters(), ids=lambda a: a.definition.provider_key)
def test_planned_requests_respect_allowlist_and_carry_no_credentials(adapter):
    d = adapter.definition
    assert d.allowed_hosts and d.supports_live and d.metadata["candidate_only"]
    value = {"username": "alexexample", "email": "alex@example.org", "domain": "example.org", "url": "https://example.org/",
             "location": "Kiel", "employer": "Beispiel GmbH", "name": "Alex Example"}[adapter.source.kinds[0]]
    request = ProviderRunRequest("case", d.provider_key, value, "Synthetic public source check", "reviewer")
    adapter.validate_request(request)
    calls = adapter.build_requests(request)
    assert 1 <= len(calls) <= 25
    for call in calls:
        assert call.method == "GET" and urlsplit(call.url).scheme == "https"
        assert urlsplit(call.url).hostname in d.allowed_hosts
        assert not {k.casefold() for k in call.headers} & FORBIDDEN_HEADERS


def test_kind_prefix_and_unsupported_kind():
    adapter = next(a for a in personosint_adapters() if a.source.key == "gravatar")
    req = ProviderRunRequest("case", adapter.definition.provider_key, "email: Alex@Example.org", "Synthetic check", "r")
    (call,) = adapter.build_requests(req)
    assert "alex" not in call.url.casefold()     # abgefragt wird nur der Prüfwert, nicht die Adresse
    with pytest.raises(ProviderValidationError, match="verarbeitet nur"):
        adapter.validate_request(ProviderRunRequest("case", adapter.definition.provider_key, "name: Alex Example", "Synthetic", "r"))


def test_multi_request_source_waits_for_all_answers_and_maps_claims():
    adapter = next(a for a in personosint_adapters() if a.source.key == "username_presence")
    req = ProviderRunRequest("case", adapter.definition.provider_key, "alexexample", "Synthetic check", "r")
    calls = adapter.build_requests(req)
    assert len(calls) == 13
    items = []
    for call in calls:
        host = urlsplit(call.url).hostname
        out = adapter.normalize(reply(call.url, 200, {"login": "alexexample"}) if host == "api.github.com" else reply(call.url, 404), req)
        if call is not calls[-1]:
            assert out == ()
        items.extend(out)
    assert len(items) == 1 and items[0].url == "https://github.com/alexexample"
    payload = items[0].raw_payload
    assert payload["engine"] == "personosint" and payload["identity_confirmed"] is False
    with pytest.raises(ProviderValidationError):       # ohne Planung keine Auswertung
        adapter.normalize(reply(calls[0].url, 404), req)


def _run(ctx, user, cid, kind, term, selected, fetch, monkeypatch):
    monkeypatch.setattr(ctx.provider_collection_120.transport, "fetch", fetch)
    plan = sources.prepare(ctx, user, cid, kind, term, selected, "Synthetic public account comparison, identity unconfirmed.")
    plan, rows = sources.package(ctx, user, cid, plan["plan_id"])
    sources.approve(ctx, user, cid, plan["plan_id"], sources.snapshot(plan, rows), "Exact sources and query wording reviewed.")
    return rows, [sources.run(ctx, user, cid, plan["plan_id"], row["query_id"], "live") for row in rows]


KEYBASE = {"status": {"code": 0}, "them": [{"basics": {"username": "alexexample"}, "profile": {"full_name": "Alex Example", "location": "Kiel"},
           "proofs_summary": {"all": [{"proof_type": "github", "nametag": "alexexample", "service_url": "https://github.com/alexexample"}]}}]}


@ws
def test_approved_case_run_stores_personosint_candidates_with_claims(workspace, monkeypatch):
    app, client, user, cid, _, other, _ = workspace
    ctx = app.state.context
    calls = []

    def fetch(request, **kwargs):
        calls.append(request.url)
        host = urlsplit(request.url).hostname
        if host == "keybase.io":
            return reply(request.url, 200, KEYBASE)
        if host == "api.github.com":
            return reply(request.url, 200, {"login": "alexexample"})
        if host == "www.reddit.com":
            return reply(request.url, 403, body=b"blocked")    # 4xx einer einzelnen Plattform bricht den Lauf nicht ab
        return reply(request.url, 404)

    rows, results = _run(ctx, user, cid, "username", "alexexample", ["po_username", "po_keybase"], fetch, monkeypatch)
    assert [r["query_text"] for r in rows] == ["benutzername: alexexample"] * 2
    assert all(r["state"] == "completed" for r in results), results
    assert len(calls) == 14 and all(urlsplit(u).scheme == "https" for u in calls)
    intake = ctx.provider_collection_120.list_intake(cid)
    by_provider = {}
    for row in intake:
        by_provider.setdefault(row["provider_key"], []).append(row)
    presence = by_provider["personosint_username_presence_501"]
    assert {x["url"] for x in presence} == {"https://github.com/alexexample", "https://keybase.io/alexexample"}
    (kb,) = by_provider["personosint_keybase_501"]
    assert kb["candidate_only"] and kb["review_status"] == "new"
    assert kb["raw_payload"]["claims"][0]["predicate"] == "konto"
    assert kb["raw_payload"]["identity_confirmed"] is False and kb["raw_payload"]["names"] == ["Alex Example"]
    assert not ctx.provider_collection_120.list_intake(other)


@ws
def test_not_found_everywhere_completes_without_candidates(workspace, monkeypatch):
    app, client, user, cid, *_ = workspace
    ctx = app.state.context
    rows, results = _run(ctx, user, cid, "username", "nobody-here", ["po_dockerhub"],
                         lambda request, **kw: reply(request.url, 404), monkeypatch)
    assert results[0]["state"] == "completed"
    assert not ctx.provider_collection_120.list_intake(cid)


@ws
def test_catalog_marks_engine_sources_ready_and_never_fetches_on_prepare(workspace, monkeypatch):
    app, client, user, cid, *_ = workspace
    ctx = app.state.context
    monkeypatch.setattr(ctx.provider_collection_120.transport, "fetch", lambda *a, **k: pytest.fail("no network on prepare"))
    rows = {r["source"].key: r for r in sources.catalog(ctx, "person")}
    assert rows["po_interpol_red"]["ready"] and rows["icij"]["ready"] and not rows["orcid"]["ready"]
    assert {r["source"].key for r in sources.catalog(ctx, "email")} == {"po_gravatar"}
    with pytest.raises(ValueError):
        sources.prepare(ctx, user, cid, "email", "alex@example.org", ["po_username"], "Synthetic wrong kind for this source.")
    plan = sources.prepare(ctx, user, cid, "email", "alex@example.org", ["po_gravatar"], "Synthetic public profile check only.")
    assert plan["plan_id"]


def _company(name, siren, people, city="Lyon"):
    return {"nom_complet": name, "siren": siren, "siege": {"adresse": "1 Rue Exemple", "libelle_commune": city},
            "etat_administratif": "A", "date_creation": "2020-01-01", "dirigeants": people}


@ws
def test_person_analysis_page_shows_contradictions_and_cross_links(workspace, monkeypatch):
    app, client, user, cid, _, other, _ = workspace
    ctx = app.state.context
    alex_a = {"nom": "EXAMPLE", "prenoms": "Alex", "qualite": "Président", "date_de_naissance": "1980-03"}
    alex_b = {"nom": "EXAMPLE", "prenoms": "Alex", "qualite": "Gérant", "date_de_naissance": "1991-11"}
    kim = {"nom": "MUSTER", "prenoms": "Kim", "qualite": "Directeur général"}
    by_query = {"Alex Example": [_company("Beispiel Alpha SAS", "111111111", [alex_a]), _company("Beispiel Beta SARL", "222222222", [alex_b])],
                "Beispiel Alpha": [_company("Beispiel Alpha SAS", "111111111", [alex_a, kim])]}

    def fetch(request, **kwargs):
        from urllib.parse import parse_qs
        term = parse_qs(urlsplit(request.url).query)["q"][0]
        return reply(request.url, 200, {"results": by_query[term]})

    empty = client.get("/workbench/personanalyse", params={"case_id": cid})
    assert empty.status_code == 200 and "Noch keine Aussagen" in empty.text
    _run(ctx, user, cid, "person", "Alex Example", ["po_fr_entreprises"], fetch, monkeypatch)
    later = ctx.provider_collection_120.clock() + 60        # Mindestabstand der Quelle ist eingehalten
    monkeypatch.setattr(ctx.provider_collection_120, "clock", lambda: later)
    _run(ctx, user, cid, "company", "Beispiel Alpha", ["po_fr_entreprises"], fetch, monkeypatch)
    data = client.get("/api/research/personanalyse", params={"case_id": cid}).json()
    assert data["available"] and not data["network_executed"] and data["candidates"] == 3
    (contra,) = data["contradictions"]
    assert contra["predicate"] == "geburtsdatum" and {v["value"] for v in contra["values"]} == {"1980-03", "1991-11"}
    assert any(c["rule"] == "gemeinsame_firma" and "Kim Muster" in c["members"] for c in data["correlations"])
    assert any(f["rule"] == "identitaet_unsicher" for f in data["red_flags"])
    page = client.get("/workbench/personanalyse", params={"case_id": cid})
    assert page.status_code == 200 and "Widersprüche" in page.text and "1991-11" in page.text
    assert 'href="/workbench/personanalyse?' in page.text     # im Menü „Auswertung“
    # Fallgrenze: der andere Fall sieht nichts.
    assert client.get("/api/research/personanalyse", params={"case_id": other}).json()["stats"]["facts"] == 0
    assert client.get("/api/research/personanalyse", params={"case_id": "missing"}).status_code == 403
    # Im Prüfeingang abgelehnte Kandidaten zählen als verworfen – der Widerspruch entfällt.
    beta = next(r for r in ctx.provider_collection_120.list_intake(cid) if "Beta" in r["title"])
    ctx.provider_collection_120.update_intake_status(beta["intake_id"], "rejected", user["username"], "Andere Person")
    data = client.get("/api/research/personanalyse", params={"case_id": cid}).json()
    assert not data["contradictions"] and data["stats"]["rejected"] >= 1
