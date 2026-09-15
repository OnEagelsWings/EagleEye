from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List

ACCESS_MANUAL_PUBLIC = "manual_public_search"
ACCESS_PUBLIC_API = "public_api"
ACCESS_PUBLIC_ARCHIVE = "public_archive"
ACCESS_OFFICIAL_PUBLIC_PORTAL = "official_public_portal"
ACCESS_LOCAL_LOOKUP = "local_lookup"

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"

REVIEW_ALWAYS = "always"
REVIEW_SENSITIVE = "sensitive"
REVIEW_OPTIONAL = "optional"

CLAIM_STRENGTH_WEAK = "weak_public_indicator"
CLAIM_STRENGTH_MEDIUM = "medium_public_indicator"
CLAIM_STRENGTH_STRONG = "strong_public_indicator_if_manually_verified"


@dataclass(frozen=True)
class SourceDefinition:
    source_key: str
    name: str
    category: str
    jurisdiction: str
    access_type: str
    public_status: str
    allowed_for_living_person: str
    allowed_for_historical_research: bool
    requires_manual_review: bool
    review_rule: str
    claim_strength_default: str
    person_data_risk: str
    expected_evidence: str
    prohibited_use: List[str]
    search_hints: List[str]
    notes: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def default_source_definitions() -> List[SourceDefinition]:
    """Curated Build 50.0 source catalog.

    The catalog intentionally mixes fully automatable public sources with manual public
    search paths. Sensitive record classes are marked high-risk and review-required so
    they cannot become direct automated profile facts.
    """
    p = [
        "no_login_bypass", "no_paywall_bypass", "no_captcha_bypass", "no_private_records",
        "no_live_tracking", "no_credential_access", "review_before_report",
    ]
    return [
        SourceDefinition("civil_birth_register_archive_de", "Archivierte Geburtsregister", "civil_registry_archive", "DE", ACCESS_PUBLIC_ARCHIVE, "public_after_retention_period", "restricted", True, True, REVIEW_ALWAYS, CLAIM_STRENGTH_STRONG, RISK_HIGH, "archival birth record candidate", p, ["Geburtsregister", "Personenstandsregister", "Geburt", "Standesamt", "Archiv"], "Aktuelle Personenstandsdaten sind kein OSINT-Provider; nur öffentlich archivische Suchpfade."),
        SourceDefinition("civil_marriage_register_archive_de", "Archivierte Eheregister", "civil_registry_archive", "DE", ACCESS_PUBLIC_ARCHIVE, "public_after_retention_period", "restricted", True, True, REVIEW_ALWAYS, CLAIM_STRENGTH_STRONG, RISK_HIGH, "archival marriage record candidate", p, ["Eheregister", "Heiratsregister", "Trauung", "Standesamt", "Archiv"], "Namens- und Ortsfit müssen manuell geprüft werden."),
        SourceDefinition("civil_death_register_archive_de", "Archivierte Sterberegister", "civil_registry_archive", "DE", ACCESS_PUBLIC_ARCHIVE, "public_after_retention_period", "restricted", True, True, REVIEW_ALWAYS, CLAIM_STRENGTH_STRONG, RISK_HIGH, "archival death record candidate", p, ["Sterberegister", "Sterbeurkunde", "Standesamt", "Archiv"], "Bei lebenden Personen nur als Ausschluss-/Dopplerprüfung verwenden."),
        SourceDefinition("church_baptism_register_public", "Öffentliche Taufregister/Kirchenbücher", "church_register", "DE/EU", ACCESS_PUBLIC_ARCHIVE, "public_archive_or_index", "restricted", True, True, REVIEW_ALWAYS, CLAIM_STRENGTH_MEDIUM, RISK_HIGH, "baptism/church book candidate", p, ["Kirchenbuch", "Taufe", "Taufregister", "Archion", "Matrikel"], "Religionsdaten sind sensibel; Export nur mit Redaction-/Legal-Prüfung."),
        SourceDefinition("church_marriage_register_public", "Öffentliche Trauungsregister/Kirchenbücher", "church_register", "DE/EU", ACCESS_PUBLIC_ARCHIVE, "public_archive_or_index", "restricted", True, True, REVIEW_ALWAYS, CLAIM_STRENGTH_MEDIUM, RISK_HIGH, "church marriage record candidate", p, ["Kirchenbuch", "Trauung", "Ehe", "Matrikel", "Archiv"], "Nur öffentlich zugängliche Register/Indizes."),
        SourceDefinition("church_burial_register_public", "Öffentliche Begräbnisregister/Kirchenbücher", "church_register", "DE/EU", ACCESS_PUBLIC_ARCHIVE, "public_archive_or_index", "restricted", True, True, REVIEW_ALWAYS, CLAIM_STRENGTH_MEDIUM, RISK_HIGH, "burial/church book candidate", p, ["Kirchenbuch", "Begräbnis", "Bestattung", "Friedhof", "Matrikel"], "OCR/Faksimile prüfen."),
        SourceDefinition("synagogue_community_archive_public", "Öffentliche jüdische Gemeindearchive", "community_archive", "DE/EU", ACCESS_PUBLIC_ARCHIVE, "public_archive_or_catalog", "restricted", True, True, REVIEW_ALWAYS, CLAIM_STRENGTH_MEDIUM, RISK_HIGH, "public community archive candidate", p, ["jüdische Gemeinde", "Synagoge", "Gemeindearchiv", "Matrikel", "Archiv"], "Besondere Schutzklasse; nicht als Targeting-Quelle missbrauchen."),
        SourceDefinition("newspaper_archive_de", "Historische Zeitungsarchive", "newspaper_archive", "DE", ACCESS_PUBLIC_ARCHIVE, "public_index_or_digitized_pages", "conditional", True, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "newspaper mention candidate", p, ["Zeitung", "Lokalzeitung", "Nachruf", "Prozessbericht", "Anzeige"], "OCR-Treffer sind Kandidaten, keine Fakten."),
        SourceDefinition("local_press_public", "Aktuelle öffentliche Presseberichte", "press_public", "global", ACCESS_MANUAL_PUBLIC, "public_web", "conditional", False, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "press mention candidate", p, ["Presse", "Bericht", "Lokal", "Polizei", "Prozess"], "Pressebericht ist kein gerichtlicher Beweis."),
        SourceDefinition("court_decisions_de_public", "Öffentliche Rechtsprechungsdatenbanken", "court_decision", "DE", ACCESS_OFFICIAL_PUBLIC_PORTAL, "public_anonymized_or_selected", "restricted", False, True, REVIEW_ALWAYS, CLAIM_STRENGTH_MEDIUM, RISK_HIGH, "public court decision candidate", p, ["Urteil", "Beschluss", "Aktenzeichen", "Justiz", "Gericht"], "Anonymisierte Entscheidungen identifizieren Personen nicht automatisch."),
        SourceDefinition("court_press_releases_public", "Öffentliche Gerichts-/Justiz-Pressemitteilungen", "court_public_notice", "DE", ACCESS_OFFICIAL_PUBLIC_PORTAL, "public_web", "conditional", False, True, REVIEW_ALWAYS, CLAIM_STRENGTH_MEDIUM, RISK_HIGH, "official justice press release candidate", p, ["Pressemitteilung", "Landgericht", "Amtsgericht", "Staatsanwaltschaft"], "Kontext und Namensdoppler zwingend prüfen."),
        SourceDefinition("public_trial_reports_press", "Öffentliche Prozessberichte der Presse", "trial_report_press", "DE/EU", ACCESS_MANUAL_PUBLIC, "public_web", "conditional", False, True, REVIEW_ALWAYS, CLAIM_STRENGTH_WEAK, RISK_HIGH, "trial report candidate", p, ["Prozess", "Gerichtsverhandlung", "Anklage", "Zeuge", "Urteil"], "Journalistische Quelle; nie automatisch als Fakt verwenden."),
        SourceDefinition("public_pdf_web", "Öffentlich auffindbare PDFs", "public_pdf", "global", ACCESS_MANUAL_PUBLIC, "public_web", "conditional", False, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "public PDF document candidate", p, ["filetype:pdf", "PDF", "Bericht", "Anlage", "Amtsblatt"], "PDFs müssen gehasht und extrahierte Zitate fundstellenfähig sein."),
        SourceDefinition("municipal_gazette_public", "Kommunale Amtsblätter/Bekanntmachungen", "gazette_notice", "DE", ACCESS_OFFICIAL_PUBLIC_PORTAL, "public_web", "conditional", True, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "municipal notice candidate", p, ["Amtsblatt", "Bekanntmachung", "Stadt", "Kreis", "Gemeinde"], "Kommunaler Kontext: Orts- und Zeitfit prüfen."),
        SourceDefinition("federal_gazette_public", "Bundesanzeiger/amtliche Veröffentlichungen", "gazette_notice", "DE", ACCESS_OFFICIAL_PUBLIC_PORTAL, "public_web", "conditional", False, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "federal notice candidate", p, ["Bundesanzeiger", "Bekanntmachung", "Jahresabschluss"], "Organisationen bevorzugt; Personendaten prüfen."),
        SourceDefinition("company_register_de", "Handels-/Unternehmensregister", "company_register", "DE", ACCESS_OFFICIAL_PUBLIC_PORTAL, "public_register", "conditional", False, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_STRONG, RISK_MEDIUM, "company register candidate", p, ["Handelsregister", "Unternehmensregister", "HRB", "HRA", "Geschäftsführer"], "Registerauszug kann starken Organisationsbeleg liefern."),
        SourceDefinition("association_register_de", "Vereinsregister", "association_register", "DE", ACCESS_OFFICIAL_PUBLIC_PORTAL, "public_register", "conditional", True, True, REVIEW_ALWAYS, CLAIM_STRENGTH_MEDIUM, RISK_HIGH, "association register candidate", p, ["Vereinsregister", "VR", "Vorstand", "Satzung"], "Vereins-/Religions-/Schulkontexte sensibel behandeln."),
        SourceDefinition("insolvency_notices_de", "Insolvenzbekanntmachungen", "insolvency_notice", "DE", ACCESS_OFFICIAL_PUBLIC_PORTAL, "public_notice", "conditional", False, True, REVIEW_ALWAYS, CLAIM_STRENGTH_MEDIUM, RISK_HIGH, "insolvency notice candidate", p, ["Insolvenz", "Insolvenzbekanntmachung", "Amtsgericht"], "Hohes Reputationsrisiko; Kontext und Aktualität prüfen."),
        SourceDefinition("procurement_public", "Öffentliche Vergabe-/Zuwendungsdaten", "procurement_public", "DE/EU", ACCESS_OFFICIAL_PUBLIC_PORTAL, "public_web", "conditional", False, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "procurement/grant candidate", p, ["Vergabe", "Zuwendung", "Förderung", "Ausschreibung"], "Primär Organisationsrecherche."),
        SourceDefinition("parliamentary_records_public", "Parlaments-/Ratsinformationssysteme", "parliamentary_record", "DE/EU", ACCESS_OFFICIAL_PUBLIC_PORTAL, "public_web", "conditional", False, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "public political record candidate", p, ["Ratsinformationssystem", "Drucksache", "Protokoll", "Anfrage"], "Politische Daten können sensibel sein."),
        SourceDefinition("education_publications_public", "Schul-/Hochschulveröffentlichungen", "education_publication", "global", ACCESS_MANUAL_PUBLIC, "public_web", "restricted", False, True, REVIEW_ALWAYS, CLAIM_STRENGTH_WEAK, RISK_HIGH, "education publication candidate", p, ["Schule", "Universität", "Abschluss", "PDF"], "Minderjährige/Schulkontext besonders schützen."),
        SourceDefinition("professional_profile_public", "Öffentliche Berufs-/Profilseiten", "professional_profile", "global", ACCESS_MANUAL_PUBLIC, "public_web", "conditional", False, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "public professional profile candidate", p, ["LinkedIn", "Xing", "Profil", "Mitarbeiter", "Team"], "Nur öffentliche Angaben; keine Login-/Kontaktumgehung."),
        SourceDefinition("public_social_profile", "Öffentliche Social-Profile", "social_public_profile", "global", ACCESS_MANUAL_PUBLIC, "public_web", "conditional", False, True, REVIEW_ALWAYS, CLAIM_STRENGTH_WEAK, RISK_HIGH, "public social profile candidate", p, ["Profil", "Username", "Instagram", "Facebook", "X", "TikTok"], "Nie private Inhalte, nie Kontaktlisten, nie Bypass."),
        SourceDefinition("github_public_user", "GitHub öffentliche Profile/Repositories", "developer_public", "global", ACCESS_PUBLIC_API, "public_api", "conditional", False, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "public developer artifact candidate", p, ["GitHub", "Repository", "Commit", "Username"], "API-Budget beachten."),
        SourceDefinition("domain_whois_rdap_public", "RDAP/WHOIS öffentliche Domaininfos", "domain_infrastructure_public", "global", ACCESS_PUBLIC_API, "public_api", "conditional", False, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "domain registry candidate", p, ["RDAP", "WHOIS", "Domain", "Registrar"], "Redaction bei Privatpersonen; Privacy-Proxy beachten."),
        SourceDefinition("dns_public", "Öffentliche DNS-Auflösung", "domain_infrastructure_public", "global", ACCESS_LOCAL_LOOKUP, "public_infrastructure", "conditional", False, False, REVIEW_OPTIONAL, CLAIM_STRENGTH_MEDIUM, RISK_LOW, "public DNS candidate", p, ["DNS", "A", "AAAA", "MX", "NS"], "Technische Quelle, keine Personenfeststellung."),
        SourceDefinition("crtsh_public", "Certificate Transparency / crt.sh", "domain_infrastructure_public", "global", ACCESS_PUBLIC_API, "public_index", "conditional", False, False, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "certificate transparency candidate", p, ["crt.sh", "certificate", "SAN", "Domain"], "Domainbezug ist kein Personenbeweis."),
        SourceDefinition("wayback_public", "Internet Archive Wayback/CDX", "web_archive", "global", ACCESS_PUBLIC_API, "public_archive", "conditional", False, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "archived web page candidate", p, ["Wayback", "archive", "snapshot", "historical URL"], "Archivierter Stand: Zeitkontext dokumentieren."),
        SourceDefinition("official_police_press_public", "Öffentliche Polizeimeldungen", "official_press_release", "DE/EU", ACCESS_OFFICIAL_PUBLIC_PORTAL, "public_web", "restricted", False, True, REVIEW_ALWAYS, CLAIM_STRENGTH_MEDIUM, RISK_HIGH, "official police press candidate", p, ["Polizei", "Presseportal", "Vermisst", "Zeugenaufruf"], "Bei Kindern/Vermissten keine eigenmächtige Täteradressierung."),
        SourceDefinition("missing_child_public_notice", "Öffentliche Vermisstenmeldungen", "missing_person_public_notice", "DE/EU", ACCESS_OFFICIAL_PUBLIC_PORTAL, "public_web", "restricted", False, True, REVIEW_ALWAYS, CLAIM_STRENGTH_MEDIUM, RISK_HIGH, "missing person public notice candidate", p, ["vermisst", "Kind", "Polizei", "116000", "Zeugenhinweis"], "Notfallmodus: Behördenkontakt priorisieren."),
        SourceDefinition("antisemitism_incident_public", "Öffentliche Meldungen zu antisemitischen Vorfällen", "antisemitism_incident_public", "DE", ACCESS_MANUAL_PUBLIC, "public_web", "restricted", False, True, REVIEW_ALWAYS, CLAIM_STRENGTH_MEDIUM, RISK_HIGH, "antisemitism incident candidate", p, ["antisemitisch", "RIAS", "Synagoge", "Bedrohung", "Sachbeschädigung"], "Schutz jüdischen Lebens; Opfer-/Zeugenschutz priorisieren."),
        SourceDefinition("ngo_public_reports", "Öffentliche NGO-/Monitoringberichte", "ngo_public_report", "global", ACCESS_MANUAL_PUBLIC, "public_web", "conditional", False, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "NGO report candidate", p, ["Report", "Monitoring", "Jahresbericht", "Lagebild"], "Quelle und Methodik prüfen."),
        SourceDefinition("archive_portal_public", "Archivportale/Kataloge", "archive_catalog", "DE/EU", ACCESS_PUBLIC_ARCHIVE, "public_catalog", "conditional", True, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "archive catalog candidate", p, ["Archivportal", "Findbuch", "Bestand", "Signatur"], "Katalogeintrag ist Suchhinweis, nicht zwingend Dokumentbeleg."),
        SourceDefinition("library_catalog_public", "Bibliotheks- und Publikationskataloge", "library_catalog", "global", ACCESS_MANUAL_PUBLIC, "public_catalog", "conditional", True, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_LOW, "publication/catalog candidate", p, ["Katalog", "Publikation", "ISBN", "Autor"], "Primär Autoren-/Publikationskontext."),
        SourceDefinition("obituary_public", "Öffentliche Nachrufe/Traueranzeigen", "obituary_public", "DE/EU", ACCESS_MANUAL_PUBLIC, "public_web_or_archive", "restricted", True, True, REVIEW_ALWAYS, CLAIM_STRENGTH_MEDIUM, RISK_HIGH, "obituary candidate", p, ["Nachruf", "Traueranzeige", "verstorben", "Familie"], "Familienbeziehungen sensibel redigieren."),
        SourceDefinition("cemetery_public_records", "Öffentliche Friedhofs-/Grabdatenbanken", "cemetery_public", "global", ACCESS_MANUAL_PUBLIC, "public_web_or_archive", "restricted", True, True, REVIEW_ALWAYS, CLAIM_STRENGTH_MEDIUM, RISK_HIGH, "cemetery record candidate", p, ["Friedhof", "Grab", "Bestattung", "Geburtsdatum", "Sterbedatum"], "Nur öffentlich; Familien-/Religionskontext schützen."),
        SourceDefinition("sanctions_public", "Öffentliche Sanktions-/Watchlisten", "sanctions_public", "global", ACCESS_OFFICIAL_PUBLIC_PORTAL, "public_register", "restricted", False, True, REVIEW_ALWAYS, CLAIM_STRENGTH_MEDIUM, RISK_HIGH, "sanctions list candidate", p, ["Sanktionsliste", "EU", "OFAC", "UN"], "Namensdoppler extrem hoch; nicht als Identitätsbestätigung verwenden."),
        SourceDefinition("charity_register_public", "Öffentliche Stiftungs-/Charityregister", "charity_register", "DE/EU", ACCESS_OFFICIAL_PUBLIC_PORTAL, "public_register", "conditional", True, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "charity/foundation register candidate", p, ["Stiftung", "Stiftungsverzeichnis", "gemeinnützig", "Vorstand"], "Organisationskontext; Personen redigieren."),
        SourceDefinition("event_public_listings", "Öffentliche Event-/Veranstaltungslisten", "event_public", "global", ACCESS_MANUAL_PUBLIC, "public_web", "conditional", False, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_WEAK, RISK_MEDIUM, "public event listing candidate", p, ["Veranstaltung", "Speaker", "Programm", "Agenda"], "Teilnahmehinweis ist kein aktueller Aufenthaltsort."),
        SourceDefinition("academic_publications_public", "Öffentliche wissenschaftliche Veröffentlichungen", "academic_publication", "global", ACCESS_MANUAL_PUBLIC, "public_catalog", "conditional", False, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_LOW, "academic publication candidate", p, ["Publikation", "DOI", "Autor", "ORCID"], "Autorenidentität prüfen."),
        SourceDefinition("patent_trademark_public", "Öffentliche Patent-/Markenregister", "ip_register_public", "global", ACCESS_OFFICIAL_PUBLIC_PORTAL, "public_register", "conditional", False, True, REVIEW_SENSITIVE, CLAIM_STRENGTH_MEDIUM, RISK_MEDIUM, "IP register candidate", p, ["Patent", "Marke", "DPMA", "EUIPO", "WIPO"], "Adressdaten ggf. redigieren."),
        SourceDefinition("public_web_search", "Allgemeine öffentliche Websuche", "public_web_search", "global", ACCESS_MANUAL_PUBLIC, "public_web", "conditional", False, True, REVIEW_ALWAYS, CLAIM_STRENGTH_WEAK, RISK_MEDIUM, "web search candidate", p, ["exact phrase", "site:", "filetype:", "date window"], "Fallback-Quelle; nie allein stark."),
    ]
