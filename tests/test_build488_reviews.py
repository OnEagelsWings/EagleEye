"""Build 488 review ledger smoke: reject unsupported decisions before writes."""
import pytest
from fastapi import HTTPException
from eagleeye.application.build488.reviews import record_review, DECISIONS


class NoDatabase:
    def __getattr__(self, name):
        raise AssertionError("No persistence or audit may occur for rejected input")


CANDIDATE = {"case_id": "case-a", "left_entity_id": "1",
             "right_entity_id": "2", "review_status": "unreviewed"}
USER = {"username": "analyst"}


@pytest.mark.parametrize("decision", ["merged", "identity_confirmed", "approve_evidence", "", None])
def test_no_automatic_merge_or_evidence_decisions(decision):
    with pytest.raises(HTTPException) as exc:
        record_review(NoDatabase(), USER, "case-a", CANDIDATE, decision, "x" * 30)
    assert exc.value.status_code == 422


def test_decision_vocabulary_is_review_only():
    assert DECISIONS == {"possible_match", "not_same", "needs_evidence"}


@pytest.mark.parametrize("candidate", [
    {**CANDIDATE, "case_id": "other-case"},
    {**CANDIDATE, "review_status": "approved"},
])
def test_cross_case_and_premature_status_rejected(candidate):
    with pytest.raises(HTTPException) as exc:
        record_review(NoDatabase(), USER, "case-a", candidate, "needs_evidence", "x" * 30)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("rationale", ["", "short", "x" * 1201])
def test_invalid_rationale_rejected(rationale):
    with pytest.raises(HTTPException) as exc:
        record_review(NoDatabase(), USER, "case-a", CANDIDATE, "not_same", rationale)
    assert exc.value.status_code == 422
