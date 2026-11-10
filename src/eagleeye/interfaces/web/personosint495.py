"""Build 495: one-case PersonOSINT workbench, without a competing server or DB.

This is a MANUAL link discovery panel. It performs no background HTTP requests.
External search sites learn the supplied query only after the user clicks.
"""
from __future__ import annotations

from html import escape
import unicodedata
from urllib.parse import urlencode, quote

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

from .operations476 import case_access, page

SOURCES = {
    "person": [
        ("Wikidata", "www.wikidata.org", "Öffentlich dokumentierte Personen und Beziehungen",
         "https://www.wikidata.org/w/index.php?search={query}"),
        ("OpenAlex", "api.openalex.org", "Wissenschaftliche Autoren und Institutionen",
         "https://api.openalex.org/authors?search={query}"),
        ("GitHub", "github.com", "Öffentliche Profile; keine verifizierte Identität",
         "https://github.com/search?q={query}&type=users"),
        ("ORCID", "orcid.org", "Forschendenprofile und institutionelle Angaben",
         "https://orcid.org/orcid-search/search?searchQuery={query}"),
    ],
    "unternehmen": [
        ("UK Companies House", "find-and-update.company-information.service.gov.uk",
         "Offizielle britische Unternehmensregistersuche",
         "https://find-and-update.company-information.service.gov.uk/search?q={query}"),
        ("OpenCorporates", "opencorporates.com", "Öffentlich zusammengestellte Registereinträge",
         "https://opencorporates.com/companies?q={query}"),
        ("Wikidata", "www.wikidata.org", "Beschriebene Organisationen und öffentliche Beziehungen",
         "https://www.wikidata.org/w/index.php?search={query}"),
        ("GitHub", "github.com", "Öffentliche Organisations- und Projektspuren",
         "https://github.com/search?q={query}&type=repositories"),
    ],
    "benutzername": [
        ("GitHub", "github.com", "Öffentliche Benutzerprofile",
         "https://github.com/search?q={query}&type=users"),
        ("GitLab", "gitlab.com", "Öffentliche Profile und Projekte",
         "https://gitlab.com/search?search={query}&scope=users"),
        ("Codeberg", "codeberg.org", "Öffentliche Code-Repositories",
         "https://codeberg.org/explore/repos?q={query}"),
    ],
}
WORKFLOW = [
    ("PersonOSINT-Quellen importieren", "/workbench/personosint493"),
    ("PersonOSINT-Entitäten prüfen", "/workbench/personosint494"),
    ("Ungeprüfte Recherchefunde", "/workbench/leads483"),
    ("Original-Webbeleg sichern (WARC)", "/workbench/intel/web"),
    ("Originaldokumente und Fundstellen", "/documents458"),
    ("Entity-Prüfung", "/workbench/entities488"),
    ("Netzwerk und Beziehungen", "/workbench/intel/network"),
    ("Prüfung und Bericht", "/workbench/report"),
]


def external_links(term: str, kind: str) -> list[dict]:
    if kind not in SOURCES:
        raise ValueError("Unbekannte Recherchekategorie")
    if not isinstance(term, str) or len(term) > 120 or any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in term):
        raise ValueError("Ungültiger Suchbegriff")
    term = " ".join(term.split())
    if not term:
        return []
    query = quote(term, safe="")
    return [
        {"provider": label, "host": host, "note": description,
         "url": template.replace("{query}", query)}
        for label, host, description, template in SOURCES[kind]
    ]


def attach_personosint495(app, build: str) -> None:
    app.state.personosint495 = True

    @app.get("/workbench/personosint495", response_class=HTMLResponse)
    def person_workbench(request: Request, case_id: str = "", kind: str = "person", term: str = ""):
        _user, _case = case_access(app, request, case_id)
        # Existing canonical public-provider registry: read-only catalogue, no network call.
        # Manual discovery must remain usable if an optional provider registry fails.
        # Do not expose provider exception details in the rendered case workspace.
        try:
            provider_catalog = app.state.context.provider_collection_120.list_providers()
        except Exception:
            provider_catalog = []
        try:
            links = external_links(term, kind)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        opts = "".join(
            '<option value="' + escape(k, quote=True) + '"' +
            (' selected' if kind == k else '') + '>' +
            escape({"person":"Person", "unternehmen":"Unternehmen", "benutzername":"Benutzername"}[k]) +
            '</option>' for k in SOURCES
        )
        body = (
            "<p>Ein gemeinsamer Recherchearbeitsplatz für öffentliche Personen- und "
            "Unternehmensquellen. PersonOSINT-Recherche, EagleEye-Webbelege, "
            "Entitätenprüfung und Graph bleiben Teil derselben Fallakte.</p>"
            '<section class="card"><h2>Öffentliche Quellen gezielt öffnen</h2>'
            '<form method="get" action="/workbench/personosint495">'
            '<input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '">'
            '<label for="po-kind">Recherchetyp</label><select name="kind" id="po-kind">' + opts + '</select>'
            '<label for="po-term">Suchbegriff</label>'
            '<input type="search" id="po-term" name="term" maxlength="120" value="' +
            escape(term, quote=True) + '" placeholder="Name, Firma oder Benutzername">'
            '<button type="submit">Quellenlinks vorbereiten</button></form>'
            '<p class="warn">Diese Seite ruft keine externen Anbieter automatisch auf. '
            'Erst dein Klick übermittelt den Suchbegriff an den Anbieter. '
            'Externe Zugriffe sind nicht automatisch anonymisiert oder Beweise. '
            'Vorher Zweck, Freigabe und OPSEC prüfen.</p></section>'
        )
        if links:
            body += "<h2>Quellenangebote – ungeprüft</h2>"
            for link in links:
                body += (
                    '<section class="card"><h3>' + escape(link["provider"]) + '</h3>'
                    '<p>' + escape(link["note"]) + '</p>'
                    '<p><a target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer" href="' +
                    escape(link["url"], quote=True) + '">Öffentliche Suche öffnen (' +
                    escape(link["host"]) + ')</a></p></section>'
                )
        # Show the *real* governed adapters already present in EagleEye, rather
        # than presenting manual Claude-source links as if they were automated.
        relevant_types = {"public_code_profile", "scholarly_identity", "scholarly_metadata",
                          "corporate_registry", "authority_identity", "social_profile"}
        governed = [p for p in provider_catalog if p.get("provider_type") in relevant_types]
        body += ("<h2>Bestehende kontrollierte EagleEye-Provider (" + str(len(governed)) + ")</h2>"
                 "<p>Diese Adapter verwenden den gemeinsamen Recherche- und Freigabemotor. "
                 "Ihre Ausführung ist hier nicht automatisch erlaubt; Live-Abfragen erfordern "
                 "eine gültige fallgebundene Suchfreigabe.</p>")
        for adapter in governed:
            body += ('<section class="card"><strong>' + escape(adapter["label"]) + '</strong>'
                     '<p>' + escape(", ".join(adapter.get("allowed_hosts", []))) + '</p>'
                     '<p class="muted">' + escape(str(adapter.get("terms_profile") or "")) + '</p></section>')
        body += ('<p><a href="/workbench/expert?' + escape(urlencode({"case_id":case_id}),quote=True) +
                 '">Gemeinsame freigabepflichtige Expertenwerkzeuge öffnen</a></p>')
        body += "<h2>Weiter im gemeinsamen EagleEye-Fall</h2><div class='grid'>"
        for title, path in WORKFLOW:
            url = path + "?" + urlencode({"case_id":case_id})
            body += '<section class="card"><a href="' + escape(url, quote=True) + '">' + escape(title) + '</a></section>'
        body += "</div><p>Alle überführten Treffer bleiben bis zur Originalprüfung ausdrücklich unbestätigt.</p>"
        return HTMLResponse(page("PersonOSINT Intelligence – EagleEye 495", case_id, body, build),
                            headers={"Cache-Control":"no-store", "Referrer-Policy":"no-referrer"})
