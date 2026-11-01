"""Build 484 – case-scoped visual comparison of original public image records."""
from io import BytesIO
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app484 import create_workspace_app484
from test_build471_local_ai import workspace
from test_build482_operator import png_bytes

pytestmark=pytest.mark.parametrize("workspace",[create_workspace_app484],indirect=True)

def test_image_comparison_and_graph_are_reachable_from_active_case(workspace):
    app,client,user,cid,docid,other,*_=workspace
    ctx=app.state.context
    assert app.version=="484.0"
    assert client.get("/health").json()["build"]=="484.0"
    page=client.get("/workbench",params={"case_id":cid})
    assert "Bildbeziehungen vergleichen" in page.text
    assert "/workbench/media484?case_id="+cid in page.text
    empty=client.get("/workbench/media484",params={"case_id":cid})
    assert empty.status_code==200 and "Noch keine Bildähnlichkeitskandidaten" in empty.text
    raw=png_bytes()
    first=ctx.build354.ingest_image(case_id=cid,content=raw,
        declared_media_type="image/png",filename="original.png")
    second=ctx.build354.ingest_image(case_id=cid,content=raw,
        declared_media_type="image/png",filename="duplicate.png")
    assert first["media_id"] != second["media_id"]
    pairs=ctx.build354.similarity_links(case_id=cid)
    assert pairs, "stored Build-354 similarity relationship absent"
    view=client.get("/workbench/media484",params={"case_id":cid})
    assert view.status_code==200
    assert first["media_id"] in view.text and second["media_id"] in view.text
    assert "Ungeprüfte Bildähnlichkeit" in view.text
    assert "Keine Aussage über identische" in view.text
    assert "/graph464?case_id="+cid in view.text
    assert client.get("/graph464",params={"case_id":cid}).status_code==200
    foreign=client.get("/workbench/media484",params={"case_id":other})
    assert foreign.status_code==200
    assert first["media_id"] not in foreign.text and second["media_id"] not in foreign.text
    with TestClient(app) as anonymous:
        assert anonymous.get("/workbench/media484",params={"case_id":cid}).status_code==401

def test_broken_image_relationship_fails_closed(workspace):
    app,client,user,cid,*_=workspace
    ctx=app.state.context
    raw=png_bytes()
    ctx.build354.ingest_image(case_id=cid,content=raw,
        declared_media_type="image/png",filename="a.png")
    ctx.build354.ingest_image(case_id=cid,content=raw,
        declared_media_type="image/png",filename="b.png")
    link=ctx.build354.similarity_links(case_id=cid)[0]
    ctx.db.execute("UPDATE phase15_object_links SET to_id=? WHERE link_id=?",
                   ("media_not_in_this_case",link["link_id"]))
    denied=client.get("/workbench/media484",params={"case_id":cid})
    assert denied.status_code==409
