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
    try:
        ctx.team_governance_359.authorize(user,case_id=case_id,
            capability=capability,object_type="operational_case",object_id=case_id)
    except PermissionError as exc:
        raise HTTPException(403,"Keine Fallberechtigung") from exc
    cases=visible_operational_cases(ctx,user)
    case=next((c for c in cases if str(c.get("case_id"))==case_id),None)
    if case is None:
        ctx.team_identity_359.record_access(user_id=user['user_id'],username=user['username'],
            session_id=user.get('session_id',''),case_id=case_id,capability=capability,
            allowed=False,reason='not_an_operational_visible_case',object_type='operational_case',object_id=case_id)
        raise HTTPException(403,"Kein Zugriff auf diesen Fall")
    return user, case


def page(title, case_id, body, build):
    link = lambda p: escape(p+"?"+urlencode({"case_id":case_id}),quote=True)
    return ('<!doctype html><html lang="de"><head><meta charset="utf-8">'
       '<meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title>'
       '<style>body{font:16px/1.6 system-ui;background:#102238;color:#f4faff;margin:0}'
       'main{max-width:1080px;margin:1.5rem auto;padding:1rem}'
       'header{background:#1d3856;padding:1rem}nav{display:flex;gap:1rem;flex-wrap:wrap}'
       'a{color:#9af3de}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem}'
       '.card{overflow-wrap:anywhere;background:#1c3451;border:1px solid #647b93;border-radius:12px;padding:1.2rem;margin:.6rem 0}'
       '.warn{border-left:5px solid #ffd18a;padding:.8rem;background:#344b61}'
       'input,textarea,select{box-sizing:border-box;width:100%;padding:.6rem;margin:.3rem 0 1rem}'
       'button{padding:.7rem;cursor:pointer}table{width:100%;border-collapse:collapse}'
       'td,th{padding:.6rem;text-align:left;border-bottom:1px solid #647b93;word-break:break-word}'
       'h1{font-size:1.7rem}h2{font-size:1.15rem}a:focus,button:focus{outline:3px solid #f9e099}'
       '</style></head><body><header><strong>EagleEye – Build '+escape(str(build))+'</strong>'
       '<nav><a href="'+link('/')+'">Hauptansicht</a><a href="/new-case">Neuen Fall anlegen</a>'
       '<a href="'+link('/workbench')+'">Arbeitsablauf</a>'
       '<a href="'+link('/documents458')+'">Dokumente &amp; Quellen</a>'
       '<a href="'+link('/entities462')+'">Entitäten</a>'
       '<a href="'+link('/workbench/expert')+'">Expertenwerkzeuge</a>'
       '<a href="'+link('/workbench/bridge481')+'">Quelle → Evidence</a>' + ('<a href="'+link('/workbench/sources487')+'">Quellenzuordnung</a>' if int(str(build).split(".")[0]) >= 487 else '') + ('<a href="'+link('/workbench/entities488')+'">Entity-Prüfung</a>' if int(str(build).split(".")[0]) >= 488 else '') + '</nav></header><main><h1>'+escape(title)+'</h1>'
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
        if not case_id:
            fp=hashlib.sha256("|".join((request.headers.get("user-agent",""),
                request.headers.get("accept-language",""),request.client.host if request.client else "")).encode()).hexdigest()
            current=ctx.team_identity_359.validate_session(request.cookies.get(COOKIE,""),client_fingerprint=fp,touch=True)
            if current:
                available=visible_operational_cases(ctx,current)
                case_id=str(available[0]['case_id']) if available else ""
        result = old_home(request, view=view, case_id=case_id)
        if not isinstance(result, HTMLResponse):
            return result
        case_access(app,request,case_id)
        href = "/workbench?" + urlencode({"case_id":case_id})
        expert_url = "/workbench/expert?" + urlencode({"case_id":case_id})
        html = result.body.decode("utf-8")
        # Link old expert entrypoints to the preserved Build-448 advanced panels,
        # rather than a possibly empty or redirected legacy workspace.
        html = html.replace('href="/legacy?case_id=', 'href="/workbench/expert?case_id=')
        html = html.replace('href="/legacy"', 'href="'+escape(expert_url,quote=True)+'"')
        html = html.replace(
            "</nav>", '<a href="'+escape(href,quote=True)+'">Geführte Recherche</a>'
            '<a href="'+escape(expert_url,quote=True)+'">Alle Ermittlungswerkzeuge</a>'
            '</nav>', 1)
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
        # Number steps in their actual displayed order: previous versions
        # duplicated step six once advanced tools and sources were appended.
        step_index = 0
        intel = bool(getattr(app.state, "intel492", False))
        def step(n,title,desc,path):
            nonlocal step_index
            step_index += 1
            return ('<section class="card"><h2>'+str(step_index)+'. '+escape(title)+'</h2>'
                '<p>'+escape(desc)+'</p><a href="'+escape(path+"?"+urlencode({"case_id":case_id}),quote=True)
                +'">Jetzt öffnen →</a></section>')
        steps = [
            step(1,"Auftrag & Leitfragen","Rechercheziel, Rechtsgrundlage, Untersuchungsgrenzen festlegen.","/workflow461"),
            step(2,"Öffentliche Quellen beschaffen","Rechtmäßig zugängliche Quellen gezielt erfassen.","/collect469"),
            step(3,"Dokumente & Originalstellen","Originaldateien importieren, Textanker und Herkunft prüfen.","/documents458"),
            step(4,"Entitäten & Beziehungen","Beziehungen als Hypothesen formulieren und im Graph überprüfen.","/graph464"),
            step(5,"Quellenkritische Fallprüfung","Unklare und fehlende Belege sichtbar halten.","/review465"),
            step(6,"Erweiterte Ermittlungswerkzeuge",
                 "Vorhandene KI-, Evidence-, Claims-, Graph-, Timeline- und Dossierfunktionen fallbezogen öffnen.",
                 "/workbench/expert"),
            step(7,"Evidence → Claims → Dossier",
                 "Original-Evidence und importierte Dokumente unterscheiden, belegte Claims und formale Vier-Augen-Freigabe nachvollziehen.",
                 "/workbench/closure"),
        ]
        if stage>=477:
            steps.append(step(6,"Quellenbestand","Alle importierten Dokumente mit Herkunft und Vollständigkeit sehen.","/workbench/sources"))
        if stage>=478:
            steps.append(step(7,"Arbeitsbefunde","Eigene beleggebundene Beobachtungen als nicht bestätigte Befunde speichern.","/workbench/findings"))
        if stage>=479:
            steps.append(step(8,"Arbeitsbericht","Quellengebundenen Bericht zur manuellen Prüfung und Weiterarbeit erzeugen.","/workbench/report"))
        if stage>=480:
            steps.append(step(9,"Prüfpunkt 480","Belegstand und offene Einsatzgrenzen transparent überprüfen.","/workbench/checkpoint"))
        if stage>=481:
            steps.append(step(10,"Geprüfte Quellen als Evidence übernehmen","Originaldokument nach manueller Extraktionsprüfung fallgebunden in die prüfpflichtige Evidence-Kette aufnehmen.","/workbench/bridge481"))
        if stage>=482:
            # The operator sees six stable work phases, not an unsorted build ledger.
            # Older build factories retain the exact previous layout.
            step_index = 0
            phases = [
                ("1 · Auftrag und Fall",
                 [step(1,"Rechercheauftrag definieren",
                       "Rechtsgrundlage, Ziel und erlaubte Methoden zuerst dokumentieren.",
                       "/workflow461")]),
                ("2 · Recherche",
                 [step(2,"Dork-Recherche",
                       "Öffentliche Suchlinks mit der vorhandenen Dork-Engine erzeugen.",
                       "/workbench/dorks482"),
                  ] + ([step(2,"Ermittlungsplan & Freigabe",
                       "Rechercheziele, Arbeitsschritte, Quellfreigaben und Ergebnisse protokollieren.",
                       "/workbench/plan496")] if getattr(app.state, "investigation_plan496", False) else []) + ([step(3,"Recherchefunde sichern",
                       "Einen tatsächlich im Browser geprüften Treffer als ungeprüften Fallhinweis speichern.",
                       "/workbench/leads483")] if stage>=483 else []) + ([step(3,"PersonOSINT Intelligence",
                       "Gezielt öffentliche Quellen recherchieren und Ergebnisse in der einen Fallakte weiterverarbeiten.",
                       "/workbench/personosint495")] if getattr(app.state,"personosint495",False) else []) + ([step(3,"PersonOSINT-Quellen übernehmen",
                       "Öffentliche Recherchetreffer aus dem Claude-PersonOSINT-Export als ungeprüfte Hinweise aufnehmen.",
                       "/workbench/personosint493")] if getattr(app.state,"personosint493",False) else []) + [
                  ] + ([step(3,"Öffentliche Quellen und Personenrecherche",
                       "Nachrichten, Personenverzeichnisse, Forschung und Register gemeinsam auswählen und fallgebunden abfragen.",
                       "/workbench/public-sources")] if getattr(app.state,"public_sources501",False) else []) + [
                  step(3,"Öffentliche Datenquellen",
                       "DNS-, RDAP- oder DOI-Quellen im definierten Fall abrufen.",
                       "/collect469")] + ([step(3,"Webseite als Beleg sichern",
                       "Öffentliche oder archivierte Seite als WARC-Original mit prüfbarem Haupttext sichern.",
                       "/workbench/intel/web")] if intel else [])),
                ("3 · Quellen und Evidence",
                 [step(4,"Originaldokumente sichern",
                       "TXT/PDF importieren, Herkunft und Textanker prüfen.",
                       "/documents458"),
                  step(5,"Bildakte und Metadaten",
                       "Bildoriginale, EXIF und lokale Ähnlichkeitsanalyse prüfen.",
                       "/workbench/images482"),
                  ] + ([step(5,"Bildbeziehungen vergleichen",
                        "Vorhandene lokale Ähnlichkeitskandidaten anhand der Originalbilder bewerten.",
                        "/workbench/media484")] if stage>=484 else []) + [

                  ] + ([step(5,"Struktur & Texterkennung",
                        "Tabellen, Überschriften und Scans (OCR) als zusätzliche Fundstellen erschließen.",
                        "/workbench/intel/documents"),
                        step(5,"Quellenunabhängigkeit",
                        "Übernommene und gespiegelte Texte erkennen: wie viele unabhängige Ursprünge?",
                        "/workbench/intel/lineage")] if intel else []) + [
                  step(6,"Quelleninventar",
                       "Originaldokumente und Vollständigkeit überprüfen.",
                       "/workbench/sources"),
                  step(7,"Geprüfte Dokumente als Evidence",
                       "Nur nach ausdrücklicher manueller Extraktionsprüfung übernehmen.",
                       "/workbench/bridge481")]),
                ("4 · Entitäten und Graph",
                 [step(8,"Interaktiver Beziehungsgraph",
                       "Belegverknüpfungen und unbestätigte Beziehungen prüfen.",
                       "/graph464")] + ([step(9,"Entity-Kandidaten prüfen",
                       "Ähnliche reale Fallentitäten manuell prüfen und auditieren – keine automatische Zusammenführung.",
                       "/workbench/entities488")] if stage>=488 else []) + [
                  ] + ([step(9,"Netzwerkanalyse",
                       "Gruppen, Brückenpersonen und am besten belegte Verbindungswege auswerten.",
                       "/workbench/intel/network")] if intel else []) + [
                  ] + ([step(9,"PersonOSINT-Entitäten prüfen",
                       "Externe Personen und Organisationen mit Prüfvermerk vormerken, ohne den Graph zu verändern.",
                       "/workbench/personosint494")] if getattr(app.state,"personosint494",False) else []) + [
                  step(9,"KI-Ermittler",
                       "Quellengebundene Vorschläge – nicht bestätigte Tatsachen.",
                       "/assistant471")]),
                ("5 · Prüfung und Gegenbelege",
                 [step(10,"Evidence → Claims → Dossier",
                       "Bestehende Prüf- und Vier-Augen-Gates nachvollziehen.",
                       "/workbench/closure"),
                  step(11,"Quellenkritische Fallprüfung",
                       "Widersprüche und Beleglücken offen kennzeichnen.",
                       "/review465"),
                  step(12,"Quellengebundene Arbeitsbefunde",
                       "Eigene Beobachtungen mit Originaltextstellen sichern.",
                       "/workbench/findings")]),
                ("6 · Ergebnis und Übergabe",
                 [step(13,"Quellenkritischer Arbeitsbericht",
                       "Einen überprüfbaren, ausdrücklich nicht freigegebenen Arbeitsbericht exportieren.",
                       "/workbench/report"),
                  step(14,"Operativer Prüfpunkt",
                       "Vollständigkeit und Freigabegrenzen vor Übergabe prüfen.",
                       "/workbench/checkpoint"),
                  step(15,"Erweiterte Ermittlungswerkzeuge",
                       "Originale Evidence-, KI-, Graph- und Dossiersysteme öffnen.",
                       "/workbench/expert")
                  ] + ([step(16,"Pilotprüfung: vollständiger Recherchefall",
                      "Den echten Fallbestand und die nicht erfüllten Prüfungen überprüfen.",
                      "/workbench/pilot485")] if stage>=485 else [])),
            ]
            grouped = "".join(
                '<section aria-label="'+escape(heading,quote=True)+'"><h2>'+escape(heading)+
                '</h2><div class="grid">'+ "".join(cards)+'</div></section>'
                for heading,cards in phases
            )
        body = '<p><strong>'+escape(str(case.get("title") or ""))+'</strong> · '+str(len(docs))+' gespeicherte Dokumente.</p>'
        body += '<section class="card"><h2>Dein Rechercheauftrag</h2><p>'+escape(str(case.get('purpose') or 'Im Fall dokumentiert'))+'</p><p>Rechtsgrundlage: '+escape(str(case.get('legal_basis') or 'Im Fall dokumentiert'))+'</p></section>'
        if not docs:
            # A freshly created case is intentionally empty. Previously this was
            # indistinguishable from a broken scraper or a blank AI response.
            # Provide an actionable, non-automatic path through existing services.
            source_url = "/workbench/public-sources?" + urlencode({"case_id":case_id})
            import_url = "/documents458?" + urlencode({"case_id":case_id})
            body += (
                '<section class="card" role="status"><h2>Noch keine Dokumenttexte im Fall</h2>'
                '<p>Das Anlegen eines Falls startet <strong>keine automatische Recherche</strong>. '
                'EagleEye hat noch keine Originaldokumente, Quellentexte oder KI-Ausgaben für diesen Fall. '
                'Leere Ergebnislisten bedeuten nicht, dass eine Suche erfolglos war.</p>'
                '<p><strong>Erster Funktionsnachweis:</strong> Eine öffentliche TXT- oder PDF-Datei '
                'unter „Dokumente &amp; Quellen“ importieren und den gespeicherten Text prüfen. '
                'Alternativ eine passende Quelle auswählen, ein Suchpaket anlegen, '
                'ausdrücklich freigeben und den Einzelabruf starten. '
                'Nicht jede Katalogquelle besitzt einen ausführbaren Adapter.</p>'
                '<p>Der lokale KI-Ermittler benötigt zusätzlich ein bereits installiertes '
                'Ollama-Modell; ohne Modell bleibt die manuelle Fallarbeit möglich.</p>'
                '<nav><a href="' + escape(import_url, quote=True) + '">Dokumenttext importieren →</a> '
                '<a href="' + escape(source_url, quote=True) + '">Öffentliche Quellen prüfen →</a></nav>'
                '</section>'
            )
        body += grouped if stage>=482 else '<div class="grid">'+"".join(steps)+'</div>'
        return HTMLResponse(page("Dein Ermittlungs- und Rechercheablauf",case_id,body,workspace_build),
                            headers={"Cache-Control":"no-store"})

    # Reuse the existing, secure research views instead of reimplementing a
    # competing simplified claims/dossier system.
    from .tool_center477 import attach_tool_center
    attach_tool_center(app, workspace_build)
