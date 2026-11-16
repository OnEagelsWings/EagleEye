"""Office pages in real Chromium: landing, mandate form, screening, booking, phone width, labels."""
import os
import socket
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import uvicorn

from eagleeye.interfaces.web.server import create_workspace_app

PW = "Build471!Password_88"
PAGES = ["/buero", "/buero/auftrag/neu", "/buero/mandanten", "/buero/einstellungen", "/buero/loeschprotokoll", "/buero/team", "/buero/konto"]


def test_office_pages_in_chromium(tmp_path):
    from playwright.sync_api import sync_playwright

    app = create_workspace_app(base_dir=tmp_path)
    ctx = app.state.context
    ctx.team_identity_359.create_initial_admin(username="chef", display_name="Chef", password=PW)
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
        base = f"http://127.0.0.1:{port}"
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=os.environ.get("EAGLEEYE_CHROMIUM_PATH") or None)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                problems = []
                page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: problems.append(str(e)))
                page.on("response", lambda r: problems.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
                token = (tmp_path / "data/security_364/local_session_token").read_text(encoding="utf-8").strip()
                page.goto(base + "/security/start?" + urlencode({"token": token}))
                page.locator('input[name="username"]').fill("chef")
                page.locator('input[name="password"]').fill(PW)
                page.get_by_role("button", name="Anmelden", exact=True).click()
                page.wait_for_load_state()
                assert urlparse(page.url).path == "/buero", "a fresh office starts in the office overview"

                page.get_by_role("link", name="Neuen Auftrag anlegen").click()
                page.get_by_label("Art des Mandanten").select_option("kanzlei")
                page.get_by_label("Name", exact=True).fill("Kanzlei Weber")
                page.get_by_label("Titel des Auftrags").fill("Vermögensermittlung Schuldner M.")
                page.get_by_label("Auftrag und Zweck (was soll geklärt werden, wofür?)").fill("Vermögenswerte zur Vollstreckung ermitteln.")
                page.locator('select[name="legal_basis_key"]').select_option("rechtsanspruch")
                page.get_by_role("button", name="Auftrag anlegen").click()
                page.wait_for_url("**done=created**")
                case_id = parse_qs(urlparse(page.url).query)["case_id"][0]
                assert page.get_by_role("status").inner_text().startswith("Auftrag angelegt")
                for question in ("beziehung", "schutz", "schutzanordnung", "anschrift"):
                    page.locator(f'input[name="q_{question}"][value="nein"]').check()
                page.locator('input[name="q_identitaet"][value="ja"]').check()
                page.get_by_label("Ausweis eingesehen (keine Kopie ohne Rechtsgrundlage)").check()
                page.get_by_label("Auftrag annehmen").check()
                page.get_by_role("button", name="Prüfung speichern").click()
                page.wait_for_url("**done=screened**")
                page.get_by_label("Dauer in Stunden (z. B. 1,5 oder 1:30)").fill("1:45")
                page.get_by_role("button", name="Zeit buchen").click()
                page.wait_for_url("**done=time**")
                assert page.get_by_text("1:45 Std.").count() >= 1
                page.get_by_role("link", name="Zur Recherche").click()
                assert urlparse(page.url).path == "/workbench"
                assert page.get_by_role("link", name="Büro", exact=True).count() == 1

                akte = "/buero/auftrag?" + urlencode({"case_id": case_id})
                for width in (1280, 390):
                    page.set_viewport_size({"width": width, "height": 900})
                    for path in PAGES + [akte]:
                        response = page.goto(base + path)
                        assert response.status == 200, path
                        assert page.locator("h1").count() == 1, path
                        overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
                        assert overflow <= 1, f"{path} scrolls horizontally by {overflow}px at {width}px"
                        unlabeled = page.evaluate("""() => [...document.querySelectorAll('main input:not([type=hidden]), main select, main textarea')]
                            .filter(el => !el.closest('label') && !el.getAttribute('aria-label') && !(el.id && document.querySelector('label[for="' + el.id + '"]'))).length""")
                        assert unlabeled == 0, path
                assert not [p for p in problems if not p.startswith("Failed to load resource")], problems
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
