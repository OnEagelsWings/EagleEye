"""Operational research workbench: visible tasks, real case state, no automatic truth promotion."""
from __future__ import annotations
import hashlib
from html import escape
from urllib.parse import urlencode
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from .app448 import COOKIE
from .app449 import _drop
from .app459 import visible_operational_cases


def case_access(app, request, case_id, capability="case.read"):
    ctx = app.state.context
    fp = hashlib.sha256("|".join((request.headers.get("user-agent",""),
             request.headers.get("accept-language",""),
             request.client.host if request.client else "")).encode()).hexdigest()
    user = ctx.team_identity_359.validate_session(request.cookies.get(COOKIE, ""),
                      client_fingerprint=fp, touch=True)
    if not user:
        raise HTTPException(401, "Bitte anmelden")
    cases = visible_operational_cases(ctx,user)
    case = next((c for c in cases if str(c.get("case_id")) == case_id), None)
    if case is None:
        raise HTTPException(403, "Kein Zugriff auf diesen Fall")
    try:
        ctx.team_governance_359.authorize(user, case_id=case_id,
                    capability=capability, object_type="operational_case", object_id=case_id)
    except PermissionError as exc:
        raise HTTPException(403, "Keine Fallberechtigung") from exc
    return user, case


def page(title, case_id, body, build):
    link = lambda p: escape(p+"?"+urlencode({"case_id":case_id}),quote=True)
    return ('<!doctype html><html lang="de"><head><meta charset="utf-8">'
       '<meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title>'
       '<style>body{font:16px/1.6 system-ui;background:#102238;color:#f4faff;margin:0}'
       'main{max-width:1080px;margin:1.5rem auto;padding:1rem}'
       'header{background:#1d3856;padding:1rem}nav{display:flex;gap:1rem;flex-wrap:wrap}'
       'a{color:#9af3de}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem}'
       '.card{background:#1c3451;border:1px solid #647b93;border-radius:12px;padding:1.2rem;margin:.6rem 0}'
       '.warn{border-left:5px solid #ffd18a;padding:.8rem;background:#344b61}'
       'input,textarea,select{box-sizing:border-box;width:100%;padding:.6rem;margin:.3rem 0 1rem}'
       'button{padding:.7rem;cursor:pointer}table{width:100%;border-collapse:collapse}'
       'td,th{padding:.6rem;text-align:left;border-bottom:1px solid #647b93;word-break:break-word}'
       'h1{font-size:1.7rem}h2{font-size:1.15rem}a:focus,button:focus{outline:3px solid #f9e099}'
       '</style></head><body><header><strong>EagleEye – Build '+escape(str(build))+'</strong>'
       '<nav><a href="/">Hauptansicht</a><a href="/new-case">Neuen Fall anlegen</a>'
       '<a href="'+link('/workbench')+'">Arbeitsablauf</a>'
       '<a href="'+link('/documents458')+'">Dokumente &amp; Quellen</a>'
       '<a href="'+link('/entities462')+'">Entitäten</a></nav></header><main><h1>'+escape(title)+'</h1>'
       +body+'<p class="warn"><strong>Entwicklungsstand: keine Produktivfreigabe.</strong>'
       ' Nur öffentliche oder synthetische, unkritische Quellen verwenden. KI-Entwürfe'
       ' und Beziehungen sind nicht automatisch bestätigte Tatsachen.</p>'
       '</main></body></html>')


def attach_workbench(app, workspace_build):
    ctx = app.state.context
    stage = int(workspace_build.split(".")[0])
    old_home = next((r.endpoint for r in reversed(app.router.routes)
                     if r.path == "/" and "GET" in (r.methods or set())), None)
    if old_home is None:
        raise RuntimeError("Main workspace route not found")
    _drop(app, "/", {"GET"})

    @app.get("/")
    def primary(request: Request, view: str = "overview", case_id: str = ""):
        result = old_home(request, view=view, case_id=case_id)
        if not isinstance(result, HTMLResponse):
            return result
        href = "/workbench?" + urlencode({"case_id":case_id})
        html = result.body.decode("utf-8").replace(
            "</nav>", '<a href="'+escape(href,quote=True)+'">Geführte Recherche</a></nav>', 1)
        return HTMLResponse(html, status_code=result.status_code,
                            headers={"Cache-Control":"no-store"})

    @app.get("/workbench", response_class=HTMLResponse)
    def workbench(request: Request, case_id: str = ""):
        if not case_id:
            fp = hashlib.sha256("|".join((request.headers.get("user-agent",""),
                request.headers.get("accept-language",""),
                request.client.host if request.client else "")).encode()).hexdigest()
            user = ctx.team_identity_359.validate_session(
                request.cookies.get(COOKIE,""),client_fingerprint=fp,touch=True)
            if not user:
                return RedirectResponse("/security/login",status_code=303)
            cases = visible_operational_cases(ctx,user)
            if not cases:
                return RedirectResponse("/new-case",status_code=303)
            case_id = str(cases[0]["case_id"])
        user,case = case_access(app,request,case_id)
        docs = ctx.document_intelligence_458.documents(identity=user,case_id=case_id)
        def step(n,title,desc,path):
            return ('<section class="card"><h2>'+str(n)+'. '+escape(title)+'</h2>'
                '<p>'+escape(desc)+'</p><a href="'+escape(path+"?"+urlencode({"case_id":case_id}),quote=True)
                +'">Jetzt öffnen →</a></section>')
        steps = [
            step(1,"Auftrag & Leitfragen","Rechercheziel, Rechtsgrundlage, Untersuchungsgrenzen festlegen.","/workflow461"),
            step(2,"Öffentliche Quellen beschaffen","Rechtmäßig zugängliche Quellen gezielt erfassen.","/collect469"),
            step(3,"Dokumente & Originalstellen","Originaldateien importieren, Textanker und Herkunft prüfen.","/documents458"),
            step(4,"Entitäten & Beziehungen","Beziehungen als Hypothesen formulieren und im Graph überprüfen.","/graph464"),
            step(5,"Quellenkritische Fallprüfung","Unklare und fehlende Belege sichtbar halten.","/review465"),
        ]
        if stage>=477:
            steps.append(step(6,"Quellenbestand","Alle importierten Dokumente mit Herkunft und Vollständigkeit sehen.","/workbench/sources"))
        if stage>=478:
            steps.append(step(7,"Arbeitsbefunde","Eigene beleggebundene Beobachtungen als nicht bestätigte Befunde speichern.","/workbench/findings"))
        if stage>=479:
            steps.append(step(8,"Arbeitsbericht","Quellengebundenen Bericht zur manuellen Prüfung und Weiterarbeit erzeugen.","/workbench/report"))
        if stage>=480:
            steps.append(step(9,"Prüfpunkt 480","Belegstand und offene Einsatzgrenzen transparent überprüfen.","/workbench/checkpoint"))
        body = '<p><strong>'+escape(str(case.get("title") or ""))+'</strong> · '+str(len(docs))+' gespeicherte Dokumente.</p>'
        body += '<div class="grid">'+"".join(steps)+'</div>'
        return HTMLResponse(page("Dein Ermittlungs- und Rechercheablauf",case_id,body,workspace_build),
                            headers={"Cache-Control":"no-store"})
