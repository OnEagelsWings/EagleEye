"""Build 488 regression: untrusted entity labels must remain inert in the review UI.

The existing Build-462 entity registry stores user-supplied labels; a matching
candidate must never render one as executable HTML.
"""
from html import escape

import pytest

from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye.interfaces.web.app488 import create_workspace_app488
from test_build471_local_ai import workspace

pytestmark = pytest.mark.parametrize(
    "workspace", [create_workspace_app488], indirect=True
)


def test_untrusted_entity_labels_are_escaped_in_candidate_view(workspace, tmp_path):
    _app, client, _user, case_id, *_ = workspace
    hostile = '<img src=x onerror="alert(488)">'
    with EntityRegistry461(tmp_path / "entity_registry_462.sqlite3") as registry:
        registry.create_entity(case_id=case_id, kind="person", label=hostile)
        registry.create_entity(case_id=case_id, kind="person", label=hostile)

    response = client.get("/workbench/entities488", params={"case_id": case_id})
    assert response.status_code == 200
    assert hostile not in response.text
    assert escape(hostile) in response.text
    assert 'name="left_entity_id"' in response.text
    assert 'name="right_entity_id"' in response.text
