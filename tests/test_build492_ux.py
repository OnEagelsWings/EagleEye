"""Build 492, stage 4: readable error pages for browser navigation."""
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build492_intel import csrf_session, ws

BROWSER = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


@ws
def test_browser_gets_a_page_with_explanation_and_way_back(workspace):
    app, client, user, case_id, *_ = workspace
    csrf_session(workspace)
    response = client.get("/workbench/intel/web", params={"case_id": case_id, "lead": "lead483_unknown"},
                          headers={**BROWSER, "Referer": "http://testserver/workbench/leads483?case_id=" + case_id})
    assert response.status_code == 422 and response.headers["content-type"].startswith("text/html")
    html = response.text
    assert "<h1>Bitte Eingaben prüfen</h1>" in html and "Der Recherchefund gehört nicht zu diesem Fall." in html
    assert "← Zurück zur vorherigen Seite" in html and "Zum Arbeitsablauf" in html and "Fehlercode 422" in html
    assert 'role="alert"' in html and "default-src 'self'" in response.headers["content-security-policy"]
    foreign = client.get("/workbench/intel", params={"case_id": workspace[5] + "x"}, headers=BROWSER)
    assert foreign.status_code == 403 and "<h1>Kein Zugriff</h1>" in foreign.text


@ws
def test_api_fetch_and_plain_clients_keep_json(workspace):
    app, client, user, case_id, *_ = workspace
    csrf_session(workspace)
    plain = client.get("/workbench/intel/web", params={"case_id": case_id, "lead": "lead483_unknown"})
    assert plain.status_code == 422 and plain.json() == {"detail": "Der Recherchefund gehört nicht zu diesem Fall."}
    fetch = client.get("/workbench/intel/web", params={"case_id": case_id, "lead": "x"},
                       headers={**BROWSER, "Sec-Fetch-Mode": "cors"})
    assert fetch.headers["content-type"].startswith("application/json")
    api = client.get("/api/build458/documents/missing/anchors", headers=BROWSER)
    assert api.headers["content-type"].startswith("application/json")
    js = client.get("/workbench/intel/jobs.json", params={"case_id": "foreign"}, headers=BROWSER)
    assert js.status_code == 403 and js.headers["content-type"].startswith("application/json")


@ws
def test_error_page_escapes_and_handles_missing_parameters(workspace):
    app, client, user, case_id, *_ = workspace
    csrf_session(workspace)
    missing = client.get("/documents458", headers=BROWSER)  # required case_id missing
    assert missing.status_code == 422 and "unvollständig" in missing.text and "<h1>Bitte Eingaben prüfen</h1>" in missing.text
    hostile = client.get("/workbench/intel/web", params={"case_id": case_id, "lead": "x"},
                         headers={**BROWSER, "Referer": "javascript:alert(1)"})
    assert "javascript:" not in hostile.text
    other_site = client.get("/workbench/intel/web", params={"case_id": case_id, "lead": "x"},
                            headers={**BROWSER, "Referer": "https://evil.example/page"})
    assert "evil.example" not in other_site.text
    client.cookies.clear()
    logged_out = client.get("/workbench/intel", params={"case_id": case_id}, headers=BROWSER)
    assert logged_out.status_code == 401 and 'href="/security/login"' in logged_out.text


# ------------------------------------------------- document view (U1) with extraction review
import re

from test_build475_ai_checkpoint import member
from test_build492_convergence import RATIONALE
from test_build492_intel import _pdf_with_table_and_scan


def _doc(workspace, text="Erster Absatz über die Y GmbH in Hamburg.\n\nZweiter Absatz: Max Beispiel ist Geschäftsführer.\n\n"
                         "Dritter Absatz ohne Bezug.", title="Registertext"):
    app, client, user, case_id, *_ = workspace
    return app.state.context.document_intelligence_458.import_bytes(
        identity=user, case_id=case_id, filename="r.txt", raw=text.encode(), title=title,
        source_url="https://register.example/y")["document_id"]


def _review_form(client, html):
    return {name: value for name, value in re.findall(r'<input type="hidden" name="([a-z_]+)" value="([^"]*)"',
                                                       html.split('action="/workbench/document/review"')[1].split("</form>")[0])}


@ws
def test_legacy_document_path_redirects_and_library_lists_documents(workspace):
    app, client, user, case_id, doc_id, *_ = workspace
    csrf_session(workspace)
    jump = client.get("/documents458", params={"case_id": case_id, "document_id": doc_id, "anchor_id": "a1"}, follow_redirects=False)
    assert jump.status_code == 303 and jump.headers["location"] == f"/workbench/document?case_id={case_id}&document_id={doc_id}&anchor_id=a1"
    library = client.get("/documents458", params={"case_id": case_id})
    assert library.status_code == 200 and "<h1>Dokumente und Fundstellen</h1>" in library.text
    assert "Synthetic Source" in library.text and "Extraktion noch nicht geprüft" in library.text
    assert 'id="upload"' in library.text and "/assets/build458/documents.js" in library.text
    assert "Webseite als Beleg sichern" in library.text


@ws
def test_extraction_review_in_the_ui_unlocks_evidence(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    csrf_session(workspace)
    doc_id = _doc(workspace)
    page = client.get("/workbench/document", params={"case_id": case_id, "document_id": doc_id}).text
    assert "<h2>Extraktion prüfen</h2>" in page and "Als Evidence übernehmen" not in page
    assert "SHA-256 des Originals" in page and "(Angabe beim Import, unbestätigt)" in page
    fields = _review_form(client, page)
    assert fields["document_id"] == doc_id and fields["expected_hash"]
    bad = client.post("/workbench/document/review", data={**fields, "decision": "approve", "note": "kurz", "confirm": "yes"})
    assert bad.status_code == 422 and ctx.document_intelligence_458._document(doc_id)["state"] == "review_required"
    stale = client.post("/workbench/document/review", data={**fields, "expected_hash": "0" * 64, "decision": "approve",
                                                             "note": "Alle drei Absätze mit dem Original verglichen.", "confirm": "yes"})
    assert stale.status_code == 409
    ok = client.post("/workbench/document/review", data={**fields, "decision": "approve",
                                                          "note": "Alle drei Absätze mit dem Original verglichen.", "confirm": "yes"},
                     follow_redirects=False)
    assert ok.status_code == 303 and "done=reviewed" in ok.headers["location"]
    doc = ctx.document_intelligence_458._document(doc_id)
    assert doc["state"] == "extraction_approved" and doc["review_note"] == "Alle drei Absätze mit dem Original verglichen."
    after = client.get(ok.headers["location"]).text
    assert "Extraktionsprüfung gespeichert" in after and "Extraktion freigegeben" in after
    assert "<h2>Extraktion prüfen</h2>" not in after and "Als Evidence übernehmen" in after
    promoted = client.post("/workbench/bridge481", data={"csrf": csrf_session(workspace), "case_id": case_id,
                           "document_id": doc_id, "rationale": RATIONALE, "confirm": "yes"}, follow_redirects=False)
    assert promoted.status_code == 303, "the guided path from document to evidence works without the API"
    fields["csrf"] = client.cookies.get(CSRF_COOKIE)  # the bridge step above opened a new session
    again = client.post("/workbench/document/review", data={**fields, "decision": "reject",
                                                             "note": "Zweiter Versuch nach der Freigabe.", "confirm": "yes"})
    assert again.status_code in {409, 422}


@ws
def test_filter_search_highlight_and_anchor_jump(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    csrf_session(workspace)
    pdf = ctx.document_intelligence_458.import_bytes(identity=user, case_id=case_id, filename="b.pdf",
                                                     raw=_pdf_with_table_and_scan(), title="Jahresbericht")["document_id"]
    from eagleeye.application.intel492 import docstructure
    docstructure.enrich_document(ctx, identity=user, document_id=pdf)
    base = {"case_id": case_id, "document_id": pdf}
    full = client.get("/workbench/document", params=base).text
    assert "Tabellen (1)" in full and "Überschriften (1)" in full and "OCR" not in full.split("Fundstellen</h2>")[1].split("<form")[0]
    tables = client.get("/workbench/document", params={**base, "kind": "table"}).text
    assert "1 von 7 Fundstellen" in tables and "Max Beispiel | Geschäftsführer" in tables and "Jahresbericht 2025</p>" not in tables
    found = client.get("/workbench/document", params={**base, "q": "hamburg"}).text
    assert "<mark>Hamburg</mark>" in found and "passen zur Suche" in found
    none = client.get("/workbench/document", params={**base, "q": "nichtvorhanden"}).text
    assert "Keine Fundstelle passt zu Filter oder Suche." in none
    heading = next(a for a in ctx.document_intelligence_458.anchors(identity=user, document_id=pdf)["anchors"] if a["anchor_kind"] == "heading")
    jump = client.get("/workbench/document", params={**base, "kind": "table", "anchor_id": heading["anchor_id"]}).text
    assert 'id="anchor-' + heading["anchor_id"] + '"' in jump, "a jump target hidden by a filter is still shown"
    assert client.get("/workbench/document", params={**base, "anchor_id": "missing"}).status_code == 404
    hostile = client.get("/workbench/document", params={**base, "q": "<script>"}).text
    assert "<script>" not in hostile.split("<main>")[1].replace('<script src="', "")


@ws
def test_document_view_permissions_integrity_and_class(workspace):
    app, client, admin, case_id, doc_id, other_case, other_doc = workspace
    ctx = app.state.context
    csrf_session(workspace)
    assert client.get("/workbench/document", params={"case_id": case_id, "document_id": other_doc}).status_code == 403
    page = client.get("/workbench/document", params={"case_id": case_id, "document_id": doc_id}).text
    assert "Schutzklasse des Dokuments ändern" in page
    data = {"case_id": case_id, "csrf": client.cookies.get(CSRF_COOKIE), "document_id": doc_id,
            "document_class": "besonders_schutzwuerdig", "reason": "Gesundheitsangaben."}
    assert client.post("/workbench/document/class", data={**data, "reason": ""}).status_code == 422
    saved = client.post("/workbench/document/class", data=data, follow_redirects=False)
    assert saved.status_code == 303
    assert "besonders schutzwürdig (Art. 9/10 DSGVO)" in client.get(saved.headers["location"]).text
    member(workspace, "investigator")
    csrf_session(workspace, "member475", "Independent!Secret_881")
    seen = client.get("/workbench/document", params={"case_id": case_id, "document_id": doc_id}).text
    assert "wartet auf Prüfung durch eine Person mit Quellenprüfungsrecht" in seen and "<h2>Extraktion prüfen</h2>" not in seen
    review = {"case_id": case_id, "csrf": client.cookies.get(CSRF_COOKIE), "document_id": doc_id, "expected_hash": "x",
              "decision": "approve", "note": "Ohne Prüfrecht versucht.", "confirm": "yes"}
    assert client.post("/workbench/document/review", data=review).status_code == 403
    service = ctx.document_intelligence_458
    (service.root / service._document(doc_id)["stored_relpath"]).write_bytes(b"changed")
    assert client.get("/workbench/document", params={"case_id": case_id, "document_id": doc_id}).status_code == 409
