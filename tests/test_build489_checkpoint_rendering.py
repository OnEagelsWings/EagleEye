"""Build 489: review checkpoint renders untrusted case metadata safely."""
import pytest
from eagleeye.interfaces.web.app489 import create_workspace_app489
from test_build471_local_ai import workspace

pytestmark = pytest.mark.parametrize(
    "workspace", [create_workspace_app489], indirect=True
)


def test_checkpoint_escapes_untrusted_case_title_and_disables_cache(workspace):
    app, client, user, case_id, *_ = workspace
    marker = '<img src=x onerror=alert(489)>'
    # The case title is read from the existing case registry; never trust it
    # when interpolating into the combined review/source HTML.
    app.state.context.db.execute(
        "UPDATE cases SET title=? WHERE id=?", (marker, case_id)
    )
    response = client.get("/workbench/checkpoint489", params={"case_id": case_id})
    assert response.status_code == 200
    assert marker not in response.text
    assert "&lt;img src=x onerror=alert(489)&gt;" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
