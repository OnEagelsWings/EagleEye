from __future__ import annotations
import hashlib
import re
from unittest.mock import patch
from fastapi.testclient import TestClient
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app470 import create_workspace_app470
from eagleeye.application.collectors469 import collect
from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye_pro.version import BUILD

def test_build470_case_from_public_capture_to_review_and_readiness(tmp_path):
    app=create_workspace_app470(base_dir=tmp_path)
    assert app.version=="470.0"
    ctx=app.state.context
    try:
        with TestClient(app) as client:
            assert client.get("/readiness470",params={"case_id":"fake"},follow_redirects=False).status_code==303
            ctx.team_identity_359.create_initial_admin(
                username="qa470",display_name="QA",password="Build470!Password_88")
            fp=hashlib.sha256(b"testclient||testclient").hexdigest()
            session=ctx.team_identity_359.authenticate(
                username="qa470",password="Build470!Password_88",client_fingerprint=fp)
            ident=ctx.team_identity_359.validate_session(
                session.token,client_fingerprint=fp,touch=False)
            case=ctx.team_governance_359.create_case(
                identity=ident,title="Source to graph checkpoint",client="QA",
                purpose="Synthetic end-to-end checkpoint",legal_basis="public_data")
            case_id=case["case_id"]
            client.cookies.set(COOKIE,session.token)
            collect_page=client.get("/collect469",params={"case_id":case_id})
            assert collect_page.status_code==200
            token=re.search(r'name="csrf_token" value="([a-f0-9]{64})"',collect_page.text)
            assert token
            with patch("eagleeye.interfaces.web.app469.collect",
                       side_effect=lambda provider,indicator: collect(
                           provider,indicator,fetcher=lambda url:{"Status":0,"Answer":[]})):
                posted=client.post("/collect469/import",data={
                    "case_id":case_id,"provider":"dns","indicator":"example.com",
                    "csrf_token":token.group(1)},follow_redirects=False)
            assert posted.status_code==303
            documents=ctx.document_intelligence_458.documents(identity=ident,case_id=case_id)
            assert len(documents)==1
            doc_id=documents[0]["document_id"]
            with EntityRegistry461(tmp_path/"entity_registry_462.sqlite3") as store:
                a=store.create_entity(case_id=case_id,kind="person",label="Research subject")
                b=store.create_entity(case_id=case_id,kind="organization",label="DNS record")
                rel=store.create_relation(case_id=case_id,source_id=a["id"],target_id=b["id"],
                    predicate="possible_reference",source_refs=["doc458:"+doc_id])
            graph=client.get("/graph464",params={"case_id":case_id,"focus":rel["id"]})
            assert graph.status_code==200 and "DNS" in graph.text
            report=client.get("/review465",params={"case_id":case_id})
            assert report.status_code==200 and "possible_reference" in report.text
            provenance=client.get("/provenance466",params={"case_id":case_id})
            assert provenance.status_code==200 and "SHA-256" in provenance.text
            readiness=client.get("/readiness470",params={"case_id":case_id})
            assert readiness.status_code==200
            assert "Source to graph checkpoint" in readiness.text
            assert "Reale Produkt-Suchqualität" in readiness.text
            assert "N/A" in readiness.text and "Produktivfreigabe" in readiness.text
            assert client.get("/readiness470",params={"case_id":"foreign"},follow_redirects=False).status_code==303
            home=client.get("/",params={"case_id":case_id})
            assert "/readiness470?" in home.text
            health=client.get("/health").json()
            assert health["build"]=="470.0" and not health["production_release_ready"]
        with EntityRegistry461(tmp_path/"entity_registry_462.sqlite3") as store:
            persisted=store.graph(case_id)
        assert len(persisted["relations"])==1 and len(persisted["entities"])==2
    finally:
        ctx.close()
