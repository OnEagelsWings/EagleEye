from pathlib import Path
import runpy
import ssl

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


def case(c, title="Surface Hardening 442"):
    return c.build442.team_create_case(
        identity=ident(c),
        title=title,
        client="QA",
        purpose="surface retrieval hardening qualification",
        legal_basis="public_data",
    )


def register_source(c, identity, suffix, *, fixture=False):
    return c.build421.register_source(
        identity=identity,
        name=f"Surface 442 {suffix}",
        source_type="website",
        access_mode="public",
        base_url=f"https://surface442-{suffix}.example.org/",
        capabilities=["public_pages"],
        coverage={"fixture_only": True, "live_execution_forbidden": True} if fixture else {},
    )


def task(c, identity, case_id, source, path="/page"):
    host = source["base_url"].split("/")[2]
    return c.crawler_core_425.create_task(
        identity=identity,
        case_id=case_id,
        source_id=source["source_id"],
        target=source["base_url"].rstrip("/") + path,
        objective="Build 442 hardening test",
        scope={"allowed_hosts": [host]},
        budget={"max_pages": 1, "max_bytes": 100000, "max_seconds": 5},
    )


def allowed_replay(source, crawl_task, *, target_status=200, target_body=b"ok"):
    robots = source["base_url"] + "robots.txt"
    target = crawl_task["target"]
    return StaticTransport(
        {
            robots: FetchResponse(
                robots,
                200,
                {"content-type": "text/plain"},
                b"User-agent: *\nAllow: /\n",
                1,
            ),
            target: FetchResponse(
                target,
                target_status,
                {"content-type": "text/plain"},
                target_body,
                2,
            ),
        }
    )


def test_build442_selftest_validates_retry_backoff_dns_and_telemetry(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c)["case_id"]
        result = c.build442.run_surface_hardening_case_selftest(identity=i, case_id=cid)
        assert result["result"] == "PASS"
        assert all(result["checks"].values())
        assert result["hardening"]["attempt_count"] == 3
        assert any(int(x["http_status"]) == 503 for x in result["telemetry"])
        assert c.surface_hardening_442.verify_integrity()["valid"]


def test_dns_rebind_to_private_address_fails_before_target_fetch(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "DNS rebind 442")["case_id"]
        source = register_source(c, i, "rebind", fixture=True)
        crawl_task = task(c, i, cid, source)
        transport = allowed_replay(source, crawl_task)
        answers = iter([[PUBLIC_IP], ["127.0.0.1"]])

        with pytest.raises(RuntimeError):
            c.surface_hardening_442.execute_replay(
                identity=i,
                task_id=crawl_task["task_id"],
                transport=transport,
                resolver=lambda _host: next(answers),
            )

        assert transport.calls == [source["base_url"] + "robots.txt"]
        run = c.build442.surface_hardening_runs_442(cid)[-1]
        assert run["state"] == "failed"
        assert run["dns_report"]["rebind_violations"]
        assert c.crawler_core_425.get(crawl_task["task_id"])["state"] == "failed"


def test_public_dns_change_is_observed_but_original_pin_is_retained(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Public DNS change 442")["case_id"]
        source = register_source(c, i, "cdnchange", fixture=True)
        crawl_task = task(c, i, cid, source)
        transport = allowed_replay(source, crawl_task)
        answers = iter([[PUBLIC_IP], ["1.1.1.1"]])

        result = c.surface_hardening_442.execute_replay(
            identity=i,
            task_id=crawl_task["task_id"],
            transport=transport,
            resolver=lambda _host: next(answers),
        )
        report = result["hardening"]["dns_report"]
        assert result["hardening"]["state"] == "completed"
        assert report["public_set_changes"]
        pinned = next(iter(report["pinned"].values()))
        assert pinned == [PUBLIC_IP]
        assert report["rebind_violations"] == []


def test_tls_certificate_failure_is_not_retried(tmp_path):
    class TLSFailureTransport:
        transport_kind = "tls_failure_fixture"
        externally_configured = False
        requires_resolved_ips = False

        def __init__(self):
            self.calls = 0

        def fetch(self, url, **kwargs):
            self.calls += 1
            raise ssl.SSLCertVerificationError("certificate verify failed")

    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "TLS 442")["case_id"]
        source = register_source(c, i, "tls", fixture=True)
        crawl_task = task(c, i, cid, source)
        transport = TLSFailureTransport()

        with pytest.raises(RuntimeError):
            c.surface_hardening_442.execute_replay(
                identity=i,
                task_id=crawl_task["task_id"],
                transport=transport,
                resolver=lambda _host: [PUBLIC_IP],
            )

        telemetry = c.build442.surface_task_telemetry_442(crawl_task["task_id"])
        assert transport.calls == 1
        assert len(telemetry) == 1
        assert telemetry[0]["error_class"] == "SSLCertVerificationError"
        assert int(telemetry[0]["transient"]) == 0
        assert int(telemetry[0]["backoff_ms"]) == 0


def test_source_minimum_interval_fails_closed_without_touching_second_task(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Rate 442")["case_id"]
        source = register_source(c, i, "rate", fixture=True)
        first = task(c, i, cid, source, "/one")
        second = task(c, i, cid, source, "/two")
        c.surface_hardening_442.clock = lambda: 1000.0
        c.surface_hardening_442.sleep = lambda _seconds: None

        first_transport = allowed_replay(source, first)
        c.surface_hardening_442.execute_replay(
            identity=i,
            task_id=first["task_id"],
            transport=first_transport,
            resolver=lambda _host: [PUBLIC_IP],
        )

        second_transport = allowed_replay(source, second)
        with pytest.raises(PermissionError):
            c.surface_hardening_442.execute_replay(
                identity=i,
                task_id=second["task_id"],
                transport=second_transport,
                resolver=lambda _host: [PUBLIC_IP],
            )
        assert second_transport.calls == []
        assert c.crawler_core_425.get(second["task_id"])["state"] == "planned"


def test_external_validation_requires_separate_exact_opt_in(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "External opt-in 442")["case_id"]
        source = register_source(c, i, "external")
        crawl_task = task(c, i, cid, source)
        with pytest.raises(PermissionError):
            c.surface_hardening_442.validate_external_task(
                identity=i,
                task_id=crawl_task["task_id"],
                confirmation="SURFACE442_LIVE",
            )
        assert c.crawler_core_425.get(crawl_task["task_id"])["state"] == "planned"


def test_fixture_cannot_be_used_for_external_validation(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "External fixture block 442")["case_id"]
        source = register_source(c, i, "externalfixture", fixture=True)
        crawl_task = task(c, i, cid, source)
        with pytest.raises(PermissionError):
            c.surface_hardening_442.validate_external_task(
                identity=i,
                task_id=crawl_task["task_id"],
                confirmation="VALIDATE442_EXTERNAL",
            )
        assert c.crawler_core_425.get(crawl_task["task_id"])["state"] == "planned"


def test_hardening_record_tamper_breaks_integrity(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Tamper 442")["case_id"]
        result = c.build442.run_surface_hardening_case_selftest(identity=i, case_id=cid)
        rid = result["hardening"]["hardening_run_id"]
        c.db.execute(
            "UPDATE surface_hardening_run_442 SET attempt_count=99 WHERE hardening_run_id=?",
            (rid,),
        )
        assert c.surface_hardening_442.verify_integrity()["valid"] is False


def test_status_truthfully_distinguishes_logical_from_process_isolation(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        ident(c)
        status = c.build442.surface_hardening_status_442()
        assert status["dns_rebinding_defense"]
        assert status["bounded_retry"]
        assert status["per_source_rate_limit"]
        assert status["source_scoped_worker_lock"]
        assert status["single_concurrent_live_worker"]
        assert status["ephemeral_transport_per_live_run"]
        assert status["shared_cookie_or_session_state"] is False
        assert status["process_isolation"] is False
        assert status["external_validation_requires_explicit_confirmation"]
        assert status["automatic_external_validation"] is False
        assert status["production_release_ready"] is False


def test_contract_version_launcher_and_phase20_position(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as c:
        status = c.build442.surface_hardening_status_442()
        assert status["version_coherent"]
        assert status["phase"] == 20
        assert status["phase20_builds_completed"] == 2
        assert status["build441_surface_executor_retained"]
        assert status["surface_hardening_complete_for_current_scope"]
        assert status["next_build"] == "443.0"
        assert status["next_hard_checkpoint"] == "445.0"
        assert status["general_live_collection_complete"] is False
        assert status["production_release_ready"] is False

    import eagleeye.interfaces.web.app442 as appmod

    calls = []
    monkeypatch.setattr(
        appmod,
        "create_workspace_app442",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    namespace = runpy.run_path(str(ROOT / "EAGLEEYE_PRO_442_0.py"), run_name="__mp_main__")
    assert calls == []
    assert namespace["app"] is None
    assert "app447 import create_workspace_app447" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text()
    assert (ROOT / "BUILD_442_CASE_TEST.md").exists()
    assert (ROOT / "README_BUILD_442_0.md").exists()
    readme = (ROOT / "README.md").read_text()
    assert "EAGLEEYE_PRO_447_0.py" in readme
    assert "test_build447_integrated.py" in readme
