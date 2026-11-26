"""TED (EU public procurement): query building, response parsing, stored searches, page."""
from __future__ import annotations

import pytest

from eagleeye.application import ted
from eagleeye.interfaces.web.app500 import create_workspace_app500
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build492_intel import csrf_session

ws = pytest.mark.parametrize("workspace", [create_workspace_app500], indirect=True)

NOTICE = {
    "publication-number": "123456-2026",
    "notice-title": {"deu": ["Lieferung von Laborgeräten"], "eng": ["Supply of laboratory equipment"]},
    "publication-date": "2026-03-14+01:00",
    "buyer-name": {"deu": ["Universitätsklinikum Beispielstadt"]},
    "buyer-country": ["DEU"],
    "winner-name": {"deu": ["Muster GmbH", "Muster GmbH", "Beispiel AG"]},
    "notice-type": "can-standard",
    "classification-cpv": ["38000000"],
    "total-value": "245000", "total-value-cur": "EUR",
    "links": {"html": {"ENG": "https://ted.europa.eu/en/notice/-/detail/123456-2026",
                       "DEU": "https://ted.europa.eu/de/notice/-/detail/123456-2026"}},
}


def test_query_is_built_from_role_country_and_dates():
    assert ted.build_query("Muster GmbH", role="gewinner") == 'winner-name ~ ("Muster GmbH")'
    assert ted.build_query('Muster "GmbH" (alt)', role="alle", country="deu", date_from="2025-01-01", date_to="2025-12-31") == (
        'FT ~ ("Muster GmbH alt") AND buyer-country = DEU AND publication-date >= 20250101 AND publication-date <= 20251231')
    assert ted.build_query("Stadt Köln", role="auftraggeber").startswith('buyer-name ~ ("Stadt Köln")')
    for kwargs, message in (({"term": "x"}, "Firmennamen"), ({"term": "Muster", "country": "DE"}, "dreistelligen"),
                            ({"term": "Muster", "date_from": "1.1.2025"}, "JJJJ"), ({"term": "Muster", "role": "?"}, "Suchart"),
                            ({"term": "Muster", "date_from": "2025-02-01", "date_to": "2025-01-01"}, "nach dem Bis")):
        term = kwargs.pop("term")
        with pytest.raises(ted.TedError, match=message):
            ted.build_query(term, **kwargs)


def test_notice_is_read_in_german_with_link_and_value():
    row = ted.parse_notice(NOTICE)
    assert row == {"number": "123456-2026", "date": "2026-03-14", "title": "Lieferung von Laborgeräten",
                   "buyer": "Universitätsklinikum Beispielstadt", "country": "DEU", "winner": "Muster GmbH; Beispiel AG",
                   "type": "Zuschlag", "cpv": "38000000", "value": "245000 EUR",
                   "url": "https://ted.europa.eu/de/notice/-/detail/123456-2026"}
    bare = ted.parse_notice({"publication-number": "9-2026", "notice-title": {"fra": "Travaux"}})
    assert bare["title"] == "Travaux" and bare["url"].endswith("/9-2026") and bare["value"] == ""


@ws
def test_search_is_stored_and_falls_back_without_value_fields(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    sent = []

    def post(body):
        sent.append(body)
        if "total-value" in body["fields"]:
            raise ted.TedError("TED lehnte die Anfrage ab (HTTP 400): unknown field total-value")
        return {"notices": [NOTICE], "totalNoticeCount": 1}

    result = ted.search(ctx, user=user, case_id=case_id, term="Muster", role="gewinner", country="DEU", post=post)
    assert result["total"] == 1 and result["results"][0]["winner"] == "Muster GmbH; Beispiel AG"
    assert sent[0]["query"] == 'winner-name ~ ("Muster") AND buyer-country = DEU' and sent[0]["limit"] == ted.PAGE_SIZE
    assert "total-value" not in sent[1]["fields"], "a rejected value field does not break the search"
    stored = ted.searches(ctx, case_id)[0]
    assert stored["term"] == "Muster" and stored["results"][0]["number"] == "123456-2026"
    assert ctx.db.one("SELECT COUNT(*) AS n FROM audit_events WHERE action='ted_search_500'")["n"] == 1


@ws
def test_ted_page_search_and_saving_as_web_evidence(workspace, monkeypatch):
    app, client, user, case_id, *_ = workspace
    csrf = csrf_session(workspace)
    view = client.get("/workbench/ted", params={"case_id": case_id})
    assert view.status_code == 200 and "Öffentliche Aufträge in der EU" in view.text
    assert 'href="/workbench/ted?case_id=' in view.text, "TED is in the menu"
    monkeypatch.setattr(ted, "_post", lambda body: {"notices": [NOTICE], "totalNoticeCount": 3})
    unconfirmed = client.post("/workbench/ted", data={"case_id": case_id, "csrf": csrf, "term": "Muster", "role": "gewinner"})
    assert unconfirmed.status_code == 422
    found = client.post("/workbench/ted", data={"case_id": case_id, "csrf": csrf, "term": "Muster", "role": "gewinner", "opsec": "yes"})
    assert found.status_code == 200 and "3 Bekanntmachungen" in found.text and "Universitätsklinikum Beispielstadt" in found.text
    assert "Als Web-Beleg sichern" in found.text and "url=https%3A%2F%2Fted.europa.eu%2Fde%2Fnotice" in found.text
    again = client.get("/workbench/ted", params={"case_id": case_id, "search_id": ted.searches(app.state.context, case_id)[0]["search_id"]})
    assert "Lieferung von Laborgeräten" in again.text and "Frühere Suchen" in again.text
    bad_csrf = client.post("/workbench/ted", data={"case_id": case_id, "csrf": "0" * 64, "term": "Muster", "opsec": "yes"})
    assert bad_csrf.status_code == 403


@ws
def test_provenance_check_is_back_in_the_menu(workspace):
    app, client, user, case_id, *_ = workspace
    csrf_session(workspace)
    page = client.get("/workbench/report", params={"case_id": case_id}).text
    assert 'href="/provenance466?case_id=' in page and "Belegprüfung" in page
    assert client.get("/provenance466", params={"case_id": case_id}).status_code == 200
