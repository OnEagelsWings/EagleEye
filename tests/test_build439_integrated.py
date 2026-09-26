from pathlib import Path
import runpy
import pytest

from eagleeye_pro.core.app_context import AppContext

ROOT = Path(__file__).resolve().parents[1]


def ident(c):
    if c.team_identity_359.bootstrap_required():
        return c.team_identity_359.create_initial_admin(
            username="analyst",
            display_name="Analyst Fixture",
            password="SecureFixturePassword!2026",
        )
    return c.team_identity_359.public_user("analyst")


def case(c, title="AI Loop 439"):
    return c.build439.team_create_case(
        identity=ident(c),
        title=title,
        client="QA",
        purpose="authorized bounded AI investigation loop",
        legal_basis="public_data",
    )


def test_case_selftest_runs_plan_to_synthesis_without_network(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c)["case_id"]
        result = c.build439.run_ai_investigation_case_selftest(identity=i, case_id=cid)
        assert result["result"] == "PASS"
        assert all(result["checks"].values())
        step = result["step"]
        assert step["snapshot"]["network_execution"] is False
        assert step["snapshot"]["automatic_go"] is False
        assert step["snapshot"]["automatic_scope_expansion"] is False
        assert step["snapshot"]["truth_determined"] is False
        assert step["snapshot"]["synthesis_id"]


def test_explicit_go_required_and_public_collection_tasks_are_bounded(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "GO boundary 439")["case_id"]
        source = c.build421.register_source(
            identity=i,
            name="Build 439 public source",
            source_type="website",
            base_url="https://public439.example.org",
            capabilities=["public_pages"],
            coverage={"build439_test": True},
        )
        loop = c.build439.create_ai_investigation_loop_439(
            identity=i,
            case_id=cid,
            objective="Test bounded public source orchestration",
            subquestions=["What public evidence is available?"],
            allowed_source_ids=[source["source_id"]],
            max_cycles=2,
            max_collection_tasks_per_cycle=1,
        )
        assert loop["state"] == "awaiting_human_authorization"
        with pytest.raises(PermissionError):
            c.build439.advance_ai_investigation_loop_439(identity=i, loop_id=loop["loop_id"])
        with pytest.raises(PermissionError):
            c.build439.authorize_ai_investigation_loop_439(
                identity=i, loop_id=loop["loop_id"], confirmation="GO"
            )
        active = c.build439.authorize_ai_investigation_loop_439(
            identity=i,
            loop_id=loop["loop_id"],
            confirmation="AUTHORIZE INVESTIGATION LOOP",
        )
        assert active["state"] == "active"
        step = c.build439.advance_ai_investigation_loop_439(
            identity=i, loop_id=loop["loop_id"]
        )
        tasks = step["snapshot"]["collection_tasks"]
        assert len(tasks) == 1
        assert tasks[0]["source_id"] == source["source_id"]
        assert tasks[0]["network_execution"] is False
        task = c.crawler_core_425.get(tasks[0]["task_id"])
        assert task["state"] in {"planned", "deferred"}
        assert c.db.one(
            "SELECT COUNT(*) n FROM crawl_task_425 WHERE case_id=?", (cid,)
        )["n"] == 1


def test_tor_source_keeps_isolated_worker_boundary(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Tor boundary 439")["case_id"]
        onion = "b" * 56 + ".onion"
        source = c.build421.register_source(
            identity=i,
            name="Build 439 onion source",
            source_type="tor_onion",
            access_mode="tor_public",
            base_url="http://" + onion + "/",
            capabilities=["public_pages"],
            coverage={"build439_test": True},
        )
        loop = c.build439.create_ai_investigation_loop_439(
            identity=i,
            case_id=cid,
            objective="Verify specialized Tor routing",
            subquestions=["What evidence requires isolated Tor review?"],
            allowed_source_ids=[source["source_id"]],
            max_cycles=2,
            max_collection_tasks_per_cycle=1,
        )
        c.build439.authorize_ai_investigation_loop_439(
            identity=i,
            loop_id=loop["loop_id"],
            confirmation="AUTHORIZE INVESTIGATION LOOP",
        )
        step = c.build439.advance_ai_investigation_loop_439(
            identity=i, loop_id=loop["loop_id"]
        )
        assert step["snapshot"]["collection_tasks"] == []
        special = step["snapshot"]["specialized_source_actions"]
        assert len(special) == 1
        assert special[0]["action"] == "isolated_tor_worker_review_required"
        assert c.db.one(
            "SELECT COUNT(*) n FROM crawl_task_425 WHERE case_id=?", (cid,)
        )["n"] == 0


def test_hypotheses_remain_working_candidates_and_gaps_visible(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Hypothesis discipline 439")["case_id"]
        loop = c.build439.create_ai_investigation_loop_439(
            identity=i,
            case_id=cid,
            objective="Test hypothesis discipline",
            subquestions=["Could explanation A account for the observed public record?"],
            allowed_source_ids=[],
            max_cycles=2,
        )
        rows = c.db.all(
            "SELECT * FROM hypothesis_417 WHERE session_id=?", (loop["session_id"],)
        )
        assert len(rows) == 1
        assert rows[0]["statement"].startswith("Working hypothesis candidate for question:")
        matrix = c.evidence_hypothesis_matrix_418.matrix(
            session_id=loop["session_id"], identity=i
        )
        assert matrix["gaps"]
        assert matrix["truth_determined"] is False


def test_loop_integrity_tamper_fails_closed(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Tamper 439")["case_id"]
        loop = c.build439.create_ai_investigation_loop_439(
            identity=i,
            case_id=cid,
            objective="Integrity test",
            subquestions=["Is the loop record intact?"],
            allowed_source_ids=[],
        )
        c.db.execute(
            "UPDATE phase19_ai_loop_439 SET objective='tampered' WHERE loop_id=?",
            (loop["loop_id"],),
        )
        assert c.ai_investigation_loop_439.verify_integrity()["valid"] is False


def test_case_isolation(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        ca = case(c, "A439")["case_id"]
        cb = case(c, "B439")["case_id"]
        a = c.build439.create_ai_investigation_loop_439(
            identity=i,
            case_id=ca,
            objective="Case A",
            subquestions=["Question A"],
            allowed_source_ids=[],
        )
        b = c.build439.create_ai_investigation_loop_439(
            identity=i,
            case_id=cb,
            objective="Case B",
            subquestions=["Question B"],
            allowed_source_ids=[],
        )
        assert a["case_id"] == ca and b["case_id"] == cb
        assert a["loop_id"] != b["loop_id"]
        assert {x["case_id"] for x in c.build439.ai_investigation_loops_439(ca)} == {ca}
        assert {x["case_id"] for x in c.build439.ai_investigation_loops_439(cb)} == {cb}


def test_contract_launcher_and_checkpoint_position(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as c:
        status = c.build439.ai_investigation_status_439()
        assert status["version_coherent"]
        assert status["phase19_builds_completed"] == 19
        assert status["next_hard_checkpoint"] == "440.0"
        assert status["ai_investigation_loop"]
        assert status["plan_to_synthesis_orchestration"]
        assert status["phase19_source_selection"]
        assert status["bounded_collection_task_planning"]
        assert status["entity_resolution_integrated"]
        assert status["temporal_relationship_fusion_integrated"]
        assert status["hypothesis_counterevidence_gap_analysis"]
        assert status["new_research_waves_integrated"]
        assert status["investigation_synthesis_integrated"]
        assert status["explicit_human_go_required"]
        assert status["direct_network_authority"] is False
        assert status["external_retrieval_adapter_required"]
        assert status["automatic_go"] is False
        assert status["automatic_scope_expansion"] is False
        assert status["automatic_evidence_promotion"] is False
        assert status["truth_determined"] is False
        assert status["production_release_ready"] is False

    import eagleeye.interfaces.web.app439 as appmod

    calls = []
    monkeypatch.setattr(
        appmod,
        "create_workspace_app439",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    namespace = runpy.run_path(str(ROOT / "EAGLEEYE_PRO_439_0.py"), run_name="__mp_main__")
    assert calls == []
    assert namespace["app"] is None
    assert "app441 import create_workspace_app441" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text()
    assert (ROOT / "BUILD_439_CASE_TEST.md").exists()
    assert (ROOT / "README_BUILD_439_0.md").exists()
    readme = (ROOT / "README.md").read_text()
    assert "EAGLEEYE_PRO_441_0.py" in readme
    assert "test_build441_integrated.py" in readme
