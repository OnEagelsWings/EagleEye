"""Client report PDF: recipient level decides content, sources are cited, letterhead and file number."""
import pymupdf
import pytest

from eagleeye.application.buero import service as buero
from eagleeye.interfaces.web.app492 import create_workspace_app492
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build492_markings import ADMIN, add_finding, fresh, login, review

ws = pytest.mark.parametrize("workspace", [create_workspace_app492], indirect=True)
PW = "Build471!Password_88"


def _text(pdf: bytes) -> str:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


@ws
def test_client_report_follows_recipient_level(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    login(workspace, ADMIN)
    buero.save_settings(ctx, user, {**buero.DEFAULT_SETTINGS, "firma": "Detektei Adler", "anschrift": "Marktplatz 3",
                                    "stundensatz": "85", "km_satz": "0,30", "ust_modus": "regel",
                                    "aufbewahrung_monate": "36", "bericht_fusszeile": "Streng vertraulich"})
    row = buero.attach_mandate(ctx, user, case_id, {"kind": "due_diligence", "legal_basis_key": "berechtigtes_interesse",
                                                    "client_id": "neu", "client_kind": "unternehmen",
                                                    "client_name": "Muster AG", "recipient": "Muster AG, Vorstand"})
    public = add_finding(workspace, "Gründungsjahr laut Handelsregister", "offen")
    add_finding(workspace, "Interne Arbeitshypothese", "intern")
    unreviewed = add_finding(workspace, "Ungeprüfte Beobachtung", "offen")
    review(workspace, fresh(app, case_id, public["title"]))

    akte = client.get("/buero/auftrag", params={"case_id": case_id}).text
    assert "Bericht für Mandant (PDF)" in akte
    assert "1 von 3 Befunden enthalten; zurückgehalten:" in akte

    response = client.get("/buero/bericht.pdf", params={"case_id": case_id})
    assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
    assert f'Bericht_{row["aktenzeichen"]}.pdf' in response.headers["content-disposition"]
    text = _text(response.content)
    for expected in ("Detektei Adler", "Muster AG, Vorstand", "Ermittlungsbericht", row["aktenzeichen"],
                     "Gründungsjahr laut Handelsregister", "Quellenverzeichnis", "SHA-256", "Methodik und Grenzen",
                     "Empfängerstufe: Mandant", "Streng vertraulich", "Seite 1"):
        assert expected in text, expected
    assert "Interne Arbeitshypothese" not in text and unreviewed["title"] not in text
    assert "zurückgehalten" not in text, "the client copy does not list what was held back"

    internal = _text(client.get("/buero/bericht.pdf", params={"case_id": case_id, "level": "intern"}).content)
    assert "Interner Arbeitsstand" in internal and "Interne Arbeitshypothese" in internal
    assert client.get("/buero/bericht.pdf", params={"case_id": case_id, "level": "presse"}).status_code == 422
    exports = ctx.db.all("SELECT details_json FROM audit_events WHERE action='buero_client_report_exported' AND case_id=?",
                         (case_id,))
    assert len(exports) == 2 and '"kept": 1' in exports[0]["details_json"]

    ctx.team_identity_359.create_user(identity=user, username="leser", display_name="Leser", global_role="read_only", password=PW)
    ctx.team_governance_359.assign_case_role(identity=user, case_id=case_id, username="leser", case_role="read_only")
    login(workspace, ("leser", PW))
    assert client.get("/buero/bericht.pdf", params={"case_id": case_id}).status_code == 403


@ws
def test_report_pdf_renders_foreign_scripts_and_long_findings(workspace, tmp_path):
    """Quotes from foreign sources keep their characters; long reports break across pages."""
    from eagleeye.interfaces.web import buero_report
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    login(workspace, ADMIN)
    buero.attach_mandate(ctx, user, case_id, {"kind": "online", "legal_basis_key": "einwilligung", "client_id": "neu",
                                              "client_kind": "privat", "client_name": "Frau Müller"})
    for n in range(12):
        finding = add_finding(workspace, f"Befund {n} – Иванов / 王 / Ελλάδα", "offen")
        review(workspace, fresh(app, case_id, finding["title"]))
    pdf = buero_report.report_pdf(app, user, case_id, "mandant")
    text = _text(pdf)
    if buero_report._fonts()[0] == "EEReport":
        assert "Иванов" in text and "Ελλάδα" in text
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        assert doc.page_count >= 2
    (tmp_path / "bericht.pdf").write_bytes(pdf)
