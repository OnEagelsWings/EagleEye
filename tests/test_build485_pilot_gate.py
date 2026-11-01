"""Build 485 – genuine case-specific pilot UI and hard case isolation."""
import pytest
from fastapi.testclient import TestClient
from eagleeye.interfaces.web.app485 import create_workspace_app485
from eagleeye.interfaces.web.pilot485 import pilot_counts
from test_build471_local_ai import workspace
from test_build482_operator import png_bytes

pytestmark=pytest.mark.parametrize("workspace",[create_workspace_app485],indirect=True)

def test_pilot_displays_actual_case_instead_of_fake_customer_ready(workspace):
    app,client,actor,cid,document_id,other,*_=workspace
    ctx=app.state.context
    assert app.version=="485.0"
    assert client.get("/health").json()["build"]=="485.0"
    check=client.get("/workbench/pilot485",params={"case_id":cid})
    assert check.status_code==200
    assert "Freigabe: NEIN" in check.text
    assert "Quellenintegrität" in check.text
    assert "Interaktiver Netzwerkgraph" in check.text
    assert "Bildakte" in check.text
    assert "Quellen" in check.text
    assert "Dossier" in check.text
    status=pilot_counts(ctx,actor,cid)
    assert status["documents"]>=1
    assert status["images"]==0 and status["search_leads"]==0
    ctx.build354.ingest_image(case_id=cid,content=png_bytes(),
        declared_media_type="image/png",filename="public_graph.png")
    stats=pilot_counts(ctx,actor,cid)
    assert stats["images"]==1
    assert stats["integrity_ok"]
    assert client.get("/workbench/pilot485",params={"case_id":cid}).status_code==200
    assert client.get("/workbench/pilot485",params={"case_id":other}).status_code==200
    assert "1 Bildoriginale" not in client.get(
        "/workbench/pilot485",params={"case_id":other}).text
    assert client.get("/workbench/pilot485",params={"case_id":"wrong_case"}).status_code==403
    with TestClient(app) as anon:
        assert anon.get("/workbench/pilot485",params={"case_id":cid}).status_code==401

def test_pilot_is_read_only_and_does_not_issue_formal_dossier(workspace):
    app,client,actor,cid,*_=workspace
    ctx=app.state.context
    before=ctx.evidence_claims_dossier_447.case_dossiers(cid)
    exports=ctx.evidence_claims_dossier_447.exports(cid)
    for _ in range(3):
        assert client.get("/workbench/pilot485",params={"case_id":cid}).status_code==200
    assert before==ctx.evidence_claims_dossier_447.case_dossiers(cid)
    assert exports==ctx.evidence_claims_dossier_447.exports(cid)
    assert "Pilotprüfung" in client.get("/workbench",params={"case_id":cid}).text


def test_pilot_refuses_to_display_healthy_progress_after_chain_integrity_failure(workspace,monkeypatch):
    app,client,user,cid,*_=workspace
    engine=app.state.context.evidence_claims_dossier_447
    monkeypatch.setattr(engine,"verify_integrity",lambda:{"valid":False,"reason":"tampered"})
    result=client.get("/workbench/pilot485",params={"case_id":cid})
    assert result.status_code==409
    assert "Integrität" not in result.text or "fehlgeschlagen" in result.text
