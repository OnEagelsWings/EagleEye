from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class QueryTemplate:
    source_category: str
    source_key_hint: str
    template: str
    expected_evidence: str
    priority: int
    purpose: str


PERSON_TEMPLATES: List[QueryTemplate] = [
    QueryTemplate("public_web_search", "public_web_search", '"{name}"', "general public mention", 50, "baseline exact-name discovery"),
    QueryTemplate("public_pdf", "public_pdf_web", '"{name}" filetype:pdf', "public PDF mention", 85, "locate public PDF documents"),
    QueryTemplate("court_decision", "court_decisions_de_public", '"{name}" Urteil OR Beschluss OR Aktenzeichen', "court document candidate", 80, "court/public legal document search"),
    QueryTemplate("trial_report_press", "public_trial_reports_press", '"{name}" Prozess OR Gerichtsverhandlung OR Anklage', "trial press report candidate", 75, "trial report search"),
    QueryTemplate("newspaper_archive", "newspaper_archive_de", '"{name}" Zeitung OR Lokalzeitung OR Nachruf', "newspaper article candidate", 70, "press/archive search"),
    QueryTemplate("civil_registry_archive", "civil_birth_register_archive_de", '"{name}" Geburtsregister OR Personenstandsregister OR Standesamt Archiv', "civil birth registry archive candidate", 65, "archival vital-record path"),
    QueryTemplate("civil_registry_archive", "civil_marriage_register_archive_de", '"{name}" Eheregister OR Heiratsregister OR Standesamt Archiv', "civil marriage registry archive candidate", 60, "archival marriage-record path"),
    QueryTemplate("civil_registry_archive", "civil_death_register_archive_de", '"{name}" Sterberegister OR Sterbeurkunde OR Standesamt Archiv', "civil death registry archive candidate", 65, "archival death-record path"),
    QueryTemplate("church_register", "church_baptism_register_public", '"{name}" Kirchenbuch OR Taufe OR Taufregister', "church baptism record candidate", 55, "public church-record path"),
    QueryTemplate("church_register", "church_marriage_register_public", '"{name}" Kirchenbuch OR Trauung OR Matrikel', "church marriage record candidate", 55, "public church-record path"),
    QueryTemplate("church_register", "church_burial_register_public", '"{name}" Kirchenbuch OR Begräbnis OR Friedhof', "church burial/cemetery candidate", 55, "public church/cemetery-record path"),
    QueryTemplate("community_archive", "synagogue_community_archive_public", '"{name}" "jüdische Gemeinde" OR Synagoge OR Gemeindearchiv', "public community archive candidate", 60, "public community archive path"),
    QueryTemplate("professional_profile", "professional_profile_public", '"{name}" Team OR Mitarbeiter OR Profil OR Lebenslauf', "professional profile candidate", 50, "public role/profile search"),
    QueryTemplate("education_publication", "education_publications_public", '"{name}" Schule OR Universität OR Abschluss filetype:pdf', "education publication candidate", 45, "public education mention search"),
    QueryTemplate("obituary_public", "obituary_public", '"{name}" Nachruf OR Traueranzeige OR verstorben', "obituary candidate", 65, "obituary and family notice search"),
    QueryTemplate("domain_infrastructure_public", "domain_whois_rdap_public", '"{name}" Domain OR Impressum', "domain/imprint candidate", 45, "public domain/imprint association search"),
]

ORG_TEMPLATES: List[QueryTemplate] = [
    QueryTemplate("company_register", "company_register_de", '"{name}" Handelsregister OR Unternehmensregister OR HRB OR HRA', "company register candidate", 95, "official organization registry search"),
    QueryTemplate("association_register", "association_register_de", '"{name}" Vereinsregister OR VR OR Satzung OR Vorstand', "association register candidate", 90, "official association registry search"),
    QueryTemplate("gazette_notice", "federal_gazette_public", '"{name}" Bundesanzeiger OR Bekanntmachung OR Jahresabschluss', "gazette notice candidate", 85, "official publication search"),
    QueryTemplate("insolvency_notice", "insolvency_notices_de", '"{name}" Insolvenz OR Insolvenzbekanntmachung', "insolvency notice candidate", 80, "public insolvency notice search"),
    QueryTemplate("procurement_public", "procurement_public", '"{name}" Vergabe OR Zuwendung OR Förderung OR Ausschreibung', "procurement/grant candidate", 70, "public procurement/funding search"),
    QueryTemplate("public_pdf", "public_pdf_web", '"{name}" Satzung filetype:pdf', "statute PDF candidate", 80, "locate statutes and public PDFs"),
    QueryTemplate("public_pdf", "public_pdf_web", '"{name}" Vorstand filetype:pdf', "board PDF candidate", 75, "locate public board documents"),
    QueryTemplate("court_decision", "court_decisions_de_public", '"{name}" Urteil OR Beschluss OR Klage OR Aktenzeichen', "legal document candidate", 65, "court/legal context search"),
    QueryTemplate("press_public", "local_press_public", '"{name}" Presse OR Bericht OR Veranstaltung', "press mention candidate", 55, "public press search"),
    QueryTemplate("domain_infrastructure_public", "domain_whois_rdap_public", '"{name}" Domain OR Impressum OR Webseite', "domain/imprint candidate", 65, "public domain and imprint search"),
    QueryTemplate("antisemitism_incident_public", "antisemitism_incident_public", '"{name}" antisemitisch OR Synagoge OR Bedrohung OR RIAS', "incident context candidate", 70, "protective threat/incident context search"),
]

INCIDENT_TEMPLATES: List[QueryTemplate] = [
    QueryTemplate("official_press_release", "official_police_press_public", '"{place}" "{date_hint}" Polizei OR Pressemitteilung OR Zeugenaufruf', "official police press candidate", 95, "official incident confirmation search"),
    QueryTemplate("missing_person_public_notice", "missing_child_public_notice", '"{place}" "{date_hint}" vermisst OR Kind OR Zeugenhinweis', "missing person public notice", 100, "missing child/person public notice search"),
    QueryTemplate("press_public", "local_press_public", '"{place}" "{date_hint}" Bericht OR Lokalzeitung OR Vorfall', "press incident candidate", 70, "public press incident search"),
    QueryTemplate("antisemitism_incident_public", "antisemitism_incident_public", '"{place}" "{date_hint}" antisemitisch OR Synagoge OR jüdisch OR Bedrohung', "antisemitic incident candidate", 90, "Jewish life protection incident search"),
    QueryTemplate("court_public_notice", "court_press_releases_public", '"{place}" "{date_hint}" Staatsanwaltschaft OR Gericht OR Anklage', "public justice follow-up candidate", 75, "justice follow-up search"),
    QueryTemplate("municipal_notice", "municipal_gazette_public", '"{place}" "{date_hint}" Amtsblatt OR Bekanntmachung OR Sicherheit', "municipal notice candidate", 50, "municipal incident context"),
    QueryTemplate("public_pdf", "public_pdf_web", '"{place}" "{date_hint}" filetype:pdf Vorfall OR Bericht OR Sicherheit', "public PDF incident candidate", 60, "documented incident search"),
]
