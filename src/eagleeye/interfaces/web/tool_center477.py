"""Case-scoped restoration of already implemented advanced OSINT functions.

This page is a navigation bridge. It deliberately does not add bypass routes,
grant capabilities, generate reports or promote AI suggestions into evidence.
"""
from __future__ import annotations
from html import escape
from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import HTMLResponse

from .operations476 import case_access, page

# All views are the existing Build-448 investigator panels, not new substitutes.
ADVANCED_VIEWS = (
    ("research", "Recherche & Quellenarbeit",
     "Vorhandene Recherche-, Beschaffungs- und Auftragsfunktionen. Live-Abdeckung gesondert prüfen."),
    ("ai", "KI-Ermittlungsablauf",
     "Ältere fallbezogene KI-Abläufe; Vorschläge benötigen beleggestützte menschliche Prüfung."),
    ("evidence", "Evidence & Belegprüfung",
     "Erfasste Beweise und ihre Herkunft, Status- und Integritätsprüfung."),
    ("claims", "Claims, Hypothesen & Gegenbelege",
     "Aussagen nachvollziehbar aus Evidence ableiten, Prüfstatus und Unsicherheit beachten."),
    ("analysis", "Graph, Timeline & Beziehungsanalyse",
     "Vorhandene zeitliche/graphische Analysen; Beziehungen belegen statt aus Nähe zu schließen."),
    ("dossier", "Living Dossier & Freigabe",
     "Build-447-Dossierrevisionen und der Build-449-Vier-Augen-Prozess – kein automatischer Export."),
    ("operations", "Team, OPSEC & Review",
     "Bestehende Rollen-, Freigabe- und operative Auditfunktionen."),
)

# Explicitly scoped GET endpoints. Missing routes are reported, not faked.
SPECIAL_TOOLS = (
    ("Dokumente und Originalanker", "/documents458",
     "Lokaler PDF/TXT/Markdown-Import und verifizierbare Fundstellen."),
    ("Quelleninventar", "/workbench/sources",
     "Im Fall gespeicherte Dokumente und Herkunft."),
    ("Geführter Ermittlungsauftrag", "/workflow461",
     "Recherchefrage und Arbeitsschritte einordnen."),
    ("Öffentliche Metadaten", "/collect469",
     "Nur DNS, RDAP .com und Crossref; kein allgemeiner Webcrawler."),
    ("Entitätenregister", "/entities462",
     "Entitäten und Beziehungsdaten fallbezogen betrachten."),
    ("Interaktiver Netzwerkgraph", "/graph464",
     "Vorhandene graphische Fallbeziehungen."),
    ("Fallprüfung", "/review465",
     "Quellennachweise, Unsicherheit und Abweichungen überprüfen."),
    ("Lokaler KI-Ermittler", "/assistant471",
     "Quellengebundene Entwürfe; Ollama und lokal geladenes Modell erforderlich."),
    ("Arbeitsbefunde", "/workbench/findings",
     "Menschliche, an Originalanker gebundene vorläufige Beobachtungen (ab Build 478)."),
    ("Evidence → Claims → Dossier (Original-Workflow)", "/workbench/closure",
     "Echte Fallstände, Quellenlücke und vorhandene Vier-Augen-Gates nachvollziehen."),
    ("Quellenkritischer Arbeitsbericht", "/workbench/report",
     "Arbeitsbericht, keine behördliche/freigegebene Dossierfassung (ab Build 479)."),
)


def _path_exists(app, url_path):
    return any(
        getattr(route, "path", None) == url_path
        and "GET" in (getattr(route, "methods", set()) or set())
        for route in app.router.routes
    )


def _card(label, details, url=None, *, status=""):
    action = ('<a href="' + escape(url, quote=True) + '">Werkzeug öffnen →</a>'
              if url else '<span class="muted">In diesem Build nicht angebunden</span>')
    return ('<section class="card"><h2>' + escape(label) + '</h2><p>' +
            escape(details) + '</p>' +
            ('<p><small>' + escape(status) + '</small></p>' if status else '') +
            action + '</section>')


def attach_tool_center(app, build):
    @app.get("/workbench/expert", response_class=HTMLResponse)
    def expert_tools(request: Request, case_id: str = ""):
        # Case authorization and qualification-case isolation precede all links.
        user, case = case_access(app, request, case_id)
        del user
        params = {"case_id": case_id}
        cards = []
        for view, title, notes in ADVANCED_VIEWS:
            url = "/?" + urlencode({**params, "view": view})
            cards.append(_card(title, notes, url,
                               status="Bereits vorhandene Ermittleroberfläche · keine neue Testfunktion"))
        specials = []
        for label, route, notes in SPECIAL_TOOLS:
            available = _path_exists(app, route)
            url = route + "?" + urlencode(params) if available else None
            specials.append(_card(label, notes, url,
                                  status=("GET-Oberfläche vorhanden; Live-Funktion nicht durch die Linkprüfung belegt"
                                          if available else "Route im aktuellen Build nicht vorhanden")))
        main = (
            '<p>Aktiver Ermittlungsfall: <strong>' +
            escape(str(case.get("title") or "")) +
            '</strong>. Die folgenden Links öffnen <strong>die bereits bestehenden</strong> '
            'Ermittlungsfunktionen. Eine Route ist noch kein Nachweis funktionierender '
            'Websuche, Graphlogik oder Dossierqualität.</p>'
            '<p class="warn"><strong>Arbeitsregel:</strong> Quelle sichern → Originaltext prüfen → '
            'Evidence bewerten → Claim/Hypothese prüfen → Gegenbelege suchen → '
            'Dossierrevision → unabhängiges Vier-Augen-Review. '
            'Ein früheres Build-Protokoll ist keine Freigabe für vertrauliche Ermittlungen.</p>'
            '<h2>Vollständiger Ermittlungsarbeitsplatz (bestehende Build-448-/449-Funktionen)</h2>'
            '<div class="grid">' + "".join(cards) + '</div>'
            '<h2>Zusätzliche fallbezogene Werkzeuge</h2>'
            '<div class="grid">' + "".join(specials) + '</div>'
            '<p class="warn">Öffentliche DNS/RDAP/DOI-Abfragen übertragen Eingaben an externe Anbieter; '
            'keine personenbezogenen oder vertraulichen Suchkennzeichen. '
            'Ein freigegebener Dossierexport ist von einem einfachen Arbeitsbericht zu unterscheiden.</p>'
        )
        return HTMLResponse(
            page("Alle Ermittlungswerkzeuge – Expertenmodus", case_id, main, build),
            headers={"Cache-Control": "no-store", "Referrer-Policy": "same-origin"},
        )
