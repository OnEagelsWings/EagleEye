from __future__ import annotations
import hashlib
from fastapi.testclient import TestClient
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app463 import create_workspace_app463
from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye_pro.version import BUILD

def test_463_real_case_document_must_exist_and_is_linked(tmp_path):
    assert BUILD == "463.0"
    app=create_workspace_app463(base_dir=tmp_path)
    ctx=app.state.context
    try:
        with TestClient(app) as client:
            assert client.get("/source-links463",params={"case_id":"forged"},follow_redirects=False).status_code==303
            ctx.team_identity_359.create_initial_admin(username="qa463",display_name="QA",password="Build463!Password_88")
            fp=hashlib.sha256(b"testclient||testclient").hexdigest()
            session=ctx.team_identity_359.authenticate(username="qa463",password="Build463!Password_88",client_fingerprint=fp)
            identity=ctx.team_identity_359.validate_session(session.token,client_fingerprint=fp,touch=False)
            case=ctx.team_governance_359.create_case(identity=identity,title="Evidence case",client="QA",
                purpose="Source-linked relationships",legal_basis="public_data")
            case_id=case["case_id"]
            document=ctx.document_intelligence_458.import_bytes(identity=identity,case_id=case_id,
                filename="report.txt",raw=b"This document supports a hypothesis only.",title="Report A",
                source_url="https://example.org/report")
            with EntityRegistry461(tmp_path/"entity_registry_462.sqlite3") as store:
                a=store.create_entity(case_id=case_id,kind="person",label="Person A")
                b=store.create_entity(case_id=case_id,kind="organization",label="Org B")
            client.cookies.set(COOKIE,session.token)
            page=client.get("/source-links463",params={"case_id":case_id})
            assert page.status_code==200 and "Report A" in page.text
            bad=client.post("/source-links463/create",data={"case_id":case_id,"source_id":a["id"],
                "target_id":b["id"],"predicate":"associated","document_id":"fake"},follow_redirects=False)
            assert bad.status_code==422
            good=client.post("/source-links463/create",data={"case_id":case_id,"source_id":a["id"],
                "target_id":b["id"],"predicate":"mentioned_in","document_id":document["document_id"]},
                follow_redirects=False)
            assert good.status_code==303
            with EntityRegistry461(tmp_path/"entity_registry_462.sqlite3") as store:
                graph=store.graph(case_id)
            assert len(graph["relations"])==1
            assert graph["relations"][0]["sources"][0]["source_ref"]=="doc458:"+document["document_id"]
            assert graph["relations"][0]["source_verified"] is False
            assert client.get("/source-links463",params={"case_id":"foreign"},follow_redirects=False).status_code==303
    finally:
        ctx.close()
