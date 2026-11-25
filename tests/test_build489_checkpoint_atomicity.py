"""Build 489: checkpoint never renders another case's review/source records.

The checkpoint is a read-only cross-register view. Its underlying services
must always receive the authenticated, selected case identifier.
"""
import pytest
from unittest.mock import patch
from eagleeye.interfaces.web.app489 import create_workspace_app489
from eagleeye.interfaces.web import checkpoint489
from test_build471_local_ai import workspace

pytestmark = pytest.mark.parametrize(
    "workspace", [create_workspace_app489], indirect=True
)


def test_checkpoint_passes_selected_case_to_both_integrity_checked_registers(workspace):
    app, client, user, case_id, *_ = workspace
    original_reviews = checkpoint489.reviews_for_case
    original_sources = checkpoint489.source_links
    calls = []

    def guarded_reviews(ctx, identity, selected_case):
        calls.append(("reviews", selected_case, identity["username"]))
        return original_reviews(ctx, identity, selected_case)

    def guarded_sources(ctx, identity, selected_case):
        calls.append(("sources", selected_case, identity["username"]))
        return original_sources(ctx, identity, selected_case)

    with patch.object(checkpoint489, "reviews_for_case", side_effect=guarded_reviews), \
         patch.object(checkpoint489, "source_links", side_effect=guarded_sources):
        response = client.get("/workbench/checkpoint489", params={"case_id": case_id})

    assert response.status_code == 200
    assert calls == [
        ("reviews", case_id, user["username"]),
        ("sources", case_id, user["username"]),
    ]


def test_checkpoint_does_not_render_partial_results_if_source_integrity_fails(workspace):
    app, client, user, case_id, *_ = workspace
    from fastapi import HTTPException

    with patch.object(checkpoint489, "reviews_for_case", return_value=[{
        "left_entity_id": "should-not-appear", "right_entity_id": "other",
        "decision": "reject", "rationale": "sensitive-review",
        "reviewed_by": "tester", "reviewed_at": "2026-11-04"
    }]), patch.object(
        checkpoint489, "source_links",
        side_effect=HTTPException(status_code=409, detail="source integrity mismatch")
    ):
        response = client.get("/workbench/checkpoint489", params={"case_id": case_id})

    assert response.status_code == 409
    assert "sensitive-review" not in response.text
    assert "should-not-appear" not in response.text
