from __future__ import annotations

import hashlib
from fastapi.testclient import TestClient
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app466 import create_workspace_app466, resolve_provenance
from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye_pro.version import BUILD


def test_build466_case_provenance_and_missing_source_are_visible(tmp_path):
    assert BUILD == "466.0"
    app = create_workspace_app466(base_dir=tmp_path)
    ctx = app.state.context
    try:
        with TestClient(app) as client:
            assert client.get("/provenance466", params={"case_id":"no"}, follow_redirects=False).status_code == 303
            ctx.team_identity_359.create_initial_admin(
                username="admin466", display_name="QA", password="Build466!Password_88")
            fp = hashlib.sha256(b"testclient||testclient").hexdigest()
            issued = ctx.team_identity_359.authenticate(
                username="admin466", password="Build466!Password_88", client_fingerprint=fp)
            identity = ctx.team_identity_359.validate_session(
                issued.token, client_fingerprint=fp, touch=False)
            case = ctx.team_governance_359.create_case(
                identity=identity, title="Provenance <test>", client="QA",
                purpose="Verify case-specific document lineage", legal_basis="public_data")
            case_id = case["case_id"]
            doc = ctx.document_intelligence_458.import_bytes(
                identity=identity, case_id=case_id, filename="evidence.txt",
                raw=b"Known provenance fixture", title="Source 466",
                source_url="https://example.org/source")
            with EntityRegistry461(tmp_path/"entity_registry_462.sqlite3") as store:
                a = store.create_entity(case_id=case_id,kind="person",label="Alice")
                b = store.create_entity(case_id=case_id,kind="organization",label="Company")
                store.create_relation(case_id=case_id,source_id=a["id"],target_id=b["id"],
                    predicate="referenced_by",source_refs=["doc458:"+doc["document_id"],"manual:unknown"])
                graph=store.graph(case_id)
            packet=resolve_provenance(ctx.document_intelligence_458,identity,case_id,graph)
            references=packet[0]["sources"]
            assert references[0]["sha256"] == hashlib.sha256(b"Known provenance fixture").hexdigest()
            assert references[0]["uri"] == "https://example.org/source"
            assert references[1]["status"] == "unverified"
            client.cookies.set(COOKIE,issued.token)
            view=client.get("/provenance466",params={"case_id":case_id})
            assert view.status_code == 200
            assert references[0]["sha256"] in view.text
            assert "manual:unknown" in view.text
            assert client.get("/provenance466",params={"case_id":"foreign"},follow_redirects=False).status_code==303
            home=client.get("/",params={"case_id":case_id})
            assert "/provenance466?" in home.text
            health=client.get("/health").json()
            assert health["build"] == "466.0"
            assert not health["production_release_ready"]
    finally:
        ctx.close()
