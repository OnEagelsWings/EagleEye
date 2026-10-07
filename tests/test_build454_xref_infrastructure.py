from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app454 import create_workspace_app454

ROOT = Path(__file__).resolve().parents[1]


def ident(ctx):
    if ctx.team_identity_359.bootstrap_required():
        return ctx.team_identity_359.create_initial_admin(
            username="analyst454",
            display_name="Analyst 454",
            password="SecureFixturePassword!2026",
        )
    return ctx.team_identity_359.public_user("analyst454")


def make_case(ctx, identity, title="Build 454 Fixture"):
    return ctx.team_governance_359.create_case(
        identity=identity,
        title=title,
        client="Internal QA",
        purpose="Public OSINT infrastructure correlation regression",
        legal_basis="Legitimate internal software QA",
    )


def register_provider(ctx, identity, *, name, base_url):
    return ctx.build421.register_source(
        identity=identity,
        name=name,
        source_type="api",
        access_mode="public",
        base_url=base_url,
        capabilities=["public_infrastructure_metadata"],
        coverage={"fixture_only": True},
    )


def import_json_for_lookup(ctx, identity, case_id, lookup, source, payload):
    raw = payload.encode("utf-8")
    event = ctx.build422.record_event(
        identity=identity,
        case_id=case_id,
        source_id=source["source_id"],
        target=lookup["request_url"],
        method="api",
        status="retrieved",
        content_sha256=hashlib.sha256(raw).hexdigest(),
        media_type="application/json",
        bytes_count=len(raw),
        provenance={"build": "454.0", "synthetic_fixture": True},
        usage={"public_only": True},
    )
    content = ctx.build423.ingest_content(
        identity=identity,
        event_id=event["event_id"],
        content=payload,
        media_type="application/json",
        metadata={"build454_fixture": True},
    )
    return ctx.infrastructure_454.import_payload(
        identity=identity,
        lookup_id=lookup["lookup_id"],
        payload=payload,
        event_id=event["event_id"],
        content_id=content["content_id"],
        source_ref=lookup["request_url"],
    ), event, content


def test_domain_plan_has_public_rdap_dns_ct_without_network_authority(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = ident(ctx)
        case = make_case(ctx, identity)
        plan = ctx.infrastructure_454.plan_domain(
            identity=identity, case_id=case["case_id"], domain="Example.COM"
        )
        assert plan["domain"] == "example.com"
        assert len(plan["lookups"]) == 6
        assert {x["provider"] for x in plan["lookups"]} == {"rdap_domain", "dns_google", "ct_crtsh"}
        assert sum(x["provider"] == "dns_google" for x in plan["lookups"]) == 4
        assert plan["network_used"] is False
        assert plan["ownership_or_control_determined"] is False
        assert ctx.infrastructure_454.status()["active_scanning"] is False
        assert ctx.infrastructure_454.status()["port_scanning"] is False
        with pytest.raises(ValueError):
            ctx.infrastructure_454.plan_domain(
                identity=identity, case_id=case["case_id"], domain="127.0.0.1"
            )


def test_dns_import_is_hash_bound_and_creates_ip_pivots(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = ident(ctx)
        case = make_case(ctx, identity)
        case_id = case["case_id"]
        plan = ctx.infrastructure_454.plan_domain(identity=identity, case_id=case_id, domain="example.com")
        lookup = next(
            x for x in plan["lookups"]
            if x["provider"] == "dns_google" and "type=A" in x["request_url"]
        )
        source = register_provider(ctx, identity, name="Google Public DNS Fixture", base_url="https://dns.google")
        payload = json.dumps({
            "Status": 0,
            "Answer": [{"name": "example.com.", "type": 1, "TTL": 300, "data": "93.184.216.34"}],
        }, separators=(",", ":"))
        imported, event, content = import_json_for_lookup(
            ctx, identity, case_id, lookup, source, payload
        )
        assert imported["fact_count"] >= 2
        facts = ctx.infrastructure_454.facts(case_id, resource="example.com")
        assert any(f["fact_type"] == "ip" and f["normalized_value"] == "93.184.216.34" for f in facts)

        with pytest.raises(ValueError, match="does not match referenced content hash"):
            ctx.infrastructure_454.import_payload(
                identity=identity,
                lookup_id=lookup["lookup_id"],
                payload=payload + " ",
                event_id=event["event_id"],
                content_id=content["content_id"],
            )

        pivots = ctx.infrastructure_454.plan_ip_pivots(
            identity=identity, case_id=case_id, domain="example.com"
        )
        assert {x["provider"] for x in pivots["lookups"]} == {"rdap_ip", "ripestat_network"}
        assert pivots["active_scanning"] is False
        assert pivots["port_scanning"] is False
        assert ctx.infrastructure_454.verify_integrity()["valid"]


def test_provider_host_contract_blocks_mismatched_event_target(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = ident(ctx)
        case = make_case(ctx, identity)
        case_id = case["case_id"]
        plan = ctx.infrastructure_454.plan_domain(identity=identity, case_id=case_id, domain="example.com")
        lookup = next(x for x in plan["lookups"] if x["provider"] == "rdap_domain")
        source = register_provider(ctx, identity, name="RDAP Fixture", base_url="https://rdap.org")
        payload = json.dumps({"ldhName": "EXAMPLE.COM", "handle": "fixture"})
        raw = payload.encode()
        event = ctx.build422.record_event(
            identity=identity, case_id=case_id, source_id=source["source_id"],
            target="https://example.net/wrong-provider", method="api", status="retrieved",
            content_sha256=hashlib.sha256(raw).hexdigest(),
            media_type="application/json", bytes_count=len(raw),
        )
        content = ctx.build423.ingest_content(
            identity=identity, event_id=event["event_id"], content=payload,
            media_type="application/json",
        )
        with pytest.raises(ValueError, match="target host"):
            ctx.infrastructure_454.import_payload(
                identity=identity, lookup_id=lookup["lookup_id"], payload=payload,
                event_id=event["event_id"], content_id=content["content_id"],
            )


def test_xref_connects_entities_domains_shared_public_infrastructure_and_path(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = ident(ctx)
        case = make_case(ctx, identity)
        case_id = case["case_id"]

        source = register_provider(ctx, identity, name="Google DNS XRef Fixture", base_url="https://dns.google")
        domains = ["alpha.example.com", "beta.example.net"]
        for domain in domains:
            plan = ctx.infrastructure_454.plan_domain(identity=identity, case_id=case_id, domain=domain)
            lookup = next(
                x for x in plan["lookups"]
                if x["provider"] == "dns_google" and "type=A" in x["request_url"]
            )
            payload = json.dumps({
                "Status": 0,
                "Answer": [{"name": domain + ".", "type": 1, "TTL": 120, "data": "93.184.216.34"}],
            }, separators=(",", ":"))
            import_json_for_lookup(ctx, identity, case_id, lookup, source, payload)

        entity_id = ctx.entity_resolution_115.register_entity(
            case_id=case_id,
            entity_type="organisation",
            display_name="Alpha Research Organisation",
            created_by=identity["username"],
            source_entity_id="fixture:alpha-org",
            anchors=[{
                "type": "domain", "value": "alpha.example.com",
                "reliability": .95, "source_ref": "fixture:public_registry",
            }],
        )

        run = ctx.xref_454.run_case(identity=identity, case_id=case_id)
        assert run["candidate_count"] >= 2
        candidates = ctx.xref_454.candidates(case_id, min_score=.35)
        assert any(
            c["relation_type"] == "entity_domain_anchor_candidate"
            and {c["left_ref"], c["right_ref"]} == {entity_id, "alpha.example.com"}
            for c in candidates
        )
        infra_edge = next(
            c for c in candidates
            if c["relation_type"] == "shared_public_infrastructure_candidate"
            and {c["left_ref"], c["right_ref"]} == set(domains)
        )
        assert any(s["fact_type"] == "ip" for s in infra_edge["signals"])
        assert any("does not prove common ownership/control" in x["note"] for x in infra_edge["contradictions"])

        path = ctx.xref_454.shortest_candidate_path(
            case_id=case_id,
            start_kind="entity", start_ref=entity_id,
            end_kind="domain", end_ref="beta.example.net",
            min_score=.35,
        )
        assert path["found"] is True
        assert len(path["edges"]) == 2
        assert path["candidate_path_not_proof"] is True
        assert ctx.xref_454.verify_integrity()["valid"]


def test_build454_status_health_version_and_test_cadence(tmp_path):
    app = create_workspace_app454(base_dir=tmp_path)
    try:
        status = app.state.context.build454.build454_status()
        assert status["build"] == "454.0"
        assert status["focused_development_build"] is True
        assert status["full_research_gate_this_build"] is False
        assert status["next_build"] == "455.0"
        assert status["infrastructure"]["direct_network_authority"] is False
        assert status["cross_reference"]["automatic_ownership_determination"] is False
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"ok": True, "status": "ok", "build": "454.0"}
    finally:
        app.state.context.close()

    assert 'version = "454.0.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'BUILD = "454.0"' in (ROOT / "eagleeye_pro/version.py").read_text(encoding="utf-8")
    assert "app454 import create_workspace_app454" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text(encoding="utf-8")
    assert (ROOT / "EAGLEEYE_PRO_454_0.py").exists()
    assert (ROOT / "INSTALL_EAGLEEYE_454.py").exists()
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "build_number % 5 == 0" in ci
    assert "test_build454_xref_infrastructure.py" in ci
