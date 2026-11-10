"""Build 495: one-case PersonOSINT source workbench and safe manual links."""
import pytest

from eagleeye.interfaces.web.app495 import create_workspace_app495
from eagleeye.interfaces.web.personosint495 import external_links
from test_build471_local_ai import workspace  # noqa: F401

ws = pytest.mark.parametrize("workspace", [create_workspace_app495], indirect=True)


def test_source_catalog_is_explicit_manual_network_only():
    links = external_links("Müller, Max", "person")
    assert len(links) >= 3
    assert all(z["url"].startswith("https://") for z in links)
    assert any("M%C3%BCller" in z["url"] for z in links)
    assert all("@" not in z["provider"] for z in links)
    assert external_links("", "person") == []
    with pytest.raises(ValueError):
        external_links("x", "unknown")
    with pytest.raises(ValueError):
        external_links("bad\nheader", "person")
    with pytest.raises(ValueError):
        external_links("x" * 121, "person")
    # Invisible Unicode controls must not disguise names or alter displayed links.
    for unsafe in ("Alice\u202eBob", "Alice\u200bBob", "Alice\u2066Bob", "Alice\ud800Bob"):
        with pytest.raises(ValueError):
            external_links(unsafe, "person")


@ws
def test_person_osint_uses_existing_case_auth_and_full_pipeline(workspace):
    app, client, user, case_id, *_ = workspace
    response = client.get("/workbench/personosint495",
                          params={"case_id":case_id, "kind":"person", "term":"Müller, Max"})
    assert response.status_code == 200
    assert "PersonOSINT Intelligence" in response.text
    assert "github.com" in response.text
    assert "M%C3%BCller" in response.text
    assert 'referrerpolicy="no-referrer"' in response.text
    for route in ("/workbench/personosint493", "/workbench/personosint494",
                  "/workbench/intel/web", "/workbench/intel/network"):
        assert route in response.text
    assert client.get("/workbench/personosint495", params={"case_id":"not-visible"}).status_code == 403
    assert client.get("/workbench/personosint495",
                      params={"case_id":case_id, "kind":"invalid"}).status_code == 422


@ws
def test_main_hub_renders_full_combined_personosint(workspace):
    app, client, user, case_id, *_ = workspace
    hub = client.get("/workbench/intel", params={"case_id":case_id})
    assert hub.status_code == 200 and "PersonOSINT Intelligence" in hub.text
    flow = client.get("/workbench", params={"case_id":case_id})
    assert flow.status_code == 200
    assert "PersonOSINT-Quellen übernehmen" in flow.text
    assert "PersonOSINT-Entitäten prüfen" in flow.text
