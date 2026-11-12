"""Source discovery and search packages in the existing plan/search/run tables.

This module does not introduce a second evidence, entity or case database.
Catalog browsing and preparing a package never issue network requests.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import unicodedata
from urllib.parse import quote

from . import plan496, execution497
from eagleeye.infrastructure.providers.contracts import ProviderRunRequest
from eagleeye.infrastructure.providers.policy import validate_public_scope

KINDS = {"topic": "Thema", "person": "Person", "company": "Unternehmen",
         "username": "Benutzername", "url": "Webadresse", "place": "Ort",
         "federal": "Bund, Bundestag und öffentliche Register"}


@dataclass(frozen=True)
class Source:
    key: str
    label: str
    kinds: tuple[str, ...]
    description: str
    website: str
    provider: str = ""
    access: str = "api"
    terms: str = "Originalrechte und Nutzungsbedingungen beachten."


SOURCES = (
    Source("gdelt", "GDELT", ("topic", "person", "company", "place"), "Internationale Medienverweise; DOC-Suche mit begrenztem Zeitfenster.", "https://www.gdeltproject.org/", "gdelt_doc_public_149", terms="Kostenlos; kein Volltext- oder Wahrheitsnachweis."),
    Source("media_cloud", "Media Cloud", ("topic", "person", "company"), "Medienvergleich, Artikelverweise und Berichterstattungsmuster.", "https://www.mediacloud.org/", access="setup", terms="Kostenloses Kontingent; eigener API-Zugang nötig; keine Artikelvolltexte."),
    Source("wayback", "Wayback Machine", ("url",), "Archivfassungen einer konkreten öffentlichen Webadresse.", "https://web.archive.org/", "wayback_cdx_public_120"),
    Source("common_crawl", "Common Crawl", ("url",), "URL-Index einer ausdrücklich ausgewählten Crawl-Sammlung; keine globale Stichwortsuche.", "https://index.commoncrawl.org/", "commoncrawl_index_public_501", terms="Kostenlos; Indexhinweise, kein WARC-Download und kein Replay."),
    Source("internet_archive", "Internet Archive", ("topic", "person", "company"), "Öffentliche Archivmetadaten, Bücher und andere Veröffentlichungen.", "https://archive.org/", "internet_archive_public_128"),
    Source("gnd", "GND / lobid – Personen", ("person",), "Normierte Personen mit Namensvarianten, Berufsangaben und GND-Kennung.", "https://lobid.org/gnd", "lobid_gnd_persons_public_501", terms="CC0; jede Zuordnung bleibt ein Personenkandidat."),
    Source("abgeordnetenwatch", "Abgeordnetenwatch", ("person",), "Kandidierende und Mandatsträger; Funktion und Zeitraum separat prüfen.", "https://www.abgeordnetenwatch.de/", "abgeordnetenwatch_persons_public_501", terms="CC0; öffentliches politisches Wirken, keine automatische Identitätsbestätigung."),
    Source("wikidata", "Wikidata", ("topic", "person", "company", "place"), "Mehrsprachige öffentliche Entitäten, Beschreibungen und Kennungen.", "https://www.wikidata.org/", "wikidata_entities_public_128", terms="Strukturierte Daten CC0; Community-Angaben gegenprüfen."),
    Source("openalex_authors", "OpenAlex – Autoren", ("person",), "Forschendenprofile und institutionelle Publikationsbezüge.", "https://openalex.org/", "openalex_authors_public_128", terms="Kostenloses anonymes Kontingent; kein kostenpflichtiger Fallback."),
    Source("openalex_works", "OpenAlex – Veröffentlichungen", ("topic", "company"), "Forschungsarbeiten und DOI-Verweise zu einem Thema.", "https://openalex.org/", "openalex_works_public_501", terms="Kostenloses anonymes Kontingent; Volltextrechte je Original."),
    Source("crossref_authors", "Crossref – Autorenbezug", ("person",), "Publikationen zu einem Autorennamen; Namensgleichheit ist keine Identität.", "https://www.crossref.org/", "crossref_works_public_128"),
    Source("crossref_topics", "Crossref – Themen", ("topic", "company"), "Bibliografische Themenrecherche über Titel und weitere Metadaten.", "https://www.crossref.org/", "crossref_topics_public_501"),
    Source("dblp", "DBLP – Autoren", ("person",), "Öffentliche Autorenverzeichnisse aus der Informatik.", "https://dblp.org/", "dblp_authors_public_149"),
    Source("viaf", "VIAF", ("person",), "Bibliothekarische Normdatensätze aus verschiedenen Ländern.", "https://viaf.org/", "viaf_autosuggest_public_149"),
    Source("openlibrary", "Open Library – Autoren", ("person",), "Autoren und bibliografische Namensvarianten.", "https://openlibrary.org/", "openlibrary_authors_public_128"),
    Source("orcid", "ORCID", ("person",), "Öffentliche Forschendenprofile und ORCID-Kennungen.", "https://orcid.org/orcid-search/search?searchQuery={query}", access="manual", terms="Öffentliche Suche; Public API nur für nichtkommerzielle Dienste, daher hier kein automatischer Anschluss."),
    Source("lobbyregister", "Lobbyregister des Bundestages", ("person", "company"), "Öffentlich eingetragene Personen, Vertretungsrollen und Organisationen.", "https://www.lobbyregister.bundestag.de/personensuche", access="manual"),
    Source("eu_whoiswho", "EU Whoiswho", ("person", "company"), "Amtliche öffentliche Funktionen und Organisationseinheiten der EU.", "https://op.europa.eu/de/web/who-is-who", access="manual", terms="Öffentliche berufliche Rollen; Zweck- und Weiterverwendungsbedingungen beachten."),
    Source("companies_house", "Companies House – Officers", ("person", "company"), "Britische Gesellschaften und öffentlich registrierte Organfunktionen.", "https://find-and-update.company-information.service.gov.uk/search/officers?q={query}", access="manual", terms="Öffentliche Suche; API benötigt eigenen Zugang."),
    Source("handelsregister", "Handels- und Vereinsregister", ("person", "company"), "Amtliche Registerauszüge mit öffentlich eingetragenen Vertretungs- und Organfunktionen.", "https://www.handelsregister.de/", access="manual", terms="Kostenlose Einzelabrufe; systematischer Aufbau paralleler Register ist unzulässig."),
    Source("github", "GitHub – öffentliches Profil", ("username",), "Öffentliches Profil zu einem konkreten Benutzernamen.", "https://github.com/", "github_public_profile_120"),
    Source("gitlab", "GitLab – öffentliches Profil", ("username",), "Öffentliches Profil zu einem konkreten Benutzernamen.", "https://gitlab.com/", "gitlab_public_profile_120"),
    Source("bluesky", "Bluesky – öffentliche Profile", ("person", "username"), "Öffentliche Profilsuche, ausschließlich unbestätigte Kandidaten.", "https://bsky.app/", "bluesky_actor_search_public_147"),
    Source("gleif", "GLEIF / LEI", ("company",), "Rechtsträger mit LEI-Kennung; kein vollständiges Firmenverzeichnis.", "https://www.gleif.org/", "gleif_lei_public_135", terms="CC0; Quelle und zeitliche Gültigkeit prüfen."),
    Source("icij", "ICIJ Offshore Leaks", ("person", "company"), "Historische Offshore-Verknüpfungen und strukturierte Downloads.", "https://offshoreleaks.icij.org/search?q={query}", access="download", terms="ODbL / CC BY-SA; Quellenangabe und Weitergabebedingungen; Eintrag ist kein Straftatnachweis."),
    Source("aleph", "OCCRP Aleph", ("person", "company", "topic"), "Öffentliche investigative Dokument- und Registersammlungen.", "https://aleph.occrp.org/", access="manual", terms="Öffentliche Bestände kostenlos; weitere Zugänge beschränkt; journalistische API-Bedingungen."),
    Source("eu_sanctions", "EU-Sanktionsliste", ("person", "company"), "Amtliche Listungen und ihre jeweiligen Rechtsgrundlagen.", "https://finance.ec.europa.eu/eu-and-world/sanctions-restrictive-measures/overview-sanctions-and-related-resources_en", access="download"),
    Source("un_sanctions", "UN-Sanktionsliste", ("person", "company"), "Konsolidierte amtliche Listungen; Identität separat abgleichen.", "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list", access="download"),
    Source("ofac", "OFAC-Sanktionslisten", ("person", "company"), "Amtliche US-Listungen und öffentliche Dateidownloads.", "https://ofac.treasury.gov/sanctions-list-service", access="download"),
    Source("ted", "TED – öffentliche Aufträge", ("company", "topic"), "Europäische Ausschreibungen und veröffentlichte Vergaben.", "https://ted.europa.eu/", access="manual", terms="Kostenlose öffentliche Daten; Search API benötigt POST, der aktuelle Providertransport ist GET-only."),
    Source("dip", "DIP – Parlamentsdokumente", ("topic", "person", "company"), "Bundestag/Bundesrat: Drucksachen, Debatten und Regierungsantworten.", "https://dip.bundestag.de/", access="setup", terms="Kostenlose API benötigt einen eigenen Schlüssel; hier zunächst Recherchezugang."),
    Source("zenodo", "Zenodo", ("topic", "person", "company"), "Forschungsberichte, veröffentlichte Dateien und Datensätze.", "https://zenodo.org/", "zenodo_records_public_149", terms="Zugang und Lizenz je Veröffentlichung; Anhänge separat prüfen."),
    Source("hdx", "HDX", ("topic", "place"), "Humanitäre Datensätze mit Herkunft, Lizenz und Downloadverweisen.", "https://data.humdata.org/", "hdx_catalog_public_501", terms="Kostenloser öffentlicher Katalog; Lizenz und Zugriffsrechte pro Datensatz."),
    Source("ucdp", "UCDP", ("topic", "place"), "Strukturierte Daten zu organisierter Gewalt; keine juristische Einzelfallentscheidung.", "https://ucdp.uu.se/downloads/", access="download", terms="Downloads CC BY 4.0; kostenlose API nach Token-Antrag."),
    Source("reliefweb", "ReliefWeb", ("topic", "place"), "Humanitäre Berichte und Lageinformationen.", "https://reliefweb.int/", access="setup", terms="Kostenloser Recherchezugang; API nach Appname-Freigabe; kommerzielle Übernahme gesondert klären."),
    Source("ohchr", "OHCHR", ("topic", "person", "place"), "Menschenrechtsberichte und Untersuchungsdokumente.", "https://ukraine.ohchr.org/en/reports", access="manual"),
    Source("hudoc", "HUDOC", ("topic", "person", "company"), "Veröffentlichte Rechtsprechung des Europäischen Gerichtshofs für Menschenrechte.", "https://hudoc.echr.coe.int/", access="manual"),
    Source("cir", "Eyes on Russia / CIR", ("topic", "place"), "Geografisch und zeitlich erschlossene überprüfte Medienhinweise.", "https://www.info-res.org/eyes-on-russia-maps/", access="manual"),
    Source("geonames", "GeoNames", ("place",), "Ortsnamen, Namensvarianten und Koordinaten.", "https://www.geonames.org/", access="setup", terms="CC BY; kostenloses Webdienst-Kontingent benötigt registrierten Nutzernamen."),
    Source("copernicus", "Copernicus Data Space", ("place", "topic"), "Sentinel-Satellitendaten zu einem Gebiet und Zeitraum.", "https://dataspace.copernicus.eu/", access="setup", terms="Sentinel-Daten kostenlos nach Anmeldung; Verarbeitungskontingente separat."),
    Source("data_europa", "data.europa.eu", ("topic", "place", "company"), "Europäische Datenkataloge; Lizenz und Qualität beim Herausgeber prüfen.", "https://data.europa.eu/", access="manual"),
    Source("zeitungsportal", "Deutsches Zeitungsportal", ("topic", "person", "company", "place"), "Historische Presse mit Volltextsuche und dauerhaften Quellenverweisen.", "https://www.deutsche-digitale-bibliothek.de/newspaper", access="manual"),
)
FEDERAL_SOURCES = (
    Source("bundesanzeiger", "Bundesanzeiger", ("company", "person", "topic", "federal"), "Amtliche Bekanntmachungen, Unternehmensnachrichten und veröffentlichte Finanzberichte; Inhaltsvolltextsuche bei Rechnungslegungsunterlagen eingeschränkt.", "https://www.bundesanzeiger.de/", access="manual", terms="Recherche kostenlos ohne Registrierung; sitzungsgebundene Trefferlinks durch Fundstelle, Datum und Originaldokument ergänzen."),
    Source("unternehmensregister", "Unternehmensregister", ("company", "person", "topic", "federal"), "Registerinformationen, Unternehmensveröffentlichungen und Rechnungslegung; veröffentlichte und hinterlegte Unterlagen unterscheiden.", "https://www.unternehmensregister.de/", access="manual", terms="Recherche und Registerinformationen kostenlos; hinterlegte Jahresabschlüsse und Beglaubigungen kostenpflichtig. Kein automatischer Kauf."),
    Source("bundestag_opendata", "Bundestag – Open Data", ("person", "topic", "federal"), "Abgeordneten-Stammdaten seit 1949, Drucksachen, Plenarprotokolle und namentliche Abstimmungen.", "https://www.bundestag.de/services/opendata", access="download", terms="Maschinenlesbare öffentliche Downloads; keine automatische Gleichsetzung historischer und aktueller Mandate."),
    Source("wissenschaftliche_dienste", "Bundestag – Wissenschaftliche Dienste", ("topic", "federal"), "Veröffentlichte Ausarbeitungen, Sachstände und Dokumentationen mit Literatur- und Quellenhinweisen.", "https://www.bundestag.de/dokumente/analysen", access="manual", terms="Öffentlich bereitgestellte Arbeiten; Veröffentlichungsstand und Hinweise der jeweiligen Arbeit beachten."),
    Source("bundesrat", "Bundesrat – Dokumente", ("topic", "person", "federal"), "Öffentliche Drucksachen, Plenarprotokolle und parlamentarische Vorlagen.", "https://www.bundesrat.de/DE/dokumente/dokumente-node.html", access="manual"),
    Source("govdata", "GovData – Datenportal für Deutschland", ("topic", "company", "place", "federal"), "Zentraler Katalog öffentlicher Verwaltungsdatensätze von Bund, Ländern und Kommunen; verweist auf die Originalanbieter.", "https://www.govdata.de/", access="manual", terms="Lizenz, Kostenfreiheit und technische Abrufmöglichkeit beim jeweiligen Datensatz prüfen."),
    Source("bundesgesetzblatt", "Bundesgesetzblatt / recht.bund.de", ("topic", "federal"), "Amtliche Verkündung von Bundesgesetzen und Verordnungen; Fundstellen und Fassungsdaten.", "https://www.recht.bund.de/", access="manual"),
    Source("gesetze_im_internet", "Gesetze im Internet", ("topic", "federal"), "Konsolidiertes geltendes Bundesrecht; keine automatische historische Rechtsstandsprüfung.", "https://www.gesetze-im-internet.de/", access="download", terms="Deutsche Normtexte frei nutzbar; amtliche Verkündungsfassung im Bundesgesetzblatt gegenprüfen."),
    Source("rechtsprechung_bund", "Rechtsprechung im Internet", ("topic", "company", "federal"), "Ausgewählte veröffentlichte, anonymisierte Bundesgerichtsentscheidungen mit Aktenzeichen und Datum; kein allgemeines Strafregister.", "https://www.rechtsprechung-im-internet.de/", access="download", terms="Öffentlich bereitgestellte Entscheidungen; Anonymisierung respektieren, keine Deanonymisierung."),
    Source("verwaltungsvorschriften", "Verwaltungsvorschriften im Internet", ("topic", "federal"), "Öffentlich bereitgestellte Verwaltungsvorschriften des Bundes.", "https://www.verwaltungsvorschriften-im-internet.de/", access="manual"),
    Source("bundeshaushalt", "Bundeshaushalt digital", ("topic", "company", "federal"), "Haushaltstitel, Einnahmen, Ausgaben und Datendownloads; Planansatz ist kein Nachweis einer tatsächlichen Zahlung.", "https://www.bundeshaushalt.de/", access="download"),
    Source("foerderdatenbank", "Förderdatenbank des Bundes", ("topic", "company", "place", "federal"), "Förderprogramme und Förderorganisationen von Bund, Ländern und EU; keine vollständige Empfängerliste.", "https://www.foerderdatenbank.de/", access="manual"),
    Source("bundesarchiv", "Bundesarchiv – invenio", ("topic", "person", "company", "federal"), "Öffentlich recherchierbare Archivbeschreibungen und verfügbare Digitalisate.", "https://www.bundesarchiv.de/im-archiv-recherchieren/archivgut-recherchieren/recherchesysteme/invenio/", access="manual", terms="Öffentliche Findmittel bedeuten nicht freien Zugriff auf jede Akte; Schutzfristen und Nutzungsbedingungen beachten."),
)
# Registerportal der Länder und kooperative Angebote gehören fachlich in diese
# Recherchegruppe, ohne sie fälschlich als Bundesbehörden zu bezeichnen.
SOURCES = tuple(replace(s, kinds=s.kinds + ("federal",)) if s.key in
                {"handelsregister", "dip", "lobbyregister"} else s for s in SOURCES) + FEDERAL_SOURCES
BY_KEY = {source.key: source for source in SOURCES}


def clean_term(term):
    if not isinstance(term, str) or not 3 <= len(term.strip()) <= 190:
        raise ValueError("Suchbegriff muss 3–190 Zeichen enthalten")
    if any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in term):
        raise ValueError("Suchbegriff enthält unzulässige Steuerzeichen")
    term = " ".join(term.split())
    validate_public_scope(term, "Öffentliche fallbezogene Quellenrecherche")
    return term


def catalog(ctx, kind="topic", term=""):
    if kind not in KINDS:
        raise ValueError("Unbekannte Rechercheart")
    if term:
        term = clean_term(term)
    providers = {x["provider_key"]: x for x in ctx.provider_collection_120.list_providers()}
    out = []
    for source in SOURCES:
        if kind not in source.kinds:
            continue
        provider = providers.get(source.provider)
        out.append({"source": source, "ready": bool(provider and provider["supports_live"]),
                    "url": source.website.replace("{query}", quote(term, safe="")),
                    "provider": provider})
    return out


def _authorize(ctx, user, case_id, capability):
    ctx.team_governance_359.authorize(user, case_id=case_id, capability=capability,
                                    object_type="operational_case", object_id=case_id)


def prepare(ctx, user, case_id, kind, term, selected, purpose, collection=""):
    _authorize(ctx, user, case_id, "research.run")
    term = clean_term(term)
    purpose = plan496._safe_text(purpose, field="purpose", minimum=20, maximum=400)
    if kind not in KINDS or not 1 <= len(selected) <= 8 or len(selected) != len(set(selected)):
        raise ValueError("Eine bis acht unterschiedliche verfügbare Quellen auswählen")
    prepared = []
    for key in selected:
        source = BY_KEY.get(key)
        if not source or kind not in source.kinds or not source.provider:
            raise ValueError("Quelle ist für diese Recherche nicht automatisch verfügbar")
        provider = ctx.provider_collection_120.provider(source.provider)
        if not provider["enabled"] or not provider["supports_live"]:
            raise ValueError("Quelle ist deaktiviert")
        query = (collection.strip() + " " + term) if key == "common_crawl" else term
        adapter = ctx.provider_collection_120._adapters[source.provider]
        request = ProviderRunRequest(case_id, source.provider, query, purpose, user["username"], max_results=20)
        adapter.validate_request(request)
        # Validate before any write, without issuing HTTP/DNS requests.
        for call in adapter.build_requests(request):
            ctx.provider_collection_120.policy.validate_url(call.url, allowed_hosts=adapter.definition.allowed_hosts)
        prepared.append((source, query))
    search = ctx.search_intelligence_114
    with ctx.audit.actor_scope(user["username"]), ctx.db.transaction(immediate=True):
        plan = plan496.create_plan(ctx, user, case_id, "Quellenrecherche " + KINDS[kind] + ": " + term,
                                  purpose + " Öffentliche Quellen; Treffer bleiben ungeprüfte Kandidaten. Original und Zuordnung separat prüfen.")
        for source, query in prepared:
            step = plan496.add_step(ctx, user, case_id, plan["plan_id"], "provider_proposal",
                                    source.label + ": " + query + ". Herkunft und Namensverwechslungen prüfen. "
                                    "Abfrage-Fingerabdruck: " + hashlib.sha256(query.encode()).hexdigest(), source.provider)
            intent = search.create_intent(case_id, "Öffentliche Quellenrecherche: " + query, purpose,
                "Quellengebundene Hinweise; kein Identitäts- oder Straftatnachweis.", user["username"],
                intent_type="identity" if kind == "person" else "other", workflow_id=plan["plan_id"], step_id=step["step_id"],
                sensitivity="elevated" if kind == "person" else "normal")
            search.propose_query(intent, source.provider, query, source.label + "; " + source.terms, user["username"])
        ctx.audit.log("public_source_package_prepared_501", "case_plan", plan["plan_id"], case_id,
                      {"sources": list(selected), "network": False, "kind": kind})
    return plan


def package(ctx, user, case_id, plan_id):
    _authorize(ctx, user, case_id, "case.read")
    plan = plan496.get_plan(ctx, case_id, plan_id)
    rows = ctx.db.all("""SELECT q.*, i.intent_id, i.step_id, i.purpose, i.state AS intent_state
        FROM search_intents_114 i JOIN search_queries_114 q ON q.intent_id=i.intent_id
        WHERE i.case_id=? AND i.workflow_id=? ORDER BY i.created_at,i.step_id""", (case_id, plan_id))
    steps = {s["step_id"]: s for s in plan496.list_steps(ctx, case_id, plan_id)}
    if not rows or len(rows) != len(steps) or len({r["step_id"] for r in rows}) != len(rows):
        raise ValueError("Kein eindeutiges Quellen-Suchpaket")
    for row in rows:
        step = steps.get(row["step_id"])
        if not step or step["provider_key"] != row["provider"]:
            raise ValueError("Quellenzuordnung wurde verändert")
        if "Abfrage-Fingerabdruck: " + hashlib.sha256(row["query_text"].encode()).hexdigest() not in step["instruction"]:
            raise ValueError("Suchanfrage geändert; Suchpaket neu vorbereiten")
        row["execution"] = execution497.get_execution(ctx, case_id, row["step_id"])
    return plan, rows


def snapshot(plan, rows):
    material = {"plan": plan["record_hash"], "queries": [
        [r[k] for k in ("query_id", "intent_id", "step_id", "provider", "query_text", "purpose", "state", "intent_state")]
        for r in rows]}
    return hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def approve(ctx, user, case_id, plan_id, expected_hash, reason):
    _authorize(ctx, user, case_id, "source.review")
    search = ctx.search_intelligence_114
    with ctx.audit.actor_scope(user["username"]), ctx.db.transaction(immediate=True):
        plan, rows = package(ctx, user, case_id, plan_id)
        if snapshot(plan, rows) != expected_hash:
            raise ValueError("Suchpaket geändert; Freigabeansicht neu laden")
        if any(row["state"] != "draft" or row["intent_state"] != "draft" for row in rows):
            raise ValueError("Suchpaket wurde bereits geprüft oder verändert")
        plan496.review_plan(ctx, user, case_id, plan_id, "approved", reason, plan["record_hash"])
        # Explicit source-query approval is separate from the plan review and
        # covers only the exact queries displayed in this package.
        for row in rows:
            search.approve_intent(row["intent_id"], user["username"])
            search.approve_query(row["query_id"], user["username"])
        ctx.audit.log("public_source_queries_approved_501", "case_plan", plan_id, case_id,
                      {"query_ids": [r["query_id"] for r in rows], "network": False})


def run(ctx, user, case_id, plan_id, query_id, mode):
    _authorize(ctx, user, case_id, "research.run")
    plan, rows = package(ctx, user, case_id, plan_id)
    row = next((r for r in rows if r["query_id"] == query_id), None)
    if not row:
        raise KeyError("Suchanfrage gehört nicht zu diesem Fall und Paket")
    return execution497.run_step(ctx, user, case_id, plan_id, row["step_id"], query=row["query_text"],
        purpose=row["purpose"], mode=mode, confirmation=execution497.APPROVAL_PHRASE,
        search_intent_id=row["intent_id"], search_query_id=row["query_id"])
