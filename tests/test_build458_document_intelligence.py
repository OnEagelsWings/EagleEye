from __future__ import annotations

import hashlib
import io
import secrets
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app458 import create_workspace_app458
from eagleeye.interfaces.web.app448 import COOKIE

ROOT=Path(__file__).resolve().parents[1]
PASSWORD="Build458!Admin_7711"
FP="build458-identity-fingerprint"


def case_and_identity(ctx):
    ctx.team_identity_359.create_initial_admin(
        username="admin458",display_name="Build 458 Admin",password=PASSWORD)
    issued=ctx.team_identity_359.authenticate(
        username="admin458",password=PASSWORD,client_fingerprint=FP)
    ident=ctx.team_identity_359.validate_session(issued.token,client_fingerprint=FP,touch=False)
    case=ctx.team_governance_359.create_case(
        identity=ident,title="Build 458 document analysis",
        client="Internal QA",purpose="Validate bounded document provenance and anchored citations.",
        legal_basis="public_data")
    return ident,case


def pdf_bytes(text="This is a source paragraph with exact words for a reliable citation."):
    doc=fitz.open()
    page=doc.new_page()
    page.insert_text((50,80),text)
    doc.new_page()  # deliberately textless second page
    raw=doc.tobytes()
    doc.close()
    return raw


def fixture_claim(ctx,case_id):
    evidence_id="ev458_"+secrets.token_hex(5)
    now="2026-10-17T09:30:00+00:00"
    row={
        "evidence_id":evidence_id,"case_id":case_id,
        "observation_id":"obs458_"+secrets.token_hex(5),
        "event_id":"event458_"+secrets.token_hex(5),
        "content_id":"content458_"+secrets.token_hex(5),
        "source_id":"src458_"+secrets.token_hex(5),
        "evidence_kind":"public_document","title":"Public document review",
        "canonical_url":"https://www.example.org/public/report.pdf",
        "observed_at":now,"content_sha256":"a"*64,
        "media_type":"application/pdf","duplicate_kind":"",
        "source_snapshot_json":"{}","provenance_json":"{}","usage_json":"{}",
        "descriptive_json":"{}","source_record_hash":"s"*64,
        "event_record_hash":"e"*64,"content_record_hash":"c"*64,
        "observation_record_hash":"o"*64,
        "review_state":"accepted","review_note":"Human-reviewed evidence for reference QA.",
        "reviewed_by":"admin458","reviewed_at":now,"created_at":now,"updated_at":now,
    }
    row["record_hash"]=ctx.evidence_claims_dossier_447._rh(row)
    ctx.document_intelligence_458.db.execute(
        "INSERT INTO evidence_item_447 VALUES("+",".join("?" for _ in row)+")",tuple(row.values()))
    claim_id="claim458_"+secrets.token_hex(5)
    claim={"claim_id":claim_id,"case_id":case_id,
           "statement":"A bounded public document statement for provenance regression.",
           "state":"candidate_review_required","uncertainty_note":"Independent review is still required.",
           "created_by":"admin458","created_at":now,"reviewed_by":"",
           "reviewed_at":"","review_note":"","updated_at":now}
    claim["record_hash"]=ctx.evidence_claims_dossier_447._rh(claim)
    ctx.document_intelligence_458.db.execute(
        "INSERT INTO claim_447 VALUES("+",".join("?" for _ in claim)+")",tuple(claim.values()))
    link_id="clink458_"+secrets.token_hex(5)
    link={"link_id":link_id,"claim_id":claim_id,"case_id":case_id,
          "evidence_id":evidence_id,"stance":"support","note":"",
          "evidence_hash_at_link":row["record_hash"],"created_by":"admin458","created_at":now}
    link["record_hash"]=ctx.evidence_claims_dossier_447._rh(link)
    ctx.document_intelligence_458.db.execute(
        "INSERT INTO claim_evidence_link_447 VALUES("+",".join("?" for _ in link)+")",
        tuple(link.values()))
    return claim_id,link_id,evidence_id,row["record_hash"]


def test_build458_pdf_anchors_and_ocr_flag(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        ident,case=case_and_identity(ctx)
        svc=ctx.document_intelligence_458
        output=svc.import_bytes(identity=ident,case_id=case["case_id"],
            filename="report.pdf",raw=pdf_bytes(),title="Report 2026",
            source_url="https://www.example.org/report.pdf")
        assert output["pages"]==2
        assert output["anchors"]>=1
        assert output["ocr_required_pages"]==[2]
        assert output["state"]=="review_required"
        assert output["automatic_evidence_promotion"] is False
        listed=svc.anchors(identity=ident,document_id=output["document_id"])
        assert listed["anchors"][0]["page_number"]==1
        assert listed["anchors"][0]["locator"].startswith(output["document_id"]+":p1:b1:")
        assert listed["anchors"][0]["extraction_method"]=="native_pdf_text"
        assert svc.verify_integrity()["valid"]
        doc=listed["document"]
        badhash="0"*64
        with pytest.raises(PermissionError):
            svc.review_extraction(
                identity=ident,document_id=doc["document_id"],expected_document_hash=badhash,
                decision="approve",note="Human reviewed and location anchored.",
                confirmation="REVIEW DOCUMENT EXTRACTION 458")
        approved=svc.review_extraction(
            identity=ident,document_id=doc["document_id"],expected_document_hash=doc["record_hash"],
            decision="approve",note="Exact paragraphs and page locations were manually checked.",
            confirmation="REVIEW DOCUMENT EXTRACTION 458")
        assert approved["state"]=="extraction_approved"
        assert svc.verify_integrity()["valid"]


def test_build458_claim_citation_hash_link_and_invalidations(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        ident,case=case_and_identity(ctx)
        svc=ctx.document_intelligence_458
        got=svc.import_bytes(identity=ident,case_id=case["case_id"],filename="notes.md",
                             raw=b"First public paragraph has a precise reference.\n\nSecond paragraph.",
                             title="Notes")
        packet=svc.anchors(identity=ident,document_id=got["document_id"])
        doc=packet["document"]
        svc.review_extraction(identity=ident,document_id=doc["document_id"],
                              expected_document_hash=doc["record_hash"],decision="approve",
                              note="Extracted UTF-8 paragraphs compared with source.",
                              confirmation="REVIEW DOCUMENT EXTRACTION 458")
        claim_id,link_id,evidence_id,evidence_hash=fixture_claim(ctx,case["case_id"])
        anchor=packet["anchors"][0]
        with pytest.raises(PermissionError):
            svc.cite_claim_anchor(identity=ident,claim_id=claim_id,link_id=link_id,
                anchor_id=anchor["anchor_id"],expected_evidence_hash=evidence_hash,
                expected_anchor_hash="0"*64,note="Analyst checked source paragraph.",
                confirmation="LINK DOCUMENT ANCHOR 458")
        row=svc.cite_claim_anchor(identity=ident,claim_id=claim_id,link_id=link_id,
            anchor_id=anchor["anchor_id"],expected_evidence_hash=evidence_hash,
            expected_anchor_hash=anchor["record_hash"],note="The cited text is on this source paragraph.",
            confirmation="LINK DOCUMENT ANCHOR 458")
        assert row["citation_id"].startswith("cite458_")
        report=svc.claim_citations(identity=ident,claim_id=claim_id)
        assert len(report["citations"])==1
        assert report["all_references_current"]
        assert "Seite 1" in report["citations"][0]["locator"]
        db=svc.db
        old=ctx.evidence_claims_dossier_447.evidence(evidence_id)
        current=dict(db.one("SELECT * FROM evidence_item_447 WHERE evidence_id=?",(evidence_id,)))
        current["review_state"]="rejected"
        current["record_hash"]=ctx.evidence_claims_dossier_447._rh(current)
        db.execute("UPDATE evidence_item_447 SET review_state=?,record_hash=? WHERE evidence_id=?",
                   (current["review_state"],current["record_hash"],evidence_id))
        stale=svc.claim_citations(identity=ident,claim_id=claim_id)
        assert stale["all_references_current"] is False
        assert stale["citations"][0]["current"] is False


def test_build458_file_bounds_and_corruption_detection(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        ident,case=case_and_identity(ctx)
        svc=ctx.document_intelligence_458
        with pytest.raises(ValueError):
            svc.import_bytes(identity=ident,case_id=case["case_id"],filename="invalid.pdf",raw=b"not a PDF")
        with pytest.raises(ValueError):
            svc.import_bytes(identity=ident,case_id=case["case_id"],filename="raw.bin",raw=b"hello")
        with pytest.raises(ValueError):
            svc.import_bytes(identity=ident,case_id=case["case_id"],filename="big.txt",raw=b"x"*(12*1024*1024+1))
        item=svc.import_bytes(identity=ident,case_id=case["case_id"],
                              filename="note.txt",raw=b"This document paragraph has reliable visible text.")
        doc=svc.anchors(identity=ident,document_id=item["document_id"])["document"]
        (svc.root/doc["stored_relpath"]).write_bytes(b"tampered")
        assert svc.verify_integrity()["valid"] is False


def test_build458_health_and_authenticated_upload(tmp_path):
    app=create_workspace_app458(base_dir=tmp_path)
    ctx=app.state.context
    try:
        ctx.team_identity_359.create_initial_admin(
            username="web458",display_name="Web 458",password="Build458!WebAdmin_8855")
        ua="build458-ci-web"
        lang="en"
        fp=hashlib.sha256(f"{ua}|{lang}|testclient".encode()).hexdigest()
        issued=ctx.team_identity_359.authenticate(
            username="web458",password="Build458!WebAdmin_8855",client_fingerprint=fp)
        ident=ctx.team_identity_359.validate_session(issued.token,client_fingerprint=fp,touch=False)
        case=ctx.team_governance_359.create_case(
            identity=ident,title="Build 458 API",client="Internal QA",
            purpose="Verify authenticated bounded upload flow.",legal_basis="public_data")
        with TestClient(app,headers={"user-agent":ua,"accept-language":lang}) as client:
            health=client.get("/health")
            assert health.status_code==200
            assert health.json()["build"]=="458.0"
            unauthorized=client.get(f"/api/build458/cases/{case['case_id']}/documents")
            assert unauthorized.status_code==401
            client.cookies.set(COOKIE,issued.token)
            posted=client.post(
                f"/api/build458/cases/{case['case_id']}/documents",
                files={"file":("source.txt",io.BytesIO(b"Visible paragraph with documented provenance."),"text/plain")})
            assert posted.status_code==200,posted.text
            assert posted.json()["anchors"]==1
            panel=client.get(f"/documents458?case_id={case['case_id']}")
            assert panel.status_code==200
            assert "source.txt" in panel.text
    finally:
        ctx.close()


def test_build458_current_installer_and_next_checkpoint():
    assert 'version = "458.0.0"' in (ROOT/"pyproject.toml").read_text()
    assert 'BUILD = "458.0"' in (ROOT/"eagleeye_pro/version.py").read_text()
    assert (ROOT/"INSTALL_EAGLEEYE_458.py").is_file()
    assert (ROOT/"EAGLEEYE_PRO_458_0.py").is_file()
