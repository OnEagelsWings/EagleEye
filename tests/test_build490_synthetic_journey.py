"""Build 490 synthetic journey, phase 1: persisted source and review -> UI drill-down.

This is intentionally a partial acceptance slice, NOT the full 490 E2E gate.
It exercises real storage and authenticated routes without external networks.
"""
import html
import re
from urllib.parse import urlsplit, parse_qs
import pytest
from eagleeye.interfaces.web.app489 import create_workspace_app489
from test_build471_local_ai import workspace
from test_build488_integration import entities, form as review_form
from test_build487_sources import lead, form as source_form
from test_build481_evidence_bridge import document_approved, form as evidence_form

pytestmark = pytest.mark.parametrize("workspace", [create_workspace_app489], indirect=True)


def test_synthetic_case_review_source_and_original_navigation(workspace, tmp_path):
    app, client, user, case_id, *_ = workspace
    assert app.title == f"EagleEye – Build {app.version}"
    left, right = entities(workspace, tmp_path)
    response = client.post(
        "/workbench/entities488",
        data=review_form(workspace, left, right),
        follow_redirects=False,
    )
    assert response.status_code == 303

    lead_id = lead(workspace)
    document_approved(workspace)
    response = client.post(
        "/workbench/sources487",
        data=source_form(workspace, lead_id),
        follow_redirects=False,
    )
    assert response.status_code == 303

    checkpoint = client.get("/workbench/checkpoint489", params={"case_id": case_id})
    assert checkpoint.status_code == 200
    assert "Auditierte Entitätsentscheidungen (1)" in checkpoint.text
    assert "Integritätsgeprüfte Quellenzuordnungen (1)" in checkpoint.text

    links = re.findall(r'href="([^"]+)"', checkpoint.text)
    original_links = [
        html.unescape(link) for link in links
        if link.startswith("/documents458?") and "document_id=" in html.unescape(link)
    ]
    assert len(original_links) == 1
    target = urlsplit(original_links[0])
    assert parse_qs(target.query)["case_id"] == [case_id]
    assert len(parse_qs(target.query)["document_id"]) == 1
    original = client.get(original_links[0])
    assert original.status_code == 200
    assert checkpoint.headers["referrer-policy"] == "no-referrer"
    assert original.headers["referrer-policy"] == "no-referrer"

    # Source links and entity decisions never auto-promote evidence or claims.
    store = app.state.context.evidence_claims_dossier_447
    assert store.case_evidence(case_id) == []
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []

    # A second, explicit authenticated action promotes the reviewed original
    # into *unreviewed* canonical Evidence, not into an accepted claim.
    handoff = client.post(
        "/workbench/bridge481", data=evidence_form(workspace),
        follow_redirects=False,
    )
    assert handoff.status_code == 303, handoff.text[:400]
    evidence = store.case_evidence(case_id)
    assert len(evidence) == 1
    assert evidence[0]["review_state"] == "unreviewed"
    document = app.state.context.document_intelligence_458._document(workspace[4])
    assert evidence[0]["content_sha256"] == document["document_sha256"]
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []
    assert store.verify_integrity()["valid"]

    # Retrying a valid handoff must not duplicate canonical Evidence.
    again = client.post(
        "/workbench/bridge481", data=evidence_form(workspace),
        follow_redirects=False,
    )
    assert again.status_code == 303
    assert len(store.case_evidence(case_id)) == 1

    # The canonical record must retain an honest, auditable local-capture
    # provenance. A manually entered research lead is NOT a network capture.
    source_event = app.state.context.acquisition_events_422.get(evidence[0]["event_id"])
    assert source_event["provenance"]["network_fetch_performed"] is False
    assert source_event["provenance"]["document_id"] == workspace[4]
    assert source_event["provenance"]["human_rationale"]
    assert source_event["usage"]["truth_determined"] is False
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []

    # Run the real local AI application against the SAME original-backed case
    # before approving its Evidence/Claim/Dossier. Only model transport is
    # deterministic; source anchoring, persistence and human review are real.
    from unittest.mock import patch
    from test_build471_local_ai import csrf as assistant_csrf, reply, provider
    from eagleeye.application.review474 import review_items
    assistant = app.state.assistant471
    assistant_token = assistant_csrf(client, case_id)
    assistant_calls = []
    assistant_answer = reply(assistant, user, case_id, workspace[4])
    with patch.object(assistant, "request", side_effect=provider(assistant_answer, assistant_calls)):
        generated = client.post(
            "/assistant471/generate",
            data={"case_id": case_id, "csrf_token": assistant_token,
                  "document_id": workspace[4], "model": "mistral:latest"},
            follow_redirects=False,
        )
    assert generated.status_code == 303, generated.text[:400]
    assert any(path == "/api/chat" for _, path, _ in assistant_calls)
    ai_run = assistant.history(user, case_id)[0]
    assert ai_run["status"] == "review_required"
    assert ai_run["sources"]
    assert ai_run["sources"][0]["anchor_id"] == assistant_answer["statements"][0]["citations"][0]["anchor_id"]
    assert ai_run["truth_determined"] is False
    assert len(store.case_claims(case_id)) == 0
    ai_items = review_items(ai_run)
    assert ai_items
    review_data = {
        "case_id": case_id, "csrf_token": assistant_token,
        "run_id": ai_run["run_id"], "decision": "acknowledged",
        "note": "All source-anchored AI items reviewed independently of claims.",
    }
    for item in ai_items:
        review_data["verdict_" + item["item_id"]] = "unclear"
        review_data["item_note_" + item["item_id"]] = (
            "Only the synthetic original is available; no independent corroboration."
        )
    ai_review_response = client.post(
        "/assistant471/review", data=review_data, follow_redirects=False,
    )
    assert ai_review_response.status_code == 303, ai_review_response.text[:400]
    reviewed_ai = assistant.history(user, case_id)[0]
    assert reviewed_ai["status"] == "acknowledged"
    assert reviewed_ai["sources"] == ai_run["sources"]
    assert reviewed_ai["truth_determined"] is False
    assert reviewed_ai["claims_created"] == 0
    assert len(store.case_claims(case_id)) == 0

    # Persist a real provenance-backed entity relation in this SAME case,
    # before the independent dossier approval and export. The graph must
    # resolve the original and must never promote an unreviewed hypothesis.
    from eagleeye.application.entity_registry461 import EntityRegistry461
    # app464 binds the graph registry to the factory base_dir, not ctx.db_path.parent.
    graph_db = tmp_path / "entity_registry_462.sqlite3"
    with EntityRegistry461(graph_db) as registry:
        graph_subject = registry.create_entity(
            case_id=case_id, kind="organization", label="Build 490 synthetic subject",
        )
        graph_source = registry.create_entity(
            case_id=case_id, kind="document", label="Build 490 original source",
        )
        graph_relation = registry.create_relation(
            case_id=case_id, source_id=graph_subject["id"],
            target_id=graph_source["id"], predicate="mentioned_in",
            source_refs=["doc458:" + workspace[4]],
        )
    with EntityRegistry461(graph_db) as registry:
        own_graph = registry.graph(case_id)
        foreign_graph = registry.graph(workspace[5])
    assert any(edge["id"] == graph_relation["id"] for edge in own_graph["relations"])
    assert all(edge["id"] != graph_relation["id"] for edge in foreign_graph["relations"])
    graph_page = client.get("/graph464", params={
        "case_id": case_id, "focus": graph_relation["id"],
    })
    assert graph_page.status_code == 200, graph_page.text[:400]
    assert graph_page.headers["referrer-policy"] == "no-referrer"
    assert graph_subject["id"] in graph_page.text
    assert "mentioned_in" in graph_page.text
    assert "document_id=" + workspace[4] in graph_page.text
    assert "nicht verifiziert" in graph_page.text or "ungeprüft" in graph_page.text

    # Continue the SAME original-backed case into the existing independent
    # four-eyes dossier workflow. Do not seed a second synthetic case.
    from test_build449_integrated import complete_review
    reviewer = app.state.context.team_governance_359.create_user(
        identity=user, username="reviewer490",
        display_name="Independent Build 490 Reviewer",
        global_role="reviewer", password="Build490ReviewerPassword!2026",
    )
    app.state.context.team_governance_359.assign_case_role(
        identity=user, case_id=case_id, username=reviewer["username"],
        case_role="reviewer", notes="Independent synthetic dossier review",
    )
    def independently_review(object_type, object_id, decision, note):
        request = app.state.context.build449.request_review_449(
            identity=user, object_type=object_type, object_id=object_id,
            note="Synthetic original-backed case: independent verification.",
            assigned_to=reviewer["username"],
        )
        result = complete_review(
            app.state.context, reviewer, request, decision, note,
        )
        assert result["review"]["state"] == "completed"
        return request

    independently_review(
        "evidence", evidence[0]["evidence_id"], "accepted",
        "Original document hash and provenance inspected in this case.",
    )
    claim = store.propose_claim(
        identity=user, case_id=case_id,
        statement="Synthetic original document was imported into this case.",
        support_evidence_ids=[evidence[0]["evidence_id"]],
        uncertainty_note="Local synthetic capture; no external network verification.",
    )
    independently_review(
        "claim", claim["claim_id"], "accepted_for_dossier",
        "Limited to the original-backed local import, not external truth.",
    )
    dossier = store.build_dossier(
        identity=user, case_id=case_id,
        title="Build 490 Original-Backed Synthetic Case",
    )
    independently_review(
        "dossier", dossier["revision_id"], "approved_for_export",
        "Evidence, claim limits and provenance preserved in dossier.",
    )
    export_review = independently_review(
        "dossier_export", dossier["revision_id"], "approve",
        "Independent export authorization for this original-backed case.",
    )
    exported = app.state.context.build449.execute_approved_export_449(
        identity=user, review_id=export_review["review_id"],
        confirmation="EXPORT DOSSIER 447",
    )
    from pathlib import Path
    import hashlib
    package = Path(exported["export"]["paths"]["case_package"])
    assert package.is_file()
    assert hashlib.sha256(package.read_bytes()).hexdigest() == exported["export"]["package_hash"]
    # Verify the real artifacts of THIS original-backed, reviewed case,
    # not only the independent export fixture below.
    from zipfile import ZipFile
    exported_paths = exported["export"]["paths"]
    exported_hashes = exported["export"]["hashes"]
    for kind in ("json", "docx", "pdf", "manifest"):
        artifact = Path(exported_paths[kind])
        assert artifact.is_file() and artifact.stat().st_size > 0, kind
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == exported_hashes[artifact.name]
    with ZipFile(package) as archive:
        assert archive.testzip() is None, "Case archive has a corrupt member"
        # Reject ambiguous or escaping paths in the actual approved export.
        # An otherwise valid ZIP must never contain duplicate names or paths
        # that could escape the extraction directory on Windows or Linux.
        names = archive.namelist()
        assert len(names) == len(set(names)), "Duplicate ZIP member names"
        for name in names:
            normalized = name.replace("\\", "/")
            parts = normalized.split("/")
            assert not normalized.startswith("/") and not re.match(r"^[A-Za-z]:", normalized)
            assert all(part not in {"", ".", ".."} for part in parts if part or name.endswith("/"))
        members = {Path(name).name for name in archive.namelist()}
        assert all(Path(exported_paths[kind]).name in members
                   for kind in ("json", "docx", "pdf", "manifest"))
        # The archive is the deliverable: each member must be byte-identical
        # to its separately SHA-256-verified artifact, not merely share a name.
        for kind in ("json", "docx", "pdf", "manifest"):
            artifact = Path(exported_paths[kind])
            matches = [name for name in archive.namelist()
                       if Path(name).name == artifact.name]
            assert len(matches) == 1, (kind, matches)
            assert hashlib.sha256(archive.read(matches[0])).hexdigest() == (
                exported_hashes[artifact.name]
            ), f"Archived {kind} differs from approved export artifact"
    # The actual approved export must carry the SAME case and original-backed
    # evidence/claim identifiers, not merely produce valid but unrelated files.
    import json
    dossier_json = json.loads(Path(exported_paths["json"]).read_text(encoding="utf-8"))
    serialized = json.dumps(dossier_json, ensure_ascii=False)
    assert case_id in serialized, "Export JSON lost its originating case identifier"
    assert evidence[0]["evidence_id"] in serialized, "Export JSON lost reviewed Evidence"
    assert claim["claim_id"] in serialized, "Export JSON lost reviewed Claim"
    assert len(store.exports(case_id)) == 1
    # Export must not mutate or drop the graph provenance in the SAME case.
    # Reopen the existing registry to verify persisted, case-isolated records
    # rather than relying on the earlier in-memory graph response.
    with EntityRegistry461(graph_db) as reopened:
        after_export = reopened.graph(case_id)
        other_after_export = reopened.graph(workspace[5])
    matching_edges = [
        edge for edge in after_export["relations"]
        if edge["id"] == graph_relation["id"]
    ]
    assert len(matching_edges) == 1
    assert any(source["source_ref"] == "doc458:" + workspace[4]
               for source in matching_edges[0]["sources"])
    assert matching_edges[0]["source_verified"] is False
    assert not any(edge["id"] == graph_relation["id"]
                   for edge in other_after_export["relations"])
    assert store.verify_integrity()["valid"]
    assert app.state.context.human_review_449.verify_integrity()["valid"]


    # The existing authenticated graph workspace must remain reachable from
    # the same synthetic case after source/evidence handoff. This is a UI
    # navigation gate, NOT proof that unreviewed candidate links are facts.
    graph = client.get("/graph464", params={"case_id": case_id})
    assert graph.status_code == 200, graph.text[:400]
    # The explicitly proposed and independently reviewed claim remains stored.
    # Only automatic promotion is forbidden; a successful export must not erase it.
    stored_claims = store.case_claims(case_id)
    assert len(stored_claims) == 1
    assert stored_claims[0]["claim_id"] == claim["claim_id"]
    assert len(store.case_dossiers(case_id)) == 1



def test_synthetic_source_bound_ai_requires_human_review(workspace):
    """Run the existing local assistant against the real imported original.

    No network model is needed: only the Ollama transport is simulated, while
    extraction, source anchors, persistence, and authenticated routes stay real.
    """
    from unittest.mock import patch
    from test_build471_local_ai import csrf as assistant_csrf, reply, provider

    app, client, user, case_id, doc_id, foreign_case, foreign_doc = workspace
    service = app.state.assistant471
    token = assistant_csrf(client, case_id)
    calls = []
    answer = reply(service, user, case_id, doc_id)
    store = app.state.context.evidence_claims_dossier_447
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []

    with patch.object(service, "request", side_effect=provider(answer, calls)):
        generated = client.post(
            "/assistant471/generate",
            data={"case_id": case_id, "csrf_token": token,
                  "document_id": doc_id, "model": "mistral:latest"},
            follow_redirects=False,
        )
    assert generated.status_code == 303, generated.text[:400]
    assert any(path == "/api/chat" for _, path, _ in calls)
    run = service.history(user, case_id)[0]
    assert run["status"] == "review_required"
    assert run["truth_determined"] is False
    assert run["claims_created"] == 0
    assert run["sources"][0]["anchor_id"] == answer["statements"][0]["citations"][0]["anchor_id"]
    assert client.get("/assistant471", params={"case_id": case_id}).status_code == 200
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []

    # Build 474's existing review contract requires a verdict and a distinct
    # explanation for EVERY statement, hypothesis and uncertainty. Use the
    # actual item identifiers, not a bypass or a blanket acknowledgment.
    from eagleeye.application.review474 import review_items
    items = review_items(run)
    assert items
    assessment_form = {
        "case_id": case_id, "csrf_token": token,
        "run_id": run["run_id"], "decision": "acknowledged",
        "note": "Originalquelle und alle Einzelbewertungen selbst geprüft.",
    }
    for item in items:
        key = item["item_id"]
        assessment_form["verdict_" + key] = "unclear"
        assessment_form["item_note_" + key] = (
            "Nur die vorliegende Quelle; unabhängige Bestätigung fehlt."
        )
    reviewed = client.post(
        "/assistant471/review", data=assessment_form, follow_redirects=False,
    )
    assert reviewed.status_code == 303, reviewed.text[:400]
    stored = type(service)(app.state.context).history(user, case_id)[0]
    assert stored["status"] == "acknowledged"
    assert stored["truth_determined"] is False
    assert set(stored["review"]["assessments"]) == {
        item["item_id"] for item in items
    }
    assert all(
        entry["verdict"] == "unclear"
        for entry in stored["review"]["assessments"].values()
    )
    assert stored["sources"] == run["sources"]
    assert stored["claims_created"] == 0
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []
    assert service.history(user, foreign_case) == []



def test_synthetic_ai_review_rejects_incomplete_assessment_without_promotion(workspace):
    """A summary cannot be acknowledged with a bare note instead of item reviews.

    This is a fail-closed regression for the stricter review contract introduced
    by the stacked workspace. The successful fully assessed review remains an
    open Build-490 integration gate and is not simulated here.
    """
    from unittest.mock import patch
    from test_build471_local_ai import csrf as assistant_csrf, reply, provider

    app, client, user, case_id, doc_id, *_ = workspace
    service = app.state.assistant471
    token = assistant_csrf(client, case_id)
    with patch.object(service, "request", side_effect=provider(
        reply(service, user, case_id, doc_id), []
    )):
        generated = client.post(
            "/assistant471/generate",
            data={"case_id": case_id, "csrf_token": token,
                  "document_id": doc_id, "model": "mistral:latest"},
            follow_redirects=False,
        )
    assert generated.status_code == 303
    run = service.history(user, case_id)[0]
    rejected = client.post(
        "/assistant471/review",
        data={"case_id": case_id, "csrf_token": token,
              "run_id": run["run_id"], "decision": "acknowledged",
              "note": "Only a generic note; no individual assessment."},
        follow_redirects=False,
    )
    assert rejected.status_code == 422
    persisted = type(service)(app.state.context).history(user, case_id)[0]
    assert persisted["status"] == "review_required"
    assert persisted["truth_determined"] is False
    # A rejected review must not discard or rewrite the cited source anchors.
    assert persisted["sources"] == run["sources"]
    assert persisted["run_id"] == run["run_id"]
    assert persisted["claims_created"] == 0
    store = app.state.context.evidence_claims_dossier_447
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []


def test_synthetic_graph_and_original_are_case_scoped(workspace):
    """Graph and original navigation must not bypass case access control."""
    from fastapi.testclient import TestClient

    app, client, user, case_id, document_id, foreign_case, foreign_doc = workspace
    # The fixture creates both cases under the SAME administrator. Access to
    # either case is authorized; a 403 here would incorrectly test ownership.
    assert client.get("/graph464", params={"case_id": foreign_case}).status_code == 200
    # A document from one case must never be resolved under another case.
    assert client.get(
        "/documents458", params={"case_id": case_id, "document_id": foreign_doc}
    ).status_code in {403, 404}
    with TestClient(app) as anonymous:
        # The workspace may return 401 or 403 for unauthenticated requests.
        # Both deny access without leaking graph data.
        graph_response = anonymous.get("/graph464", params={"case_id": case_id})
        assert graph_response.status_code in {401, 403}, graph_response.text[:400]
        assert anonymous.get(
            "/documents458", params={"case_id": case_id, "document_id": document_id}
        ).status_code in {401, 403}


def test_synthetic_persisted_graph_relationship_is_not_identity_proof(workspace):
    """Exercise stored media relationship data, not merely a graph HTTP 200.

    The existing Build-354 similarity service and Build-484 operator view are
    reused. Similarity remains a review candidate, never a confirmed identity.
    """
    from test_build482_operator import png_bytes

    app, client, user, case_id, _, foreign_case, *_ = workspace
    ctx = app.state.context
    raw = png_bytes()
    first = ctx.build354.ingest_image(
        case_id=case_id, content=raw, declared_media_type="image/png",
        filename="synthetic-a.png",
    )
    second = ctx.build354.ingest_image(
        case_id=case_id, content=raw, declared_media_type="image/png",
        filename="synthetic-b.png",
    )
    links = ctx.build354.similarity_links(case_id=case_id)
    assert links, "Expected a persisted similarity relationship"
    assert first["media_id"] != second["media_id"]
    assert any(
        {link["from_id"], link["to_id"]} ==
        {first["media_id"], second["media_id"]}
        for link in links
    ), "Persisted link must refer to the two original media records"
    operator = client.get("/workbench/media484", params={"case_id": case_id})
    assert operator.status_code == 200, operator.text[:400]
    assert first["media_id"] in operator.text
    assert second["media_id"] in operator.text
    assert "Ungeprüfte Bildähnlichkeit" in operator.text
    graph = client.get("/graph464", params={"case_id": case_id})
    assert graph.status_code == 200, graph.text[:400]
    other = client.get("/workbench/media484", params={"case_id": foreign_case})
    assert other.status_code == 200
    assert first["media_id"] not in other.text
    assert second["media_id"] not in other.text
    # Verify persisted originals through the existing operational inventory.
    # A reachable graph alone does not prove persisted case-specific data.
    from eagleeye.interfaces.web.pilot485 import pilot_counts
    own_counts = pilot_counts(ctx, user, case_id)
    foreign_counts = pilot_counts(ctx, user, foreign_case)
    assert own_counts["images"] == 2
    assert foreign_counts["images"] == 0
    assert own_counts["integrity_ok"] is True
    assert client.get("/workbench/pilot485", params={"case_id": case_id}).status_code == 200
    assert client.get("/workbench/pilot485", params={"case_id": foreign_case}).status_code == 200
    store = ctx.evidence_claims_dossier_447
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []


def test_synthetic_independently_approved_dossier_export_has_real_artifacts(workspace, tmp_path):
    """Exercise the existing four-eyes export service, not a mocked PDF/ZIP.

    This remains a separate synthetic case from the source/AI journey above;
    joining both into one continuous case is still a Build-490 release gate.
    """
    import hashlib
    from pathlib import Path
    from eagleeye_pro.core.app_context import AppContext
    from test_build449_integrated import test_four_eyes_chain_evidence_claim_dossier_and_export

    root = tmp_path / "approved_synthetic_dossier"
    test_four_eyes_chain_evidence_claim_dossier_and_export(root)
    with AppContext(base_dir=root) as ctx:
        row = ctx.db.one("SELECT case_id, record_hash FROM dossier_export_447")
        assert row is not None, "Four-eyes approval must create a real export record"
        exports = ctx.evidence_claims_dossier_447.exports(row["case_id"])
        assert len(exports) == 1
        export = exports[0]
        assert export["record_hash"] == row["record_hash"]
        package = Path(export["paths"]["case_package"])
        assert package.is_file()
        assert hashlib.sha256(package.read_bytes()).hexdigest() == export["package_hash"]
        for kind in ("json", "docx", "pdf", "manifest"):
            artifact = Path(export["paths"][kind])
            assert artifact.is_file() and artifact.stat().st_size > 0, kind
            assert hashlib.sha256(artifact.read_bytes()).hexdigest() == export["hashes"][artifact.name]
        assert ctx.human_review_449.verify_integrity()["valid"]
        assert ctx.evidence_claims_dossier_447.verify_integrity()["valid"]



def test_synthetic_real_entity_graph_links_to_original_in_same_case(workspace, tmp_path):
    """Persist real entity nodes and a source-backed edge in the active case.

    A rendered graph alone is insufficient: the relation must survive a fresh
    registry handle and resolve its original document without claiming identity.
    """
    from eagleeye.application.entity_registry461 import EntityRegistry461

    app, client, user, case_id, document_id, foreign_case, foreign_doc = workspace
    db_path = tmp_path / "entity_registry_462.sqlite3"
    with EntityRegistry461(db_path) as registry:
        subject = registry.create_entity(
            case_id=case_id, kind="organization", label="Synthetic company"
        )
        source = registry.create_entity(
            case_id=case_id, kind="document", label="Synthetic Source"
        )
        relation = registry.create_relation(
            case_id=case_id, source_id=subject["id"], target_id=source["id"],
            predicate="mentioned_in", source_refs=["doc458:" + document_id],
        )
    with EntityRegistry461(db_path) as registry:
        graph = registry.graph(case_id)
        other_graph = registry.graph(foreign_case)
    assert {subject["id"], source["id"]}.issubset(
        {node["id"] for node in graph["entities"]}
    )
    assert any(edge["id"] == relation["id"] for edge in graph["relations"])
    assert not any(edge["id"] == relation["id"] for edge in other_graph["relations"])

    page = client.get("/graph464", params={"case_id": case_id, "focus": relation["id"]})
    assert page.status_code == 200, page.text[:400]
    assert "mentioned_in" in page.text
    assert "Synthetic Source" in page.text
    assert "document_id=" + document_id in page.text
    assert "nicht verifiziert" in page.text or "ungeprüft" in page.text
    original = client.get(
        "/documents458", params={"case_id": case_id, "document_id": document_id}
    )
    assert original.status_code == 200
    foreign = client.get("/graph464", params={"case_id": foreign_case})
    assert foreign.status_code == 200
    assert relation["id"] not in foreign.text
    assert subject["id"] not in foreign.text
