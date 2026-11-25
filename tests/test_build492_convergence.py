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


# ---------------------------------------- S2 source families -> claim independence
from eagleeye_pro.phase20.entity_lineage456 import LINEAGE_CONFIRM

AGENCY = ("Die Firma X hat am Montag die vollständige Übernahme der Y GmbH mit Sitz in Hamburg bekanntgegeben. "
          "Der Kaufpreis wurde nicht genannt. Nach Angaben aus Unternehmenskreisen soll die Transaktion bis Ende "
          "des Jahres abgeschlossen sein. Die Kartellbehörde muss noch zustimmen. Beide Unternehmen beschäftigen "
          "zusammen rund 2000 Mitarbeiter in Deutschland und Österreich.")
OWN = ("Im Handelsregister ist seit 2021 Max Beispiel als Geschäftsführer der Y GmbH eingetragen. Er war zuvor bei "
       "einer Beratungsfirma in München tätig und ist an zwei weiteren Gesellschaften beteiligt, deren "
       "Jahresabschlüsse seit 2023 fehlen. Eine Anfrage blieb unbeantwortet.")


def _evidence_case(workspace):
    """Three syndicated copies + one independent text, all accepted as evidence and linked to one claim."""
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    service = ctx.document_intelligence_458
    texts = {"agentur": AGENCY, "zeitung1": AGENCY + " Die Redaktion hat bei X nachgefragt.",
             "zeitung2": "Hamburg (dpa) " + AGENCY.replace("Montag", "Dienstag"), "eigen": OWN}
    docs, evidence = {}, {}
    for name, text in texts.items():
        docs[name] = service.import_bytes(identity=user, case_id=case_id, filename=name + ".txt", raw=text.encode(),
                                          title=name, source_url=f"https://{name}.example/a")["document_id"]
        _approve_extraction(workspace, docs[name])
        assert _promote(workspace, docs[name]).status_code == 303
    mapping = {r["document_id"]: r["evidence_id"] for r in ctx.db.all(
        "SELECT document_id, evidence_id FROM document_evidence_bridge_481 WHERE case_id=?", (case_id,))}
    for name, doc_id in docs.items():
        evidence[name] = mapping[doc_id]
        ctx.evidence_claims_dossier_447.review_evidence(identity=user, evidence_id=evidence[name], decision="accepted",
                                                        note="Original geprüft.", confirmation="REVIEW EVIDENCE 447")
    claim = ctx.evidence_claims_dossier_447.propose_claim(identity=user, case_id=case_id,
                                                          statement="Die Firma X übernimmt die Y GmbH.",
                                                          support_evidence_ids=list(evidence.values()))
    return docs, evidence, claim["claim_id"]


def _origins(ctx, user, claim_id):
    return ctx.entity_lineage_456.claim_source_lineage(identity=user, claim_id=claim_id)["summary"]["support"]


def _review_own_group(ctx, user, evidence_id, group):
    evidence = ctx.evidence_claims_dossier_447.evidence(evidence_id)
    ctx.entity_lineage_456.review_source_lineage(
        identity=user, evidence_id=evidence_id, source_family=group, independence_group=group, origin_key=group,
        source_role="primary", countable=True, rationale="Einzeln geprüfte Herkunft.", confirmation=LINEAGE_CONFIRM,
        expected_evidence_hash=evidence["record_hash"])


@ws
def test_confirmed_source_family_counts_once_in_the_claim(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    docs, evidence, claim_id = _evidence_case(workspace)
    # Separate reviews per website: the copies count as three independent origins.
    for name in ("agentur", "zeitung1", "zeitung2", "eigen"):
        _review_own_group(ctx, user, evidence[name], "origin:" + name)
    assert _origins(ctx, user, claim_id)["reviewed_independent_origins"] == 4
    page = client.get("/workbench/intel/lineage", params={"case_id": case_id}).text
    assert "verschiedenen Ursprüngen zugeordnet" in page and "Als gemeinsamen Ursprung bestätigen" in page
    family_docs = re.findall(r'name="document_id" value="([^"]+)"', page)
    assert sorted(family_docs) == sorted(docs[n] for n in ("agentur", "zeitung1", "zeitung2"))
    confirm = client.post("/workbench/intel/lineage/confirm", data={
        "case_id": case_id, "csrf": csrf_session(workspace), "level": "normal", "confirm": "yes",
        "rationale": "Gleicher Agenturtext, nur Ortsmarke und Wochentag geändert.", "document_id": family_docs},
        follow_redirects=False)
    assert confirm.status_code == 303 and "done=confirmed" in confirm.headers["location"]
    support = _origins(ctx, user, claim_id)
    assert support["mentions"] == 4 and support["reviewed_independent_origins"] == 2, "family + independent text"
    lineages = [ctx.entity_lineage_456.evidence_lineage(identity=user, evidence_id=evidence[n])
                for n in ("agentur", "zeitung1", "zeitung2")]
    groups = {x["independence_group"] for x in lineages}
    assert len(groups) == 1 and next(iter(groups)).startswith("family492:")
    # documents imported in the same second: the earliest is decided deterministically, exactly one is primary
    assert sorted(x["source_role"] for x in lineages) == ["mirror", "mirror", "primary"]
    assert all("Quellfamilie Build 492: 3 Dokumente" in x["review_rationale"] for x in lineages)
    own = ctx.entity_lineage_456.evidence_lineage(identity=user, evidence_id=evidence["eigen"])
    assert own["independence_group"] == "origin:eigen", "the independent text keeps its own review"
    after = client.get(confirm.headers["location"]).text
    assert "Gemeinsamer Ursprung bestätigt" in after and "✓ In Claims zählen diese Belege als <strong>ein</strong> Ursprung" in after
    assert "Als gemeinsamen Ursprung bestätigen" not in after


@ws
def test_family_confirmation_guards(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    docs, evidence, claim_id = _evidence_case(workspace)
    family = [docs[n] for n in ("agentur", "zeitung1", "zeitung2")]

    def confirm(document_ids, **extra):
        data = {"case_id": case_id, "csrf": csrf_session(workspace), "level": "normal", "confirm": "yes",
                "rationale": "Gleicher Agenturtext, geprüft.", "document_id": list(document_ids)}
        data.update(extra)
        data = {k: v for k, v in data.items() if v is not None}
        return client.post("/workbench/intel/lineage/confirm", data=data, follow_redirects=False)

    assert confirm(family[:2]).status_code == 422, "an incomplete family is refused"
    assert confirm(family + [docs["eigen"]]).status_code == 409, "a document outside the family is refused"
    assert confirm(family, rationale="kurz").status_code == 422
    assert confirm(family, confirm=None).status_code == 422
    assert confirm(family, csrf="forged").status_code == 403
    assert _origins(ctx, user, claim_id)["reviewed_independent_origins"] == 0, "nothing was written"
    # Investigators may see the family but the confirmation is a reviewer decision.
    member(workspace, "investigator")
    csrf_session(workspace, "member475", "Independent!Secret_881")
    page = client.get("/workbench/intel/lineage", params={"case_id": case_id}).text
    assert "Aufgabe einer Person mit Quellenprüfungsrecht" in page and "Als gemeinsamen Ursprung bestätigen" not in page
    data = {"case_id": case_id, "csrf": client.cookies.get("ee_auth_csrf"), "level": "normal", "confirm": "yes",
            "rationale": "Gleicher Agenturtext, geprüft.", "document_id": family}
    assert client.post("/workbench/intel/lineage/confirm", data=data).status_code == 403


@ws
def test_family_without_enough_evidence_points_to_the_bridge(workspace):
    app, client, user, case_id, *_ = workspace
    service = app.state.context.document_intelligence_458
    for name, text in {"a": AGENCY, "b": AGENCY + " Nachtrag der Redaktion."}.items():
        service.import_bytes(identity=user, case_id=case_id, filename=name + ".txt", raw=text.encode(), title=name)
    page = client.get("/workbench/intel/lineage", params={"case_id": case_id}).text
    assert "2 Dokumente mit weitgehend gleichem Text" in page and "noch keine Evidence" in page
    assert "/workbench/bridge481?" in page and "Als gemeinsamen Ursprung bestätigen" not in page
