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


def case(c, title="Phase 19 checkpoint 440"):
    return c.build440.team_create_case(
        identity=ident(c),
        title=title,
        client="QA",
        purpose="dedicated synthetic Phase-19 hard-checkpoint qualification",
        legal_basis="public_data",
    )


def test_gate_is_fail_closed_before_qualification(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        ident(c)
        status = c.build440.phase19_qualification_status_440()
        assert status["version_coherent"]
        assert status["hard_checkpoint"]
        assert status["phase19_builds_completed"] == 20
        assert status["phase19_gate_pass"] is False
        assert status["checks"]["passing_phase19_qualification"] is False
        assert status["live_collection_complete"] is False
        assert status["real_world_general_research_ready"] is False
        assert status["production_release_ready"] is False


def test_phase19_hard_checkpoint_passes_engineering_chain_but_not_live_readiness(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        admin = ident(c)
        cid = case(c)["case_id"]
        result = c.build440.qualify_phase19(identity=admin, case_id=cid)
        report = result["report"]
        assert report["qualification_result"] == "pass"
        assert report["engineering_checkpoint_pass"] is True
        assert all(report["checkpoint_checks"].values())
        assert all(report["component_checks"].values())
        assert report["build439_case_selftest"]["result"] == "PASS"
        assert report["live_collection_complete"] is False
        assert report["real_world_general_research_ready"] is False
        assert report["production_release_ready"] is False
        status = c.build440.phase19_qualification_status_440()
        assert status["phase19_gate_pass"] is True
        assert status["production_release_ready"] is False


def test_capability_matrix_truthfully_exposes_live_retrieval_gaps(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        ident(c)
        matrix = c.build440.phase19_capability_matrix_440()
        live = matrix["live_collection"]
        assert live["ordinary_surface_web_complete"] is False
        assert live["news_retrieval_complete"] is False
        assert live["social_retrieval_complete"] is False
        assert live["controlled_tor_path_available"] is True
        assert live["complete"] is False
        assert matrix["production_release_ready"] is False
        assert matrix["real_world_general_research_ready"] is False
        assert {
            "ordinary_surface_web_network_executor_not_implemented",
            "news_network_executor_not_implemented",
            "public_social_network_executor_not_implemented",
            "external_retrieval_adapter_required_for_build439_collection_tasks",
        }.issubset(set(matrix["known_blockers"]))


def test_checkpoint_does_not_grant_forbidden_authority(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        ident(c)
        contract = c.phase19_qualification_440._authority_contract()
        assert contract["pass"] is True
        assert contract["forbidden_true"] == []
        assert contract["generic_network_authority_true"] == []
        assert contract["controlled_tor_exception_only"] is True


def test_qualification_integrity_tamper_fails(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        admin = ident(c)
        cid = case(c, "Tamper 440")["case_id"]
        result = c.build440.qualify_phase19(identity=admin, case_id=cid)
        c.db.execute(
            "UPDATE phase19_qualification_run_440 SET result='tampered' WHERE qualification_id=?",
            (result["qualification_id"],),
        )
        assert c.phase19_qualification_440.verify_integrity()["valid"] is False
        status = c.build440.phase19_qualification_status_440()
        assert status["phase19_gate_pass"] is False


def test_non_admin_cannot_run_global_checkpoint(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        admin = ident(c)
        cid = case(c, "Role boundary 440")["case_id"]
        c.team_governance_359.create_user(
            identity=admin,
            username="researcher440",
            display_name="Researcher 440",
            global_role="investigator",
            password="Cedar!Orbit!Quartz!440",
        )
        c.team_governance_359.assign_case_role(
            identity=admin,
            case_id=cid,
            username="researcher440",
            case_role="investigator",
            notes="Build 440 role-boundary test",
        )
        researcher = c.team_identity_359.public_user("researcher440")
        with pytest.raises(PermissionError):
            c.build440.qualify_phase19(identity=researcher, case_id=cid)


def test_case_specific_qualification_records_are_isolated(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        admin = ident(c)
        ca = case(c, "Checkpoint A")["case_id"]
        cb = case(c, "Checkpoint B")["case_id"]
        qa = c.build440.qualify_phase19(identity=admin, case_id=ca)
        qb = c.build440.qualify_phase19(identity=admin, case_id=cb)
        assert qa["case_id"] == ca
        assert qb["case_id"] == cb
        assert c.build440.phase19_qualification_latest_440(ca)["qualification_id"] == qa["qualification_id"]
        assert c.build440.phase19_qualification_latest_440(cb)["qualification_id"] == qb["qualification_id"]


def test_contract_launcher_and_current_server(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as c:
        ident(c)
        status = c.build440.phase19_qualification_status_440()
        assert status["version_coherent"]
        assert status["hard_checkpoint"]
        assert status["phase19_builds_completed"] == 20
        assert status["production_release_ready"] is False

    import eagleeye.interfaces.web.app440 as appmod

    calls = []
    monkeypatch.setattr(
        appmod,
        "create_workspace_app440",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    namespace = runpy.run_path(str(ROOT / "EAGLEEYE_PRO_440_0.py"), run_name="__mp_main__")
    assert calls == []
    assert namespace["app"] is None
    assert "app441 import create_workspace_app441" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text()
    assert (ROOT / "BUILD_440_CASE_TEST.md").exists()
    assert (ROOT / "README_BUILD_440_0.md").exists()
    readme = (ROOT / "README.md").read_text()
    assert "EAGLEEYE_PRO_441_0.py" in readme
    assert "test_build441_integrated.py" in readme
