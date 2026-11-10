"""Build 492: real Chromium check of the new pages (CSP, phone width, form flow).

The web capture is submitted through the rendered form; the network transport is
simulated in-process, so no live third-party result is claimed.
"""
import os
import socket
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest
import uvicorn

from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye.application.intel492 import webcapture
from eagleeye.interfaces.web.app492 import create_workspace_app492
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build492_intel import ARTICLE, FakeTransport, _pdf_with_table_and_scan

PAGES = ["/workbench", "/workbench/intel", "/workbench/intel/web", "/workbench/intel/documents",
         "/workbench/intel/lineage", "/workbench/intel/network", "/workbench/entities488"]
SHOTS = os.environ.get("EAGLEEYE_SCREENSHOT_DIR", "")


@pytest.mark.parametrize("workspace", [create_workspace_app492], indirect=True)
def test_build492_pages_render_cleanly_and_capture_form_works(workspace, monkeypatch):
    from playwright.sync_api import sync_playwright

    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    FakeTransport.calls, FakeTransport.responses = [], {
        "https://news.example/x": (200, [("Content-Type", "text/html; charset=utf-8")], ARTICLE)}
    monkeypatch.setattr(webcapture, "PinnedTransport", FakeTransport)
    ctx.document_intelligence_458.import_bytes(identity=user, case_id=case_id, filename="bericht.pdf",
                                               raw=_pdf_with_table_and_scan(), title="Jahresbericht 2025")
    with EntityRegistry461(Path(ctx.base_dir) / "entity_registry_462.sqlite3") as reg:
        a = reg.create_entity(case_id=case_id, kind="person", label="Max Müller")
        b = reg.create_entity(case_id=case_id, kind="person", label="Mueller, Max")
        c = reg.create_entity(case_id=case_id, kind="company", label="Y GmbH mit einem sehr langen Firmennamen zur Umbruchprüfung")
        reg.create_relation(case_id=case_id, source_id=a["id"], target_id=c["id"], predicate="Geschäftsführer",
                            source_refs=["https://example.org/register"], state="supported")
        reg.create_relation(case_id=case_id, source_id=b["id"], target_id=c["id"], predicate="Gesellschafter",
                            source_refs=["https://example.org/register"])

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
            browser = runtime.chromium.launch(executable_path=os.environ.get("EAGLEEYE_CHROMIUM_PATH") or None)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                problems = []
                page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: problems.append(str(e)))
                page.on("response", lambda r: problems.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
                token = (Path(app.state.base_dir) / "data/security_364/local_session_token").read_text(encoding="utf-8").strip()
                assert page.goto(base + "/security/start?" + urlencode({"token": token})).status == 200
                page.locator('input[name="username"]').fill("qa471")
                page.locator('input[name="password"]').fill("Build471!Password_88")
                page.get_by_role("button", name="Anmelden", exact=True).click()

                # Guided workflow → hub → capture form, all by clicking.
                page.goto(base + "/workbench?" + urlencode({"case_id": case_id}))
                page.get_by_role("heading", name="Webseite als Beleg sichern").locator("xpath=..").get_by_role("link").click()
                assert page.url.startswith(base + "/workbench/intel/web")
                page.get_by_label("Öffentliche Adresse").fill("https://news.example/x")
                submit = page.get_by_role("button", name="Seite jetzt sichern")
                # Native validation keeps the OPSEC confirmation mandatory.
                assert page.locator('form[action="/workbench/intel/web"] input[name="opsec"]').first.evaluate("el => el.required")
                page.locator('form[action="/workbench/intel/web"] input[name="opsec"]').first.check()
                submit.click()
                page.wait_for_load_state()
                if "done=live" not in page.url:
                    raise AssertionError(page.url + " :: " + page.locator("body").inner_text()[:800])
                assert page.get_by_role("status").inner_text().startswith("Seite gesichert")
                assert page.get_by_text("✓ unverändert").count() == 1
                assert FakeTransport.calls == ["https://news.example/x"]

                for width in (1280, 390):
                    page.set_viewport_size({"width": width, "height": 900})
                    for path in PAGES:
                        response = page.goto(base + path + "?" + urlencode({"case_id": case_id}))
                        assert response.status == 200, path
                        assert page.locator("h1").count() == 1, path
                        overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
                        assert overflow <= 1, f"{path} scrolls horizontally by {overflow}px at {width}px"
                        unlabeled = page.evaluate("""() => [...document.querySelectorAll('main input:not([type=hidden]), main select, main textarea')]
                            .filter(el => !el.closest('label') && !el.getAttribute('aria-label')).length""")
                        assert unlabeled == 0, path
                        if SHOTS:
                            Path(SHOTS).mkdir(parents=True, exist_ok=True)
                            name = path.strip("/").replace("/", "_") + f"_{width}.png"
                            page.screenshot(path=str(Path(SHOTS) / name), full_page=True)
                assert not [p for p in problems if "Content Security Policy" in p or "Refused" in p], problems
                # /favicon.ico is absent since earlier builds (generic console 404 without a page response).
                assert not [p for p in problems if not p.startswith("Failed to load resource")], problems
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
