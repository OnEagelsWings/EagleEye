"""Build 487: Chromium onboarding preserves the complete case workflow and source navigation."""
import pytest
from eagleeye.interfaces.web.app487 import create_workspace_app487
from test_build475_onboarding_browser import run_onboarding

def test_build487_first_run_and_case_workflow(tmp_path):
    run_onboarding(create_workspace_app487, tmp_path,
                   inventory=True, expert=True, findings=True,
                   report=True, dorks_images=True)


@pytest.mark.parametrize("workspace", [create_workspace_app487], indirect=True)
def test_unicode_rationale_limits_in_rendered_chromium_form(workspace):
    """Browser must count Unicode code points, not UTF-16 units or encoded bytes."""
    from test_build487_sources import lead
    from test_build481_evidence_bridge import document_approved
    from playwright.sync_api import sync_playwright

    app, client, user, case_id, *_ = workspace
    lead(workspace)
    document_approved(workspace)
    response = client.get("/workbench/sources487", params={"case_id": case_id})
    assert response.status_code == 200
    assert 'id="source487-rationale"' in response.text
    assert 'maxlength="1200"' not in response.text

    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(response.text, wait_until="load")
            rationale = page.locator("#source487-rationale")
            for value, valid in [
                ("🧭" * 1200, True),
                ("🧭" * 1201, False),
                ("🧭" * 19, False),
                ("🧭" * 20, True),
                ("日本語" * 280, True),
            ]:
                rationale.fill(value)
                assert rationale.input_value() == value  # No silent truncation.
                assert rationale.evaluate("(el) => el.validity.valid") is valid
                assert page.locator("#source487-rationale-help").inner_text().startswith(
                    str(len(value)) + " / 1200"
                )
        finally:
            browser.close()
