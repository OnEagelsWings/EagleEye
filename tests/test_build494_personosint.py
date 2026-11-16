"""Build 494 focused tests: PersonOSINT entity suggestions without a second graph DB."""
import hashlib
import json

import pytest

from eagleeye.application import personosint494 as po
from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app494 import create_workspace_app494
from test_build471_local_ai import workspace  # noqa: F401

ws = pytest.mark.parametrize("workspace", [create_workspace_app494], indirect=True)


def exported(entities):
    return json.dumps({
        "case": {"reference": "EE-PO-2026-01"},
        "entities": entities,
        "findings": [],
        "links": [{"source_id": 8, "target_id": 12, "relation": "verwandt"}],
        "audit": [{"username": "secret"}],
    }, ensure_ascii=False).encode()


def token(workspace):
    app, client, *_ = workspace
    session = app.state.context.team_identity_359.authenticate(
        username="qa471", password="Build471!Password_88",
        client_fingerprint=hashlib.sha256(b"testclient||testclient").hexdigest(),
    )
    client.cookies.clear()
    client.cookies.set(COOKIE, session.token)
    client.cookies.set(CSRF_COOKIE, session.csrf_token)
    return session.csrf_token


def upload(client, case, csrf, body, confirm="yes"):
    return client.post("/workbench/personosint494",
        data={"case_id": case, "csrf": csrf, "confirm": confirm},
        files={"export": ("person.json", body, "application/json")},
        follow_redirects=False)


def test_candidate_parser_normalizes_supported_types():
    data = po.parse_entity_suggestions(exported([
        {"id": 8, "type": "person", "label": "Max Müller", "photo": "DO NOT COPY"},
        {"id": 12, "type": "organisation", "label": "Beispiel GmbH",
         "identifiers": [{"kind": "email", "value": "never@example.org"}]},
        {"id": 13, "type": "telefon", "label": "+49 123 000"},
        {"id": 14, "type": "fahrzeug", "label": "K-ABC-000"},
    ]))
    assert len(data.proposals) == 2 and data.skipped == 2
    assert data.proposals[1].kind == "organization"
    assert "never@example.org" not in repr(data)
    assert "DO NOT COPY" not in repr(data)


def test_entity_parser_rejects_oversized_missing_identifiers():
    with pytest.raises(po.PersonOSINTImportError):
        po.parse_entity_suggestions(exported([{"id": 12, "type": "email", "label": "x"}]))
    with pytest.raises(po.PersonOSINTImportError):
        po.parse_entity_suggestions(exported([{"type": "person", "label": "x"}]))
    with pytest.raises(po.PersonOSINTImportError):
        po.parse_entity_suggestions(b"{")


@ws
def test_browser_import_review_and_case_integrity(workspace):
    app, client, user, case_id, _, other_case, _ = workspace
    ctx = app.state.context
    csrf = token(workspace)
    body = exported([
        {"id": 8, "type": "person", "label": "Max Müller"},
        {"id": 12, "type": "organisation", "label": "Beispiel GmbH"},
    ])
    page = client.get("/workbench/intel", params={"case_id": case_id})
    assert "PersonOSINT-Entitäten prüfen" in page.text
    with EntityRegistry461(ctx.base_dir / "entity_registry_462.sqlite3") as reg:
        original = reg.graph(case_id)

    assert upload(client, case_id, csrf, body).status_code == 303
    assert upload(client, case_id, csrf, body).status_code == 303  # idempotent
    queued = po.candidates(ctx, case_id)
    assert len(queued) == 2 and all(x["state"] == "unreviewed" for x in queued)
    assert po.candidates(ctx, other_case) == []

    page = client.get("/workbench/personosint494", params={"case_id": case_id})
    assert page.status_code == 200 and "Max Müller" in page.text
    candidate = queued[0]
    result = client.post("/workbench/personosint494/review",
        data={"case_id": case_id, "csrf": csrf, "candidate_id": candidate["candidate_id"],
              "decision": "for_manual_entry",
              "rationale": "Unterlagen müssen zuerst im Original geprüft und abgeglichen werden."},
        follow_redirects=False)
    assert result.status_code == 303, result.text
    after = po.candidates(ctx, case_id)
    assert len([x for x in after if x["state"] == "for_manual_entry"]) == 1
    assert client.post("/workbench/personosint494/review",
        data={"case_id": case_id, "csrf": csrf, "candidate_id": candidate["candidate_id"],
              "decision": "dismissed", "rationale": "Noch keine hinreichende belastbare Zuordnung möglich."}
    ).status_code == 409
    with EntityRegistry461(ctx.base_dir / "entity_registry_462.sqlite3") as reg:
        assert reg.graph(case_id) == original  # No automatic graph or identity changes


@ws
def test_entity_import_fail_closed(workspace):
    app, client, user, case_id, _, foreign, _ = workspace
    ctx = app.state.context
    csrf = token(workspace)
    body = exported([{"id": 88, "type": "person", "label": "Ada Test"}])
    assert upload(client, case_id, "wrong", body).status_code == 403
    assert upload(client, case_id, csrf, body, confirm="no").status_code == 422
    assert upload(client, "unknown-case", csrf, body).status_code == 403
    assert po.candidates(ctx, case_id) == []
    assert po.candidates(ctx, foreign) == []
    assert upload(client, case_id, csrf, body).status_code == 303
    item = po.candidates(ctx, case_id)[0]
    ctx.db.execute("UPDATE personosint_entity_candidates_494 SET label='tampered' WHERE candidate_id=?",
                   (item["candidate_id"],))
    with pytest.raises(ValueError, match="integrity"):
        po.candidates(ctx, case_id)
