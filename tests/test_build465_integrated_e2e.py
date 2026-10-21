"""Build 465 end-to-end acceptance: case -> imported document -> entity relation -> graph -> review."""
from __future__ import annotations
import hashlib
from fastapi.testclient import TestClient
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app465 import create_workspace_app465
from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye_pro.version import BUILD

def test_465_end_to_end_case_evidence_graph_and_governed_review(tmp_path):
    app=create_workspace_app465(base_dir=tmp_path)
    ctx=app.state.context
    try:
        with TestClient(app) as client:
            assert client.get("/review465",params={"case_id":"unknown"},follow_redirects=False).status_code==303
            ctx.team_identity_359.create_initial_admin(username="qa465",display_name="QA",password="Build465!Password_88")
            fp=hashlib.sha256(b"testclient||testclient").hexdigest()
            session=ctx.team_identity_359.authenticate(username="qa465",password="Build465!Password_88",client_fingerprint=fp)
            ident=ctx.team_identity_359.validate_session(session.token,client_fingerprint=fp,touch=False)
            case=ctx.team_governance_359.create_case(identity=ident,title="End-to-end <case>",client="QA",
                purpose="Controlled synthetic source to review",legal_basis="public_data")
            case_id=case["case_id"]
            doc=ctx.document_intelligence_458.import_bytes(identity=ident,case_id=case_id,
                filename="evidence.txt",raw=b"Public hypothetical relationship mentioned in this synthetic report.",
                title="Public document 465",source_url="https://example.org/synthetic")
            with EntityRegistry461(tmp_path/"entity_registry_462.sqlite3") as store:
                a=store.create_entity(case_id=case_id,kind="person",label="Analyst A")
                b=store.create_entity(case_id=case_id,kind="company",label="Firm B")
            client.cookies.set(COOKIE,session.token)
            assert client.get("/entities462",params={"case_id":case_id}).status_code==200
            assert client.get("/source-links463",params={"case_id":case_id}).status_code==200
            result=client.post("/source-links463/create",data={
                "case_id":case_id,"source_id":a["id"],"target_id":b["id"],
                "predicate":"mentioned_with","document_id":doc["document_id"]},follow_redirects=False)
            assert result.status_code==303
            with EntityRegistry461(tmp_path/"entity_registry_462.sqlite3") as store:
                rel=store.graph(case_id)["relations"][0]
            graph=client.get("/graph464",params={"case_id":case_id,"focus":rel["id"]})
            assert graph.status_code==200
            assert "Public document 465" in graph.text
            assert "/documents458?" in graph.text
            report=client.get("/review465",params={"case_id":case_id})
            assert report.status_code==200
            assert "End-to-end &lt;case&gt;" in report.text
            assert "Public document 465" in report.text
            assert "mentioned_with" in report.text
            assert "ungeprüft" in report.text or "nicht automatisch bestätigt" in report.text
            assert "Dossier und Freigaben" in report.text
            assert "keine Freigabe" in report.text
            assert "/?case_id=" in report.text or "/?case_id" in report.text
            assert client.get("/review465",params={"case_id":"different"},follow_redirects=False).status_code==303
            health=client.get("/health").json()
            assert health["build"]=="465.0"
            assert health["production_release_ready"] is False
        with EntityRegistry461(tmp_path/"entity_registry_462.sqlite3") as store:
            graph=store.graph(case_id)
        assert len(graph["entities"])==2 and len(graph["relations"])==1
    finally:
        ctx.close()
