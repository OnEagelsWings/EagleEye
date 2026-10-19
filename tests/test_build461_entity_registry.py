from __future__ import annotations

import pytest

from eagleeye.application.entity_registry461 import EntityRegistry461


def test_case_scoped_graph_persists_and_preserves_provenance(tmp_path):
    path = tmp_path / "graph.db"
    with EntityRegistry461(path) as db:
        a = db.create_entity(case_id="case-one", kind="person", label="Alex")
        b = db.create_entity(case_id="case-one", kind="company", label="Example Ltd")
        foreign = db.create_entity(case_id="case-two", kind="company", label="Unrelated")
        assert set(x["kind"] for x in db.graph("case-one")["entities"]) == {"person", "company"}
        with pytest.raises(ValueError, match="same case"):
            db.create_relation(case_id="case-one", source_id=a["id"], target_id=foreign["id"],
                               predicate="works_at", source_refs=["doc:1"])
        relation = db.create_relation(case_id="case-one", source_id=a["id"], target_id=b["id"],
                                      predicate="works_at", source_refs=["doc:1","doc:2"],
                                      valid_from="2020-01-01", valid_until="2024-01-01")
        assert relation["state"] == "hypothesis"
        assert relation["source_verified"] is False
        with pytest.raises(ValueError, match="at least one source"):
            db.create_relation(case_id="case-one", source_id=a["id"], target_id=b["id"],
                               predicate="works_at", source_refs=[])
        with pytest.raises(ValueError, match="date interval"):
            db.create_relation(case_id="case-one", source_id=a["id"], target_id=b["id"],
                               predicate="works_at", source_refs=["doc:3"],
                               valid_from="2024-01-01", valid_until="2020-01-01")
    with EntityRegistry461(path) as reopened:
        graph = reopened.graph("case-one")
        assert len(graph["entities"]) == 2
        assert len(graph["relations"]) == 1
        assert [s["source_ref"] for s in graph["relations"][0]["sources"]] == ["doc:1","doc:2"]
        assert graph["relations"][0]["source_verified"] is False
        assert reopened.graph("case-two")["relations"] == []


def test_invalid_records_fail_closed(tmp_path):
    with EntityRegistry461(tmp_path / "graph.db") as db:
        with pytest.raises(ValueError):
            db.create_entity(case_id="x", kind="unknown", label="Bad")
        with pytest.raises(ValueError):
            db.create_entity(case_id="x", kind="person", label=" ")
        a = db.create_entity(case_id="x", kind="person", label="Person")
        with pytest.raises(ValueError, match="self relation"):
            db.create_relation(case_id="x", source_id=a["id"], target_id=a["id"],
                               predicate="linked", source_refs=["source:1"])
