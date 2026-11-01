"""Build 482: real authenticated case UI for recovered Dork and image services."""
from io import BytesIO

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app482 import create_workspace_app482
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from test_build471_local_ai import workspace
from test_build478_findings import csrf_session

pytestmark = pytest.mark.parametrize(
    "workspace", [create_workspace_app482], indirect=True
)


def png_bytes():
    out = BytesIO()
    Image.new("RGB", (32, 24), (180, 220, 255)).save(out, "PNG")
    return out.getvalue()


def test_workflow_and_expert_restore_real_dork_image_graph_navigation(workspace):
    app, client, user, cid, *_ = workspace
    assert app.version == "482.0"
    assert client.get("/health").json()["build"] == "482.0"
    dashboard = client.get("/workbench", params={"case_id": cid})
    assert dashboard.status_code == 200
    assert "Dork-Recherche" in dashboard.text
    assert "Bildakte" in dashboard.text
    assert "/workbench/dorks482?case_id=" + cid in dashboard.text
    assert "/workbench/images482?case_id=" + cid in dashboard.text
    experts = client.get("/workbench/expert", params={"case_id": cid})
    assert experts.status_code == 200
    assert "Bildakte und Metadaten" in experts.text
    assert "Dork-Recherche" in experts.text
    assert "/graph464?case_id=" + cid in experts.text
    assert client.get("/graph464", params={"case_id": cid}).status_code == 200


def test_dork_uses_original_engine_without_backend_network_or_auto_evidence(workspace):
    app, client, user, cid, *_ = workspace
    ctx = app.state.context
    first = ctx.db.one("SELECT count(*) AS n FROM search_tasks")["n"]
    page = client.get("/workbench/dorks482", params={
        "case_id": cid, "topic": "Example Research Organization",
        "domain": "example.org", "engine": "DuckDuckGo"
    })
    assert page.status_code == 200
    assert "Dork-Recherche und öffentliche Suchlinks" in page.text
    assert "site%3Aexample.org" in page.text
    assert "https://duckduckgo.com/" in page.text
    assert "Im Suchdienst öffnen" in page.text
    assert "rel=\"noopener noreferrer\"" in page.text
    assert ctx.db.one("SELECT count(*) AS n FROM search_tasks")["n"] == first
    assert client.get("/workbench/dorks482", params={
        "case_id": cid, "topic": "captcha umgehen"
    }).status_code == 422
    assert client.get("/workbench/dorks482", params={
        "case_id": cid, "topic": "Example",
        "engine": "malicious"
    }).status_code == 422
    assert client.get("/workbench/dorks482", params={
        "case_id": cid, "topic": "Example", "domain": "127.0.0.1"
    }).status_code == 422


def test_image_upload_reuses_original_image_pipeline_and_case_scoped_preview(workspace):
    app, client, user, cid, docid, othercase, *_ = workspace
    ctx = app.state.context
    token = csrf_session(workspace)
    raw = png_bytes()
    response = client.post("/workbench/images482",
        data={"case_id": cid, "csrf": token},
        files={"image": ("public-diagram.png", raw, "image/png")},
        follow_redirects=False)
    assert response.status_code == 303, response.text[:500]
    assets = ctx.build354.image_assets(case_id=cid)
    assert len(assets) == 1
    asset = assets[0]
    assert asset["review_status"] in ("review_pending", "quarantined")
    assert asset["sha256"]
    assert asset["metadata"]["inspection"]["magic_media_type"] == "image/png"
    view = client.get("/workbench/images482", params={"case_id": cid})
    assert view.status_code == 200
    assert asset["media_id"] in view.text
    assert asset["sha256"] in view.text
    assert "Metadaten" in view.text
    assert "Bildakte" in view.text
    if asset["review_status"] == "review_pending":
        preview = client.get("/workbench/image482/" + asset["media_id"],
                             params={"case_id": cid})
        assert preview.status_code == 200
        assert preview.content == raw
        assert preview.headers["content-type"].startswith("image/png")
        assert preview.headers["cache-control"] == "no-store"
    foreign = client.get("/workbench/image482/" + asset["media_id"],
                         params={"case_id": othercase})
    assert foreign.status_code == 403


def test_image_csrf_and_mime_blocked_no_fallback_to_unsafe_upload(workspace):
    app, client, user, cid, *_ = workspace
    token = csrf_session(workspace)
    raw = png_bytes()
    for form, payload, expected in [
        ({"case_id": cid, "csrf": "invalid"}, raw, 403),
        ({"case_id": cid, "csrf": token}, b"not-a-real-image", 422),
    ]:
        response = client.post("/workbench/images482", data=form,
            files={"image": ("suspect.png", payload, "image/png")})
        assert response.status_code == expected, (response.status_code, response.text[:500])
    denied = client.post("/workbench/images482",
        data={"case_id": cid, "csrf": token},
        files={"image": ("vector.svg", b'<svg></svg>', "image/svg+xml")})
    assert denied.status_code == 422
    assert app.state.context.build354.image_assets(case_id=cid) == []


def test_anonymous_and_nonexistent_case_blocked(workspace):
    app, client, user, cid, *_ = workspace
    assert client.get("/workbench/dorks482", params={"case_id": "not_a_case"}).status_code == 403
    assert client.get("/workbench/images482", params={"case_id": "not_a_case"}).status_code == 403
    with TestClient(app) as stranger:
        assert stranger.get("/workbench/dorks482", params={"case_id": cid}).status_code == 401
        assert stranger.get("/workbench/images482", params={"case_id": cid}).status_code == 401
        assert stranger.get("/workbench/image482/media_random", params={"case_id": cid}).status_code == 401
