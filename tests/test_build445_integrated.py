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


def case(c, title="Data Acquisition Checkpoint 445"):
    return c.build445.team_create_case(
        identity=ident(c),
        title=title,
        client="QA",
        purpose="dedicated Phase-20 acquisition hard-checkpoint qualification",
        legal_basis="public_data",
    )


def test_gate_is_fail_closed_before_qualification(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        ident(c)
        status = c.build445.data_acquisition_status_445()
        assert status["version_coherent"]
        assert status["hard_checkpoint"]
        assert status["phase20_builds_completed"] == 5
        assert status["data_acquisition_gate_pass"] is False
        assert status["engineering_acquisition_stack_qualified"] is False
        assert status["all_three_paths_externally_validated"] is False
        assert status["real_world_general_research_ready"] is False
        assert status["production_release_ready"] is False


def test_checkpoint_passes_engineering_but_holds_without_real_external_validation(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        admin = ident(c)
        cid = case(c)["case_id"]
        result = c.build445.qualify_data_acquisition_445(identity=admin, case_id=cid)
        report = result["report"]

        assert report["engineering_result"] == "pass"
        assert report["external_result"] == "hold"
        assert report["qualification_result"] == "hold"
        assert report["engineering_acquisition_stack_qualified"] is True
        assert report["real_world_three_path_validation_complete"] is False
        assert report["data_acquisition_gate_pass"] is False
        assert all(report["engineering_checks"].values())
        assert all(report["component_checks"].values())
        assert all(report["capability_checks"].values())
        assert all(report["provenance_checks"].values())
        assert report["deterministic_qualification"]["all_pass"] is True
        assert report["deterministic_qualification"]["external_network_used"] is False
        assert report["external_validation"]["all_three_paths_externally_validated"] is False
        assert report["production_release_ready"] is False

        status = c.build445.data_acquisition_status_445()
        assert status["engineering_acquisition_stack_qualified"] is True
        assert status["data_acquisition_gate_pass"] is False
        assert status["last_engineering_result"] == "pass"
        assert status["last_external_result"] == "hold"
        assert status["last_qualification_result"] == "hold"


def test_deterministic_fixture_runs_never_satisfy_external_gate(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        admin = ident(c)
        cid = case(c, "Fixture exclusion 445")["case_id"]
        result = c.build445.qualify_data_acquisition_445(identity=admin, case_id=cid)
        external = result["report"]["external_validation"]
        assert external["fixture_runs_do_not_count"] is True
        assert external["ci_replay_does_not_count"] is True
        assert external["paths"]["surface"]["validated"] is False
        assert external["paths"]["news"]["validated"] is False
        assert external["paths"]["social"]["validated"] is False
        assert external["all_three_paths_externally_validated"] is False


def test_checkpoint_surfaces_live_ai_dispatch_and_process_isolation_gaps(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        admin = ident(c)
        cid = case(c, "Known gaps 445")["case_id"]
        result = c.build445.qualify_data_acquisition_445(identity=admin, case_id=cid)
        report = result["report"]
        unresolved = set(report["known_unresolved_items"])

        assert "surface_external_nonfixture_validation_missing" in unresolved
        assert "news_external_nonfixture_validation_missing" in unresolved
        assert "social_external_nonfixture_validation_missing" in unresolved
        assert "build439_specialized_news_social_adapter_dispatch_not_implemented" in unresolved
        assert "retrieval_process_isolation_not_implemented" in unresolved

        matrix = report["capability_matrix"]
        assert matrix["ai_investigation_loop"]["specialized_news_social_dispatch_implemented"] is False
        assert matrix["hardening"]["process_isolation"] is False


def test_checkpoint_retains_authority_boundaries(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        ident(c)
        contract = c.data_acquisition_qualification_445._authority_contract()
        assert contract["pass"] is True
        assert contract["forbidden_true"] == []
        assert contract["automatic_live_execution"] is False
        assert contract["automatic_scope_expansion"] is False
        assert contract["explicit_live_confirmations"] == {
            "surface": "SURFACE442_LIVE",
            "news": "NEWS443_LIVE",
            "social": "SOCIAL444_LIVE",
        }


def test_qualification_integrity_tamper_fails(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        admin = ident(c)
        cid = case(c, "Tamper 445")["case_id"]
        result = c.build445.qualify_data_acquisition_445(identity=admin, case_id=cid)
        c.db.execute(
            "UPDATE phase20_data_qualification_run_445 "
            "SET overall_result='pass' WHERE qualification_id=?",
            (result["qualification_id"],),
        )
        assert c.data_acquisition_qualification_445.verify_integrity()["valid"] is False
        status = c.build445.data_acquisition_status_445()
        assert status["integrity_valid"] is False
        assert status["data_acquisition_gate_pass"] is False
        assert status["engineering_acquisition_stack_qualified"] is False


def test_non_admin_cannot_run_global_acquisition_checkpoint(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        admin = ident(c)
        cid = case(c, "Role boundary 445")["case_id"]
        c.team_governance_359.create_user(
            identity=admin,
            username="researcher445",
            display_name="Researcher 445",
            global_role="investigator",
            password="Cedar!Orbit!Quartz!445",
        )
        c.team_governance_359.assign_case_role(
            identity=admin,
            case_id=cid,
            username="researcher445",
            case_role="investigator",
            notes="Build 445 role-boundary test",
        )
        researcher = c.team_identity_359.public_user("researcher445")
        with pytest.raises(PermissionError):
            c.build445.qualify_data_acquisition_445(identity=researcher, case_id=cid)


def test_case_specific_qualification_records_are_isolated(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        admin = ident(c)
        ca = case(c, "Acquisition Gate A")["case_id"]
        cb = case(c, "Acquisition Gate B")["case_id"]
        qa = c.build445.qualify_data_acquisition_445(identity=admin, case_id=ca)
        qb = c.build445.qualify_data_acquisition_445(identity=admin, case_id=cb)

        assert qa["case_id"] == ca
        assert qb["case_id"] == cb
        assert c.build445.data_acquisition_latest_445(ca)["qualification_id"] == qa["qualification_id"]
        assert c.build445.data_acquisition_latest_445(cb)["qualification_id"] == qb["qualification_id"]


def test_contract_launcher_and_current_server(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as c:
        ident(c)
        status = c.build445.data_acquisition_status_445()
        assert status["version_coherent"]
        assert status["hard_checkpoint"]
        assert status["phase20_builds_completed"] == 5
        assert status["core_public_acquisition_paths_implemented"]
        assert status["next_build"] == "446.0"
        assert status["next_hard_checkpoint"] == "450.0"
        assert status["production_release_ready"] is False

    import eagleeye.interfaces.web.app445 as appmod

    calls = []
    monkeypatch.setattr(
        appmod,
        "create_workspace_app445",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    namespace = runpy.run_path(str(ROOT / "EAGLEEYE_PRO_448_0.py"), run_name="__mp_main__")
    assert calls == []
    assert namespace["app"] is None
    assert "app448 import create_workspace_app448" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text()
    assert (ROOT / "BUILD_445_CASE_TEST.md").exists()
    assert (ROOT / "README_BUILD_445_0.md").exists()
    readme = (ROOT / "README.md").read_text()
    assert "EAGLEEYE_PRO_448_0.py" in readme
    assert "test_build448_integrated.py" in readme
