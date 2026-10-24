"""Build 480 real operator flow with synthetic public text; security is not a production certification."""
import hashlib
from fastapi.testclient import TestClient
from eagleeye.interfaces.web.app480 import create_workspace_app480
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.findings478 import notes_for_case


def test_operational_full_case_source_finding_report(tmp_path):
    app=create_workspace_app480(base_dir=tmp_path)
    ctx=app.state.context
    try:
        ctx.team_identity_359.create_initial_admin(
            username="qa480",display_name="Integration Tester",
            password="Unrelated!Secure-Alpha-2773")
        fp=hashlib.sha256(b"testclient||testclient").hexdigest()
        session=ctx.team_identity_359.authenticate(
            username="qa480",password="Unrelated!Secure-Alpha-2773",client_fingerprint=fp)
        user=ctx.team_identity_359.validate_session(
            session.token,client_fingerprint=fp,touch=False)
        case=ctx.team_governance_359.create_case(
            identity=user,title="Public documentary investigation",client="QA",
            purpose="Source-backed workflow pilot",legal_basis="public_data")
        cid=case["case_id"]
        document=ctx.document_intelligence_458.import_bytes(
            identity=user,case_id=cid,filename="source.txt",
            raw=b"Public source finding: the laboratory opened in 2001.\n\nThis is a simulated public test.",
            title="Synthetic public record",source_url="https://example.org/public")
        doc_id=document["document_id"]
        data=ctx.document_intelligence_458.anchors(identity=user,document_id=doc_id)
        anchor=data["anchors"][0]["anchor_id"]
        with TestClient(app) as client:
            client.cookies.set(COOKIE,session.token)
            client.cookies.set(CSRF_COOKIE,session.csrf_token)
            home=client.get("/")
            assert home.status_code==200
            assert "Geführte Recherche" in home.text
            assert client.get("/new-case").status_code==200
            assert "Neuen Ermittlungsfall" in client.get("/new-case").text
            assert client.get("/workbench",params={"case_id":cid}).status_code==200
            sources=client.get("/workbench/sources",params={"case_id":cid})
            assert sources.status_code==200 and "Synthetic public record" in sources.text
            page=client.get("/workbench/findings",params={"case_id":cid})
            assert page.status_code==200 and "Neue Beobachtung" in page.text
            forged=client.post("/workbench/findings",data={
                "case_id":cid,"anchor_ref":doc_id+"|"+anchor,"csrf":"invalid",
                "title":"Test hypothesis","interpretation":"This is a synthetic hypothesis for validation."},
                follow_redirects=False)
            assert forged.status_code==403
            created=client.post("/workbench/findings",data={
                "case_id":cid,"anchor_ref":doc_id+"|"+anchor,"csrf":session.csrf_token,
                "title":"Laboratory opening year","interpretation":"The document suggests a possible opening year, requiring corroboration."},
                follow_redirects=False)
            assert created.status_code==303
            notes=notes_for_case(app,cid)
            assert len(notes)==1 and notes[0]["review_state"]=="unreviewed"
            review=client.post("/workbench/report/review",data={
                "case_id":cid,"finding_id":notes[0]["finding_id"],
                "reason":"I compared the excerpt to the document; independent verification is still open.",
                "csrf":session.csrf_token},follow_redirects=False)
            assert review.status_code==303
            markdown=client.get("/workbench/report.md",params={"case_id":cid})
            assert markdown.status_code==200
            assert "Laboratory opening year" in markdown.text
            assert "Unrelated!Secure" not in markdown.text
            assert "reviewed_self" in markdown.text
            checkpoint=client.get("/workbench/checkpoint",params={"case_id":cid})
            assert checkpoint.status_code==200
            assert "KEINE" in checkpoint.text or "NEIN" in checkpoint.text
            assert client.get("/workbench/report.md",params={"case_id":"other-case"}).status_code==403
    finally:
        ctx.close()
