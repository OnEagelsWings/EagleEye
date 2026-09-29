from pathlib import Path
import json
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


def case(c, title="Live News 443"):
    return c.build443.team_create_case(
        identity=ident(c),
        title=title,
        client="QA",
        purpose="live public news acquisition qualification",
        legal_basis="public_data",
    )


def source(c, identity, suffix, *, source_type="rss", fixture=True, allowed_hosts=None):
    host = f"news443-{suffix}.example.org"
    return c.build421.register_source(
        identity=identity,
        name=f"News 443 {suffix}",
        source_type=source_type,
        access_mode="public",
        base_url=f"https://{host}/feed",
        capabilities=["news_feed", "public_articles"],
        coverage={
            **({"fixture_only": True, "live_execution_forbidden": True} if fixture else {}),
            "allowed_article_hosts": allowed_hosts or [host],
        },
    )


def feed_transport(src, crawl_task, body, media):
    host = src["base_url"].split("/")[2]
    robots = f"https://{host}/robots.txt"
    return StaticTransport(
        {
            robots: FetchResponse(
                robots,
                200,
                {"content-type": "text/plain"},
                b"User-agent: *\nAllow: /\n",
                1,
            ),
            crawl_task["target"]: FetchResponse(
                crawl_task["target"],
                200,
                {"content-type": media},
                body,
                2,
            ),
        }
    )


def execute_replay(c, identity, case_id, src, body, media):
    crawl_task = c.build443.create_news_feed_task_443(
        identity=identity,
        case_id=case_id,
        source_id=src["source_id"],
    )
    transport = feed_transport(src, crawl_task, body, media)
    old_sleep = c.surface_hardening_442.sleep
    c.surface_hardening_442.sleep = lambda _seconds: None
    try:
        result = c.live_news_443.execute_replay(
            identity=identity,
            case_id=case_id,
            task_id=crawl_task["task_id"],
            transport=transport,
            resolver=lambda _host: [PUBLIC_IP],
        )
    finally:
        c.surface_hardening_442.sleep = old_sleep
    return crawl_task, result


def test_build443_selftest_routes_feed_to_429_and_431_without_fake_430(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c)["case_id"]
        before = len(c.news_extraction_430.case_extractions(cid))
        result = c.build443.run_live_news_case_selftest(identity=i, case_id=cid)
        after = len(c.news_extraction_430.case_extractions(cid))
        assert result["result"] == "PASS"
        assert all(result["checks"].values())
        assert after == before
        assert result["run"]["feed_kind"] == "rss"
        assert result["run"]["ingested_items"] == 2
        assert c.live_news_443.verify_integrity()["valid"]


def test_atom_feed_is_normalized_into_news_items(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Atom 443")["case_id"]
        src = source(c, i, "atom")
        host = src["base_url"].split("/")[2]
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Atom fixture</title>
<entry>
<title>Atom report</title>
<id>tag:example.org,2026:atom-1</id>
<published>2026-09-26T12:00:00Z</published>
<link rel="alternate" href="https://{host}/atom-report"/>
<author><name>Example Author</name></author>
<summary>Public atom summary.</summary>
</entry>
</feed>""".encode()
        _task, result = execute_replay(c, i, cid, src, body, "application/atom+xml")
        assert result["run"]["feed_kind"] == "atom"
        assert result["run"]["ingested_items"] == 1
        item = c.news_connectors_429.case_items(cid)[0]
        assert item["connector_kind"] == "atom"
        assert item["title"] == "Atom report"
        assert item["canonical_url"].endswith("/atom-report")


def test_json_feed_is_supported_through_safe_surface_media(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "JSON Feed 443")["case_id"]
        src = source(c, i, "json", source_type="api")
        host = src["base_url"].split("/")[2]
        body = json.dumps(
            {
                "version": "https://jsonfeed.org/version/1.1",
                "title": "JSON fixture",
                "items": [
                    {
                        "id": "json-1",
                        "url": f"https://{host}/json-report",
                        "title": "JSON report",
                        "date_published": "2026-09-26T13:00:00Z",
                        "content_text": "JSON feed summary.",
                        "authors": [{"name": "JSON Author"}],
                    }
                ],
            }
        ).encode()
        _task, result = execute_replay(c, i, cid, src, body, "application/feed+json")
        assert result["run"]["feed_kind"] == "jsonfeed"
        assert result["run"]["ingested_items"] == 1
        item = c.news_connectors_429.case_items(cid)[0]
        assert item["connector_kind"] == "api"
        assert item["author"] == "JSON Author"


def test_duplicate_external_id_is_skipped_on_second_feed_run(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Duplicate 443")["case_id"]
        src = source(c, i, "dup")
        host = src["base_url"].split("/")[2]
        body = f"""<rss version="2.0"><channel>
<item><title>Duplicate report</title><link>https://{host}/dup</link>
<guid>duplicate-443</guid><pubDate>Sat, 26 Sep 2026 14:00:00 GMT</pubDate></item>
</channel></rss>""".encode()
        _t1, first = execute_replay(c, i, cid, src, body, "application/rss+xml")
        assert first["run"]["ingested_items"] == 1

        c.db.execute(
            "DELETE FROM surface_rate_window_442 WHERE source_id=?",
            (src["source_id"],),
        )
        _t2, second = execute_replay(c, i, cid, src, body, "application/rss+xml")
        assert second["run"]["ingested_items"] == 0
        assert second["run"]["duplicate_items"] == 1
        assert len(c.news_connectors_429.case_items(cid)) == 1


def test_item_without_valid_publication_time_is_skipped_not_fabricated(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Missing date 443")["case_id"]
        src = source(c, i, "nodate")
        host = src["base_url"].split("/")[2]
        body = f"""<rss version="2.0"><channel>
<item><title>No date report</title><link>https://{host}/nodate</link><guid>nodate-443</guid></item>
</channel></rss>""".encode()
        _task, result = execute_replay(c, i, cid, src, body, "application/rss+xml")
        assert result["run"]["ingested_items"] == 0
        assert result["run"]["skipped_items"] == 1
        assert result["run"]["items"][0]["reason"] == "missing_or_invalid_publication_time"
        assert c.news_connectors_429.case_items(cid) == []


def test_cross_host_article_link_requires_explicit_source_allowlist(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Host scope 443")["case_id"]
        src = source(c, i, "hostscope")
        body = b"""<rss version="2.0"><channel>
<item><title>Outside host</title><link>https://other.example.net/article</link>
<guid>outside-443</guid><pubDate>Sat, 26 Sep 2026 15:00:00 GMT</pubDate></item>
</channel></rss>"""
        _task, result = execute_replay(c, i, cid, src, body, "application/rss+xml")
        assert result["run"]["ingested_items"] == 0
        assert result["run"]["skipped_items"] == 1
        assert result["run"]["items"][0]["reason"] == "article_host_outside_source_allowlist"


def test_dtd_or_entity_feed_is_rejected(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "DTD 443")["case_id"]
        src = source(c, i, "dtd")
        body = b"""<?xml version="1.0"?>
<!DOCTYPE rss [<!ENTITY x "forbidden">]>
<rss version="2.0"><channel><item><title>&x;</title></item></channel></rss>"""
        crawl_task = c.build443.create_news_feed_task_443(
            identity=i, case_id=cid, source_id=src["source_id"]
        )
        transport = feed_transport(src, crawl_task, body, "application/rss+xml")
        with pytest.raises(ValueError, match="DTD/entity"):
            c.live_news_443.execute_replay(
                identity=i,
                case_id=cid,
                task_id=crawl_task["task_id"],
                transport=transport,
                resolver=lambda _host: [PUBLIC_IP],
            )


def test_live_news_requires_exact_confirmation_and_fixture_stays_off_network(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Live boundary 443")["case_id"]
        src = source(c, i, "liveboundary", fixture=True)
        crawl_task = c.build443.create_news_feed_task_443(
            identity=i, case_id=cid, source_id=src["source_id"]
        )
        with pytest.raises(PermissionError):
            c.live_news_443.execute_live(
                identity=i,
                case_id=cid,
                task_id=crawl_task["task_id"],
                confirmation="GO",
            )
        assert c.crawler_core_425.get(crawl_task["task_id"])["state"] == "planned"

        with pytest.raises(PermissionError):
            c.live_news_443.execute_live(
                identity=i,
                case_id=cid,
                task_id=crawl_task["task_id"],
                confirmation="NEWS443_LIVE",
            )
        assert c.crawler_core_425.get(crawl_task["task_id"])["state"] == "planned"


def test_news_run_tamper_breaks_integrity(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Tamper 443")["case_id"]
        result = c.build443.run_live_news_case_selftest(identity=i, case_id=cid)
        run_id = result["run"]["run_id"]
        c.db.execute(
            "UPDATE news_acquisition_run_443 SET ingested_items=99 WHERE run_id=?",
            (run_id,),
        )
        assert c.live_news_443.verify_integrity()["valid"] is False


def test_contract_version_launcher_and_phase20_position(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as c:
        status = c.build443.live_news_status_443()
        assert status["version_coherent"]
        assert status["phase"] == 20
        assert status["phase20_builds_completed"] == 3
        assert status["surface_retrieval_hardened"]
        assert status["live_news_adapter_complete_for_public_feeds"]
        assert status["supported_feed_kinds"] == ["rss", "atom", "jsonfeed"]
        assert status["public_sources_only"]
        assert status["authenticated_news_sources_supported"] is False
        assert status["build429_integration"]
        assert status["build431_provenance_integration"]
        assert status["automatic_semantic_extraction_430"] is False
        assert status["article_body_fetch"] is False
        assert status["paywall_bypass"] is False
        assert status["automatic_live_execution"] is False
        assert status["public_social_retrieval_adapter_complete"] is False
        assert status["general_live_collection_complete"] is False
        assert status["production_release_ready"] is False
        assert status["next_build"] == "444.0"
        assert status["next_hard_checkpoint"] == "445.0"

    import eagleeye.interfaces.web.app443 as appmod

    calls = []
    monkeypatch.setattr(
        appmod,
        "create_workspace_app443",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    namespace = runpy.run_path(str(ROOT / "EAGLEEYE_PRO_447_0.py"), run_name="__mp_main__")
    assert calls == []
    assert namespace["app"] is None
    assert "app447 import create_workspace_app447" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text()
    assert (ROOT / "BUILD_443_CASE_TEST.md").exists()
    assert (ROOT / "README_BUILD_443_0.md").exists()
    readme = (ROOT / "README.md").read_text()
    assert "EAGLEEYE_PRO_447_0.py" in readme
    assert "test_build447_integrated.py" in readme
