"""Chromium operator acceptance: first case, public source, note, review, export, narrow UI."""
import hashlib
import socket
import threading
import time
from urllib.parse import urlencode

import pytest
import uvicorn
from eagleeye.interfaces.web.app480 import create_workspace_app480

def test_real_chromium_operational_case_workflow(tmp_path):
    sync=pytest.importorskip("playwright.sync_api")
    app=create_workspace_app480(base_dir=tmp_path)
    ctx=app.state.context
    password="Random!Trusted-Phrase_44881"
    ctx.team_identity_359.create_initial_admin(
        username="gui480",display_name="Browser QA",password=password)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=port,log_level="warning"))
    thread=threading.Thread(target=server.run,daemon=True)
    thread.start()
    try:
        deadline=time.monotonic()+20
        while not server.started and time.monotonic()<deadline:
            time.sleep(.05)
        assert server.started
        with sync.sync_playwright() as pw:
            browser=pw.chromium.launch()
            page=browser.new_page(viewport={"width":1280,"height":900},accept_downloads=True)
            errors=[]
            page.on("pageerror",lambda e:errors.append(str(e)))
            base=f"http://127.0.0.1:{port}"
            launch_token=(tmp_path/"data/security_364/local_session_token").read_text().strip()
            response=page.goto(base+"/security/start?"+urlencode({"token":launch_token}))
            assert response.status==200
            page.locator("input[name=username]").fill("gui480")
            page.locator("input[name=password]").fill(password)
            page.get_by_role("button",name="Anmelden",exact=True).click()
            page.get_by_role("heading",name="Neuen Ermittlungsfall anlegen").wait_for()
            page.locator('input[name=title]').fill("OSINT public source trial")
            page.locator('input[name=client]').fill("Browser QA")
            page.locator('textarea[name=purpose]').fill("Validate a bounded public research process.")
            page.locator('textarea[name=legal_basis]').fill("public_data")
            with page.expect_response(lambda r: r.request.method=="POST" and r.url.endswith("/cases")) as submission:
                page.get_by_role("button",name="Fall anlegen").click()
            posted=submission.value
            assert posted.status==303, (posted.status,posted.text()[:700],page.url)
            case_url=posted.headers.get("location","")
            assert case_url.startswith("/cases/"), (case_url,page.url)
            case_id=case_url.split("/cases/",1)[1].split("?",1)[0]
            page.goto(base+"/?"+urlencode({"case_id":case_id}))
            assert "OSINT public source trial" in page.locator("body").inner_text()
            # Import a synthetic public source into the real authenticated case store.
            session=ctx.team_identity_359.authenticate(
                username="gui480",password=password,client_fingerprint="setup-browser")
            ident=ctx.team_identity_359.validate_session(
                session.token,client_fingerprint="setup-browser",touch=False)
            document=ctx.document_intelligence_458.import_bytes(
                identity=ident,case_id=case_id,filename="synthetic-source.txt",
                raw=b"Original public report says the research centre was established in 2001.",
                title="Public report for UI acceptance",
                source_url="https://example.org/public")
            assert document["document_id"]
            page.goto(base+"/")
            page.get_by_role("link",name="Geführte Recherche",exact=True).click()
            page.get_by_role("heading",name="Dein Ermittlungs- und Rechercheablauf").wait_for()
            source_card=page.locator("section.card").filter(has_text="Quellenbestand")
            source_card.get_by_role("link",name="Jetzt öffnen").click()
            page.get_by_role("heading",name="Quelleninventar und Fundstellen").wait_for()
            assert "Public report for UI acceptance" in page.locator("main").inner_text()
            page.goto(base+"/workbench/findings?"+urlencode({"case_id":case_id}))
            page.locator('select[name=anchor_ref]').select_option(index=0)
            page.locator('input[name=title]').fill("Documented founding date")
            page.locator('textarea[name=interpretation]').fill(
                "The text proposes an establishment year; independent corroboration is pending.")
            page.get_by_role("button",name="Mit Quelle als Arbeitsbefund speichern").click()
            page.get_by_role("heading",name="Documented founding date").wait_for()
            page.goto(base+"/workbench/report?"+urlencode({"case_id":case_id}))
            page.locator('textarea[name=reason]').fill(
                "Original anchor reviewed in this case; independent source still required.")
            page.get_by_role("button",name="Als eigengeprüft kennzeichnen").click()
            assert "reviewed_self" in page.locator("main").inner_text()
            with page.expect_download() as output:
                page.get_by_role("link",name="Arbeitsbericht als Markdown herunterladen").click()
            assert output.value.suggested_filename.endswith("_Arbeitsbericht.md")
            page.goto(base+"/workbench/checkpoint?"+urlencode({"case_id":case_id}))
            page.get_by_role("heading",name="Operativer Prüfpunkt 480").wait_for()
            assert "Produktionsreife" in page.locator("main").inner_text()
            page.set_viewport_size({"width":390,"height":844})
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
            page.screenshot(path=str(tmp_path/"build480-mobile.png"),full_page=True)
            assert not errors,errors
            browser.close()
    finally:
        server.should_exit=True
        thread.join(timeout=15)
        ctx.close()
