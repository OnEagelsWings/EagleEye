from __future__ import annotations
import hashlib
from fastapi.testclient import TestClient
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app464 import create_workspace_app464
from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye_pro.version import BUILD

def test_464_authorized_clickable_graph_and_real_source_drilldown(tmp_path):
    assert BUILD=="464.0"
    app=create_workspace_app464(base_dir=tmp_path)
    ctx=app.state.context
    try:
        with TestClient(app) as client:
            assert client.get("/graph464",params={"case_id":"forged"},follow_redirects=False).status_code==303
            ctx.team_identity_359.create_initial_admin(username="qa464",display_name="QA",password="Build464!Password_88")
            fp=hashlib.sha256(b"testclient||testclient").hexdigest()
            session=ctx.team_identity_359.authenticate(username="qa464",password="Build464!Password_88",client_fingerprint=fp)
            ident=ctx.team_identity_359.validate_session(session.token,client_fingerprint=fp,touch=False)
            case=ctx.team_governance_359.create_case(identity=ident,title="Case <Graph>",client="QA",
                purpose="Verify interactive graph",legal_basis="public_data")
            case_id=case["case_id"]
            doc=ctx.document_intelligence_458.import_bytes(identity=ident,case_id=case_id,
                filename="network.txt",raw=b"Two entities appear in this source.",title="Source document")
            with EntityRegistry461(tmp_path/"entity_registry_462.sqlite3") as store:
                a=store.create_entity(case_id=case_id,kind="person",label="Alice <script>")
                b=store.create_entity(case_id=case_id,kind="organization",label="Foundation B")
                r=store.create_relation(case_id=case_id,source_id=a["id"],target_id=b["id"],
                    predicate="mentioned_in",source_refs=["doc458:"+doc["document_id"]])
            client.cookies.set(COOKIE,session.token)
            home=client.get("/",params={"case_id":case_id})
            assert home.status_code==200 and "/graph464?" in home.text
            graph=client.get("/graph464",params={"case_id":case_id})
            assert graph.status_code==200
            assert '<svg' in graph.text
            assert "Alice &lt;script&gt;" in graph.text
            assert "Alice <script>" not in graph.text
            assert "mentioned_in" in graph.text
            picked=client.get("/graph464",params={"case_id":case_id,"focus":r["id"],"state":"hypothesis"})
            assert picked.status_code==200
            assert "Source document" in picked.text
            assert "/documents458?" in picked.text
            assert "nicht verifiziert" in graph.text or "ungeprüft" in picked.text
            assert client.get("/graph464",params={"case_id":"other"},follow_redirects=False).status_code==303
    finally:
        ctx.close()
