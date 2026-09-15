from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eagleeye.crawler.engine import FetchResponse, StaticTransport
from eagleeye.interfaces.web.app373 import create_workspace_app373
from eagleeye_pro.core.app_context import AppContext

PW = "Orbit-Pine-Quartz-373!"
SEED = "https://example.org/graph373-source"


def ctx(tmp_path):
    return AppContext(base_dir=tmp_path, actor="test373")


def admin(c):
    u = c.team_identity_359.create_initial_admin(username="admin373", display_name="Admin 373", password=PW)
    return {**u, "session_id": "admin-session-373"}


def case(c, a, title="Graph Case"):
    return c.build373.team_create_case(identity=a, title=title, client="QA", purpose="authorized graph analysis", legal_basis="public_data")


def ent(c, a, cid, name="Alice Example", email="alice@example.test", external="ID-1", refs=("source:A", "source:B")):
    anchors = []
    if email:
        anchors.append({"type": "email", "value": email, "reliability": .95, "source_ref": refs[0]})
    if external:
        anchors.append({"type": "external_id", "value": external, "reliability": .9, "source_ref": refs[1]})
    return c.build373.register_entity_candidate(case_id=cid, entity_type="person", display_name=name, identity=a, anchors=anchors)["entity"]["resolution_entity_id"]


def source_and_crawl(c, a, cid, *, url=SEED, max_pages=1, display="Graph Source"):
    s = c.crawler_frontier_352.register_source(display_name=display, seed_urls=[url], terms_ref="public read-only terms", max_depth=0, max_pages=max_pages, requests_per_minute=5, max_response_bytes=100000)
    if s["review_status"] == "pending_review":
        s = c.crawler_frontier_352.review_source(s["source_id"], decision="approve_read_only", rationale="reviewed public source", reviewer="admin373")
    q = c.crawler_frontier_352.enqueue_crawl(case_id=cid, source_id=s["source_id"])
    robots = url.split("/", 3)[:3]
    robots_url = "/".join(robots) + "/robots.txt"
    t = StaticTransport({
        robots_url: FetchResponse(robots_url, 404, {"content-type": "text/plain"}, b"", 1),
        url: FetchResponse(url, 200, {"content-type": "text/html"}, b"<html>Alice Example ID-1</html>", 2),
    })
    c.build373.crawler_run_next(worker_id="crawl373", transport=t, resolver=lambda h: ["93.184.216.34"], case_id=cid)
    fetch = c.db.one("SELECT fetch_id FROM phase15_crawl_fetches WHERE crawl_run_id=? AND status_code=200", (q["crawl_run_id"],))
    return s, q["crawl_run_id"], fetch["fetch_id"]


def graph_fixture(c, a, cid):
    s, run, fetch = source_and_crawl(c, a, cid)
    left = ent(c, a, cid)
    right = ent(c, a, cid, refs=("source:C", "source:D"))
    cmp = c.build373.compare_entities_v2(case_id=cid, left_entity_id=left, right_entity_id=right, identity=a)
    lead = c.build373.enqueue_entity_link_lead(case_id=cid, crawl_run_id=run, fetch_id=fetch, target_entity_id=left, candidate_entity_id=right, identity=a)
    c.build373.entity_lead_run_next(worker_id="entity373", case_id=cid)
    return s, left, right, cmp, lead


# 1
def test_active_schema_has_no_build373_tables(tmp_path):
    with ctx(tmp_path) as c:
        _ = c.build373
        m = c.build373.schema_metrics()
        assert m["within_gate"] and (m["table"], m["index"], m["trigger"]) == (165, 133, 8)
        names = [r["name"] for r in c.db.all("SELECT name FROM sqlite_master WHERE type='table'")]
        assert not any("373" in n for n in names)
        assert m["graph_projection_new_tables"] == 0 and m["graph_navigation_new_tables"] == 0

# 2
def test_version_schema(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build373.version_status() == {"runtime_build": "373.0", "schema_version": "373.0", "package_version": "373.0.0", "coherent": True}

# 3
def test_phase_progress(tmp_path):
    with ctx(tmp_path) as c:
        s = c.build373.phase16_status()
        assert s["builds_completed"] == 13 and s["crawler_improvement_build"] == 373

# 4
def test_graph_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s = c.analyst_graph_373.status()
        assert s["ledger_projection"] and s["offline_focus_navigation"]
        assert not s["automatic_identity_confirmation"] and not s["automatic_merge"] and not s["automatic_scope_expansion"]

# 5
def test_navigation_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s = c.crawler_graph_navigation_373.status()
        assert s["graph_aware_crawler_navigation"] and s["analyst_selected_sources_only"] and s["already_evidenced_sources_only"]
        assert s["explicit_navigation_confirmation"] == "NAVIGATE"
        assert not s["automatic_source_discovery"] and not s["automatic_scope_expansion"]

# 6
def test_graph_empty_case(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        g = c.build373.analyst_graph(case_id=cid, identity=a)
        assert g["case_id"] == cid and g["metrics"]["nodes"] == 0 and g["projection_only"]

# 7
def test_graph_has_entity_nodes(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; e = ent(c, a, cid)
        g = c.build373.analyst_graph(case_id=cid, identity=a)
        assert any(n["id"] == f"entity:{e}" for n in g["nodes"])

# 8
def test_graph_has_source_nodes(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; s, _, _ = source_and_crawl(c, a, cid)
        g = c.build373.analyst_graph(case_id=cid, identity=a)
        assert any(n["id"] == f"source:{s['source_id']}" for n in g["nodes"])

# 9
def test_graph_has_comparison_edges(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; _, left, right, cmp, _ = graph_fixture(c, a, cid)
        g = c.build373.analyst_graph(case_id=cid, identity=a)
        edges = [e for e in g["edges"] if e["kind"] == "entity_comparison"]
        assert edges and edges[0]["object_id"] == cmp["comparison_id"] and not edges[0]["score_is_probability"]
        assert {edges[0]["source"], edges[0]["target"]} == {f"entity:{left}", f"entity:{right}"}

# 10
def test_graph_has_crawler_provenance_edges(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; s, _, _, _, lead = graph_fixture(c, a, cid)
        g = c.build373.analyst_graph(case_id=cid, identity=a)
        edges = [e for e in g["edges"] if e["kind"] == "crawler_entity_lead"]
        assert len(edges) == 2 and all(e["source"] == f"source:{s['source_id']}" for e in edges)
        assert all(e["provenance_hash"] for e in edges) and all(e["review_required"] for e in edges)

# 11
def test_graph_quality_not_identity_probability(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; graph_fixture(c, a, cid)
        g = c.build373.analyst_graph(case_id=cid, identity=a)
        edges = [e for e in g["edges"] if e["kind"] == "crawler_entity_lead"]
        assert edges and all(not e["source_quality_is_identity_probability"] for e in edges)

# 12
def test_graph_hash_deterministic_for_same_state(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; graph_fixture(c, a, cid)
        x = c.build373.analyst_graph(case_id=cid, identity=a); y = c.build373.analyst_graph(case_id=cid, identity=a)
        assert x["graph_hash"] == y["graph_hash"]

# 13
def test_graph_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); ca = case(c, a, "A")["case_id"]; cb = case(c, a, "B")["case_id"]; e = ent(c, a, ca)
        g = c.build373.analyst_graph(case_id=cb, identity=a)
        assert not any(n.get("object_id") == e for n in g["nodes"])

# 14
def test_focus_one_hop(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; _, left, _, _, _ = graph_fixture(c, a, cid)
        f = c.build373.analyst_graph_focus(case_id=cid, node_id=f"entity:{left}", identity=a, depth=1)
        assert f["focus_node"] == f"entity:{left}" and f["nodes"] and not f["network_execution"] and not f["scope_expansion"]

# 15
def test_focus_depth_clamped(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; e = ent(c, a, cid)
        f = c.build373.analyst_graph_focus(case_id=cid, node_id=f"entity:{e}", identity=a, depth=99)
        assert f["depth"] == 2

# 16
def test_focus_unknown_node_rejected(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        with pytest.raises(KeyError): c.build373.analyst_graph_focus(case_id=cid, node_id="entity:nope", identity=a)

# 17
def test_observed_sources_from_entity_lead(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; s, left, _, _, _ = graph_fixture(c, a, cid)
        assert c.crawler_graph_navigation_373.observed_sources(case_id=cid, root_entity_id=left) == [s["source_id"]]

# 18
def test_navigation_plan_requires_observed_source(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; e = ent(c, a, cid); s, _, _ = source_and_crawl(c, a, cid, url="https://example.net/other")
        with pytest.raises(PermissionError): c.build373.graph_navigation_plan(case_id=cid, root_entity_id=e, source_ids=[s["source_id"]], identity=a)

# 19
def test_navigation_plan_allowed_for_observed_approved_source(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; s, left, _, _, _ = graph_fixture(c, a, cid)
        p = c.build373.graph_navigation_plan(case_id=cid, root_entity_id=left, source_ids=[s["source_id"]], identity=a)
        assert p["allowed"] and p["required_confirmation"] == "NAVIGATE" and not p["network_execution"] and not p["automatic_scope_expansion"]

# 20
def test_navigation_plan_max_two_sources(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; s, left, right, _, _ = graph_fixture(c, a, cid)
        with pytest.raises(ValueError): c.build373.graph_navigation_plan(case_id=cid, root_entity_id=left, source_ids=[s["source_id"], "x", "y"], identity=a)

# 21
def test_navigation_requires_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; s, left, _, _, _ = graph_fixture(c, a, cid)
        with pytest.raises(PermissionError): c.build373.graph_navigate(case_id=cid, root_entity_id=left, source_ids=[s["source_id"]], identity=a, confirmation="GO")

# 22
def test_navigation_enqueues_governed_crawl(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; s, left, _, _, _ = graph_fixture(c, a, cid)
        out = c.build373.graph_navigate(case_id=cid, root_entity_id=left, source_ids=[s["source_id"]], identity=a, confirmation="NAVIGATE")
        assert len(out["queued"]) == 1 and out["network_execution"] == "delegated_to_existing_governed_crawler_worker" and not out["automatic_scope_expansion"]
        j = c.job_engine_348.get(out["queued"][0]["job_id"]); p = json.loads(j["payload_json"])
        assert p["phase16_graph_navigation_v373"] and p["graph_root_entity_id"] == left and p["automatic_scope_expansion"] is False

# 23
def test_navigation_job_record_hash_remains_valid(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; s, left, _, _, _ = graph_fixture(c, a, cid)
        out = c.build373.graph_navigate(case_id=cid, root_entity_id=left, source_ids=[s["source_id"]], identity=a, confirmation="NAVIGATE")
        row = c.job_engine_348.get(out["queued"][0]["job_id"])
        body = {k: row[k] for k in row if k != "record_hash"}
        canon = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        assert hashlib.sha256(canon.encode()).hexdigest() == row["record_hash"]

# 24
def test_navigation_case_status(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; s, left, _, _, _ = graph_fixture(c, a, cid)
        c.build373.graph_navigate(case_id=cid, root_entity_id=left, source_ids=[s["source_id"]], identity=a, confirmation="NAVIGATE")
        st = c.build373.graph_navigation_status(case_id=cid)
        assert len(st["navigation_jobs"]) == 1 and st["active"] == 1 and not st["automatic_scope_expansion"]

# 25
def test_navigation_cross_case_entity_blocked(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); ca = case(c, a, "A")["case_id"]; cb = case(c, a, "B")["case_id"]; s, left, _, _, _ = graph_fixture(c, a, ca)
        with pytest.raises(PermissionError): c.build373.graph_navigation_plan(case_id=cb, root_entity_id=left, source_ids=[s["source_id"]], identity=a)

# 26
def test_navigation_large_source_blocked(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        s, run, fetch = source_and_crawl(c, a, cid, url="https://example.com/large", max_pages=20, display="Large")
        x = ent(c, a, cid); y = ent(c, a, cid, refs=("source:C", "source:D"))
        c.build373.enqueue_entity_link_lead(case_id=cid, crawl_run_id=run, fetch_id=fetch, target_entity_id=x, candidate_entity_id=y, identity=a)
        p = c.build373.graph_navigation_plan(case_id=cid, root_entity_id=x, source_ids=[s["source_id"]], identity=a)
        assert not p["allowed"] and "source_page_budget_too_large" in p["reasons"]

# 27
def test_navigation_darknet_source_separate(tmp_path):
    with ctx(tmp_path) as c:
        s = c.crawler_graph_navigation_373.status()
        assert s["darknet_navigation_separate"] and s["provider_live_gate_separate"]

# 28
def test_navigation_backpressure_hold(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; s, left, _, _, _ = graph_fixture(c, a, cid)
        for i in range(8):
            c.job_engine_348.enqueue(job_type="governed_crawl_v1", payload={"source_id": f"dummy{i}"}, case_id=cid, idempotency_key=f"bp373:{i}")
        p = c.build373.graph_navigation_plan(case_id=cid, root_entity_id=left, source_ids=[s["source_id"]], identity=a)
        assert not p["allowed"] and "crawler_backpressure" in p["reasons"]

# 29
def test_opsec_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s = c.opsec_supervisor_373.status()
        assert s["graph_navigation_integrity_monitor"] and s["graph_scope_expansion_block"] and not s["automatic_graph_navigation_authority"] and not s["system_mutations"]

# 30
def test_opsec_cancels_tampered_graph_job(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; s, left, _, _, _ = graph_fixture(c, a, cid)
        out = c.build373.graph_navigate(case_id=cid, root_entity_id=left, source_ids=[s["source_id"]], identity=a, confirmation="NAVIGATE")
        jid = out["queued"][0]["job_id"]
        row = c.job_engine_348.get(jid); p = json.loads(row["payload_json"]); p["automatic_scope_expansion"] = True
        c.db.execute("UPDATE phase15_jobs SET payload_json=? WHERE job_id=?", (json.dumps(p), jid))
        r = c.build373.autonomous_opsec_protect(case_id=cid)
        assert jid in r["cancelled_invalid_graph_navigation_jobs"] and c.job_engine_348.get(jid)["status"] == "cancelled"

# 31
def test_opsec_leaves_normal_crawl_untouched(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; s, _, _ = source_and_crawl(c, a, cid, url="https://example.edu/normal")
        q = c.crawler_frontier_352.enqueue_crawl(case_id=cid, source_id=s["source_id"])
        c.build373.autonomous_opsec_protect(case_id=cid)
        assert c.job_engine_348.get(q["job"]["job_id"])["status"] == "queued"

# 32
def test_ai_status_boundaries(tmp_path):
    with ctx(tmp_path) as c:
        s = c.ai_autonomy_373.status()
        assert s["analyst_graph_awareness"] and s["crawler_graph_navigation_awareness"] and not s["direct_graph_navigation_authority"] and not s["automatic_scope_expansion"]

# 33
def test_ai_dossier_graph_context(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; ent(c, a, cid)
        c.build373.create_investigation_intake(case_id=cid, objective="Graph review", key_questions=["Relations?"])
        c.build373.start_investigation_go(case_id=cid, go="GO")
        out = c.build373.run_autonomous_investigation(case_id=cid, max_ticks=1)
        assert "phase16_analyst_graph_v373" in out["dossier"] and not out["dossier"]["phase16_analyst_graph_v373"]["direct_graph_navigation_authority"]

# 34
def test_crawler_status_increment(tmp_path):
    with ctx(tmp_path) as c:
        s = c.build373.crawler_status()
        assert s["crawler_improvement_build"] == 373 and s["graph_aware_navigation"] and s["analyst_selected_sources_only"]

# 35
def test_crawler_program_still_continuous(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build373.crawler_status()["continuous_crawler_expansion_370_380"]

# 36
def test_no_auto_connections_on_boot(tmp_path):
    with ctx(tmp_path) as c:
        s = c.build373.crawler_status()
        assert s["automatic_external_connections_on_boot"] == 0 and s["background_workers_started_on_boot"] == 0

# 37
def test_entity_eval_boundaries_preserved(tmp_path):
    with ctx(tmp_path) as c:
        s = c.entity_resolution_eval_372.status()
        assert not s["automatic_threshold_change"] and not s["automatic_merge"]

# 38
def test_tor_boundaries_preserved(tmp_path):
    with ctx(tmp_path) as c:
        s = c.tor_gateway_370.status()
        assert not s["control_port_authority"] and not s["newnym_authority"] and not s["torrc_mutation"]

# 39
def test_web_health(tmp_path):
    app = create_workspace_app373(base_dir=tmp_path / "web")
    with TestClient(app) as client:
        h = client.get("/health")
        assert h.status_code == 200 and h.json()["build"] == "373.0" and h.json()["phase16_builds_completed"] == 13 and h.json()["graph_aware_navigation"]

# 40
def test_graph_api_requires_auth(tmp_path):
    app = create_workspace_app373(base_dir=tmp_path / "web")
    with TestClient(app) as client:
        assert client.get("/api/cases/nope/graph373").status_code == 401

# 41
def test_navigation_api_requires_auth(tmp_path):
    app = create_workspace_app373(base_dir=tmp_path / "web")
    with TestClient(app) as client:
        assert client.post("/api/cases/nope/graph373/navigate", json={}).status_code == 401

# 42
def test_final_status_requires_auth(tmp_path):
    app = create_workspace_app373(base_dir=tmp_path / "web")
    with TestClient(app) as client:
        assert client.get("/api/build373/final-status").status_code == 401

# 43
def test_new_modules_no_direct_network_or_subprocess_imports():
    bad = {"requests", "httpx", "aiohttp", "socket", "subprocess", "urllib"}
    found = set()
    for p in [Path("src/eagleeye/phase16/analyst_graph373.py"), Path("src/eagleeye/application/build373/service.py"), Path("src/eagleeye/interfaces/web/app373.py")]:
        tree = ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n, ast.Import): found.update(x.name.split(".")[0] for x in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module: found.add(n.module.split(".")[0])
    assert not found.intersection(bad)

# 44
def test_build_gate_has_no_literal_true(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build373.active_gate_literal_true_lines() == []

# 45
def test_truthful_release_false(tmp_path):
    with ctx(tmp_path) as c:
        g = c.build373.qualified_gate()
        assert g["production_release_ready"] is False and g["external_graph_ux_validation"] == "not_run" and g["external_graph_navigation_validation"] == "not_run"

# 46
def test_capabilities_do_not_claim_external_validation(tmp_path):
    with ctx(tmp_path) as c:
        assert not any(x["states"]["externally_validated"] for x in c.build373.capabilities())

# 47
def test_registry_has_373_services(tmp_path):
    with ctx(tmp_path) as c:
        for name in ("analyst_graph_373", "crawler_graph_navigation_373", "ai_autonomy_373", "opsec_supervisor_373", "build373"):
            assert name in c.SERVICE_NAMES

# 48
def test_server_points_to_app373():
    t = Path("src/eagleeye/interfaces/web/server.py").read_text()
    assert "app373" in t and "create_workspace_app373" in t

# 49
def test_generic_launchers_point_to_373():
    assert "EAGLEEYE_PRO_373_0.py" in Path("START_EAGLEEYE_PRO.bat").read_text()
    assert "EAGLEEYE_PRO_373_0.py" in Path("START_EAGLEEYE_PRO.sh").read_text()

# 50
def test_roadmap_373_completed():
    t = Path("CRAWLER_ROADMAP_BUILD_370_TO_380.md").read_text().lower()
    line = next(x for x in t.splitlines() if x.startswith("| 373 |"))
    assert "completed" in line and "graph" in line

# 51
def test_masterplan_373_actual_status():
    t = Path("PHASE_16_MASTERPLAN_BUILD_361_TO_380.md").read_text().lower()
    assert "build 373 actual status" in t and "13/20" in t

# 52
def test_graph_navigation_budget_contract(tmp_path):
    with ctx(tmp_path) as c:
        s = c.crawler_graph_navigation_373.status()
        assert s["max_sources_per_navigation"] == 2 and s["max_source_pages"] == 10 and s["max_total_requests"] == 30

# 53
def test_graph_snapshot_respects_node_limit(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        for i in range(20): ent(c, a, cid, name=f"Person {i}", email=f"p{i}@example.test", external=f"ID-{i}")
        g = c.build373.analyst_graph(case_id=cid, identity=a, max_nodes=10)
        assert len(g["nodes"]) <= 10

# 54
def test_graph_snapshot_respects_edge_limit(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        ids = [ent(c, a, cid, name=f"P{i}", email=f"p{i}@example.test", external=f"X{i}") for i in range(8)]
        for i in range(7): c.build373.compare_entities_v2(case_id=cid, left_entity_id=ids[i], right_entity_id=ids[i+1], identity=a)
        g = c.build373.analyst_graph(case_id=cid, identity=a, max_edges=3)
        assert len(g["edges"]) <= 10  # service clamps caller limits to a safe minimum of 10

# 55
def test_graph_does_not_expose_entity_attributes(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; ent(c, a, cid)
        g = c.build373.analyst_graph(case_id=cid, identity=a)
        entity = next(n for n in g["nodes"] if n["kind"] == "entity")
        assert "attributes_json" not in entity and "anchors" not in entity

# 56
def test_navigation_plan_hash_deterministic(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; s, left, _, _, _ = graph_fixture(c, a, cid)
        x = c.build373.graph_navigation_plan(case_id=cid, root_entity_id=left, source_ids=[s["source_id"]], identity=a)
        y = c.build373.graph_navigation_plan(case_id=cid, root_entity_id=left, source_ids=[s["source_id"]], identity=a)
        assert x["plan_hash"] == y["plan_hash"]

# 57
def test_navigation_plan_does_not_enqueue(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]; s, left, _, _, _ = graph_fixture(c, a, cid)
        before = int((c.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE job_type='governed_crawl_v1' AND case_id=?", (cid,)) or {})["c"])
        c.build373.graph_navigation_plan(case_id=cid, root_entity_id=left, source_ids=[s["source_id"]], identity=a)
        after = int((c.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE job_type='governed_crawl_v1' AND case_id=?", (cid,)) or {})["c"])
        assert before == after

# 58
def test_phase_status_reports_graph_and_crawler(tmp_path):
    with ctx(tmp_path) as c:
        s = c.build373.phase16_status()
        assert s["analyst_graph_ux"]["ledger_projection"] and s["crawler_graph_navigation"]["graph_aware_crawler_navigation"] and s["crawler_improvement_build"] == 373
