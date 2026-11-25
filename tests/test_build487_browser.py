"""Build 487: Chromium onboarding preserves the complete case workflow and source navigation."""
import pytest
from eagleeye.interfaces.web.app487 import create_workspace_app487
from test_build475_onboarding_browser import run_onboarding
from test_build471_local_ai import workspace

def test_build487_first_run_and_case_workflow(tmp_path):
    run_onboarding(create_workspace_app487, tmp_path,
                   inventory=True, expert=True, findings=True,
                   report=True, dorks_images=True)


@pytest.mark.parametrize("workspace", [create_workspace_app487], indirect=True)
def test_unicode_rationale_limits_in_rendered_chromium_form(workspace):
    """Real HTTP Chromium test includes the app's CSP and same-origin JS response."""
    import socket
    from pathlib import Path
    import threading
    import time
    from urllib.parse import urlencode
    import uvicorn
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
    assert 'src="/workbench/sources487/validation.js"' in response.text
    assert "default-src 'self'" in response.headers["content-security-policy"]

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 15
        while not server.started and time.monotonic() < deadline:
            time.sleep(.05)
        assert server.started
        base = f"http://127.0.0.1:{port}"
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            try:
                page = browser.new_page()
                launch_token = (Path(app.state.base_dir) / "data/security_364/local_session_token").read_text(encoding="utf-8").strip()
                assert page.goto(base + "/security/start?" + urlencode({"token": launch_token})).status == 200
                page.locator('input[name="username"]').fill("qa471")
                page.locator('input[name="password"]').fill("Build471!Password_88")
                page.get_by_role("button", name="Anmelden", exact=True).click()
                actual = page.goto(base + "/workbench/sources487?" + urlencode({"case_id": case_id}))
                assert actual.status == 200
                assert "default-src 'self'" in actual.headers["content-security-policy"]
                rationale = page.locator("#source487-rationale")
                assert rationale.count() == 1
                assert page.evaluate("""() => performance.getEntriesByType('resource')
                    .some(entry => entry.name.endsWith('/workbench/sources487/validation.js'))""")
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
    finally:
        server.should_exit = True
        thread.join(timeout=10)
