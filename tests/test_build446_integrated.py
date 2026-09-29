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


def case(c, title="Live AI Investigation 446"):
    return c.build446.team_create_case(
        identity=ident(c),
        title=title,
        client="QA",
        purpose="Build 446 dispatcher qualification",
        legal_basis="public_data",
    )


def source(
    c,
    identity,
    suffix,
    *,
    source_type="website",
    access_mode="public",
    capabilities=("public_pages",),
    coverage=None,
    base_url=None,
):
    if base_url is None:
        base_url = f"https://dispatch446-{suffix}.example.org/"
    return c.build421.register_source(
        identity=identity,
        name=f"Dispatch 446 {suffix}",
        source_type=source_type,
        access_mode=access_mode,
        base_url=base_url,
        capabilities=list(capabilities),
        coverage=coverage or {},
    )


def active_loop(c, identity, case_id, source_ids, *, max_tasks=None, fixtures=False):
    loop = c.ai_investigation_loop_439.create_loop(
        identity=identity,
        case_id=case_id,
        objective="Build 446 routing qualification",
        subquestions=["Which approved source should use which acquisition adapter?"],
        allowed_source_ids=source_ids,
        include_fixtures=fixtures,
        max_cycles=3,
        max_collection_tasks_per_cycle=max_tasks or len(source_ids),
    )
    c.ai_investigation_loop_439.authorize_loop(
        identity=identity,
        loop_id=loop["loop_id"],
        confirmation="AUTHORIZE INVESTIGATION LOOP",
    )
    return c.ai_investigation_loop_439.loop(loop["loop_id"])


def test_build446_selftest_routes_all_three_paths_and_refreshes_analysis(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c)["case_id"]
        result = c.build446.run_live_loop_case_selftest(identity=i, case_id=cid)
        assert result["result"] == "PASS"
        assert all(result["checks"].values())
        routes = {x["route"] for x in result["dispatches"]}
        assert routes == {"surface", "news", "social"}
        assert len(result["executions"]) == 3
        assert all(x["external_network"] is False for x in result["executions"])
        assert c.live_investigation_dispatcher_446.verify_integrity()["valid"]


def test_prepare_requires_active_human_authorized_build439_loop(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "GO boundary 446")["case_id"]
        src = source(c, i, "go", coverage={"fixture_only": True})
        loop = c.ai_investigation_loop_439.create_loop(
            identity=i,
            case_id=cid,
            objective="GO boundary",
            subquestions=["Can collection start before GO?"],
            allowed_source_ids=[src["source_id"]],
            include_fixtures=True,
            max_cycles=2,
            max_collection_tasks_per_cycle=1,
        )
        with pytest.raises(PermissionError):
            c.build446.prepare_live_loop_dispatches_446(
                identity=i,
                loop_id=loop["loop_id"],
            )
        assert c.build446.live_loop_dispatches_446(loop["loop_id"]) == []


def test_dispatch_source_must_remain_inside_loop_allowlist(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Scope boundary 446")["case_id"]
        allowed = source(c, i, "allowed", coverage={"fixture_only": True})
        outside = source(c, i, "outside", coverage={"fixture_only": True})
        loop = active_loop(c, i, cid, [allowed["source_id"]], max_tasks=1, fixtures=True)

        with pytest.raises(PermissionError):
            c.build446.prepare_live_loop_dispatches_446(
                identity=i,
                loop_id=loop["loop_id"],
                source_ids=[outside["source_id"]],
            )


def test_routing_is_conservative_and_tor_stays_separate(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Routing 446")["case_id"]

        rss = source(
            c,
            i,
            "rss",
            source_type="rss",
            capabilities=("news_feed", "rss"),
            coverage={
                "fixture_only": True,
                "allowed_article_hosts": ["dispatch446-rss.example.org"],
            },
            base_url="https://dispatch446-rss.example.org/feed.xml",
        )
        news_api = source(
            c,
            i,
            "newsapi",
            source_type="api",
            capabilities=("news_feed",),
            coverage={
                "fixture_only": True,
                "allowed_article_hosts": ["dispatch446-newsapi.example.org"],
            },
            base_url="https://dispatch446-newsapi.example.org/feed.json",
        )
        generic_api = source(
            c,
            i,
            "genericapi",
            source_type="api",
            capabilities=("public_json",),
            coverage={"fixture_only": True},
            base_url="https://dispatch446-genericapi.example.org/data.json",
        )
        social_missing_adapter = source(
            c,
            i,
            "socialreview",
            source_type="social",
            capabilities=("public_posts",),
            coverage={"fixture_only": True},
            base_url="https://dispatch446-socialreview.example.org/public.json",
        )
        tor = source(
            c,
            i,
            "tor",
            source_type="tor_onion",
            access_mode="tor_public",
            capabilities=("public_pages",),
            coverage={"fixture_only": True},
            base_url="http://dispatch446fixture.onion/",
        )

        ids = [
            rss["source_id"],
            news_api["source_id"],
            generic_api["source_id"],
            social_missing_adapter["source_id"],
            tor["source_id"],
        ]
        loop = active_loop(c, i, cid, ids, max_tasks=5, fixtures=True)
        result = c.build446.prepare_live_loop_dispatches_446(
            identity=i,
            loop_id=loop["loop_id"],
        )
        by_source = {x["source_id"]: x for x in result["dispatches"]}

        assert by_source[rss["source_id"]]["route"] == "news"
        assert by_source[news_api["source_id"]]["route"] == "news"
        assert by_source[generic_api["source_id"]]["route"] == "surface"
        assert by_source[social_missing_adapter["source_id"]]["route"] == "review"
        assert by_source[social_missing_adapter["source_id"]]["state"] == "review_required"
        assert by_source[tor["source_id"]]["route"] == "review"
        assert by_source[tor["source_id"]]["reason"] == "isolated_tor_worker_and_separate_approval_required"
        assert by_source[tor["source_id"]]["task_id"] == ""


def test_same_cycle_prepare_reuses_existing_ticket(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Idempotent prepare 446")["case_id"]
        src = source(c, i, "idem", coverage={"fixture_only": True})
        loop = active_loop(c, i, cid, [src["source_id"]], max_tasks=1, fixtures=True)

        first = c.build446.prepare_live_loop_dispatches_446(
            identity=i,
            loop_id=loop["loop_id"],
        )
        second = c.build446.prepare_live_loop_dispatches_446(
            identity=i,
            loop_id=loop["loop_id"],
        )
        assert first["dispatches"][0]["dispatch_id"] == second["dispatches"][0]["dispatch_id"]
        assert len(c.build446.live_loop_dispatches_446(loop["loop_id"])) == 1


def test_per_cycle_dispatch_budget_is_enforced(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Budget 446")["case_id"]
        a = source(c, i, "budget-a", coverage={"fixture_only": True})
        b = source(c, i, "budget-b", coverage={"fixture_only": True})
        loop = active_loop(
            c,
            i,
            cid,
            [a["source_id"], b["source_id"]],
            max_tasks=1,
            fixtures=True,
        )
        with pytest.raises(PermissionError, match="per-cycle"):
            c.build446.prepare_live_loop_dispatches_446(
                identity=i,
                loop_id=loop["loop_id"],
                source_ids=[a["source_id"], b["source_id"]],
            )


def test_wrong_live_confirmation_cannot_touch_nonfixture_task(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Confirmation 446")["case_id"]
        src = source(
            c,
            i,
            "confirm",
            coverage={},
            base_url="https://example.org/",
        )
        loop = active_loop(c, i, cid, [src["source_id"]], max_tasks=1, fixtures=False)
        result = c.build446.prepare_live_loop_dispatches_446(
            identity=i,
            loop_id=loop["loop_id"],
        )
        dispatch = result["dispatches"][0]
        assert dispatch["route"] == "surface"
        assert dispatch["state"] == "awaiting_path_confirmation"
        assert dispatch["required_confirmation"] == "SURFACE442_LIVE"

        with pytest.raises(PermissionError):
            c.build446.execute_live_loop_dispatch_446(
                identity=i,
                dispatch_id=dispatch["dispatch_id"],
                confirmation="GO",
            )
        unchanged = c.live_investigation_dispatcher_446.dispatch(dispatch["dispatch_id"])
        assert unchanged["state"] == "awaiting_path_confirmation"
        assert c.build446.live_loop_executions_446(loop["loop_id"]) == []
        assert c.crawler_core_425.get(dispatch["task_id"])["state"] == "planned"


def test_fixture_ticket_cannot_be_consumed_as_live_execution(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Fixture live block 446")["case_id"]
        src = source(c, i, "fixturelive", coverage={"fixture_only": True})
        loop = active_loop(c, i, cid, [src["source_id"]], max_tasks=1, fixtures=True)
        result = c.build446.prepare_live_loop_dispatches_446(
            identity=i,
            loop_id=loop["loop_id"],
        )
        dispatch = result["dispatches"][0]
        assert dispatch["state"] == "replay_ready"

        with pytest.raises(PermissionError, match="fixture"):
            c.build446.execute_live_loop_dispatch_446(
                identity=i,
                dispatch_id=dispatch["dispatch_id"],
                confirmation="SURFACE442_LIVE",
            )
        assert c.live_investigation_dispatcher_446.dispatch(dispatch["dispatch_id"])["state"] == "replay_ready"


def test_dispatch_tamper_breaks_integrity_and_preflight(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Tamper 446")["case_id"]
        src = source(c, i, "tamper", coverage={"fixture_only": True})
        loop = active_loop(c, i, cid, [src["source_id"]], max_tasks=1, fixtures=True)
        result = c.build446.prepare_live_loop_dispatches_446(
            identity=i,
            loop_id=loop["loop_id"],
        )
        dispatch_id = result["dispatches"][0]["dispatch_id"]
        c.db.execute(
            "UPDATE live_ai_dispatch_446 SET route='social' WHERE dispatch_id=?",
            (dispatch_id,),
        )
        assert c.live_investigation_dispatcher_446.verify_integrity()["valid"] is False


def test_status_closes_445_dispatch_gap_without_rewriting_checkpoint(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        ident(c)
        status = c.build446.live_loop_status_446()
        old = c.build445.data_acquisition_status_445()

        assert status["version_coherent"]
        assert status["phase"] == 20
        assert status["phase20_builds_completed"] == 6
        assert status["specialized_surface_dispatch"]
        assert status["specialized_news_dispatch"]
        assert status["specialized_social_dispatch"]
        assert status["specialized_news_social_dispatch_implemented"]
        assert status["specialized_news_social_dispatch_gap_closed"]
        assert status["per_path_confirmation_required"]
        assert status["batch_auto_execute"] is False
        assert status["generic_network_authority"] is False
        assert status["automatic_scope_expansion"] is False
        assert status["tor_routed_to_separate_review"]
        assert status["production_release_ready"] is False
        assert status["next_build"] == "447.0"
        assert status["next_hard_checkpoint"] == "450.0"

        assert old["build439_specialized_news_social_dispatch_implemented"] is False


def test_contract_launcher_and_current_server(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as c:
        ident(c)
        status = c.build446.live_loop_status_446()
        assert status["version_coherent"]
        assert status["production_release_ready"] is False

    import eagleeye.interfaces.web.app446 as appmod

    calls = []
    monkeypatch.setattr(
        appmod,
        "create_workspace_app446",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    namespace = runpy.run_path(str(ROOT / "EAGLEEYE_PRO_447_0.py"), run_name="__mp_main__")
    assert calls == []
    assert namespace["app"] is None
    assert "app447 import create_workspace_app447" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text()
    assert (ROOT / "BUILD_446_CASE_TEST.md").exists()
    assert (ROOT / "README_BUILD_446_0.md").exists()
    readme = (ROOT / "README.md").read_text()
    assert "EAGLEEYE_PRO_447_0.py" in readme
    assert "test_build447_integrated.py" in readme
