"""Work lists per mandate type: states, permissions, overview progress, scope in the client report."""
import pymupdf
import pytest

from eagleeye.application.buero import checklists, service as buero
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.server import create_workspace_app
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build492_intel import csrf_session

ws = pytest.mark.parametrize("workspace", [create_workspace_app], indirect=True)
PW = "Build471!Password_88"
CLEAN = {"q_beziehung": "nein", "q_schutz": "nein", "q_schutzanordnung": "nein", "q_anschrift": "nein",
         "q_identitaet": "ja", "decision": "annehmen"}


def _mandate(ctx, user, case_id, kind="due_diligence"):
    buero.attach_mandate(ctx, user, case_id, {"kind": kind, "legal_basis_key": "berechtigtes_interesse", "client_id": "neu",
                                              "client_kind": "unternehmen", "client_name": "Muster AG"})
    buero.screen(ctx, user, case_id, CLEAN)
    buero.set_status(ctx, user, case_id, {"status": "in_arbeit"})


def test_every_template_has_unique_keys_and_common_frame():
    for kind in buero.MANDATE_KINDS:
        keys = [k for k, *_ in checklists.items_for(kind)]
        assert len(keys) == len(set(keys)), kind
        assert keys[0] == "auftrag" and keys[-2:] == ["pruefung", "bericht"]


@ws
def test_every_tool_link_of_every_template_opens(workspace):
    app, client, user, case_id, *_ = workspace
    csrf_session(workspace)
    tools = {tool for kind in buero.MANDATE_KINDS for *_, tool in checklists.items_for(kind) if tool}
    for tool in sorted(tools):
        response = client.get(tool, params={"case_id": case_id})
        assert response.status_code == 200, tool


@ws
def test_states_rules_and_permissions(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    _mandate(ctx, user, case_id)
    items = checklists.checklist(ctx, user, case_id)
    assert [i["state"] for i in items] == ["offen"] * len(items)
    checklists.set_item(ctx, user, case_id, {"item_key": "handelsregister", "state": "erledigt"})
    with pytest.raises(buero.BueroError, match="begründen"):
        checklists.set_item(ctx, user, case_id, {"item_key": "sanktionen", "state": "entfaellt"})
    checklists.set_item(ctx, user, case_id, {"item_key": "sanktionen", "state": "entfaellt", "note": "Mandant prüft selbst"})
    with pytest.raises(buero.BueroError, match="gibt es"):
        checklists.set_item(ctx, user, case_id, {"item_key": "anspruch", "state": "erledigt"})
    row = buero.mandate(ctx, user, case_id)
    assert checklists.progress(ctx, [row])[case_id] == (2, len(items))
    ctx.team_identity_359.create_user(identity=user, username="leser", display_name="Leser", global_role="read_only", password=PW)
    ctx.team_governance_359.assign_case_role(identity=user, case_id=case_id, username="leser", case_role="read_only")
    with pytest.raises(PermissionError):
        checklists.set_item(ctx, ctx.team_identity_359.public_user("leser"), case_id,
                            {"item_key": "presse", "state": "erledigt"})
    # Changing the mandate type keeps recorded states of shared steps.
    buero.update_mandate(ctx, user, case_id, {"kind": "hintergrund", "legal_basis_key": "berechtigtes_interesse",
                                              "hourly_rate": "80", "recipient_level": "mandant"})
    states = {i["key"]: i["state"] for i in checklists.checklist(ctx, user, case_id)}
    assert states["sanktionen"] == "entfaellt" and "handelsregister" not in states


@ws
def test_work_list_in_file_overview_and_report(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    csrf_session(workspace)
    _mandate(ctx, user, case_id)
    total = len(checklists.items_for("due_diligence"))
    akte = client.get("/buero/auftrag", params={"case_id": case_id}).text
    assert "Arbeitsliste: Due Diligence" in akte and f"(0 von {total} erledigt)" in akte
    token = client.cookies.get(CSRF_COOKIE)
    done = client.post("/buero/arbeitsliste", data={"csrf": token, "case_id": case_id, "item_key": "handelsregister",
                                                    "state": "erledigt"}, follow_redirects=False)
    assert done.status_code == 303 and done.headers["location"].endswith("#arbeitsliste")
    missing = client.post("/buero/arbeitsliste", data={"csrf": token, "case_id": case_id, "item_key": "sanktionen",
                                                       "state": "entfaellt", "note": ""})
    assert missing.status_code == 422 and "begründen" in missing.text
    client.post("/buero/arbeitsliste", data={"csrf": token, "case_id": case_id, "item_key": "sanktionen",
                                             "state": "entfaellt", "note": "Mandant prüft Sanktionslisten selbst"})
    assert f"2/{total}" in client.get("/buero").text
    pdf = client.get("/buero/bericht.pdf", params={"case_id": case_id})
    with pymupdf.open(stream=pdf.content, filetype="pdf") as doc:
        text = " ".join(" ".join(p.get_text().split()) for p in doc)
    assert "2. Prüfumfang" in text and "geprüft" in text and "nicht geprüft" in text
    assert "entfällt: Mandant prüft Sanktionslisten selbst" in text
    assert "3. Ergebnisse" in text and "5. Quellenverzeichnis" in text
