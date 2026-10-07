from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app453 import create_workspace_app453

ROOT = Path(__file__).resolve().parents[1]


def ident(ctx):
    if ctx.team_identity_359.bootstrap_required():
        return ctx.team_identity_359.create_initial_admin(
            username="analyst453",
            display_name="Analyst 453",
            password="SecureFixturePassword!2026",
        )
    return ctx.team_identity_359.public_user("analyst453")


def archive_source(ctx, identity):
    return ctx.build421.register_source(
        identity=identity,
        name="Internet Archive Build 453",
        source_type="archive",
        base_url="https://web.archive.org",
        capabilities=["historical_web", "cdx_index"],
        coverage={"provider": "internet_archive", "fixture_only": True},
    )


def index_observation(ctx, identity, case_id, source, payload):
    event = ctx.build422.record_event(
        identity=identity,
        case_id=case_id,
        source_id=source["source_id"],
        target="https://web.archive.org/cdx/search/cdx?url=example.org",
        method="archive",
        status="retrieved",
    )
    content = ctx.build423.ingest_content(
        identity=identity,
        event_id=event["event_id"],
        content=payload,
        media_type="application/json",
        metadata={"build": "453.0", "fixture": True},
    )
    return event, content


def test_historical_query_import_ranking_and_disappearance_signal(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = ident(ctx)
        source = archive_source(ctx, identity)
        query = ctx.historical_web_453.create_query(
            identity=identity,
            case_id="case453-history",
            original_url="https://example.org/page",
            providers=["internet_archive", "common_crawl"],
            from_time="2020-01-01T00:00:00Z",
            to_time="2024-12-31T23:59:59Z",
            max_captures=20,
            common_crawl_index="CC-MAIN-2024-10",
        )
        requests = {item["provider"]: item for item in query["requests"]}
        assert requests["internet_archive"]["url"].startswith("https://web.archive.org/cdx/search/cdx?")
        assert "CC-MAIN-2024-10-index" in requests["common_crawl"]["url"]

        payload = json.dumps([
            ["timestamp", "original", "statuscode", "mimetype", "digest"],
            ["20200101000000", "https://example.org/page", "200", "text/html", "D1"],
            ["20210101000000", "https://example.org/page", "200", "text/html", "D1"],
            ["20230101000000", "https://example.org/page", "200", "text/html", "D2"],
        ])
        event, content = index_observation(ctx, identity, "case453-history", source, payload)
        with pytest.raises(ValueError, match="does not match referenced content hash"):
            ctx.historical_web_453.import_index_payload(
                identity=identity,
                query_id=query["query_id"],
                provider="internet_archive",
                payload=payload + " ",
                index_event_id=event["event_id"],
                index_content_id=content["content_id"],
            )
        with pytest.raises(ValueError, match="local/private"):
            ctx.historical_web_453.create_query(
                identity=identity,
                case_id="case453-history",
                original_url="http://127.0.0.1/private",
                providers=["internet_archive"],
            )
        imported = ctx.historical_web_453.import_index_payload(
            identity=identity,
            query_id=query["query_id"],
            provider="internet_archive",
            payload=payload,
            index_event_id=event["event_id"],
            index_content_id=content["content_id"],
            source_ref=event["target"],
        )
        assert imported["created"] == 3
        ranked = ctx.historical_web_453.ranked_candidates(query["query_id"])
        assert len(ranked) == 3
        assert any(item["content_digest_changed"] for item in ranked)
        assert all(item["retrieval_ready"] for item in ranked)

        diff = ctx.historical_web_453.compare_texts(
            older_text="Board: Alice\nPartner: Example Foundation\nOld donor page",
            newer_text="Board: Alice\nPartner: New Foundation",
        )
        assert "Old donor page" in diff["possible_disappearances"]
        assert diff["change_signal_not_truth"] is True
        assert ctx.historical_web_453.verify_integrity()["valid"]


def test_historical_candidate_links_to_build428_archive_chain(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = ident(ctx)
        source = archive_source(ctx, identity)
        payload = json.dumps([
            ["timestamp", "original", "statuscode", "mimetype", "digest"],
            ["20220304050607", "https://example.org/page", "200", "text/html", "ARCHIVE-DIGEST"],
        ])
        query = ctx.historical_web_453.create_query(
            identity=identity,
            case_id="case453-link",
            original_url="https://example.org/page",
            providers=["internet_archive"],
        )
        index_event, index_content = index_observation(ctx, identity, "case453-link", source, payload)
        imported = ctx.historical_web_453.import_index_payload(
            identity=identity,
            query_id=query["query_id"],
            provider="internet_archive",
            payload=payload,
            index_event_id=index_event["event_id"],
            index_content_id=index_content["content_id"],
        )
        candidate = ctx.historical_web_453.candidates(query["query_id"])[0]

        capture_event = ctx.build422.record_event(
            identity=identity,
            case_id="case453-link",
            source_id=source["source_id"],
            target=candidate["archive_url"],
            method="archive",
            status="retrieved",
        )
        capture_content = ctx.build423.ingest_content(
            identity=identity,
            event_id=capture_event["event_id"],
            content="<html>historical page</html>",
            media_type="text/html",
            metadata={"fixture": True},
        )
        linked = ctx.historical_web_453.link_retrieved_capture(
            identity=identity,
            candidate_id=imported["candidate_ids"][0],
            archive_source_id=source["source_id"],
            retrieved_event_id=capture_event["event_id"],
            content_id=capture_content["content_id"],
        )
        timeline = ctx.archive_history_428.timeline("case453-link", "https://example.org/page")
        assert linked["archive_capture_id"] == timeline[0]["archive_capture_id"]
        assert timeline[0]["captured_at"] == "2022-03-04T05:06:07+00:00"


def test_recovery_point_verification_staging_and_tamper_detection(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = ident(ctx)
        ctx.build421.register_source(
            identity=identity,
            name="Recovery fixture source",
            source_type="dataset",
            capabilities=["records"],
        )
        point = ctx.recovery_453.create_recovery_point(
            identity=identity,
            label="before build 454",
            confirmation="RECOVERY 453 CREATE",
        )
        verified = ctx.recovery_453.verify(point["recovery_id"])
        assert verified["valid"]
        staged = ctx.recovery_453.stage_restore(
            identity=identity,
            recovery_id=point["recovery_id"],
            confirmation="RECOVERY 453 STAGE",
        )
        assert staged["verified"]
        assert staged["active_database_overwritten"] is False
        assert Path(staged["staged_file"]).is_file()

        database_path = tmp_path / "recovery_453" / point["database_file"]
        with database_path.open("ab") as handle:
            handle.write(b"tamper")
        assert not ctx.recovery_453.verify(point["recovery_id"])["valid"]

        forged = dict(identity)
        forged["user_id"] = "fabricated-user"
        with pytest.raises(PermissionError):
            ctx.recovery_453.create_recovery_point(
                identity=forged,
                label="forged role",
                confirmation="RECOVERY 453 CREATE",
            )


def test_build453_status_health_and_runtime_contract(tmp_path):
    app = create_workspace_app453(base_dir=tmp_path)
    try:
        status = app.state.context.build453.build453_status()
        assert status["build"] == "453.0"
        assert status["focused_development_build"] is True
        assert status["full_research_gate_this_build"] is False
        assert status["next_hard_checkpoint"] == "455.0"
        assert status["historical_web"]["direct_network_authority"] is False
        assert status["recovery"]["automatic_live_database_overwrite"] is False
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"ok": True, "status": "ok", "build": "453.0"}
    finally:
        app.state.context.close()


def test_build453_version_launcher_and_five_build_ci_contract():
    assert 'version = "453.0.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'BUILD = "453.0"' in (ROOT / "eagleeye_pro/version.py").read_text(encoding="utf-8")
    assert "app453 import create_workspace_app453" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text(encoding="utf-8")
    assert (ROOT / "EAGLEEYE_PRO_453_0.py").exists()
    assert (ROOT / "INSTALL_EAGLEEYE_453.py").exists()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "EAGLEEYE_PRO_450_0.py" in readme
    assert "test_build450_integrated.py" in readme
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "build_number % 5 == 0" in ci
    assert "test_build453_historical_recovery.py" in ci
