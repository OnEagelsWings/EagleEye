from __future__ import annotations

from pathlib import Path
import hashlib

import pytest
from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app457 import create_workspace_app457
from eagleeye.interfaces.web.app448 import render_workspace, COOKIE

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "Build457!Admin_8827"


def admin(ctx):
    if ctx.team_identity_359.bootstrap_required():
        return ctx.team_identity_359.create_initial_admin(
            username="analyst457",
            display_name="Analyst 457",
            password=PASSWORD,
        )
    return ctx.team_identity_359.public_user("analyst457")


def make_case(ctx, identity, title="Build 457 Workspace Reliability"):
    return ctx.team_governance_359.create_case(
        identity=identity,
        title=title,
        client="Internal QA",
        purpose="Validate current-loop workspace and cycle-scoped dispatch budget.",
        legal_basis="public_data",
    )


def source(ctx, identity, suffix):
    return ctx.build421.register_source(
        identity=identity,
        name=f"Build 457 source {suffix}",
        source_type="website",
        access_mode="public",
        base_url=f"https://build457-{suffix}.example.org/",
        capabilities=["public_pages"],
        coverage={"fixture_only": True, "build457_test": True},
        license_note="Synthetic public-source fixture for Build 457 focused regression.",
    )


def active_loop(ctx, identity, case_id, source_ids, *, max_tasks=2):
    loop = ctx.ai_investigation_loop_439.create_loop(
        identity=identity,
        case_id=case_id,
        objective="Build 457 current-loop reliability qualification",
        subquestions=["Which approved source belongs to the current cycle?"],
        allowed_source_ids=source_ids,
        include_fixtures=True,
        max_cycles=4,
        max_collection_tasks_per_cycle=max_tasks,
    )
    return ctx.ai_investigation_loop_439.authorize_loop(
        identity=identity,
        loop_id=loop["loop_id"],
        confirmation="AUTHORIZE INVESTIGATION LOOP",
    )


def test_build457_selects_newest_active_loop_over_newer_completed_history(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = admin(ctx)
        cid = make_case(ctx, identity)["case_id"]
        src = source(ctx, identity, "active")
        first = active_loop(ctx, identity, cid, [src["source_id"]], max_tasks=1)

        second = active_loop(ctx, identity, cid, [src["source_id"]], max_tasks=1)
        ctx.ai_investigation_loop_439._update_loop(
            second["loop_id"], state="completed"
        )

        snap = ctx.build457.workspace_snapshot_457(identity=identity, case_id=cid)
        assert snap["active_loop"]["loop_id"] == first["loop_id"]
        assert snap["latest_historical_loop"]["loop_id"] == second["loop_id"]
        assert snap["latest_loop"]["loop_id"] == first["loop_id"]
        assert snap["selected_loop_reason"] == "newest_active"
        assert snap["dispatch_budget"]["loop_id"] == first["loop_id"]
        assert snap["truth_determined"] is False


def test_build457_backend_enforces_remaining_cycle_budget(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = admin(ctx)
        cid = make_case(ctx, identity, "Remaining budget 457")["case_id"]
        sources = [source(ctx, identity, x)["source_id"] for x in ("a", "b", "c")]
        loop = active_loop(ctx, identity, cid, sources, max_tasks=2)

        first = ctx.live_investigation_dispatcher_446.prepare_loop_dispatches(
            identity=identity,
            loop_id=loop["loop_id"],
            source_ids=[sources[0]],
        )
        assert len(first["dispatches"]) == 1

        with pytest.raises(PermissionError, match="remaining authorized per-cycle"):
            ctx.live_investigation_dispatcher_446.prepare_loop_dispatches(
                identity=identity,
                loop_id=loop["loop_id"],
                source_ids=[sources[1], sources[2]],
            )

        second = ctx.live_investigation_dispatcher_446.prepare_loop_dispatches(
            identity=identity,
            loop_id=loop["loop_id"],
            source_ids=[sources[1]],
        )
        assert len(second["dispatches"]) == 1

        # Existing tickets remain idempotently addressable when no budget remains.
        reused = ctx.live_investigation_dispatcher_446.prepare_loop_dispatches(
            identity=identity,
            loop_id=loop["loop_id"],
            source_ids=[sources[0], sources[1]],
        )
        assert len(reused["dispatches"]) == 2

        snap = ctx.build457.workspace_snapshot_457(identity=identity, case_id=cid)
        assert snap["dispatch_budget"]["max_per_cycle"] == 2
        assert snap["dispatch_budget"]["reserved_or_consumed"] == 2
        assert snap["dispatch_budget"]["remaining"] == 0
        assert snap["recommended_dispatch_source_ids"] == []


def test_build457_prior_cycle_dispatch_does_not_leak_into_current_cycle(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = admin(ctx)
        cid = make_case(ctx, identity, "Cycle scope 457")["case_id"]
        sources = [source(ctx, identity, x)["source_id"] for x in ("cycle-a", "cycle-b", "cycle-c")]
        loop = active_loop(ctx, identity, cid, sources, max_tasks=2)

        old = ctx.live_investigation_dispatcher_446.prepare_loop_dispatches(
            identity=identity,
            loop_id=loop["loop_id"],
            source_ids=[sources[0]],
        )["dispatches"][0]
        ctx.ai_investigation_loop_439._update_loop(
            loop["loop_id"], state="active", current_cycle=1
        )

        snap = ctx.build457.workspace_snapshot_457(identity=identity, case_id=cid)
        assert snap["dispatch_budget"]["cycle_number"] == 1
        assert snap["dispatch_budget"]["reserved_or_consumed"] == 0
        assert snap["dispatch_budget"]["remaining"] == 2
        assert len(snap["recommended_dispatch_source_ids"]) == 2
        assert snap["current_cycle_dispatches"] == []
        assert old["dispatch_id"] in {x["dispatch_id"] for x in snap["dispatches"]}
        assert any(
            x["label"] == "Quellen-Dispatch vorbereiten"
            for x in snap["next_actions"]
        )


def test_build457_reliable_workspace_renders_loop_and_budget(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = admin(ctx)
        cid = make_case(ctx, identity, "UI reliability 457")["case_id"]
        sources = [source(ctx, identity, x)["source_id"] for x in ("ui-a", "ui-b")]
        loop = active_loop(ctx, identity, cid, sources, max_tasks=2)
        ctx.live_investigation_dispatcher_446.prepare_loop_dispatches(
            identity=identity,
            loop_id=loop["loop_id"],
            source_ids=[sources[0]],
        )

        snap = ctx.build457.workspace_snapshot_457(identity=identity, case_id=cid)
        markup = render_workspace(snap, view="research", cases=[snap["case"]], audits=[])
        assert "Build 457.0" in markup
        assert "Workspace Reliability" in markup
        assert "Zyklusbudget" in markup
        assert "Verbraucht / reserviert" in markup
        assert "Verbleibend" in markup
        assert loop["loop_id"] in markup
        assert "@media(max-width:1000px)" in markup
        assert ":focus-visible" in markup
        assert 'aria-live="polite"' in markup


def test_build457_http_current_workspace_and_version_contract(tmp_path):
    app = create_workspace_app457(base_dir=tmp_path)
    ctx = app.state.context
    try:
        identity = admin(ctx)
        cid = make_case(ctx, identity, "HTTP 457")["case_id"]
        src = source(ctx, identity, "http")
        active_loop(ctx, identity, cid, [src["source_id"]], max_tasks=1)

        ua = "build457-http-test"
        lang = "en"
        fingerprint = hashlib.sha256(f"{ua}|{lang}|testclient".encode()).hexdigest()
        session = ctx.team_identity_359.authenticate(
            username="analyst457",
            password=PASSWORD,
            client_fingerprint=fingerprint,
        )
        assert session is not None

        with TestClient(app, headers={"user-agent": ua, "accept-language": lang}) as client:
            client.cookies.set(COOKIE, session.token)
            root = client.get("/", params={"view": "research", "case_id": cid})
            assert root.status_code == 200
            assert "Build 457.0" in root.text
            assert "Zyklusbudget" in root.text
            api = client.get(f"/api/build457/cases/{cid}/snapshot")
            assert api.status_code == 200
            assert api.json()["workspace_build"] == "457.0"
            health = client.get("/health")
            assert health.status_code == 200
            assert health.json()["build"] == "457.0"
            assert health.json()["full_research_gate_this_build"] is False
    finally:
        ctx.close()

    assert 'version = "457.0.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'BUILD = "457.0"' in (ROOT / "eagleeye_pro/version.py").read_text(encoding="utf-8")
    assert "app457 import create_workspace_app457" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text(encoding="utf-8")
    assert (ROOT / "INSTALL_EAGLEEYE_457.py").exists()
    assert (ROOT / "EAGLEEYE_PRO_457_0.py").exists()


def test_build457_status_preserves_authority_boundaries(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin(ctx)
        status = ctx.build457.build457_status()
        assert status["build"] == "457.0"
        assert status["active_loop_selected_independently"] is True
        assert status["loop_scoped_recommendations"] is True
        assert status["remaining_dispatch_budget_enforced"] is True
        assert status["automatic_research_action"] is False
        assert status["automatic_truth_determination"] is False
        assert status["full_research_gate_this_build"] is False
        assert status["next_checkpoint"] == "460.0"
