"""Fixes for the review of PR #96 (deletion recovery, reports/, forced password change, provider leads)."""
import pytest

from eagleeye.interfaces.web.app492 import create_workspace_app492
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build492_intel import csrf_session

ws = pytest.mark.parametrize("workspace", [create_workspace_app492], indirect=True)


def _intake(ctx, case_id, n, url):
    ctx.db.conn.execute("PRAGMA foreign_keys=OFF")
    try:
        ctx.db.execute(
            "INSERT INTO provider_intake_120(intake_id,case_id,target_id,run_id,provider_key,title,url,canonical_url,source_host,"
            "snippet,source_type,published_at,content_fingerprint,raw_payload_json,review_status,candidate_only,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"intake_{n}", case_id, "", f"run_{n}", "google_books_120", f"Treffer {n}", url, url, "books.example",
             "", "book", "", f"fp{n}", "{}", "new", 1, f"2026-11-1{n}T10:00:00", f"2026-11-1{n}T10:00:00"))
    finally:
        ctx.db.conn.execute("PRAGMA foreign_keys=ON")


@ws
def test_one_http_provider_candidate_does_not_break_the_leads_page(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    csrf_session(workspace)
    _intake(ctx, case_id, 1, "http://books.example/info?id=1")
    _intake(ctx, case_id, 2, "https://books.example/info?id=2")
    _intake(ctx, case_id, 3, "https://books.example:8443/info?id=3")
    page = client.get("/workbench/leads483", params={"case_id": case_id})
    assert page.status_code == 200
    assert 'href="https://books.example/info?id=2"' in page.text
    assert "Fundadresse nicht verlinkt" in page.text and "http://books.example/info?id=1" in page.text
    assert 'href="http://books.example' not in page.text and 'href="https://books.example:8443' not in page.text


@ws
def test_forced_password_change_blocks_every_authenticated_request(workspace):
    from eagleeye.application.buero import service as buero
    from eagleeye.interfaces.web.app364 import CSRF_COOKIE
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    csrf_session(workspace)
    token = client.cookies.get(CSRF_COOKIE)
    client.post("/buero/team/benutzer", data={"csrf": token, "username": "anna", "display_name": "Anna Beispiel",
                                              "global_role": "investigator", "password": "Herbstlaub!Fenster_2026"})
    row = buero.attach_mandate(ctx, user, case_id, {"kind": "online", "legal_basis_key": "einwilligung", "client_id": "neu",
                                                    "client_kind": "privat", "client_name": "Kunde"})
    buero.screen(ctx, user, case_id, {"q_beziehung": "nein", "q_schutz": "nein", "q_schutzanordnung": "nein",
                                      "q_anschrift": "nein", "q_identitaet": "ja", "decision": "annehmen"})
    ctx.team_governance_359.assign_case_role(identity=user, case_id=case_id, username="anna", case_role="investigator")
    client.post("/buero/team/passwort", data={"csrf": token, "username": "anna", "password": "Sommerregen?Tasse_31"})

    csrf_session(workspace, "anna", "Sommerregen?Tasse_31")
    token = client.cookies.get(CSRF_COOKIE)
    assert client.get("/buero", headers={"accept": "application/json"}).status_code == 403
    assert client.get(f"/api/cases/{case_id}/team").status_code == 403
    booked = client.post("/buero/zeit", data={"csrf": token, "case_id": case_id, "duration": "1", "activity": "recherche"})
    assert booked.status_code == 403 and not buero.time_entries(ctx, user, case_id)
    form_post = client.post("/buero/zeit", data={"csrf": token, "case_id": case_id, "duration": "1", "activity": "recherche"},
                            headers={"accept": "text/html"}, follow_redirects=False)
    assert form_post.status_code == 303 and form_post.headers["location"] == "/buero/konto"
    assert not buero.time_entries(ctx, user, case_id), "a redirected form must not have been executed"
    assert client.get("/buero/konto").status_code == 200
    assert client.post("/buero/konto", data={"csrf": token, "current": "Sommerregen?Tasse_31", "new": "Morgenrot&Kanne_58",
                                             "repeat": "Morgenrot&Kanne_58"}, follow_redirects=False).status_code == 303
    assert client.post("/buero/zeit", data={"csrf": token, "case_id": case_id, "duration": "1", "activity": "recherche"},
                       follow_redirects=False).status_code == 303
    assert len(buero.time_entries(ctx, user, case_id)) == 1
    assert row["aktenzeichen"]


MARK = "Restmarker Zielperson Kranichfeld"


def _closed_case(workspace):
    from datetime import date
    from pathlib import Path
    from eagleeye.application.buero import service as buero
    from eagleeye.application.entity_registry461 import EntityRegistry461
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    csrf_session(workspace)
    buero.attach_mandate(ctx, user, case_id, {"kind": "online", "legal_basis_key": "einwilligung", "client_id": "neu",
                                              "client_kind": "privat", "client_name": "Kunde"})
    buero.screen(ctx, user, case_id, {"q_beziehung": "nein", "q_schutz": "nein", "q_schutzanordnung": "nein",
                                      "q_anschrift": "nein", "q_identitaet": "ja", "decision": "annehmen"})
    doc = ctx.document_intelligence_458.import_bytes(identity=user, case_id=case_id, filename="z.txt",
                                                     raw=(MARK + " laut Quelle.\n\nZweiter Absatz.").encode(), title=MARK)
    with EntityRegistry461(Path(ctx.base_dir) / "entity_registry_462.sqlite3") as reg:
        reg.create_entity(case_id=case_id, kind="person", label=MARK)
    buero.set_status(ctx, user, case_id, {"status": "in_arbeit"})
    buero.set_status(ctx, user, case_id, {"status": "abgeschlossen"}, today=date(2020, 1, 15))
    return ctx, user, case_id, doc["document_id"], buero.mandate(ctx, user, case_id)["aktenzeichen"]


@ws
def test_unreadable_store_blocks_deletion_before_anything_changes(workspace):
    from pathlib import Path
    from eagleeye.application.buero import deletion, service as buero
    from eagleeye.interfaces.web.app364 import CSRF_COOKIE
    app, client, *_ = workspace
    ctx, user, case_id, doc_id, az = _closed_case(workspace)
    (Path(ctx.base_dir) / "kaputt_123.sqlite3").write_bytes(b"this is not a database" * 100)
    preview = deletion.plan(ctx, user, case_id)
    assert preview["unreadable"] == ["kaputt_123.sqlite3"]
    page = client.get("/buero/loeschen", params={"case_id": case_id}).text
    assert "nicht lesbar" in page and "Fallakte endgültig löschen</button>" not in page
    refused = client.post("/buero/loeschen", data={"csrf": client.cookies.get(CSRF_COOKIE), "case_id": case_id,
                                                   "confirm": az, "checked": "on"})
    assert refused.status_code == 422 and "nicht lesbar" in refused.text
    assert buero.mandate(ctx, user, case_id) is not None, "nothing was deleted"
    assert ctx.db.one("SELECT COUNT(*) AS n FROM buero_deletions")["n"] == 0


@ws
def test_interrupted_deletion_is_recorded_and_can_be_resumed(workspace, monkeypatch):
    import sqlite3
    from pathlib import Path
    from eagleeye.application.buero import deletion, service as buero
    from eagleeye.interfaces.web.app364 import CSRF_COOKIE
    app, client, *_ = workspace
    ctx, user, case_id, doc_id, az = _closed_case(workspace)
    base = Path(ctx.base_dir)
    real = deletion._plan_or_purge

    def locked(con, cid, *, execute, seed=None):
        if execute and con is not ctx.db.conn:
            raise sqlite3.OperationalError("database is locked")
        return real(con, cid, execute=execute, seed=seed)
    monkeypatch.setattr(deletion, "_plan_or_purge", locked)
    token = client.cookies.get(CSRF_COOKIE)
    failed = client.post("/buero/loeschen", data={"csrf": token, "case_id": case_id, "confirm": az, "checked": "on"})
    assert failed.status_code == 409 and "unvollständig" in failed.text and "Löschung fortsetzen" in failed.text
    job = ctx.db.one("SELECT * FROM buero_deletions")
    assert job["status"] == "unvollstaendig" and job["keys_json"] and job["files_json"]
    assert ctx.db.one("SELECT 1 FROM buero_mandates WHERE case_id=?", (case_id,)) is None, "main store already purged"
    assert (base / "data/documents_458" / (doc_id + ".bin")).exists(), "files not yet deleted"
    assert "Löschung unvollständig" in client.get("/buero").text

    monkeypatch.setattr(deletion, "_plan_or_purge", real)
    resumed = client.post("/buero/loeschen/fortsetzen", data={"csrf": token, "deletion_id": job["deletion_id"]},
                          follow_redirects=False)
    assert resumed.status_code == 303
    job = ctx.db.one("SELECT * FROM buero_deletions")
    assert job["status"] == "abgeschlossen" and job["keys_json"] == "" and job["files_json"] == ""
    assert not (base / "data/documents_458" / (doc_id + ".bin")).exists()
    leftovers = [str(p) for p in base.rglob("*") if p.is_file() and MARK.encode() in p.read_bytes()]
    assert leftovers == [], leftovers
    assert "Löschung unvollständig" not in client.get("/buero").text


@ws
def test_reports_folder_is_part_of_the_deletion(workspace):
    from pathlib import Path
    from eagleeye.application.buero import deletion
    app, client, *_ = workspace
    ctx, user, case_id, doc_id, az = _closed_case(workspace)
    reports = Path(ctx.base_dir) / "reports"
    (reports / "report_builder_pro_89" / case_id).mkdir(parents=True, exist_ok=True)
    (reports / "report_builder_pro_89" / case_id / "rep_1.md").write_text(MARK, encoding="utf-8")
    (reports / "graph_ui_76").mkdir(parents=True, exist_ok=True)
    (reports / "graph_ui_76" / f"{case_id}_gui76_x.html").write_text(MARK, encoding="utf-8")
    shared = reports / "uebersicht_alle_faelle.json"
    shared.write_text('{"cases": ["' + case_id + '", "case_other"]}', encoding="utf-8")
    preview = deletion.plan(ctx, user, case_id)
    assert preview["files"] >= 3 and preview["mentions"] == ["reports/uebersicht_alle_faelle.json"]
    result = deletion.delete_case(ctx, user, case_id, {"confirm": az, "checked": "on"})
    assert not (reports / "report_builder_pro_89" / case_id).exists()
    assert not (reports / "graph_ui_76" / f"{case_id}_gui76_x.html").exists()
    assert shared.exists(), "a shared file is reported, not deleted"
    assert result["residual"].get("Dateien, die den Fall noch erwähnen (bitte prüfen)") == 1
