"""Each intermediate release must open a real, authenticated source-backed case, not a draft."""
import hashlib
import pytest
from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app476 import create_workspace_app476
from eagleeye.interfaces.web.app477 import create_workspace_app477
from eagleeye.interfaces.web.app478 import create_workspace_app478
from eagleeye.interfaces.web.app479 import create_workspace_app479
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app364 import CSRF_COOKIE

@pytest.mark.parametrize("build,factory", [
    (476,create_workspace_app476),
    (477,create_workspace_app477),
    (478,create_workspace_app478),
    (479,create_workspace_app479),
])
def test_each_release_is_operational(build,factory,tmp_path):
    app=factory(base_dir=tmp_path)
    ctx=app.state.context
    assert app.version==str(build)+".0"
    try:
        ctx.team_identity_359.create_initial_admin(
            username="qaops",display_name="Research QA",
            password="Separate!Research-Token-7284")
        fp=hashlib.sha256(b"testclient||testclient").hexdigest()
        issued=ctx.team_identity_359.authenticate(
            username="qaops",password="Separate!Research-Token-7284",client_fingerprint=fp)
        user=ctx.team_identity_359.validate_session(
            issued.token,client_fingerprint=fp,touch=False)
        with TestClient(app) as client:
            client.cookies.set(COOKIE,issued.token)
            client.cookies.set(CSRF_COOKIE,issued.csrf_token)
            # Every edition starts with an accessible first-run case form.
            initial=client.get("/",follow_redirects=False)
            assert initial.status_code==303 and initial.headers["location"]=="/new-case"
            assert client.get("/new-case").status_code==200
            row=ctx.team_governance_359.create_case(
                identity=user,title="Public research case",client="QA",
                purpose="Evaluate bounded legal source examination",legal_basis="public_data")
            cid=row["case_id"]
            doc=ctx.document_intelligence_458.import_bytes(
                identity=user,case_id=cid,filename="public.txt",
                raw=b"An original public document with a verifiable textual anchor.",
                title="Synthetic public source",source_url="https://example.org/source")
            home=client.get("/",params={"case_id":cid})
            assert home.status_code==200
            assert "Geführte Recherche" in home.text
            guided=client.get("/workbench",params={"case_id":cid})
            assert guided.status_code==200
            assert "Dein Ermittlungs- und Rechercheablauf" in guided.text
            assert client.get("/documents458",params={"case_id":cid}).status_code==200
            assert client.get("/workbench",params={"case_id":"nonexistent"}).status_code==403
            if build>=477:
                inventory=client.get("/workbench/sources",params={"case_id":cid})
                assert inventory.status_code==200 and "Synthetic public source" in inventory.text
            if build>=478:
                page=client.get("/workbench/findings",params={"case_id":cid})
                assert page.status_code==200 and doc["document_id"] in page.text
            if build>=479:
                page=client.get("/workbench/report",params={"case_id":cid})
                assert page.status_code==200
                dl=client.get("/workbench/report.md",params={"case_id":cid})
                assert dl.status_code==200 and "Arbeitsbericht" in dl.text
    finally:
        ctx.close()
