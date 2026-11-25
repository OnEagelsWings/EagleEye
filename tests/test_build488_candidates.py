"""Focused Build 488 smoke tests: no cross-case or automatic identity assertions."""
import pytest
from eagleeye.application.build488.candidates import suggest_case_pairs


def entity(id, name, case="case-a", kind="person"):
    return {"case_id": case, "entity_id": id, "name": name, "entity_type": kind}


def test_exact_and_multilingual_candidates_are_review_only():
    pairs = suggest_case_pairs("case-a", [
        entity("1", "Müller"), entity("2", "Müller"),
        entity("3", "Алексей"), entity("4", "Aleksey"),
    ], threshold=0.7)
    assert any(p["left_entity_id"] == "1" and p["right_entity_id"] == "2" for p in pairs)
    assert all(not p["identity_confirmed"] and not p["automatically_merged"] and
               not p["evidence_created"] and p["review_status"] == "unreviewed" for p in pairs)


def test_cross_case_and_duplicate_rejected():
    with pytest.raises(ValueError, match="cross-case"):
        suggest_case_pairs("case-a", [entity("1", "Alice"), entity("2", "Alice", case="case-b")])
    with pytest.raises(ValueError, match="duplicate"):
        suggest_case_pairs("case-a", [entity("1", "Alice"), entity("1", "Alicia")])


def test_different_types_not_merged_and_order_stable():
    records = [entity("b", "Acme", kind="person"), entity("a", "Acme", kind="organization")]
    assert suggest_case_pairs("case-a", records) == []
    records = [entity("z", "Alice"), entity("a", "Alice"), entity("m", "Alice")]
    assert suggest_case_pairs("case-a", records) == suggest_case_pairs("case-a", records)


def test_bounded_and_invalid_inputs():
    with pytest.raises(ValueError):
        suggest_case_pairs("", [])
    with pytest.raises(ValueError):
        suggest_case_pairs("case-a", [], limit=0)
    with pytest.raises(ValueError, match="limit exceeded"):
        suggest_case_pairs("case-a", [entity(str(i), "A") for i in range(1001)])
