from pathlib import Path
import runpy

import pytest

from eagleeye.crawler.engine import FetchResponse, StaticTransport
from eagleeye_pro.core.app_context import AppContext

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_IP = "93.184.216.34"


def ident(c):
    if c.team_identity_359.bootstrap_required():
        return c.team_identity_359.create_initial_admin(
            username="analyst",
            display_name="Analyst Fixture",
            password="SecureFixturePassword!2026",
        )
    return c.team_identity_359.public_user("analyst")


def case(c, title="Surface Retrieval 441"):
    return c.build441.team_create_case(
        identity=ident(c),
        title=title,
        client="QA",
        purpose="controlled public surface retrieval qualification",
        legal_basis="public_data",
    )


def source_and_task(c, identity, case_id, *, suffix="ok", coverage=None, path="/page", media_budget=None):
    base = f"https://surface441-{suffix}.example.org/"
    source = c.build421.register_source(
        identity=identity,
        name=f"Surface 441 {suffix}",
        source_type="website",
        access_mode="public",
        base_url=base,
        capabilities=["public_pages"],
        coverage=coverage or {},
    )
    task = c.crawler_core_425.create_task(
        identity=identity,
        case_id=case_id,
        source_id=source["source_id"],
        target=base.rstrip("/") + path,
        objective="Build 441 controlled retrieval test",
        scope={"allowed_hosts": [f"surface441-{suffix}.example.org"]},
        budget=media_budget or {"max_pages": 1, "max_bytes": 100000, "max_seconds": 5},
    )
    return source, task, base


def replay(base, target, *, robots=b"User-agent: *\nAllow: /\n", status=200, headers=None, body=b"hello"):
    robots_url = base + "robots.txt"
    return StaticTransport(
        {
            robots_url: FetchResponse(robots_url, 200, {"content-type": "text/plain"}, robots, 1),
            target: FetchResponse(target, status, headers or {"content-type": "text/plain"}, body, 2),
        }
    )


def resolver(_host):
    return [PUBLIC_IP]


def test_case_selftest_closes_build425_execution_gap_without_network(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c)["case_id"]
        result = c.build441.run_surface_retrieval_case_selftest(identity=i, case_id=cid)
        assert result["result"] == "PASS"
        assert all(result["checks"].values())
        assert result["run"]["execution_mode"] == "deterministic_replay"
        assert c.surface_retrieval_441.verify_integrity()["valid"]


def test_replay_routes_public_get_into_existing_provenance_chain(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Provenance 441")["case_id"]
        source, task, base = source_and_task(c, i, cid, suffix="provenance")
        target = task["target"]
        transport = replay(base, target, body=b"public provenance content")
        result = c.surface_retrieval_441.execute_replay(
            identity=i,
            task_id=task["task_id"],
            transport=transport,
            resolver=resolver,
        )
        assert result["run"]["state"] == "completed"
        assert c.crawler_core_425.get(task["task_id"])["state"] == "completed"
        event = c.acquisition_events_422.get(result["accepted"]["event_id"])
        assert event["status"] == "retrieved"
        assert event["source_id"] == source["source_id"]
        assert event["provenance"]["build"] == "441.0"
        assert event["usage"]["robots_respected"] is True
        assert result["accepted"]["content"]["content_id"]
        assert transport.calls == [base + "robots.txt", target]


def test_robots_disallow_blocks_target_before_fetch(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Robots 441")["case_id"]
        _source, task, base = source_and_task(c, i, cid, suffix="robots", path="/secret")
        target = task["target"]
        transport = replay(
            base,
            target,
            robots=b"User-agent: *\nDisallow: /secret\n",
            body=b"must not be fetched",
        )
        result = c.surface_retrieval_441.execute_replay(
            identity=i,
            task_id=task["task_id"],
            transport=transport,
            resolver=resolver,
        )
        assert result["run"]["state"] == "blocked"
        assert result["run"]["error_class"] == "disallowed_by_robots"
        assert transport.calls == [base + "robots.txt"]
        assert c.crawler_core_425.get(task["task_id"])["state"] == "failed"


def test_private_or_reserved_dns_is_rejected_before_network_fetch(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "SSRF 441")["case_id"]
        _source, task, base = source_and_task(c, i, cid, suffix="ssrf")
        target = task["target"]
        transport = replay(base, target)
        with pytest.raises(RuntimeError):
            c.surface_retrieval_441.execute_replay(
                identity=i,
                task_id=task["task_id"],
                transport=transport,
                resolver=lambda _host: ["127.0.0.1"],
            )
        assert transport.calls == []
        assert c.crawler_core_425.get(task["task_id"])["state"] == "failed"


def test_cross_host_redirect_fails_closed_without_fetching_destination(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Redirect 441")["case_id"]
        _source, task, base = source_and_task(c, i, cid, suffix="redirect")
        target = task["target"]
        robots_url = base + "robots.txt"
        transport = StaticTransport(
            {
                robots_url: FetchResponse(
                    robots_url, 200, {"content-type": "text/plain"}, b"User-agent: *\nAllow: /\n", 1
                ),
                target: FetchResponse(
                    target,
                    302,
                    {"content-type": "text/plain", "location": "https://other.example.org/next"},
                    b"",
                    2,
                ),
            }
        )
        with pytest.raises(RuntimeError):
            c.surface_retrieval_441.execute_replay(
                identity=i,
                task_id=task["task_id"],
                transport=transport,
                resolver=resolver,
            )
        assert transport.calls == [robots_url, target]
        assert c.crawler_core_425.get(task["task_id"])["state"] == "failed"


def test_unsafe_download_media_is_blocked_not_ingested(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Media 441")["case_id"]
        _source, task, base = source_and_task(c, i, cid, suffix="media")
        target = task["target"]
        transport = replay(
            base,
            target,
            headers={"content-type": "application/octet-stream"},
            body=b"\x00\x01binary",
        )
        result = c.surface_retrieval_441.execute_replay(
            identity=i,
            task_id=task["task_id"],
            transport=transport,
            resolver=resolver,
        )
        assert result["run"]["state"] == "blocked"
        assert result["run"]["error_class"] == "unsafe_media_type"
        assert result["accepted"]["content"] is None


def test_live_fixture_execution_is_forbidden_before_external_fetch(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Fixture live boundary 441")["case_id"]
        _source, task, _base = source_and_task(
            c,
            i,
            cid,
            suffix="fixture",
            coverage={"fixture_only": True, "live_execution_forbidden": True},
        )
        with pytest.raises(RuntimeError):
            c.surface_retrieval_441.execute_live(
                identity=i,
                task_id=task["task_id"],
                confirmation="SURFACE441_LIVE",
            )
        assert c.crawler_core_425.get(task["task_id"])["state"] == "failed"


def test_explicit_live_confirmation_required(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Confirmation 441")["case_id"]
        _source, task, _base = source_and_task(c, i, cid, suffix="confirmation")
        with pytest.raises(PermissionError):
            c.surface_retrieval_441.execute_live(
                identity=i,
                task_id=task["task_id"],
                confirmation="GO",
            )
        assert c.crawler_core_425.get(task["task_id"])["state"] == "planned"


def test_active_build439_loop_can_supply_existing_human_authorization(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Loop authorization 441")["case_id"]
        source = c.build421.register_source(
            identity=i,
            name="Loop source 441",
            source_type="website",
            access_mode="public",
            base_url="https://loop441.example.org/",
            capabilities=["public_pages"],
        )
        loop = c.build439.create_ai_investigation_loop_439(
            identity=i,
            case_id=cid,
            objective="Authorized surface research",
            subquestions=["What does the reviewed public source state?"],
            allowed_source_ids=[source["source_id"]],
            max_cycles=2,
            max_collection_tasks_per_cycle=1,
        )
        c.build439.authorize_ai_investigation_loop_439(
            identity=i,
            loop_id=loop["loop_id"],
            confirmation="AUTHORIZE INVESTIGATION LOOP",
        )
        step = c.build439.advance_ai_investigation_loop_439(identity=i, loop_id=loop["loop_id"])
        task_id = step["snapshot"]["collection_tasks"][0]["task_id"]
        called = {}

        def fake_execute(**kwargs):
            called.update(kwargs)
            return {"authorization_mode": kwargs["authorization_mode"], "task_id": kwargs["task_id"]}

        monkeypatch.setattr(c.surface_retrieval_441, "_execute", fake_execute)
        result = c.surface_retrieval_441.execute_authorized_loop_task(identity=i, task_id=task_id)
        assert result["authorization_mode"] == "authorized_build439_loop"
        assert called["live"] is True
        assert called["task_id"] == task_id


def test_contract_version_launcher_and_phase20_position(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as c:
        status = c.build441.surface_retrieval_status_441()
        assert status["version_coherent"]
        assert status["phase"] == 20
        assert status["phase20_builds_completed"] == 1
        assert status["phase19_checkpoint_retained"]
        assert status["controlled_surface_network_executor"]
        assert status["ordinary_surface_retrieval_available"]
        assert status["robots_required_fail_closed"]
        assert status["dns_ip_pinning"]
        assert status["authenticated_sources_supported"] is False
        assert status["cookies_supported"] is False
        assert status["write_methods_supported"] is False
        assert status["onion_execution"] is False
        assert status["autonomous_scope_expansion"] is False
        assert status["general_live_collection_complete"] is False
        assert status["production_release_ready"] is False
        assert status["next_hard_checkpoint"] == "460.0"

    import eagleeye.interfaces.web.app441 as appmod

    calls = []
    monkeypatch.setattr(
        appmod,
        "create_workspace_app441",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    namespace = runpy.run_path(str(ROOT / "EAGLEEYE_PRO_441_0.py"), run_name="__mp_main__")
    assert calls == []
    assert namespace["app"] is None
    assert "app441 import create_workspace_app441" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text()
    assert (ROOT / "BUILD_441_CASE_TEST.md").exists()
    assert (ROOT / "README_BUILD_441_0.md").exists()
    readme = (ROOT / "README.md").read_text()
    assert "EAGLEEYE_PRO_441_0.py" in readme
    assert "test_build441_integrated.py" in readme
