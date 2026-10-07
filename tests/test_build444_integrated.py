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


def case(c, title="Public Social 444"):
    return c.build444.team_create_case(
        identity=ident(c),
        title=title,
        client="QA",
        purpose="controlled public social acquisition qualification",
        legal_basis="public_data",
    )


def source(c, identity, suffix, *, adapter, fixture=True, allowed_hosts=None, generic=False):
    host = f"social444-{suffix}.example.org"
    coverage = {
        "social_adapter": adapter,
        "allowed_object_hosts": allowed_hosts or [host],
    }
    if fixture:
        coverage.update({"fixture_only": True, "live_execution_forbidden": True})
    if generic:
        coverage["generic_schema"] = "eagleeye_public_social_v1"
    return c.build421.register_source(
        identity=identity,
        name=f"Social 444 {suffix}",
        source_type="social",
        access_mode="public",
        base_url=f"https://{host}/public.json",
        capabilities=["public_posts", "public_json"],
        coverage=coverage,
    )


def transport_for(src, crawl_task, payload, media="application/json"):
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
                json.dumps(payload).encode("utf-8"),
                2,
            ),
        }
    )


def replay(c, identity, case_id, src, payload, media="application/json"):
    crawl_task = c.build444.create_public_social_task_444(
        identity=identity,
        case_id=case_id,
        source_id=src["source_id"],
    )
    transport = transport_for(src, crawl_task, payload, media)
    old_sleep = c.surface_hardening_442.sleep
    c.surface_hardening_442.sleep = lambda _seconds: None
    try:
        result = c.public_social_444.execute_replay(
            identity=identity,
            case_id=case_id,
            task_id=crawl_task["task_id"],
            transport=transport,
            resolver=lambda _host: [PUBLIC_IP],
        )
    finally:
        c.surface_hardening_442.sleep = old_sleep
    return crawl_task, result


def test_build444_selftest_routes_public_json_into_build432(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c)["case_id"]
        result = c.build444.run_public_social_case_selftest(identity=i, case_id=cid)
        assert result["result"] == "PASS"
        assert all(result["checks"].values())
        assert result["run"]["ingested_objects"] == 1
        assert c.public_social_444.verify_integrity()["valid"]


def test_mastodon_public_and_unlisted_are_accepted_private_is_skipped(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Mastodon 444")["case_id"]
        src = source(c, i, "mastodon", adapter="mastodon_public")
        host = src["base_url"].split("/")[2]
        payload = [
            {
                "id": "m-public",
                "created_at": "2026-09-26T17:00:00Z",
                "url": f"https://{host}/@alice/1",
                "visibility": "public",
                "content": "<p>Public status</p>",
                "account": {"id": "a1", "acct": "alice"},
                "replies_count": 1,
                "reblogs_count": 2,
                "favourites_count": 3,
            },
            {
                "id": "m-unlisted",
                "created_at": "2026-09-26T17:05:00Z",
                "url": f"https://{host}/@alice/2",
                "visibility": "unlisted",
                "content": "<p>Unlisted but publicly accessible</p>",
                "account": {"id": "a1", "acct": "alice"},
            },
            {
                "id": "m-private",
                "created_at": "2026-09-26T17:10:00Z",
                "url": f"https://{host}/@alice/3",
                "visibility": "private",
                "content": "<p>Private</p>",
                "account": {"id": "a1", "acct": "alice"},
            },
        ]
        _task, result = replay(c, i, cid, src, payload)
        assert result["run"]["ingested_objects"] == 2
        assert result["run"]["skipped_objects"] == 1
        rows = c.social_public_432.case_items(cid, adapter="mastodon_public", include_fixtures=False)
        assert {r["external_object_id"] for r in rows} == {"m-public", "m-unlisted"}
        assert all(r["visibility"] in {"public", "unlisted"} for r in rows)


def test_bluesky_appview_feed_normalizes_post_without_graph_expansion(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Bluesky 444")["case_id"]
        api_host = "social444-bluesky.example.org"
        src = source(
            c,
            i,
            "bluesky",
            adapter="bluesky_public",
            allowed_hosts=[api_host, "bsky.app"],
        )
        payload = {
            "feed": [
                {
                    "post": {
                        "uri": "at://did:plc:example/app.bsky.feed.post/rkey123",
                        "author": {"did": "did:plc:example", "handle": "alice.example"},
                        "record": {
                            "text": "Public Bluesky post",
                            "createdAt": "2026-09-26T18:00:00Z",
                            "langs": ["en"],
                        },
                        "replyCount": 2,
                        "repostCount": 3,
                        "likeCount": 4,
                        "quoteCount": 1,
                        "indexedAt": "2026-09-26T18:00:10Z",
                    }
                }
            ],
            "cursor": "ignored-by-build-444",
        }
        _task, result = replay(c, i, cid, src, payload)
        assert result["run"]["ingested_objects"] == 1
        assert result["automatic_pagination"] is False
        assert result["social_graph_enumeration"] is False
        row = c.social_public_432.case_items(cid, adapter="bluesky_public", include_fixtures=False)[0]
        assert row["external_object_id"].startswith("at://")
        assert row["canonical_url"] == "https://bsky.app/profile/alice.example/post/rkey123"
        assert row["metrics"]["likes"] == 4


def test_generic_schema_duplicate_is_skipped_on_second_run(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Duplicate 444")["case_id"]
        src = source(c, i, "dup", adapter="generic_public", generic=True)
        host = src["base_url"].split("/")[2]
        payload = {
            "items": [
                {
                    "external_object_id": "dup-444",
                    "canonical_url": f"https://{host}/posts/dup",
                    "published_at": "2026-09-26T19:00:00Z",
                    "text": "Duplicate public post",
                    "platform": "generic",
                    "visibility": "public",
                }
            ]
        }
        _t1, first = replay(c, i, cid, src, payload)
        assert first["run"]["ingested_objects"] == 1
        c.db.execute("DELETE FROM surface_rate_window_442 WHERE source_id=?", (src["source_id"],))
        _t2, second = replay(c, i, cid, src, payload)
        assert second["run"]["ingested_objects"] == 0
        assert second["run"]["duplicate_objects"] == 1
        assert len(c.social_public_432.case_items(cid, include_fixtures=False)) == 1


def test_object_host_outside_allowlist_is_skipped(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Host boundary 444")["case_id"]
        src = source(c, i, "host", adapter="generic_public", generic=True)
        payload = {
            "items": [
                {
                    "external_object_id": "outside-444",
                    "canonical_url": "https://outside.example.net/post/1",
                    "published_at": "2026-09-26T20:00:00Z",
                    "text": "Outside host",
                    "platform": "generic",
                    "visibility": "public",
                }
            ]
        }
        _task, result = replay(c, i, cid, src, payload)
        assert result["run"]["ingested_objects"] == 0
        assert result["run"]["skipped_objects"] == 1
        assert result["run"]["items"][0]["reason"] == "object_host_outside_source_allowlist"


def test_credential_like_response_fields_are_rejected_before_social_persistence(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Credential boundary 444")["case_id"]
        src = source(c, i, "credential", adapter="generic_public", generic=True)
        host = src["base_url"].split("/")[2]
        payload = {
            "access_token": "must-not-be-ingested",
            "items": [
                {
                    "external_object_id": "cred-444",
                    "canonical_url": f"https://{host}/post/1",
                    "published_at": "2026-09-26T21:00:00Z",
                    "text": "Public item",
                    "visibility": "public",
                }
            ],
        }
        crawl_task = c.build444.create_public_social_task_444(
            identity=i, case_id=cid, source_id=src["source_id"]
        )
        transport = transport_for(src, crawl_task, payload)
        with pytest.raises(ValueError, match="credential/session-like"):
            c.public_social_444.execute_replay(
                identity=i,
                case_id=cid,
                task_id=crawl_task["task_id"],
                transport=transport,
                resolver=lambda _host: [PUBLIC_IP],
            )
        assert c.social_public_432.case_items(cid, include_fixtures=False) == []


def test_generic_profile_collection_time_is_labeled_not_presented_as_publication_time(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Profile timestamp 444")["case_id"]
        src = source(c, i, "profile", adapter="generic_public", generic=True)
        host = src["base_url"].split("/")[2]
        payload = {
            "items": [
                {
                    "external_object_id": "profile-444",
                    "canonical_url": f"https://{host}/profile/alice",
                    "text": "Public profile description",
                    "platform": "generic",
                    "object_type": "profile",
                    "visibility": "public",
                    "account_handle": "@alice",
                }
            ]
        }
        _task, result = replay(c, i, cid, src, payload)
        assert result["run"]["ingested_objects"] == 1
        row = c.social_public_432.case_items(cid, include_fixtures=False)[0]
        assert row["metadata"]["timestamp_semantics"] == "observed_at_collection_time"


def test_live_requires_exact_confirmation_and_fixture_never_goes_live(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Live boundary 444")["case_id"]
        src = source(c, i, "live", adapter="generic_public", generic=True, fixture=True)
        crawl_task = c.build444.create_public_social_task_444(
            identity=i, case_id=cid, source_id=src["source_id"]
        )
        with pytest.raises(PermissionError):
            c.public_social_444.execute_live(
                identity=i,
                case_id=cid,
                task_id=crawl_task["task_id"],
                confirmation="GO",
            )
        assert c.crawler_core_425.get(crawl_task["task_id"])["state"] == "planned"

        with pytest.raises(PermissionError):
            c.public_social_444.execute_live(
                identity=i,
                case_id=cid,
                task_id=crawl_task["task_id"],
                confirmation="SOCIAL444_LIVE",
            )
        assert c.crawler_core_425.get(crawl_task["task_id"])["state"] == "planned"


def test_run_tamper_breaks_integrity(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Tamper 444")["case_id"]
        result = c.build444.run_public_social_case_selftest(identity=i, case_id=cid)
        run_id = result["run"]["run_id"]
        c.db.execute(
            "UPDATE social_acquisition_run_444 SET ingested_objects=99 WHERE run_id=?",
            (run_id,),
        )
        assert c.public_social_444.verify_integrity()["valid"] is False


def test_contract_version_launcher_and_checkpoint_position(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as c:
        status = c.build444.public_social_status_444()
        assert status["version_coherent"]
        assert status["phase"] == 20
        assert status["phase20_builds_completed"] == 4
        assert status["surface_retrieval_hardened"]
        assert status["live_news_adapter_complete_for_public_feeds"]
        assert status["public_social_adapter_complete_for_reviewed_json_endpoints"]
        assert status["core_public_acquisition_paths_implemented"]
        assert status["mastodon_public_json"]
        assert status["bluesky_public_appview_json"]
        assert status["authenticated_social_supported"] is False
        assert status["private_or_direct_content_supported"] is False
        assert status["automatic_pagination"] is False
        assert status["follower_following_enumeration"] is False
        assert status["social_graph_enumeration"] is False
        assert status["automatic_live_execution"] is False
        assert status["general_live_collection_complete"] is False
        assert status["production_release_ready"] is False
        assert status["next_build"] == "445.0"
        assert status["next_hard_checkpoint"] == "445.0"

    import eagleeye.interfaces.web.app444 as appmod

    calls = []
    monkeypatch.setattr(
        appmod,
        "create_workspace_app444",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    namespace = runpy.run_path(str(ROOT / "EAGLEEYE_PRO_450_0.py"), run_name="__mp_main__")
    assert calls == []
    assert namespace["app"] is None
    assert "app452 import create_workspace_app452" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text()
    assert (ROOT / "BUILD_444_CASE_TEST.md").exists()
    assert (ROOT / "README_BUILD_444_0.md").exists()
    readme = (ROOT / "README.md").read_text()
    assert "EAGLEEYE_PRO_450_0.py" in readme
    assert "test_build450_integrated.py" in readme
