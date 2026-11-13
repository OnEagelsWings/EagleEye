"""Current Build-500 pilot regression: an empty case is actionable, never fabricated."""
import pytest

from eagleeye.application import public_sources501
from eagleeye.interfaces.web.app500 import create_workspace_app500
from test_build471_local_ai import workspace


@pytest.mark.parametrize("workspace", [create_workspace_app500], indirect=True)
def test_new_case_explains_missing_text_and_links_to_real_workflows(workspace):
    app, client, user, seeded_case, *_ = workspace
    ctx = app.state.context
    empty = ctx.team_governance_359.create_case(
        identity=user, title="Leerer Testfall", client="Test",
        purpose="Prüfung ohne Belege", legal_basis="synthetische Daten"
    )
    case_id = empty["case_id"]
    response = client.get("/workbench", params={"case_id": case_id})
    assert response.status_code == 200
    assert "Noch keine Dokumenttexte im Fall" in response.text
    assert "keine automatische Recherche" in response.text
    assert "/documents458?case_id=" + case_id in response.text
    assert "/workbench/public-sources?case_id=" + case_id in response.text
    assert "0 gespeicherte Dokumente" in response.text
    assert client.get("/workbench", params={"case_id": seeded_case}).status_code == 200
    assert "Noch keine Dokumenttexte im Fall" not in client.get(
        "/workbench", params={"case_id": seeded_case}
    ).text


@pytest.mark.parametrize("workspace", [create_workspace_app500], indirect=True)
def test_disabled_catalog_adapter_cannot_be_offered_as_available(workspace, monkeypatch):
    app, client, user, case_id, *_ = workspace
    providers = app.state.context.provider_collection_120

    def mock_catalog(enabled):
        monkeypatch.setattr(providers, "list_providers", lambda: [{
            "provider_key": "gdelt_doc_public_149",
            "supports_live": True,
            "enabled": enabled,
        }])
        rows = public_sources501.catalog(app.state.context, kind="topic")
        return next(row for row in rows if row["source"].key == "gdelt")

    assert mock_catalog(False)["ready"] is False
    assert mock_catalog(True)["ready"] is True
