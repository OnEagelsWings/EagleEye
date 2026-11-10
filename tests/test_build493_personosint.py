"""Build 493 focused acceptance: authenticated PersonOSINT -> unverified leads.

Exercises the actual app493 factory, existing 483 canonical persistence,
case isolation and browser CSRF. No old build regressions or live searches.
"""
import hashlib
import json
from pathlib import Path

import pytest

from eagleeye.application.personosint493 import (
    MAX_EXPORT_BYTES, PersonOSINTImportError, parse_personosint_export,
)
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app493 import create_workspace_app493
from eagleeye.interfaces.web.research483 import listed
from test_build471_local_ai import workspace  # noqa: F401 (fixture)


ws = pytest.mark.parametrize("workspace", [create_workspace_app493], indirect=True)
ROOT = Path(__file__).resolve().parents[1]


def export(*findings):
    return json.dumps({
        "export_id": "personosint-exp-test", "case": {"id": 17, "reference": "PO-2026-017"},
        "entities": [{"label": "DO NOT IMPORT PERSON"}],
        "links": [{"relation": "DO NOT IMPORT GRAPH EDGE"}],
        "findings": list(findings),
    }, ensure_ascii=False).encode("utf-8")


def authorized_csrf(workspace):
    app, client, *_ = workspace
    sess = app.state.context.team_identity_359.authenticate(
        username="qa471", password="Build471!Password_88",
        client_fingerprint=hashlib.sha256(b"testclient||testclient").hexdigest()
    )
    client.cookies.clear()
    client.cookies.set(COOKIE, sess.token)
    client.cookies.set(CSRF_COOKIE, sess.csrf_token)
    return sess.csrf_token


def send(client, case_id, token, blob, confirm="yes"):
    return client.post(
        "/workbench/personosint493",
        data={"case_id": case_id, "csrf": token, "confirm": confirm},
        files={"export": ("fall.json", blob, "application/json")},
        follow_redirects=False,
    )


def test_parser_only_accepts_public_https_leads():
    result = parse_personosint_export(export(
        {"title": "Handelsregister Y GmbH", "url": "https://register.example/abc",
         "source": "Handelsregister", "status": "bestätigt", "score": 95},
        {"title": "Doppel", "url": "https://register.example/abc", "status": "neu"},
        {"title": "Intern", "url": "http://localhost/secrets", "status": "neu"},
        {"title": "Verworfen", "url": "https://example.org/false", "status": "verworfen"},
    ))
    assert len(result.leads) == 1 and result.skipped == 3
    assert result.foreign_case == "PO-2026-017"
    assert "ungeprüfter Suchhinweis" in result.leads[0].note
    assert "Identitätsnachweis" in result.leads[0].note
    assert not hasattr(result, "entities") and not hasattr(result, "links")


@pytest.mark.parametrize("raw", [
    b"not json", b"[]", b"{}", b"{}", b" " * (MAX_EXPORT_BYTES + 1),
    b'{"case":{"id":17},"findings":"not a list"}',
])
def test_parser_rejects_malformed_or_oversized_input(raw):
    with pytest.raises(PersonOSINTImportError):
        parse_personosint_export(raw)


@ws
def test_browser_imports_to_existing_case_without_promoting_claims(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    token = authorized_csrf(workspace)
    hub = client.get("/workbench/intel", params={"case_id": case_id})
    assert hub.status_code == 200 and "PersonOSINT-Export übernehmen" in hub.text
    view = client.get("/workbench/personosint493", params={"case_id": case_id})
    assert view.status_code == 200 and "nur öffentliche HTTPS-Recherchehinweise" in view.text

    original_claims = ctx.db.one("SELECT count(*) AS n FROM operational_findings_478")["n"]
    body = export({"title": "Öffentliche Handelsregisterseite", "url": "https://company.example/public",
                   "source": "Register", "status": "bestätigt"})
    response = send(client, case_id, token, body)
    assert response.status_code == 303, response.text
    rows = listed(ctx, case_id)
    assert len(rows) == 1
    assert rows[0]["review_state"] == "unverified_lead"
    assert rows[0]["url"] == "https://company.example/public"
    assert "PersonOSINT-Fallexport" in rows[0]["analyst_note"]
    assert ctx.db.one("SELECT count(*) AS n FROM operational_findings_478")["n"] == original_claims
    assert "DO NOT IMPORT PERSON" not in client.get("/workbench/leads483", params={"case_id": case_id}).text
    # Idempotency: importing the same export does not duplicate a candidate.
    assert send(client, case_id, token, body).status_code == 303
    assert len(listed(ctx, case_id)) == 1


@ws
def test_import_rejects_bad_csrf_cross_case_and_local_urls(workspace):
    app, client, user, case_id, _, other_case, _ = workspace
    ctx = app.state.context
    token = authorized_csrf(workspace)
    valid = export({"title": "Quelle", "url": "https://example.org/open", "source": "Public"})
    assert send(client, case_id, "wrong", valid).status_code == 403
    assert send(client, "not-your-case", token, valid).status_code == 403
    malicious = export({"title": "Interne Seite", "url": "https://127.0.0.1/admin",
                        "source": "Untrusted"})
    assert send(client, case_id, token, malicious).status_code == 422
    assert send(client, case_id, token, valid, confirm="no").status_code == 422
    assert listed(ctx, case_id) == []
    # Other case is not changed either.
    assert listed(ctx, other_case) == []


def test_launchers_keep_case_data_outside_upgradeable_install_folder():
    for name in ("START_EAGLEEYE_PRO.bat", "START_EAGLEEYE_PRO.sh"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "INSTALL_EAGLEEYE_490.py" in text
        assert ".eagleeye-runtime-490" in text
        assert ".eagleeye-data-490" not in text
        assert ".eagleeye-config-490" not in text
    for name in ("EAGLEEYE_START_DIAGNOSE.bat", "EAGLEEYE_DATENORDNER_WAEHLEN.bat",
                 "EAGLEEYE_SICHERUNG.bat", "EAGLEEYE_WIEDERHERSTELLEN.bat"):
        assert ".eagleeye-runtime-490\\Scripts\\python.exe" in (ROOT / name).read_text(encoding="utf-8")
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".eagleeye-runtime-*/" in ignore
    assert ".eagleeye-config-*/" in ignore
    assert ".eagleeye-data-*/" in ignore
