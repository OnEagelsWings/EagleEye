"""Build 492, plan step 3.4: protection classes for findings/documents and recipient levels."""
import hashlib

import pytest

from eagleeye.application.intel492 import captures, markings
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.findings478 import notes_for_case
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build475_ai_checkpoint import member
from test_build492_intel import ARTICLE, csrf_session, fake_network, ws  # noqa: F401
from test_build492_hardening import HTML, post

ADMIN = ("qa471", "Build471!Password_88")
SECOND = ("member475", "Independent!Secret_881")


def login(workspace, who):
    return csrf_session(workspace, *who)


def add_finding(workspace, title, protection="intern", document_id=None, anchor_index=0):
    app, client, user, case_id, doc_id, *_ = workspace
    document_id = document_id or doc_id
    anchor = app.state.context.document_intelligence_458.anchors(identity=user, document_id=document_id)["anchors"][anchor_index]
    data = {"case_id": case_id, "csrf": client.cookies.get(CSRF_COOKIE), "anchor_ref": document_id + "|" + anchor["anchor_id"],
            "kind": "observation", "title": title, "interpretation": "Eigene Beobachtung mit offener Restunsicherheit.",
            "protection": protection}
    response = client.post("/workbench/findings", data=data, follow_redirects=False)
    assert response.status_code == 303, response.text[:300]
    return next(r for r in notes_for_case(app, case_id) if r["title"] == title)


def review(workspace, finding, decision="reviewed"):
    app, client, user, case_id, *_ = workspace
    data = {"case_id": case_id, "finding_id": finding["finding_id"], "expected_hash": finding["record_hash"],
            "csrf": client.cookies.get(CSRF_COOKIE), "decision": decision,
            "reason": "Original verglichen, Restunsicherheit bleibt benannt."}
    assert client.post("/workbench/report/review", data=data, follow_redirects=False).status_code == 303


def fresh(app, case_id, title):
    return next(r for r in notes_for_case(app, case_id) if r["title"] == title)


def report(workspace, level):
    app, client, user, case_id, *_ = workspace
    return client.get("/workbench/report.md", params={"case_id": case_id, "level": level})


@ws
def test_finding_form_requires_a_class_and_defaults_to_internal(workspace):
    app, client, user, case_id, doc_id, *_ = workspace
    login(workspace, ADMIN)
    page = client.get("/workbench/findings", params={"case_id": case_id}).text
    assert 'name="protection"' in page and '<option value="intern" selected>' in page
    finding = add_finding(workspace, "Gründungsjahr laut Quelle")
    marks = markings.current(app.state.context, case_id)
    assert markings.marking_of(marks, "finding", finding["finding_id"]) == ("intern", True)
    bad = {"case_id": case_id, "csrf": client.cookies.get(CSRF_COOKIE), "kind": "observation", "title": "Ungültige Klasse",
           "interpretation": "Darf nicht gespeichert werden, Klasse unbekannt.", "protection": "geheim",
           "anchor_ref": finding["document_id"] + "|" + finding["anchor_id"]}
    assert client.post("/workbench/findings", data=bad).status_code == 422
    assert all(r["title"] != "Ungültige Klasse" for r in notes_for_case(app, case_id))


@ws
def test_recipient_levels_select_and_report_omissions(workspace):
    app, client, admin, case_id, doc_id, *_ = workspace
    login(workspace, ADMIN)
    a = add_finding(workspace, "A offen zweitgeprüft", "offen")
    b = add_finding(workspace, "B offen eigengeprüft", "offen", anchor_index=1)
    c = add_finding(workspace, "C intern geprüft", "intern")
    d = add_finding(workspace, "D schutzwürdig zweitgeprüft", "besonders_schutzwuerdig", anchor_index=1)
    e = add_finding(workspace, "E offen ungeprüft", "offen")
    review(workspace, fresh(app, case_id, b["title"]))  # self review
    review(workspace, fresh(app, case_id, c["title"]))
    member(workspace, "reviewer")
    login(workspace, SECOND)
    review(workspace, fresh(app, case_id, a["title"]))
    review(workspace, fresh(app, case_id, d["title"]))
    login(workspace, ADMIN)

    intern = report(workspace, "intern").text
    assert all(x["title"] in intern for x in (a, b, c, d, e)) and "Empfängerstufe: intern" in intern
    assert "Enthaltene Arbeitsbefunde: 5 von 5." in intern

    client_md = report(workspace, "mandant")
    assert client_md.headers["content-disposition"].endswith('_Arbeitsbericht_mandant.md"')
    text = client_md.text
    assert a["title"] in text and b["title"] in text
    assert c["title"] not in text and d["title"] not in text and e["title"] not in text
    assert "Enthaltene Arbeitsbefunde: 2 von 5." in text
    assert "- 1 × Schutzklasse intern" in text and "- 1 × Schutzklasse besonders schutzwürdig (Art. 9/10 DSGVO)" in text
    assert "- 1 × nicht geprüft oder verworfen" in text
    assert "Schutzklasse (wirksam):" in text and "    offen" in text

    authority = report(workspace, "behoerde").text
    assert a["title"] in authority and d["title"] in authority
    assert b["title"] not in authority and c["title"] not in authority and e["title"] not in authority
    assert "- 1 × nicht von einem zweiten Konto geprüft" in authority
    assert "besonders schutzwürdig (Art. 9/10 DSGVO)" in authority

    page = client.get("/workbench/report", params={"case_id": case_id}).text
    assert "Bericht für Mandant herunterladen</a> – 2 von 5 Befunden" in page
    assert "Bericht für Behörde/Gericht herunterladen</a> – 2 von 5 Befunden" in page
    assert report(workspace, "presse").status_code == 422


@ws
def test_document_class_is_inherited_and_changes_need_a_reason(workspace):
    app, client, admin, case_id, doc_id, *_ = workspace
    login(workspace, ADMIN)
    finding = add_finding(workspace, "Offener Befund", "offen")
    review(workspace, fresh(app, case_id, finding["title"]))
    assert finding["title"] in report(workspace, "mandant").text

    def change(finding_class, document_class, reason="Gesundheitsangaben im Quelldokument."):
        return client.post("/workbench/intel/markings", data={
            "case_id": case_id, "csrf": client.cookies.get(CSRF_COOKIE), "finding_id": finding["finding_id"],
            "finding_class": finding_class, "document_class": document_class, "reason": reason}, follow_redirects=False)

    assert change("offen", "besonders_schutzwuerdig", reason="").status_code == 422
    assert change("offen", "streng geheim").status_code == 422
    assert change("offen", "besonders_schutzwuerdig").status_code == 303
    text = report(workspace, "mandant").text
    assert finding["title"] not in text and "Schutzklasse besonders schutzwürdig" in text
    card = client.get("/workbench/report", params={"case_id": case_id}).text
    assert "Quelldokument <strong>besonders schutzwürdig (Art. 9/10 DSGVO)</strong>" in card
    assert "wirksam <strong>besonders schutzwürdig" in card
    rows = app.state.context.db.all("SELECT object_type, marking, reason FROM marking_492 WHERE case_id=? ORDER BY rowid", (case_id,))
    assert [(r["object_type"], r["marking"]) for r in rows] == [("finding", "offen"), ("document", "besonders_schutzwuerdig")]
    # foreign findings and read-only members cannot change classes
    other = app.state.context.db.one("SELECT finding_id FROM operational_findings_478 WHERE case_id=?", (case_id,))["finding_id"]
    data = {"case_id": workspace[5], "csrf": client.cookies.get(CSRF_COOKIE), "finding_id": other,
            "finding_class": "offen", "document_class": "offen", "reason": "Versuch aus fremdem Fall."}
    assert client.post("/workbench/intel/markings", data=data).status_code in {403, 404}
    member(workspace, "read_only")
    login(workspace, SECOND)
    assert "Schutzklasse ändern" not in client.get("/workbench/report", params={"case_id": case_id}).text
    data.update(case_id=case_id, csrf=client.cookies.get(CSRF_COOKIE))
    assert client.post("/workbench/intel/markings", data=data).status_code == 403


@ws
def test_damaged_marking_counts_as_internal(workspace):
    app, client, admin, case_id, *_ = workspace
    ctx = app.state.context
    login(workspace, ADMIN)
    finding = add_finding(workspace, "Offener Befund", "offen")
    review(workspace, fresh(app, case_id, finding["title"]))
    ctx.db.execute("UPDATE marking_492 SET reason='geändert ohne Hash' WHERE object_id=?", (finding["finding_id"],))
    assert finding["title"] not in report(workspace, "mandant").text
    assert "Markierung ist beschädigt" in client.get("/workbench/report", params={"case_id": case_id}).text
    assert finding["title"] in report(workspace, "intern").text


@ws
def test_authority_level_requires_unchanged_source_and_warc(workspace, fake_network):
    app, client, admin, case_id, doc_id, *_ = workspace
    ctx = app.state.context
    fake_network.responses["https://news.example/x"] = (200, HTML, ARTICLE)
    login(workspace, ADMIN)
    assert post(workspace, "https://news.example/x").status_code == 303
    capture = captures.captures_for_case(ctx, case_id)[0]
    login(workspace, ADMIN)
    web_finding = add_finding(workspace, "Web-Befund", "offen", document_id=capture["document_id"], anchor_index=1)
    local_finding = add_finding(workspace, "Lokaler Befund", "offen")
    member(workspace, "reviewer")
    login(workspace, SECOND)
    review(workspace, fresh(app, case_id, web_finding["title"]))
    review(workspace, fresh(app, case_id, local_finding["title"]))
    login(workspace, ADMIN)
    before = report(workspace, "behoerde").text
    assert web_finding["title"] in before and local_finding["title"] in before
    path = captures.warc_root(ctx) / capture["warc_relpath"]
    path.write_bytes(path.read_bytes()[:-4] + b"evil")
    service = ctx.document_intelligence_458
    (service.root / service._document(doc_id)["stored_relpath"]).write_bytes(b"changed original")
    after = report(workspace, "behoerde").text
    assert web_finding["title"] not in after and local_finding["title"] not in after
    assert "- 1 × Quelle verändert oder nicht mehr verfügbar" in after and "- 1 × WARC-Datei des Web-Belegs verändert" in after
    assert "Enthaltene Arbeitsbefunde: 0 von 2." in after
