"""Search terms (often names of target persons) are posted, not put into the address bar."""
import pytest

from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.server import create_workspace_app
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build492_intel import csrf_session

ws = pytest.mark.parametrize("workspace", [create_workspace_app], indirect=True)


@ws
def test_person_workbench_posts_the_search_term(workspace):
    app, client, user, case_id, *_ = workspace
    csrf_session(workspace)
    page = client.get("/workbench/personosint495", params={"case_id": case_id}).text
    assert '<form method="post" action="/workbench/personosint495">' in page and 'name="csrf"' in page
    data = {"case_id": case_id, "kind": "person", "term": "Erika Mustermann", "csrf": client.cookies.get(CSRF_COOKIE)}
    result = client.post("/workbench/personosint495", data=data)
    assert result.status_code == 200 and "Erika%20Mustermann" in result.text
    assert "term=Erika" not in result.text, "no follow-up link carries the name"
    assert client.post("/workbench/personosint495", data={**data, "csrf": "0" * 64}).status_code == 403
    assert client.post("/workbench/personosint495", data={**data, "kind": "x"}).status_code == 422


@ws
def test_source_catalog_filter_posts_the_search_term(workspace):
    app, client, user, case_id, *_ = workspace
    csrf_session(workspace)
    page = client.get("/workbench/public-sources", params={"case_id": case_id}).text
    assert 'action="/workbench/public-sources/filter"' in page
    data = {"case_id": case_id, "kind": "person", "term": "Erika Mustermann", "csrf": client.cookies.get(CSRF_COOKIE)}
    result = client.post("/workbench/public-sources/filter", data=data)
    assert result.status_code == 200 and 'value="Erika Mustermann"' in result.text
    assert client.post("/workbench/public-sources/filter", data={**data, "csrf": ""}).status_code == 403
