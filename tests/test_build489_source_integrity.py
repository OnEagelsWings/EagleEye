"""Build 489: checkpoint must fail closed if source provenance is altered.

This is an integration regression for the *combined* review view, not merely
for the standalone source-association page.
"""
import pytest
from eagleeye.interfaces.web.app489 import create_workspace_app489
from test_build471_local_ai import workspace
from test_build487_sources import lead, form as source_form
from test_build481_evidence_bridge import document_approved

pytestmark = pytest.mark.parametrize(
    "workspace", [create_workspace_app489], indirect=True
)


def test_checkpoint_rejects_tampered_source_association(workspace):
    app, client, user, case_id, *_ = workspace
    lead_id = lead(workspace)
    document_approved(workspace)
    assert client.post(
        "/workbench/sources487",
        data=source_form(workspace, lead_id),
        follow_redirects=False,
    ).status_code == 303
    endpoint = "/workbench/checkpoint489"
    assert client.get(endpoint, params={"case_id": case_id}).status_code == 200
    app.state.context.db.execute(
        "UPDATE lead_original_links_487 SET rationale=? WHERE case_id=?",
        ("forged source provenance", case_id),
    )
    assert client.get(endpoint, params={"case_id": case_id}).status_code == 409


def test_checkpoint_rejects_modified_original_bytes(workspace):
    app, client, user, case_id, document_id, *_ = workspace
    lead_id = lead(workspace)
    document_approved(workspace)
    assert client.post(
        "/workbench/sources487",
        data=source_form(workspace, lead_id),
        follow_redirects=False,
    ).status_code == 303
    ctx = app.state.context
    document = ctx.document_intelligence_458._document(document_id)
    original_path = ctx.document_intelligence_458.root / document["stored_relpath"]
    original = original_path.read_bytes()
    try:
        original_path.write_bytes(b"modified original")
        assert client.get(
            "/workbench/checkpoint489", params={"case_id": case_id}
        ).status_code == 409
    finally:
        original_path.write_bytes(original)
