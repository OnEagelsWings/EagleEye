from __future__ import annotations

from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app448 import render_workspace
from eagleeye.interfaces.web.app457 import create_workspace_app457

ROOT = Path(__file__).resolve().parents[1]
TEST_PASSWORD = "Build" + "457!" + "Test_" + "8842"


def setup_case(ctx):
    ctx.team_identity_359.create_initial_admin(
        username="admin457",
        display_name="Build 457 Admin",
        password=TEST_PASSWORD,
    )
    issued = ctx.team_identity_359.authenticate(
        username="admin457",
        password=TEST_PASSWORD,
        client_fingerprint="build457-fixture",
    )
    assert issued is not None
    identity = ctx.team_identity_359.validate_session(
        issued.token, client_fingerprint="build457-fixture", touch=False
    )
    assert identity is not None
    case = ctx.team_governance_359.create_case(
        identity=identity,
        title="Build 457 workspace reliability fixture",
        client="Internal QA",
        purpose="Validate cycle-scoped operator state.",
        legal_basis="public_data",
    )
    return identity, case


def insert_loop(ctx, case_id, loop_id, state, created_at, *, cycle=1, max_tasks=2, sources=()):
    row = {
        "loop_id": loop_id,
        "case_id": case_id,
        "objective": "Build 457 reliability fixture",
        "plan_id": "plan_" + loop_id,
        "wave_run_id": "wave_" + loop_id,
        "session_id": "session_" + loop_id,
        "state": state,
        "max_cycles": 4,
        "current_cycle": cycle,
        "scope_json": json.dumps({
            "allowed_source_ids": list(sources),
            "include_fixtures": False,
            "max_collection_tasks_per_cycle": max_tasks,
            "scope_expansion": False,
            "direct_network_authority": False,
        }, sort_keys=True, separators=(",", ":")),
        "created_by": "admin457",
        "created_at": created_at,
        "updated_at": created_at,
    }
    row["record_hash"] = ctx.ai_investigation_loop_439._rh(row)
    ctx.db.execute(
        "INSERT INTO phase19_ai_loop_439 VALUES(" + ",".join("?" for _ in row) + ")",
        tuple(row.values()),
    )


def insert_dispatch(ctx, case_id, loop_id, source_id, *, cycle=1, state="awaiting_path_confirmation"):
    row = {
        "dispatch_id": "dispatch457_" + source_id,
        "loop_id": loop_id,
        "case_id": case_id,
        "cycle_number": cycle,
        "source_id": source_id,
        "route": "surface",
        "task_id": "task457_" + source_id,
        "state": state,
        "required_confirmation": "SURFACE442_LIVE",
        "reason": "",
        "created_by": "admin457",
        "created_at": "2026-10-12T10:00:00+00:00",
        "updated_at": "2026-10-12T10:00:00+00:00",
    }
    row["record_hash"] = ctx.live_investigation_dispatcher_446._rh(row)
    ctx.db.execute(
        "INSERT INTO live_ai_dispatch_446 VALUES(" + ",".join("?" for _ in row) + ")",
        tuple(row.values()),
    )


def test_build457_status_health_version_and_focused_cadence(tmp_path):
    app = create_workspace_app457(base_dir=tmp_path)
    try:
        status = app.state.context.build457.build457_status()
        assert status["build"] == "457.0"
        assert status["active_loop_selection"] is True
        assert status["current_cycle_dispatch_scope"] is True
        assert status["remaining_dispatch_budget_enforced"] is True
        assert status["next_checkpoint"] == "460.0"
        with TestClient(app) as client:
            assert client.get("/health").json()["build"] == "457.0"
    finally:
        app.state.context.close()
    assert 'version = "457.0.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "app457 import create_workspace_app457" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text(encoding="utf-8")
    assert (ROOT / "INSTALL_EAGLEEYE_457.py").exists()
    assert (ROOT / "EAGLEEYE_PRO_457_0.py").exists()


def test_build457_newer_terminal_loop_does_not_hide_active_loop(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity, case = setup_case(ctx)
        case_id = case["case_id"]
        insert_loop(
            ctx, case_id, "ail457_active", "active",
            "2026-10-12T09:00:00+00:00",
            cycle=1, max_tasks=2, sources=("src-a", "src-b", "src-c"),
        )
        insert_loop(
            ctx, case_id, "ail457_terminal", "review_required",
            "2026-10-12T10:00:00+00:00",
            cycle=4, max_tasks=4, sources=("src-z",),
        )
        insert_dispatch(ctx, case_id, "ail457_active", "src-a", cycle=1)
        snap = ctx.build457.workspace_snapshot_457(identity=identity, case_id=case_id)
        assert snap["latest_loop"]["loop_id"] == "ail457_active"
        assert snap["active_loop"]["loop_id"] == "ail457_active"
        assert snap["latest_historical_loop"]["loop_id"] == "ail457_terminal"
        assert snap["dispatch_budget"]["authorized"] == 2
        assert snap["dispatch_budget"]["reserved"] == 1
        assert snap["dispatch_budget"]["remaining"] == 1
        assert snap["recommended_dispatch_source_ids"] == ["src-b"]
        assert [x["source_id"] for x in snap["current_cycle_dispatches"]] == ["src-a"]


def test_build457_dispatcher_counts_existing_reservations_against_budget(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        dispatcher = ctx.live_investigation_dispatcher_446
        insert_dispatch(ctx, "case457-budget", "loop457-budget", "src-a", cycle=2)
        insert_dispatch(ctx, "case457-budget", "loop457-budget", "src-b", cycle=2)
        loop = {
            "loop_id": "loop457-budget",
            "case_id": "case457-budget",
            "state": "active",
            "current_cycle": 2,
            "scope": {
                "allowed_source_ids": ["src-a", "src-b", "src-c"],
                "max_collection_tasks_per_cycle": 2,
            },
        }
        dispatcher._preflight = lambda: {}
        dispatcher._loop = lambda _loop_id, require_active=True: loop
        dispatcher._authorize = lambda identity, _case_id, **kwargs: identity
        with pytest.raises(PermissionError, match="remaining authorized"):
            dispatcher.prepare_loop_dispatches(
                identity={"username": "admin457", "user_id": "user457"},
                loop_id="loop457-budget",
                source_ids=["src-c"],
            )


def test_build457_repeated_long_feed_boilerplate_is_not_fingerprinted(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        service = ctx.news_acquisition_443
        summary = (
            "This website provides independent reporting and analysis. "
            "Visit our homepage for the latest updates and more information."
        )
        normalized = " ".join(summary.casefold().split())
        item = {"title": "Unrelated article", "summary": summary}
        assert service._publication_text_fingerprint(item)
        assert service._publication_text_fingerprint(item, {normalized}) == ""


def test_build457_entity_scan_validation_is_mapped_to_client_error():
    text = (
        ROOT / "src" / "eagleeye" / "interfaces" / "web" / "app456.py"
    ).read_text(encoding="utf-8")
    assert "except (TypeError, ValueError) as exc" in text
    assert "HTTPException(422" in text


def test_build457_workspace_render_is_responsive_and_budget_fail_closed(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity, case = setup_case(ctx)
        case_id = case["case_id"]
        insert_loop(
            ctx, case_id, "ail457_render", "active",
            "2026-10-12T10:30:00+00:00",
            cycle=1, max_tasks=1, sources=("src-only",),
        )
        insert_dispatch(ctx, case_id, "ail457_render", "src-only", cycle=1)
        snap = ctx.build457.workspace_snapshot_457(identity=identity, case_id=case_id)
        markup = render_workspace(snap, view="research", cases=[case], audits=[])
        lower = markup.lower()
        assert 'name="viewport"' in lower
        assert ":focus-visible" in markup
        assert "@media(max-width:620px)" in markup
        assert "dispatch-budget dieses zyklus ist ausgeschöpft" in lower
        assert "dispatch vorbereiten" not in lower
        assert "/legacy" in markup
