"""Build 492, plan stage 2: web captures inside the existing evidence, report and lead flows.

Network access is simulated; no live result is claimed.
"""
import json

import pytest

from eagleeye.application.intel492 import captures
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build492_intel import ARTICLE, FakeTransport, csrf_session, fake_network, ws  # noqa: F401
from test_build492_hardening import HTML, post

RATIONALE = "Öffentlich zugängliche Seite selbst gesichert; Herkunft über WARC und Hashes nachvollziehbar."


def _capture(workspace, fake_network, url="https://news.example/x"):
    app, client, user, case_id, *_ = workspace
    fake_network.responses[url] = (200, HTML, ARTICLE)
    assert post(workspace, url).status_code == 303
    return captures.captures_for_case(app.state.context, case_id)[0]


def _approve_extraction(workspace, document_id):
    app, client, user, *_ = workspace
    service = app.state.context.document_intelligence_458
    original = service._document(document_id)
    service.review_extraction(identity=user, document_id=document_id, expected_document_hash=original["record_hash"],
                              decision="approve", note="Haupttext mit der WARC-Wiedergabe verglichen.",
                              confirmation="REVIEW DOCUMENT EXTRACTION 458")


def _promote(workspace, document_id):
    app, client, user, case_id, *_ = workspace
    return client.post("/workbench/bridge481", data={"csrf": csrf_session(workspace), "case_id": case_id,
                       "document_id": document_id, "rationale": RATIONALE, "confirm": "yes"}, follow_redirects=False)


# ------------------------------------------------------------- S3 evidence chain
@ws
def test_web_capture_provenance_travels_into_evidence(workspace, fake_network):
    app, client, user, case_id, local_doc, *_ = workspace
    ctx = app.state.context
    row = _capture(workspace, fake_network)
    _approve_extraction(workspace, row["document_id"])
    assert _promote(workspace, row["document_id"]).status_code == 303
    evidence = next(e for e in ctx.evidence_claims_dossier_447.case_evidence(case_id)
                    if e["content_sha256"] == ctx.document_intelligence_458._document(row["document_id"])["document_sha256"])
    event = ctx.acquisition_events_422.get(evidence["event_id"])
    web = event["provenance"]["web_capture"]
    assert web["capture_id"] == row["capture_id"] and web["warc_sha256"] == row["warc_sha256"]
    assert web["response_sha256"] == row["body_sha256"] and web["server_ip"] == "93.184.216.34"
    assert web["integrity_verified"] is True and web["network_fetch_at_capture"] is True
    assert event["provenance"]["source_url_user_supplied_unverified"] is False
    assert event["provenance"]["network_fetch_performed"] is False, "the promotion step itself fetches nothing"
    assert event["usage"]["truth_determined"] is False
    # the same provenance is what the dossier snapshot carries for linked evidence
    assert evidence["provenance"]["web_capture"]["capture_id"] == row["capture_id"]
    # a locally imported document keeps the old provenance unchanged
    _approve_extraction(workspace, local_doc)
    assert _promote(workspace, local_doc).status_code == 303
    local = next(e for e in ctx.evidence_claims_dossier_447.case_evidence(case_id) if e["evidence_id"] != evidence["evidence_id"])
    local_event = ctx.acquisition_events_422.get(local["event_id"])
    assert "web_capture" not in local_event["provenance"]
    assert local_event["provenance"]["source_url_user_supplied_unverified"] is True
    assert ctx.evidence_claims_dossier_447.verify_integrity()["valid"]


@ws
def test_tampered_warc_blocks_promotion_to_evidence(workspace, fake_network):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    row = _capture(workspace, fake_network)
    _approve_extraction(workspace, row["document_id"])
    path = captures.warc_root(ctx) / row["warc_relpath"]
    path.write_bytes(path.read_bytes()[:-4] + b"evil")
    response = _promote(workspace, row["document_id"])
    assert response.status_code == 409 and "nicht mehr unverändert" in response.text
    assert ctx.evidence_claims_dossier_447.case_evidence(case_id) == []


# ------------------------------------------------------------------ S3 report
@ws
def test_working_report_shows_web_capture_provenance(workspace, fake_network):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    row = _capture(workspace, fake_network)
    anchor = next(a for a in ctx.document_intelligence_458.anchors(identity=user, document_id=row["document_id"])["anchors"]
                  if "Max Beispiel" in a["text_excerpt"])
    finding = client.post("/workbench/findings", data={
        "case_id": case_id, "csrf": csrf_session(workspace), "anchor_ref": row["document_id"] + "|" + anchor["anchor_id"],
        "kind": "observation", "title": "Geschäftsführer laut Bericht",
        "interpretation": "Der Artikel nennt Max Beispiel als Geschäftsführer; Registerauszug noch nicht geprüft."},
        follow_redirects=False)
    assert finding.status_code == 303
    view = client.get("/workbench/report", params={"case_id": case_id}).text
    assert "Web-Beleg, abgerufen" in view and "✓ WARC unverändert" in view and "/workbench/intel/warc?" in view
    md = client.get("/workbench/report.md", params={"case_id": case_id}).text
    for expected in ("Web-Beleg:", "Live-Abruf durch EagleEye", "SHA-256 der WARC-Datei:", row["warc_sha256"],
                     "SHA-256 der Originalantwort:", row["body_sha256"], "HTTP-Status / Server-IP:",
                     "unverändert (Datensatz, Datei und Wiedergabe geprüft)"):
        assert expected in md, expected
    path = captures.warc_root(ctx) / row["warc_relpath"]
    path.write_bytes(path.read_bytes()[:-4] + b"evil")
    assert "VERLETZT – Beleg nicht verwenden" in client.get("/workbench/report.md", params={"case_id": case_id}).text
    assert "✗ WARC verändert" in client.get("/workbench/report", params={"case_id": case_id}).text


# ------------------------------------------------------- S4 lead -> web evidence
import re

from eagleeye.interfaces.web.research483 import propose
from test_build475_ai_checkpoint import member


def _lead(workspace, url="https://news.example/x", case=None):
    app, client, user, case_id, *_ = workspace
    return propose(app.state.context, user, case or case_id, url, "Bericht über die Übernahme",
                   "Treffer aus der Dork-Recherche, im Browser geöffnet und als relevant eingeschätzt.")


@ws
def test_lead_offers_capture_prefills_url_and_shows_result(workspace, fake_network):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    fake_network.responses["https://news.example/x"] = (200, HTML, ARTICLE)
    lead = _lead(workspace)
    csrf_session(workspace)
    leads = client.get("/workbench/leads483", params={"case_id": case_id}).text
    link = re.search(r'href="(/workbench/intel/web\?[^"]+)">Als Web-Beleg sichern', leads)
    assert link, "each lead offers the capture"
    page = client.get(link.group(1).replace("&amp;", "&"))
    assert page.status_code == 200 and "Aus dem Recherchefund" in page.text
    assert 'value="https://news.example/x"' in page.text and 'name="lead_id" value="' + lead["lead_id"] in page.text
    assert fake_network.calls == [], "opening the prefilled form contacts nobody"
    done = post(workspace, "https://news.example/x", lead_id=lead["lead_id"])
    assert done.status_code == 303 and done.headers["location"].startswith("/workbench/leads483?")
    row = captures.captures_for_case(ctx, case_id)[0]
    assert ctx.db.one("SELECT lead_id FROM web_capture_lead_492 WHERE capture_id=?", (row["capture_id"],))["lead_id"] == lead["lead_id"]
    after = client.get(done.headers["location"]).text
    assert "✓ Als Web-Beleg gesichert am" in after and "(eben gesichert)" in after
    assert "Erneut als Web-Beleg sichern" in after and row["document_id"] in after
    assert "Ungeprüfter Suchhinweis – keine Evidence" in after, "the lead itself stays a lead"


@ws
def test_lead_binding_survives_a_confirmed_redirect(workspace, fake_network):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    fake_network.responses.update({
        "https://short.example/abc": (302, [("Location", "https://news.example/x")], b""),
        "https://news.example/x": (200, HTML, ARTICLE)})
    lead = _lead(workspace, url="https://short.example/abc")
    first = post(workspace, "https://short.example/abc", lead_id=lead["lead_id"])
    assert "Die Seite leitet weiter" in first.text
    assert re.findall(r'name="lead_id" value="([^"]+)"', first.text)[0] == lead["lead_id"]
    via = re.findall(r'name="via" value="([^"]+)"', first.text)
    assert post(workspace, "https://news.example/x", via=via, lead_id=lead["lead_id"]).status_code == 303
    row = captures.captures_for_case(ctx, case_id)[0]
    assert ctx.db.one("SELECT lead_id FROM web_capture_lead_492 WHERE capture_id=?", (row["capture_id"],))["lead_id"] == lead["lead_id"]
    assert "✓ Als Web-Beleg gesichert" in client.get("/workbench/leads483", params={"case_id": case_id}).text


@ws
def test_foreign_or_unknown_lead_is_refused_and_nothing_is_fetched(workspace, fake_network):
    app, client, user, case_id, doc_id, other_case, *_ = workspace
    ctx = app.state.context
    fake_network.responses["https://news.example/x"] = (200, HTML, ARTICLE)
    foreign = _lead(workspace, case=other_case)
    assert client.get("/workbench/intel/web", params={"case_id": case_id, "lead": foreign["lead_id"]}).status_code == 422
    assert post(workspace, "https://news.example/x", lead_id=foreign["lead_id"]).status_code == 422
    assert post(workspace, "https://news.example/x", lead_id="lead483_unknown").status_code == 422
    assert fake_network.calls == [] and captures.captures_for_case(ctx, case_id) == []


@ws
def test_capture_without_explicit_link_is_still_shown_at_the_matching_lead(workspace, fake_network):
    app, client, user, case_id, *_ = workspace
    fake_network.responses["https://news.example/x"] = (200, HTML, ARTICLE)
    _lead(workspace, url="https://NEWS.example/x")
    assert post(workspace, "https://news.example/x").status_code == 303
    assert "✓ Als Web-Beleg gesichert" in client.get("/workbench/leads483", params={"case_id": case_id}).text


@ws
def test_read_only_member_sees_capture_state_but_no_capture_link(workspace, fake_network):
    app, client, admin, case_id, *_ = workspace
    fake_network.responses["https://news.example/x"] = (200, HTML, ARTICLE)
    lead = _lead(workspace)
    assert post(workspace, "https://news.example/x", lead_id=lead["lead_id"]).status_code == 303
    member(workspace, "read_only")
    csrf_session(workspace, "member475", "Independent!Secret_881")
    page = client.get("/workbench/leads483", params={"case_id": case_id}).text
    assert "✓ Als Web-Beleg gesichert" in page and "Als Web-Beleg sichern →" not in page
