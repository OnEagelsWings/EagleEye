"""Final deletion of a closed case: content gone (also byte-wise), other cases intact, chains verifiable."""
from datetime import date
from pathlib import Path

import pytest

from eagleeye.application.buero import deletion, service as buero
from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.app492 import create_workspace_app492
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build492_convergence import _evidence_case, _lead
from test_build492_markings import ADMIN, add_finding, fresh, login, review

ws = pytest.mark.parametrize("workspace", [create_workspace_app492], indirect=True)
MARKER = "Loeschmarker Zielperson Quastenberg"
PW = "Build471!Password_88"


def _rich_case(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    login(workspace, ADMIN)
    buero.attach_mandate(ctx, user, case_id, {"kind": "online", "legal_basis_key": "einwilligung", "client_id": "neu",
                                              "client_kind": "privat", "client_name": "Kunde Beispiel"})
    buero.screen(ctx, user, case_id, {"q_beziehung": "nein", "q_schutz": "nein", "q_schutzanordnung": "nein",
                                      "q_anschrift": "nein", "q_identitaet": "ja", "decision": "annehmen"})
    ctx.document_intelligence_458.import_bytes(identity=user, case_id=case_id, filename="ziel.txt",
                                               raw=(MARKER + " wohnt laut Quelle in Musterstadt.\n\nZweiter Absatz.").encode(),
                                               title=MARKER, source_url="https://example.org/ziel")
    _evidence_case(workspace)
    _lead(workspace, url="https://news.example/x")
    finding = add_finding(workspace, "Befund " + MARKER, "offen")
    review(workspace, fresh(app, case_id, finding["title"]))
    buero.add_time(ctx, user, case_id, {"duration": "1", "activity": "recherche", "note": MARKER}, today=date.today())
    with EntityRegistry461(Path(ctx.base_dir) / "entity_registry_462.sqlite3") as reg:
        reg.create_entity(case_id=case_id, kind="person", label=MARKER)
        reg.create_entity(case_id=workspace[5], kind="person", label="Andere Person im anderen Fall")
    return case_id


def _bytes_contain(base: Path, needle: str) -> list[str]:
    raw = needle.encode()
    hits = []
    for path in base.rglob("*"):
        if path.is_file() and path.suffix not in (".log",) and raw in path.read_bytes():
            hits.append(str(path.relative_to(base)))
    return hits


@ws
def test_deletion_removes_case_and_keeps_everything_else(workspace):
    app, client, user, case_id, doc_id, foreign_case, foreign_doc = workspace
    ctx = app.state.context
    base = Path(ctx.base_dir)
    _rich_case(workspace)
    assert _bytes_contain(base, MARKER), "precondition: the marker is stored"
    foreign_docs_before = len(ctx.document_intelligence_458.documents(identity=user, case_id=foreign_case))

    with pytest.raises(buero.BueroError, match="abgeschlossene oder abgelehnte"):
        deletion.plan(ctx, user, case_id)
    buero.set_status(ctx, user, case_id, {"status": "in_arbeit"})
    buero.set_status(ctx, user, case_id, {"status": "abgeschlossen"}, today=date(2020, 1, 15))
    preview = deletion.plan(ctx, user, case_id)
    assert preview["due"] and preview["row_total"] > 20 and preview["files"] >= 3 and preview["documents"] >= 3
    assert "phase15_access_events" in preview["kept"]

    page = client.get("/buero/loeschen", params={"case_id": case_id})
    assert page.status_code == 200 and "Was gelöscht wird" in page.text and "Zugriffsprotokoll" in page.text
    token = client.cookies.get(CSRF_COOKIE)
    wrong = client.post("/buero/loeschen", data={"csrf": token, "case_id": case_id, "confirm": "falsch", "checked": "on"})
    assert wrong.status_code == 422 and "Aktenzeichen genau" in wrong.text
    unchecked = client.post("/buero/loeschen", data={"csrf": token, "case_id": case_id, "confirm": preview["mandate"]["aktenzeichen"]})
    assert unchecked.status_code == 422 and "Aufbewahrungspflicht" in unchecked.text

    done = client.post("/buero/loeschen", data={"csrf": token, "case_id": case_id, "checked": "on",
                                                "confirm": preview["mandate"]["aktenzeichen"]}, follow_redirects=False)
    assert done.status_code == 303 and done.headers["location"] == "/buero/loeschprotokoll?done=deleted"

    assert _bytes_contain(base, MARKER) == [], "no byte of the case content may remain in any workspace file"
    assert not (base / "data/documents_458" / (doc_id + ".bin")).exists()
    assert (base / "data/documents_458" / (foreign_doc + ".bin")).exists()
    assert ctx.db.one("SELECT 1 FROM cases WHERE case_id=?", (case_id,)) is None
    assert ctx.db.one("SELECT 1 FROM buero_mandates WHERE case_id=?", (case_id,)) is None
    assert len(ctx.document_intelligence_458.documents(identity=user, case_id=foreign_case)) == foreign_docs_before
    with EntityRegistry461(base / "entity_registry_462.sqlite3") as reg:
        assert reg.graph(foreign_case)["entities"] and not reg.graph(case_id)["entities"]
    assert ctx.team_identity_359.verify_access_chain()["ok"], "the cross-case access chain stays verifiable"
    assert buero.clients(ctx, user)[0]["name"] == "Kunde Beispiel", "the client stays in the client list"

    log = deletion.deletions(ctx, user)
    assert len(log) == 1 and log[0]["rows_deleted"] > 20 and log[0]["files_deleted"] >= 3
    assert set(k.split(" ")[0] for k in log[0]["residual"]) <= {"phase15_access_events"}
    assert MARKER not in str(log[0])
    protocol = client.get("/buero/loeschprotokoll", params={"done": "deleted"}).text
    assert "endgültig gelöscht" in protocol and "Zugriffsprotokoll" in protocol
    assert client.get("/buero").status_code == 200
    assert client.get("/workbench", params={"case_id": foreign_case}).status_code == 200
    assert client.get("/buero/auftrag", params={"case_id": case_id}).status_code in (403, 404)


@ws
def test_deletion_rules(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    login(workspace, ADMIN)
    row = buero.attach_mandate(ctx, user, case_id, {"kind": "online", "legal_basis_key": "einwilligung", "client_id": "neu",
                                                    "client_kind": "privat", "client_name": "Kunde"})
    rejected = buero.screen(ctx, user, case_id, {"q_beziehung": "ja", "q_schutz": "nein", "q_schutzanordnung": "nein",
                                                 "q_anschrift": "nein", "q_identitaet": "ja", "decision": "ablehnen",
                                                 "reason": "Ex-Partner sucht neue Anschrift ohne Rechtsanspruch."})
    assert rejected["decision"] == "ablehnen"
    current = buero.mandate(ctx, user, case_id)
    assert current["status"] == "abgelehnt" and current["retention_until"] > date.today().isoformat()
    assert "Aufbewahren bis" in client.get("/buero/auftrag", params={"case_id": case_id}).text
    form = {"confirm": row["aktenzeichen"], "checked": "on"}
    with pytest.raises(buero.BueroError, match="Aufbewahrungsfrist läuft noch"):
        deletion.delete_case(ctx, user, case_id, form)
    ctx.team_identity_359.create_user(identity=user, username="ermittler", display_name="Ermittler", global_role="investigator", password=PW)
    ctx.team_governance_359.assign_case_role(identity=user, case_id=case_id, username="ermittler", case_role="case_lead")
    other = ctx.team_identity_359.public_user("ermittler")
    with pytest.raises(PermissionError):
        deletion.plan(ctx, other, case_id)
    result = deletion.delete_case(ctx, user, case_id, {**form, "reason": "Löschverlangen der betroffenen Person vom 16.11.2026."})
    assert result["early_reason"].startswith("Löschverlangen")
    assert ctx.db.one("SELECT 1 FROM cases WHERE case_id=?", (case_id,)) is None
