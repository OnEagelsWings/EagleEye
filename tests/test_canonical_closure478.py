"""Canonical Evidence→Claim→Dossier UI reuses existing security and immutable records."""
import pytest

from eagleeye.interfaces.web.app478 import create_workspace_app478
from eagleeye.interfaces.web.closure_workflow478 import case_closure_counts
from test_build471_local_ai import workspace
from test_build447_integrated import seed_evidence
from test_build475_ai_checkpoint import member
from fastapi.testclient import TestClient

pytestmark = pytest.mark.parametrize(
    "workspace", [create_workspace_app478], indirect=True
)


def test_uploaded_document_is_not_mislabeled_as_canonical_evidence(workspace):
    app,client,actor,cid,doc_id,*rest=workspace
    state=case_closure_counts(app.state.context,actor,cid)
    assert state["documents"] >= 1
    assert state["evidence"] == 0
    assert state["claims"] == state["dossiers"] == state["exports"] == 0
    shown=client.get("/workbench/closure",params={"case_id":cid})
    assert shown.status_code==200
    assert "Wichtige Integrationslücke" in shown.text
    assert "noch kein prüfbares" in shown.text
    assert "Evidence → Claims → Dossier" in shown.text
    assert "0/0" in shown.text
    assert "Vier-Augen" in shown.text
    assert "production_release_ready" not in shown.text
    assert "/?case_id="+cid+"&amp;view=claims" in shown.text
    assert shown.headers["cache-control"]=="no-store"
    assert "/workbench/closure?case_id="+cid in client.get("/workbench/expert",params={"case_id":cid}).text


def test_original_registered_acquisition_becomes_evidence_not_approved_fact(workspace):
    app,client,actor,cid,doc_id,*_=workspace
    ctx=app.state.context
    *_upstream,evidence=seed_evidence(ctx,actor,cid,"canonical-evidence-integration")
    state=case_closure_counts(ctx,actor,cid)
    assert state["documents"]>=1 and state["evidence"]==1
    assert state["reviewed_evidence"]==0
    assert state["accepted_claims"]==0
    assert state["approved_dossiers"]==0
    page=client.get("/workbench/closure",params={"case_id":cid})
    assert "0/1 akzeptiert" in page.text
    assert "Ein PDF/TXT im Dokumentenarchiv" not in page.text
    assert "keine wahrheitsbestätigung" in page.text.lower()


def test_foreign_and_missing_sessions_never_reveal_canonical_counts(workspace):
    app,client,actor,cid,doc_id,foreign,*_=workspace
    member(workspace,"read_only")
    assert client.get("/workbench/closure",params={"case_id":foreign}).status_code==403
    assert client.get("/workbench/closure",params={"case_id":"case_missing"}).status_code==403
    with TestClient(app) as visitor:
        r=visitor.get("/workbench/closure",params={"case_id":cid})
        assert r.status_code==401
        assert "Synthetic AI case" not in r.text


def test_tampered_canonical_chain_blocks_operational_progress_display(workspace):
    app,client,actor,cid,doc_id,*_=workspace
    ctx=app.state.context
    *_items, ev=seed_evidence(ctx,actor,cid,"tamper-alert")
    ctx.db.execute(
        "UPDATE evidence_item_447 SET content_sha256=? WHERE evidence_id=?",
        ("unverified-sha",ev["evidence_id"])
    )
    denied=client.get("/workbench/closure",params={"case_id":cid})
    assert denied.status_code==409
    assert "Evidence-/Claim-Integrität" in denied.text
