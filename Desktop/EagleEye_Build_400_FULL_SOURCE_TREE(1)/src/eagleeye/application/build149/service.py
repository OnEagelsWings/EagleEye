from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping
from urllib.parse import quote_plus, urlsplit

from eagleeye.application.build148.service import ConnectorManifest148, RUN_CONFIRMATION
from eagleeye.infrastructure.providers.policy import sanitize_mapping, validate_public_scope
from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

PLAN_CONFIRMATION = "QUELLENPLAN 149 FREIGEBEN"
JOB_CONFIRMATION = "QUELLENJOB 149 AUSFÜHREN"
CLUSTER_CONFIRMATION = "QUELLENERGEBNISSE 149 CLUSTERN"

SOURCE_FAMILIES = {
    "official_registry", "sanctions_watchlist", "scholarly_identity", "publications_archive",
    "social_community", "web_news_archive", "domain_infrastructure", "legal_public_records",
    "licensed_enrichment", "media_visual", "company_intelligence", "identity_authority",
}
ACCESS_TIERS = {"public_native", "public_guided", "auth_required", "licensed", "bulk_import"}
RISK_LEVELS = {"low", "medium", "high", "restricted"}
SENSITIVE_MARKERS = {
    "health", "medical", "religion", "political", "sexual", "minor", "child", "biometric",
    "face_embedding", "password", "secret", "access_token", "full_case", "date_of_birth_exact",
}
EXACT_EMAIL_SOURCES = {"hibp_api"}
WATCHLIST_FAMILIES = {"sanctions_watchlist"}


def _safe(value: Any, limit: int = 4000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _norm(value: str) -> str:
    return unicodedata.normalize("NFKC", _safe(value, 1000)).casefold()


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _dedupe(values: Iterable[str], limit: int = 100) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _safe(value, 1000)
        key = _norm(text)
        if text and key not in seen:
            seen.add(key)
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _host(url: str) -> str:
    try:
        return (urlsplit(str(url or "")).hostname or "").casefold().strip(".")
    except ValueError:
        return ""


@dataclass(frozen=True, slots=True)
class SourceSpec149:
    key: str
    label: str
    family: str
    category: str
    access_tier: str
    connector_type: str
    execution_backend: str
    official_url: str
    documentation_url: str
    allowed_hosts: tuple[str, ...]
    input_types: tuple[str, ...]
    provider_key: str = ""
    search_template: str = ""
    jurisdiction: str = "global"
    geographic_scope: str = "global"
    authority_score: int = 70
    independence_score: int = 70
    freshness_days: int = 30
    risk_level: str = "low"
    persona_required: bool = False
    exact_email_allowed: bool = False
    bulk_capable: bool = False
    legal_status: str = "approved_public"
    terms_profile: str = "official_public_interface"
    priority: int = 60
    secret_names: tuple[str, ...] = ()
    required_secret_names: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,95}", self.key):
            raise ValueError("Unsicherer Build-149-Source-Key")
        if self.family not in SOURCE_FAMILIES or self.access_tier not in ACCESS_TIERS or self.risk_level not in RISK_LEVELS:
            raise ValueError("Ungültige Quellenklassifikation")
        if self.connector_type not in {"LOOKUP", "IMPORT", "GUIDED_BROWSER"}:
            raise ValueError("Build 149 unterstützt nur Lookup, Import und Guided Browser")
        if self.execution_backend not in {"provider_collection_120", "guided_browser_136", "external_worker"}:
            raise ValueError("Ungültiges Connector-Backend")
        if not self.allowed_hosts:
            raise ValueError("Externe Quellen benötigen eine exakte Host-Allowlist")
        if not 0 <= self.authority_score <= 100 or not 0 <= self.independence_score <= 100:
            raise ValueError("Quellenwerte müssen zwischen 0 und 100 liegen")
        if not 1 <= self.freshness_days <= 3650:
            raise ValueError("Ungültiges Aktualitätsfenster")


NATIVE_SOURCES_149: tuple[SourceSpec149, ...] = (
    SourceSpec149("dblp_authors", "DBLP Author Search", "scholarly_identity", "computer_science_authors", "public_native", "LOOKUP", "provider_collection_120", "https://dblp.org/", "https://dblp.org/faq/How+to+use+the+dblp+search+API.html", ("dblp.org",), ("name",), "dblp_authors_public_149", authority_score=87, independence_score=80, freshness_days=14, priority=91),
    SourceSpec149("semantic_scholar_authors", "Semantic Scholar Authors", "scholarly_identity", "academic_graph", "public_native", "LOOKUP", "provider_collection_120", "https://www.semanticscholar.org/", "https://api.semanticscholar.org/api-docs/", ("api.semanticscholar.org",), ("name", "organisation"), "semantic_scholar_authors_public_149", authority_score=82, independence_score=72, freshness_days=14, priority=88),
    SourceSpec149("arxiv_authors", "arXiv Author Search", "publications_archive", "preprint_repository", "public_native", "LOOKUP", "provider_collection_120", "https://arxiv.org/", "https://info.arxiv.org/help/api/", ("export.arxiv.org", "arxiv.org"), ("name",), "arxiv_author_public_149", authority_score=84, independence_score=78, freshness_days=7, priority=86),
    SourceSpec149("pubmed_authors", "NCBI PubMed Author Search", "publications_archive", "biomedical_literature", "public_native", "LOOKUP", "provider_collection_120", "https://pubmed.ncbi.nlm.nih.gov/", "https://www.ncbi.nlm.nih.gov/home/develop/api/", ("eutils.ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov"), ("name",), "ncbi_pubmed_author_public_149", authority_score=93, independence_score=88, freshness_days=3, priority=94),
    SourceSpec149("zenodo_records", "Zenodo Records", "publications_archive", "research_repository", "public_native", "LOOKUP", "provider_collection_120", "https://zenodo.org/", "https://developers.zenodo.org/", ("zenodo.org",), ("name", "organisation", "keyword", "identifier"), "zenodo_records_public_149", authority_score=85, independence_score=78, freshness_days=7, priority=84),
    SourceSpec149("hal_publications", "HAL Open Archive", "publications_archive", "research_repository", "public_native", "LOOKUP", "provider_collection_120", "https://hal.science/", "https://api.archives-ouvertes.fr/docs/search", ("api.archives-ouvertes.fr", "hal.science"), ("name", "organisation", "keyword"), "hal_publications_public_149", authority_score=87, independence_score=82, freshness_days=7, jurisdiction="FR/EU", geographic_scope="France/EU", priority=85),
    SourceSpec149("library_of_congress", "Library of Congress", "publications_archive", "national_archive", "public_native", "LOOKUP", "provider_collection_120", "https://www.loc.gov/", "https://www.loc.gov/apis/json-and-yaml/", ("www.loc.gov",), ("name", "organisation", "keyword", "location"), "library_of_congress_public_149", authority_score=96, independence_score=92, freshness_days=30, jurisdiction="US", geographic_scope="global", priority=90),
    SourceSpec149("stackexchange_users", "Stack Exchange Users", "social_community", "technical_community", "public_native", "LOOKUP", "provider_collection_120", "https://stackoverflow.com/", "https://api.stackexchange.com/docs/users", ("api.stackexchange.com", "stackoverflow.com"), ("name", "username"), "stackexchange_users_public_149", authority_score=62, independence_score=58, freshness_days=3, risk_level="medium", priority=70),
    SourceSpec149("gdelt_news", "GDELT DOC News Search", "web_news_archive", "global_news", "public_native", "LOOKUP", "provider_collection_120", "https://www.gdeltproject.org/", "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/", ("api.gdeltproject.org",), ("name", "organisation", "keyword", "location"), "gdelt_doc_public_149", authority_score=58, independence_score=45, freshness_days=1, risk_level="medium", priority=74, metadata={"source_independence_review_required": True}),
    SourceSpec149("wikimedia_commons", "Wikimedia Commons", "media_visual", "public_media_archive", "public_native", "LOOKUP", "provider_collection_120", "https://commons.wikimedia.org/", "https://commons.wikimedia.org/wiki/Commons:API/MediaWiki", ("commons.wikimedia.org", "upload.wikimedia.org"), ("name", "organisation", "keyword", "location"), "wikimedia_commons_public_149", authority_score=68, independence_score=55, freshness_days=7, risk_level="medium", priority=72, metadata={"automatic_download": False, "license_review_required": True}),
    SourceSpec149("ripestat_whois", "RIPEstat Whois", "domain_infrastructure", "network_registry", "public_native", "LOOKUP", "provider_collection_120", "https://stat.ripe.net/", "https://stat.ripe.net/docs/data-api/api-endpoints/whois", ("stat.ripe.net",), ("domain", "ip", "asn"), "ripestat_whois_public_149", authority_score=92, independence_score=90, freshness_days=1, priority=90, metadata={"infrastructure_not_person_control": True}),
    SourceSpec149("dnb_sru", "Deutsche Nationalbibliothek SRU", "identity_authority", "national_library_catalog", "public_native", "LOOKUP", "provider_collection_120", "https://portal.dnb.de/", "https://www.dnb.de/DE/Professionell/Metadatendienste/Datenbezug/SRU/sru.html", ("services.dnb.de", "portal.dnb.de"), ("name", "organisation", "keyword", "identifier"), "dnb_sru_public_149", authority_score=96, independence_score=92, freshness_days=14, jurisdiction="DE", geographic_scope="Germany", priority=94),
    SourceSpec149("viaf_authority", "VIAF Authority Search", "identity_authority", "library_authority", "public_native", "LOOKUP", "provider_collection_120", "https://viaf.org/", "https://viaf.org/", ("viaf.org",), ("name",), "viaf_autosuggest_public_149", authority_score=88, independence_score=78, freshness_days=30, priority=88),
)

GUIDED_SOURCES_149: tuple[SourceSpec149, ...] = (
    SourceSpec149("google_scholar", "Google Scholar", "scholarly_identity", "academic_search", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://scholar.google.com/", "https://scholar.google.com/intl/en/scholar/help.html", ("scholar.google.com",), ("name", "organisation", "keyword"), search_template="https://scholar.google.com/scholar?q={query}", authority_score=70, independence_score=55, freshness_days=7, risk_level="medium", persona_required=True, priority=78),
    SourceSpec149("researchgate", "ResearchGate", "scholarly_identity", "academic_social", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://www.researchgate.net/", "https://www.researchgate.net/", ("www.researchgate.net", "researchgate.net"), ("name", "organisation", "keyword"), search_template="https://www.researchgate.net/search/researcher?q={query}", authority_score=58, independence_score=48, freshness_days=7, risk_level="high", persona_required=True, priority=60),
    SourceSpec149("common_crawl", "Common Crawl Index", "web_news_archive", "web_crawl_index", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://commoncrawl.org/", "https://commoncrawl.org/get-started", ("commoncrawl.org", "index.commoncrawl.org"), ("domain", "url", "keyword"), search_template="https://index.commoncrawl.org/", authority_score=72, independence_score=75, freshness_days=30, risk_level="medium", priority=72, metadata={"index_selection_manual": True}),
    SourceSpec149("eu_vies", "EU VIES VAT Validation", "official_registry", "vat_registry", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://ec.europa.eu/taxation_customs/vies/", "https://ec.europa.eu/taxation_customs/vies/", ("ec.europa.eu",), ("vat_id", "organisation"), search_template="https://ec.europa.eu/taxation_customs/vies/", jurisdiction="EU", geographic_scope="EU", authority_score=98, independence_score=96, freshness_days=1, priority=96),
    SourceSpec149("dpma_register", "DPMAregister", "official_registry", "patent_trademark_registry", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://register.dpma.de/", "https://www.dpma.de/service/e_dienstleistungen/dpmaregister/", ("register.dpma.de", "www.dpma.de"), ("name", "organisation", "identifier", "keyword"), search_template="https://register.dpma.de/DPMAregister/Uebersicht", jurisdiction="DE", geographic_scope="Germany", authority_score=98, independence_score=96, freshness_days=7, priority=95),
    SourceSpec149("euipo_esearch", "EUIPO eSearch", "official_registry", "trademark_registry", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://euipo.europa.eu/eSearch/", "https://euipo.europa.eu/", ("euipo.europa.eu",), ("name", "organisation", "identifier", "keyword"), search_template="https://euipo.europa.eu/eSearch/", jurisdiction="EU", geographic_scope="EU", authority_score=98, independence_score=96, freshness_days=7, priority=94),
    SourceSpec149("wipo_branddb", "WIPO Global Brand Database", "official_registry", "global_trademark_registry", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://branddb.wipo.int/", "https://www.wipo.int/reference/en/branddb/", ("branddb.wipo.int", "www.wipo.int"), ("name", "organisation", "identifier", "keyword"), search_template="https://branddb.wipo.int/", geographic_scope="global", authority_score=98, independence_score=96, freshness_days=7, priority=94),
    SourceSpec149("eurlex", "EUR-Lex", "legal_public_records", "eu_law", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://eur-lex.europa.eu/", "https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html", ("eur-lex.europa.eu",), ("name", "organisation", "keyword", "identifier"), search_template="https://eur-lex.europa.eu/search.html?text={query}&scope=EURLEX&type=quick", jurisdiction="EU", geographic_scope="EU", authority_score=99, independence_score=98, freshness_days=1, priority=98),
    SourceSpec149("hudoc", "HUDOC ECHR", "legal_public_records", "human_rights_case_law", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://hudoc.echr.coe.int/", "https://www.echr.coe.int/hudoc-database", ("hudoc.echr.coe.int", "www.echr.coe.int"), ("name", "organisation", "keyword", "identifier"), search_template="https://hudoc.echr.coe.int/eng#{%22fulltext%22:[%22{query}%22]}", jurisdiction="CoE", geographic_scope="Europe", authority_score=99, independence_score=98, freshness_days=1, priority=97),
    SourceSpec149("rechtsprechung_de", "Rechtsprechung im Internet", "legal_public_records", "german_case_law", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://www.rechtsprechung-im-internet.de/", "https://www.rechtsprechung-im-internet.de/", ("www.rechtsprechung-im-internet.de", "rechtsprechung-im-internet.de"), ("name", "organisation", "keyword", "identifier"), search_template="https://www.rechtsprechung-im-internet.de/jportal/portal/page/bsjrsprod.psml", jurisdiction="DE", geographic_scope="Germany", authority_score=99, independence_score=98, freshness_days=1, priority=97),
    SourceSpec149("congress_gov", "Congress.gov", "legal_public_records", "us_legislative_records", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://www.congress.gov/", "https://api.congress.gov/", ("www.congress.gov", "api.congress.gov"), ("name", "organisation", "keyword", "identifier"), search_template="https://www.congress.gov/search?q={query}", jurisdiction="US", geographic_scope="US", authority_score=99, independence_score=98, freshness_days=1, priority=95),
    SourceSpec149("govinfo", "GovInfo", "legal_public_records", "us_government_documents", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://www.govinfo.gov/", "https://www.govinfo.gov/developers", ("www.govinfo.gov",), ("name", "organisation", "keyword", "identifier"), search_template="https://www.govinfo.gov/app/search/{query}", jurisdiction="US", geographic_scope="US", authority_score=99, independence_score=98, freshness_days=1, priority=95),
    SourceSpec149("ofac_sls", "OFAC Sanctions List Service", "sanctions_watchlist", "us_sanctions", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://ofac.treasury.gov/sanctions-list-service", "https://ofac.treasury.gov/sanctions-list-service", ("ofac.treasury.gov",), ("name", "organisation", "identifier"), search_template="https://ofac.treasury.gov/sanctions-list-service", jurisdiction="US", geographic_scope="global", authority_score=100, independence_score=100, freshness_days=1, risk_level="high", priority=99, metadata={"watchlist_not_guilt": True, "objective_gate": "sanctions"}),
    SourceSpec149("uk_sanctions", "UK Sanctions List", "sanctions_watchlist", "uk_sanctions", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://www.gov.uk/government/publications/the-uk-sanctions-list", "https://www.gov.uk/guidance/format-guide-for-the-uk-sanctions-list", ("www.gov.uk", "sanctionslist.fcdo.gov.uk", "search-uk-sanctions-list.service.gov.uk"), ("name", "organisation", "identifier"), search_template="https://search-uk-sanctions-list.service.gov.uk/", jurisdiction="UK", geographic_scope="global", authority_score=100, independence_score=100, freshness_days=1, risk_level="high", priority=99, metadata={"watchlist_not_guilt": True, "objective_gate": "sanctions"}),
    SourceSpec149("eu_sanctions", "EU Financial Sanctions", "sanctions_watchlist", "eu_sanctions", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions", "https://finance.ec.europa.eu/eu-and-world/sanctions-restrictive-measures/overview-sanctions-and-related-resources_en", ("data.europa.eu", "finance.ec.europa.eu", "webgate.ec.europa.eu"), ("name", "organisation", "identifier"), search_template="https://webgate.ec.europa.eu/fsd/fsf", jurisdiction="EU", geographic_scope="global", authority_score=100, independence_score=100, freshness_days=1, risk_level="high", priority=99, metadata={"watchlist_not_guilt": True, "objective_gate": "sanctions"}),
    SourceSpec149("un_sanctions", "UN Security Council Consolidated List", "sanctions_watchlist", "un_sanctions", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list", "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list", ("main.un.org",), ("name", "organisation", "identifier"), search_template="https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list", jurisdiction="UN", geographic_scope="global", authority_score=100, independence_score=100, freshness_days=1, risk_level="high", priority=99, metadata={"watchlist_not_guilt": True, "objective_gate": "sanctions"}),
    SourceSpec149("interpol_red_notices", "INTERPOL Red Notices", "sanctions_watchlist", "international_notices", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://www.interpol.int/How-we-work/Notices/Red-Notices/View-Red-Notices", "https://www.interpol.int/How-we-work/Notices/Red-Notices", ("www.interpol.int",), ("name", "nationality"), search_template="https://www.interpol.int/How-we-work/Notices/Red-Notices/View-Red-Notices", jurisdiction="INTERPOL", geographic_scope="global", authority_score=100, independence_score=100, freshness_days=1, risk_level="restricted", priority=94, metadata={"notice_not_conviction": True, "objective_gate": "sanctions_or_wanted"}),
    SourceSpec149("europol_most_wanted", "EU Most Wanted", "sanctions_watchlist", "wanted_persons", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://eumostwanted.eu/", "https://eumostwanted.eu/", ("eumostwanted.eu",), ("name", "nationality"), search_template="https://eumostwanted.eu/", jurisdiction="EU", geographic_scope="EU", authority_score=98, independence_score=98, freshness_days=1, risk_level="restricted", priority=92, metadata={"wanted_listing_requires_manual_review": True, "objective_gate": "sanctions_or_wanted"}),
    SourceSpec149("opencorporates_browser", "OpenCorporates Browser", "company_intelligence", "global_company_search", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://opencorporates.com/", "https://api.opencorporates.com/documentation/API-Reference", ("opencorporates.com", "api.opencorporates.com"), ("organisation", "name", "identifier"), search_template="https://opencorporates.com/companies?q={query}", geographic_scope="global", authority_score=72, independence_score=65, freshness_days=7, risk_level="medium", priority=78),
    SourceSpec149("worldcat", "WorldCat", "identity_authority", "global_library_catalog", "public_guided", "GUIDED_BROWSER", "guided_browser_136", "https://search.worldcat.org/", "https://www.oclc.org/developer/api/oclc-apis/worldcat-search-api.en.html", ("search.worldcat.org", "www.oclc.org"), ("name", "organisation", "keyword", "identifier"), search_template="https://search.worldcat.org/search?q={query}", geographic_scope="global", authority_score=82, independence_score=75, freshness_days=30, risk_level="low", priority=80),
)

LICENSED_SOURCES_149: tuple[SourceSpec149, ...] = (
    SourceSpec149("opencorporates_api", "OpenCorporates API", "company_intelligence", "global_company_api", "licensed", "LOOKUP", "external_worker", "https://api.opencorporates.com/", "https://api.opencorporates.com/documentation/API-Reference", ("api.opencorporates.com",), ("organisation", "name", "identifier"), authority_score=75, independence_score=68, freshness_days=7, risk_level="medium", legal_status="approved_licensed", terms_profile="licensed_official_api_terms_review", priority=82, secret_names=("opencorporates_api_token",), required_secret_names=("opencorporates_api_token",)),
    SourceSpec149("europeana_api", "Europeana API", "media_visual", "european_cultural_heritage", "auth_required", "LOOKUP", "external_worker", "https://www.europeana.eu/", "https://pro.europeana.eu/page/apis", ("api.europeana.eu", "www.europeana.eu"), ("name", "organisation", "keyword", "location"), jurisdiction="EU", geographic_scope="Europe", authority_score=88, independence_score=82, freshness_days=14, risk_level="medium", legal_status="approved_licensed", terms_profile="official_api_key_terms", priority=82, secret_names=("europeana_api_key",), required_secret_names=("europeana_api_key",)),
    SourceSpec149("core_api", "CORE API", "publications_archive", "open_research_aggregator", "auth_required", "LOOKUP", "external_worker", "https://core.ac.uk/", "https://core.ac.uk/services/api", ("api.core.ac.uk", "core.ac.uk"), ("name", "organisation", "keyword", "identifier"), authority_score=78, independence_score=62, freshness_days=7, risk_level="medium", legal_status="approved_licensed", terms_profile="official_api_key_terms", priority=78, secret_names=("core_api_key",), required_secret_names=("core_api_key",)),
    SourceSpec149("brave_search_api", "Brave Search API", "web_news_archive", "web_search_api", "licensed", "LOOKUP", "external_worker", "https://brave.com/search/api/", "https://api-dashboard.search.brave.com/app/documentation", ("api.search.brave.com", "brave.com"), ("name", "username", "organisation", "domain", "keyword"), authority_score=55, independence_score=45, freshness_days=1, risk_level="high", persona_required=True, legal_status="approved_licensed", terms_profile="licensed_search_api_terms", priority=70, secret_names=("brave_search_api_key",), required_secret_names=("brave_search_api_key",), metadata={"broad_web_disclosure": True}),
    SourceSpec149("shodan_api", "Shodan API", "domain_infrastructure", "internet_exposure", "licensed", "LOOKUP", "external_worker", "https://www.shodan.io/", "https://developer.shodan.io/api", ("api.shodan.io", "www.shodan.io"), ("ip", "domain", "organisation"), authority_score=72, independence_score=68, freshness_days=1, risk_level="high", persona_required=True, legal_status="approved_licensed", terms_profile="licensed_security_api_terms", priority=76, secret_names=("shodan_api_key",), required_secret_names=("shodan_api_key",)),
    SourceSpec149("censys_api", "Censys Search API", "domain_infrastructure", "internet_exposure", "licensed", "LOOKUP", "external_worker", "https://search.censys.io/", "https://docs.censys.com/", ("search.censys.io", "api.platform.censys.io"), ("ip", "domain", "organisation"), authority_score=75, independence_score=70, freshness_days=1, risk_level="high", persona_required=True, legal_status="approved_licensed", terms_profile="licensed_security_api_terms", priority=76, secret_names=("censys_api_token",), required_secret_names=("censys_api_token",)),
    SourceSpec149("virustotal_api", "VirusTotal API", "domain_infrastructure", "public_security_context", "licensed", "LOOKUP", "external_worker", "https://www.virustotal.com/", "https://docs.virustotal.com/reference/overview", ("www.virustotal.com",), ("domain", "ip", "url", "file_hash"), authority_score=72, independence_score=60, freshness_days=1, risk_level="high", persona_required=True, legal_status="approved_licensed", terms_profile="licensed_security_api_terms", priority=74, secret_names=("virustotal_api_key",), required_secret_names=("virustotal_api_key",)),
    SourceSpec149("hibp_api", "Have I Been Pwned API", "licensed_enrichment", "breach_exposure", "licensed", "LOOKUP", "external_worker", "https://haveibeenpwned.com/", "https://haveibeenpwned.com/API/v3", ("haveibeenpwned.com",), ("email",), authority_score=78, independence_score=72, freshness_days=1, risk_level="restricted", persona_required=True, exact_email_allowed=True, legal_status="approved_licensed", terms_profile="licensed_sensitive_api_terms_explicit_authority_required", priority=45, secret_names=("hibp_api_key",), required_secret_names=("hibp_api_key",), metadata={"sensitive_exact_email": True, "not_breach_attribution": True}),
)

NEW_SOURCES_149 = NATIVE_SOURCES_149 + GUIDED_SOURCES_149 + LICENSED_SOURCES_149


class Build149DataEcosystemService:
    """Phase-5 data ecosystem, local source planning and OPSEC minimisation.

    The service broadens source coverage but preserves the Build-148 connector
    boundary. Results stay candidate-only in connector quarantine. Local AI is
    deterministic and can only propose a bounded plan; it never executes a query.
    """

    BUILD = "149.0"

    def __init__(self, db: Any, audit: Any, *, build148: Any, build147: Any, build143: Any, clock: Any | None = None) -> None:
        self.db = db
        self.audit = audit
        self.build148 = build148
        self.build147 = build147
        self.build143 = build143
        self.clock = clock or time.time
        self.seed_ecosystem()

    # ---------- common ----------
    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not row:
            raise KeyError("Fall nicht gefunden")
        return row

    def _target(self, case_id: str, target_id: str) -> dict[str, Any] | None:
        if not target_id:
            return None
        row = self.db.one("SELECT * FROM targets WHERE case_id=? AND target_id=?", (case_id, target_id))
        if not row:
            raise KeyError("Zielperson nicht gefunden oder falscher Fall")
        result = dict(row)
        for key in ("aliases_json", "emails_json", "usernames_json", "locations_json", "companies_json", "domains_json"):
            result[key] = loads(str(result.get(key) or "[]"))
        return result

    def _event(self, *, event_type: str, actor: str, case_id: str = "", plan_id: str = "", job_id: str = "", source_key: str = "", payload: Mapping[str, Any] | None = None) -> str:
        safe = sanitize_mapping(dict(payload or {}))
        previous = self.db.one("SELECT event_hash FROM source_events_149 WHERE COALESCE(case_id,'')=? ORDER BY sequence DESC LIMIT 1", (case_id,))
        previous_hash = str((previous or {}).get("event_hash") or "GENESIS")
        event_id = new_id("src149"); stamp = now_ts()
        material = {"event_id": event_id, "case_id": case_id, "plan_id": plan_id, "job_id": job_id, "source_key": source_key, "actor": _safe(actor, 120), "event_type": event_type, "payload": safe, "previous_hash": previous_hash, "created_at": stamp}
        event_hash = _sha(material)
        self.db.execute("INSERT INTO source_events_149(event_id,case_id,plan_id,job_id,source_key,actor,event_type,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (event_id, case_id or None, plan_id, job_id, source_key, _safe(actor, 120), event_type, dumps(safe), previous_hash, event_hash, stamp))
        self.audit.log("source_ecosystem", "source149", source_key or plan_id or job_id or event_id, case_id or None, {"event_type": event_type, **safe})
        return event_id

    # ---------- source seeding ----------
    @staticmethod
    def _input_schema(inputs: Iterable[str]) -> dict[str, Any]:
        props: dict[str, Any] = {"query": {"type": "string", "minLength": 1, "maxLength": 1000}, "max_results": {"type": "integer", "minimum": 1, "maximum": 250}}
        for item in inputs:
            key = str(item).strip().casefold().replace("-", "_")
            if re.fullmatch(r"[a-z][a-z0-9_]{1,63}", key) and key not in props:
                props[key] = {"type": "string", "maxLength": 1000}
        return {"type": "object", "properties": props, "required": ["query"], "additionalProperties": False}

    @staticmethod
    def _output_schema() -> dict[str, Any]:
        return {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object"}}, "result_count": {"type": "integer", "minimum": 0}, "candidate_only": {"type": "boolean", "const": True}}, "required": ["items", "candidate_only"], "additionalProperties": True}

    def _manifest(self, spec: SourceSpec149) -> ConnectorManifest148:
        spec.validate()
        metadata = dict(spec.metadata)
        metadata.update({
            "build": self.BUILD, "source_family": spec.family, "category": spec.category,
            "access_tier": spec.access_tier, "official_url": spec.official_url,
            "documentation_url": spec.documentation_url, "search_template": spec.search_template,
            "jurisdiction": spec.jurisdiction, "geographic_scope": spec.geographic_scope,
            "authority_score": spec.authority_score, "independence_score": spec.independence_score,
            "risk_level": spec.risk_level, "persona_required": spec.persona_required,
            "exact_email_allowed": spec.exact_email_allowed, "bulk_capable": spec.bulk_capable,
            "provider_key": spec.provider_key, "required_secret_names": list(spec.required_secret_names),
            "candidate_only": True, "automatic_evidence_write": False,
        })
        return ConnectorManifest148(
            connector_id=f"source149_{spec.key}", source_key=spec.key, label=spec.label,
            connector_version="1.0.0", connector_type=spec.connector_type, publisher="EagleEye built-in source portfolio",
            entrypoint=spec.provider_key if spec.execution_backend == "provider_collection_120" else ("eagleeye.guided_browser" if spec.execution_backend == "guided_browser_136" else f"eagleeye.external149.{spec.key}"),
            execution_backend=spec.execution_backend, input_schema=self._input_schema(spec.input_types), output_schema=self._output_schema(),
            entity_types=("person", "organisation", "public_profile", "document", "media", "infrastructure"),
            secret_names=spec.secret_names, allowed_hosts=spec.allowed_hosts,
            rate_limit_per_minute=20 if spec.access_tier == "public_native" else 10,
            cost_model="free_public" if spec.access_tier.startswith("public_") else "licensed_or_quota_bound",
            legal_status=spec.legal_status, terms_profile=spec.terms_profile,
            retention_profile="case_policy_candidate_only", data_classification=("public_data", "personal_data_candidate"),
            health_probe={"kind": "provider_contract" if spec.execution_backend == "provider_collection_120" else "official_url", "provider_key": spec.provider_key},
            metadata=metadata, code_sha256=_sha({"source": spec.key, "provider": spec.provider_key, "build": self.BUILD}),
            signature_status="internal_trusted", enabled=True,
        )

    def _seed_guided_source147(self, spec: SourceSpec149) -> None:
        if spec.execution_backend != "guided_browser_136":
            return
        stamp = now_ts()
        metadata = {"build": self.BUILD, "source_family": spec.family, "documentation_url": spec.documentation_url, "candidate_only": True}
        self.db.execute(
            """INSERT INTO research_sources_147(source_key,label,source_group,category,access_mode,official_url,search_url_template,provider_key,allowed_hosts_json,input_types_json,auth_requirement,terms_profile,risk_level,persona_recommended,native_execution,enabled,priority,metadata_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_key) DO UPDATE SET label=excluded.label,source_group=excluded.source_group,category=excluded.category,access_mode=excluded.access_mode,official_url=excluded.official_url,search_url_template=excluded.search_url_template,allowed_hosts_json=excluded.allowed_hosts_json,input_types_json=excluded.input_types_json,auth_requirement=excluded.auth_requirement,terms_profile=excluded.terms_profile,risk_level=excluded.risk_level,persona_recommended=excluded.persona_recommended,native_execution=excluded.native_execution,enabled=excluded.enabled,priority=excluded.priority,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",
            (spec.key, spec.label, "database" if spec.family != "social_community" else "social", spec.category, "guided_browser", spec.official_url, spec.search_template or spec.official_url, "", dumps(list(spec.allowed_hosts)), dumps(list(spec.input_types)), "account_or_manual" if spec.persona_required else "official_browser_interface", spec.terms_profile, spec.risk_level, int(spec.persona_required), 0, 1, spec.priority, dumps(metadata), stamp, stamp),
        )

    def _upsert_portfolio(self, spec: SourceSpec149) -> None:
        stamp = now_ts(); connector_id = f"source149_{spec.key}"
        self.db.execute(
            """INSERT INTO source_portfolio_149(source_key,connector_id,label,source_family,category,jurisdiction,geographic_scope,access_tier,authority_score,independence_score,freshness_days,risk_level,persona_required,exact_email_allowed,bulk_capable,input_types_json,official_url,documentation_url,legal_status,terms_profile,priority,enabled,metadata_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_key) DO UPDATE SET connector_id=excluded.connector_id,label=excluded.label,source_family=excluded.source_family,category=excluded.category,jurisdiction=excluded.jurisdiction,geographic_scope=excluded.geographic_scope,access_tier=excluded.access_tier,authority_score=excluded.authority_score,independence_score=excluded.independence_score,freshness_days=excluded.freshness_days,risk_level=excluded.risk_level,persona_required=excluded.persona_required,exact_email_allowed=excluded.exact_email_allowed,bulk_capable=excluded.bulk_capable,input_types_json=excluded.input_types_json,official_url=excluded.official_url,documentation_url=excluded.documentation_url,legal_status=excluded.legal_status,terms_profile=excluded.terms_profile,priority=excluded.priority,enabled=excluded.enabled,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",
            (spec.key, connector_id, spec.label, spec.family, spec.category, spec.jurisdiction, spec.geographic_scope, spec.access_tier, spec.authority_score, spec.independence_score, spec.freshness_days, spec.risk_level, int(spec.persona_required), int(spec.exact_email_allowed), int(spec.bulk_capable), dumps(list(spec.input_types)), spec.official_url, spec.documentation_url, spec.legal_status, spec.terms_profile, spec.priority, 1, dumps(sanitize_mapping(dict(spec.metadata))), stamp, stamp),
        )

    def _import_existing_portfolio(self) -> None:
        stamp = now_ts()
        for row in self.build148.list_connectors():
            connector_id = str(row["connector_id"])
            if connector_id.startswith("source149_") or connector_id.startswith("eagleeye_"):
                continue
            metadata = dict(row.get("metadata") or {})
            source_key = f"legacy_{connector_id}"[:95]
            group = str(metadata.get("source_group") or "")
            family = str(metadata.get("source_family") or ("social_community" if group == "social" else "official_registry"))
            if family not in SOURCE_FAMILIES:
                category = str(metadata.get("category") or "")
                family = "social_community" if "social" in category or metadata.get("source_group") == "social" else "official_registry"
            access_tier = "public_native" if row.get("execution_backend") == "provider_collection_120" else "public_guided" if row.get("execution_backend") == "guided_browser_136" else "auth_required"
            risk = str(metadata.get("risk_level") or "low")
            if risk not in RISK_LEVELS:
                risk = "medium"
            official = str(metadata.get("official_url") or "https://example.invalid/")
            self.db.execute(
                """INSERT INTO source_portfolio_149(source_key,connector_id,label,source_family,category,jurisdiction,geographic_scope,access_tier,authority_score,independence_score,freshness_days,risk_level,persona_required,exact_email_allowed,bulk_capable,input_types_json,official_url,documentation_url,legal_status,terms_profile,priority,enabled,metadata_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source_key) DO UPDATE SET connector_id=excluded.connector_id,label=excluded.label,source_family=excluded.source_family,category=excluded.category,access_tier=excluded.access_tier,risk_level=excluded.risk_level,persona_required=excluded.persona_required,input_types_json=excluded.input_types_json,official_url=excluded.official_url,legal_status=excluded.legal_status,terms_profile=excluded.terms_profile,enabled=excluded.enabled,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",
                (source_key, connector_id, row.get("label") or connector_id, family, metadata.get("category") or row.get("connector_type") or "legacy", metadata.get("jurisdiction") or "global", metadata.get("geographic_scope") or "global", access_tier, int(metadata.get("authority_score") or 60), int(metadata.get("independence_score") or 55), 30, risk, int(bool(metadata.get("persona_recommended"))), 0, 0, dumps(list((row.get("input_schema") or {}).get("properties", {}).keys())), official, str(metadata.get("documentation_url") or ""), row.get("legal_status") or "terms_review_required", row.get("terms_profile") or "", int(metadata.get("priority") or 50), int(bool(row.get("enabled"))), dumps(sanitize_mapping(metadata)), stamp, stamp),
            )

    def seed_ecosystem(self) -> None:
        for spec in NEW_SOURCES_149:
            spec.validate()
            manifest = self._manifest(spec)
            self.build148._upsert_manifest(manifest, actor="build149-seed", preserve_governance=True)
            self._seed_guided_source147(spec)
            self._upsert_portfolio(spec)
        self._import_existing_portfolio()
        self.build148.refresh_all_health()

    # ---------- portfolio ----------
    @staticmethod
    def _decode_source(row: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["input_types"] = loads(str(result.pop("input_types_json", "[]")))
        result["metadata"] = loads(str(result.pop("metadata_json", "{}")))
        result["persona_required"] = bool(result.get("persona_required"))
        result["exact_email_allowed"] = bool(result.get("exact_email_allowed"))
        result["bulk_capable"] = bool(result.get("bulk_capable"))
        result["enabled"] = bool(result.get("enabled"))
        return result

    def list_sources(self, *, family: str = "", access_tier: str = "", enabled_only: bool = True) -> list[dict[str, Any]]:
        clauses: list[str] = []; params: list[Any] = []
        if family:
            clauses.append("p.source_family=?"); params.append(family)
        if access_tier:
            clauses.append("p.access_tier=?"); params.append(access_tier)
        if enabled_only:
            clauses.append("p.enabled=1")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.db.all(f"SELECT p.*,m.lifecycle_status,h.health_state,h.contract_state FROM source_portfolio_149 p JOIN connector_manifests_148 m ON m.connector_id=p.connector_id LEFT JOIN connector_health_148 h ON h.connector_id=p.connector_id{where} ORDER BY p.source_family,p.priority DESC,p.authority_score DESC,p.label", params)
        return [self._decode_source(row) for row in rows]

    def get_source(self, source_key: str) -> dict[str, Any]:
        row = self.db.one("SELECT p.*,m.lifecycle_status,h.health_state,h.contract_state FROM source_portfolio_149 p JOIN connector_manifests_148 m ON m.connector_id=p.connector_id LEFT JOIN connector_health_148 h ON h.connector_id=p.connector_id WHERE p.source_key=?", (source_key,))
        if not row:
            raise KeyError("Build-149-Quelle nicht gefunden")
        return self._decode_source(row)

    # ---------- anchors and local AI ----------
    def _anchors(self, target: Mapping[str, Any] | None, provided: Mapping[str, Any] | None = None) -> dict[str, list[str]]:
        anchors: dict[str, list[str]] = {key: [] for key in ("name", "alias", "username", "email", "organisation", "location", "domain", "identifier", "keyword", "ip", "asn", "vat_id", "nationality")}
        if target:
            anchors["name"] = [str(target.get("name") or "")]
            anchors["alias"] = [str(x) for x in target.get("aliases_json") or []]
            anchors["username"] = [str(x) for x in target.get("usernames_json") or []]
            anchors["email"] = [str(x) for x in target.get("emails_json") or []]
            anchors["organisation"] = [str(x) for x in target.get("companies_json") or []]
            anchors["location"] = [str(x) for x in target.get("locations_json") or []]
            anchors["domain"] = [str(x) for x in target.get("domains_json") or []]
        for key, value in dict(provided or {}).items():
            if key not in anchors:
                continue
            values = value if isinstance(value, (list, tuple)) else [value]
            anchors[key].extend(str(x) for x in values)
        return {key: _dedupe(values, 12) for key, values in anchors.items() if _dedupe(values, 12)}

    @staticmethod
    def _objective_families(objective: str) -> list[str]:
        text = _norm(objective)
        if any(word in text for word in ("sanktion", "sanction", "watchlist", "wanted", "fahnd")):
            return ["sanctions_watchlist", "official_registry", "identity_authority", "web_news_archive"]
        if any(word in text for word in ("firma", "unternehmen", "company", "organisation", "geschäft")):
            return ["official_registry", "company_intelligence", "legal_public_records", "web_news_archive", "domain_infrastructure"]
        if any(word in text for word in ("publikation", "publication", "wissenschaft", "academic", "autor")):
            return ["scholarly_identity", "publications_archive", "identity_authority", "media_visual"]
        if any(word in text for word in ("bild", "foto", "image", "media")):
            return ["media_visual", "web_news_archive", "social_community", "publications_archive"]
        if any(word in text for word in ("digital", "social", "username", "account", "profil")):
            return ["social_community", "domain_infrastructure", "web_news_archive", "identity_authority"]
        if any(word in text for word in ("recht", "court", "gericht", "legal")):
            return ["legal_public_records", "official_registry", "web_news_archive", "identity_authority"]
        return ["official_registry", "identity_authority", "scholarly_identity", "publications_archive", "social_community", "web_news_archive", "domain_infrastructure"]

    @staticmethod
    def _query_for_source(source: Mapping[str, Any], anchors: Mapping[str, list[str]], disclosure_budget: int) -> tuple[str, list[str]] | None:
        allowed = [str(x) for x in source.get("input_types") or []]
        choices: list[tuple[str, str]] = []
        order = ("username", "domain", "identifier", "vat_id", "ip", "asn", "name", "alias", "organisation", "location", "keyword", "nationality", "email")
        for anchor_type in order:
            if anchor_type not in allowed and not (anchor_type == "alias" and "name" in allowed):
                continue
            for value in anchors.get(anchor_type, [])[:2]:
                choices.append((anchor_type, value))
                break
        if not choices:
            return None
        family = str(source.get("source_family") or "")
        if family in {"scholarly_identity", "publications_archive", "official_registry", "company_intelligence", "legal_public_records"}:
            preferred = [item for item in choices if item[0] in {"name", "alias", "organisation", "identifier", "vat_id", "keyword"}]
        elif family == "social_community":
            preferred = [item for item in choices if item[0] in {"username", "name", "alias", "keyword"}]
        elif family == "domain_infrastructure":
            preferred = [item for item in choices if item[0] in {"domain", "ip", "asn", "organisation"}]
        elif family == "sanctions_watchlist":
            preferred = [item for item in choices if item[0] in {"name", "alias", "organisation", "identifier", "nationality"}]
        else:
            preferred = choices
        selected = (preferred or choices)[:max(1, min(disclosure_budget, 3))]
        query = " ".join(value for _, value in selected)
        return (_safe(query, 1000), [kind for kind, _ in selected]) if query else None

    def _active_persona(self, case_id: str) -> dict[str, Any] | None:
        try:
            rows = self.db.all("SELECT * FROM research_persona_sessions_143 WHERE case_id=? AND status='active' AND expires_epoch>? ORDER BY launched_at DESC LIMIT 1", (case_id, int(self.clock())))
            return rows[0] if rows else None
        except Exception:
            return None

    def create_plan(self, *, case_id: str, target_id: str = "", objective: str, purpose: str, legal_basis: str, requested_families: Iterable[str] = (), anchors: Mapping[str, Any] | None = None, disclosure_budget: int = 3, max_external_actions: int = 10, allow_exact_email: bool = False, allow_licensed_sources: bool = False, actor: str) -> dict[str, Any]:
        self._case(case_id); target = self._target(case_id, target_id)
        if len(_safe(objective)) < 8 or len(_safe(purpose)) < 10 or len(_safe(legal_basis)) < 8:
            raise ValueError("Ermittlungsziel, Zweck und Rechtsgrundlage müssen nachvollziehbar dokumentiert sein")
        disclosure_budget = max(1, min(int(disclosure_budget), 3)); max_actions = max(1, min(int(max_external_actions), 20))
        anchor_map = self._anchors(target, anchors)
        if not anchor_map:
            raise ValueError("Mindestens ein nicht sensibles Identitäts- oder Sachmerkmal ist erforderlich")
        family_list = [x for x in _dedupe(requested_families, 12) if x in SOURCE_FAMILIES] or self._objective_families(objective)
        all_sources = self.list_sources()
        sanctions_intent = any(mark in _norm(objective) for mark in ("sanktion", "sanction", "watchlist", "wanted", "fahnd"))
        selected: list[dict[str, Any]] = []; excluded: list[dict[str, Any]] = []
        for source in all_sources:
            reasons: list[str] = []
            if source["source_family"] not in family_list:
                reasons.append("family_not_requested")
            if source["access_tier"] in {"licensed", "auth_required"} and not allow_licensed_sources:
                reasons.append("licensed_not_enabled")
            if source["source_family"] in WATCHLIST_FAMILIES and not sanctions_intent:
                reasons.append("watchlist_objective_gate")
            if source["source_key"].replace("legacy_source149_", "") in EXACT_EMAIL_SOURCES and not allow_exact_email:
                reasons.append("exact_email_not_enabled")
            if source.get("health_state") in {"quarantined", "offline", "changed_contract"}:
                reasons.append(f"health_{source.get('health_state')}")
            query = self._query_for_source(source, anchor_map, disclosure_budget)
            if not query:
                reasons.append("no_compatible_anchor")
            if reasons:
                excluded.append({"source_key": source["source_key"], "connector_id": source["connector_id"], "reasons": reasons})
                continue
            query_text, anchor_types = query
            risk_penalty = {"low": 0, "medium": 12, "high": 25, "restricted": 40}[source["risk_level"]]
            auth_penalty = 12 if source["access_tier"] in {"licensed", "auth_required"} else 0
            health_penalty = 8 if source.get("health_state") not in {"operational", "terms_review_required", "authentication_required"} else 0
            family_bonus = 10 if source["source_family"] in family_list[:2] else 0
            expected = max(0.0, min(100.0, source["authority_score"] * 0.42 + source["independence_score"] * 0.28 + source["priority"] * 0.20 + family_bonus - risk_penalty - auth_penalty - health_penalty))
            selected.append({"source_key": source["source_key"], "connector_id": source["connector_id"], "label": source["label"], "source_family": source["source_family"], "query": query_text, "anchor_types": anchor_types, "expected_value": round(expected, 2), "risk_level": source["risk_level"], "persona_required": source["persona_required"], "access_tier": source["access_tier"], "authority_score": source["authority_score"], "independence_score": source["independence_score"]})
        # Diversified greedy selection: first best source per family, then fill by value.
        selected.sort(key=lambda x: (x["expected_value"], x["authority_score"], x["independence_score"]), reverse=True)
        diversified: list[dict[str, Any]] = []; seen_families: set[str] = set()
        for item in selected:
            if item["source_family"] not in seen_families:
                diversified.append(item); seen_families.add(item["source_family"])
            if len(diversified) >= max_actions:
                break
        for item in selected:
            if len(diversified) >= max_actions:
                break
            if item not in diversified:
                diversified.append(item)
        selected = diversified[:max_actions]
        family_counts: dict[str, int] = {}
        for item in selected:
            family_counts[item["source_family"]] = family_counts.get(item["source_family"], 0) + 1
        missing_families = [family for family in family_list if family not in family_counts]
        ai_brief = {
            "mode": "local_deterministic_source_planner_149", "external_ai_calls": 0,
            "selected_count": len(selected), "family_coverage": family_counts,
            "missing_families": missing_families, "excluded_count": len(excluded),
            "selection_logic": ["authority", "independence", "objective_fit", "current_connector_state", "risk_penalty", "source_family_diversity"],
            "claims": ["Quellenauswahl ist eine Planungsempfehlung.", "Treffer bleiben candidate-only.", "Watchlist-Treffer sind weder Schuld- noch Identitätsnachweis."],
        }
        plan_id = new_id("plan149"); stamp = now_ts()
        expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(self.clock()) + 24 * 3600))
        self.db.execute("INSERT INTO source_plans_149(plan_id,case_id,target_id,objective,purpose,legal_basis,requested_families_json,anchors_json,selected_connectors_json,excluded_sources_json,ai_brief_json,opsec_assessment_json,disclosure_budget,max_external_actions,allow_exact_email,allow_licensed_sources,risk_level,status,expires_at,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'draft',?,?,?,?)", (plan_id, case_id, target_id or None, _safe(objective,1000), _safe(purpose,2000), _safe(legal_basis,2000), dumps(family_list), dumps(sanitize_mapping(anchor_map)), dumps(selected), dumps(excluded[:200]), dumps(ai_brief), dumps({}), disclosure_budget, max_actions, int(allow_exact_email), int(allow_licensed_sources), "medium", expires_at, _safe(actor,120), stamp, stamp))
        assessment = self.assess_opsec(case_id=case_id, plan_id=plan_id, actor=actor)
        self._event(event_type="source_plan_created_149", actor=actor, case_id=case_id, plan_id=plan_id, payload={"selected_count": len(selected), "families": sorted(family_counts), "external_ai_calls": 0, "automatic_actions": 0})
        return self.get_plan(case_id=case_id, plan_id=plan_id)

    def get_plan(self, *, case_id: str, plan_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM source_plans_149 WHERE case_id=? AND plan_id=?", (case_id, plan_id))
        if not row:
            raise KeyError("Quellenplan nicht gefunden oder falscher Fall")
        result = dict(row)
        for old, new, default in (("requested_families_json","requested_families",[]),("anchors_json","anchors",{}),("selected_connectors_json","selected_connectors",[]),("excluded_sources_json","excluded_sources",[]),("ai_brief_json","ai_brief",{}),("opsec_assessment_json","opsec_assessment",{})):
            result[new] = loads(str(result.pop(old, dumps(default))))
        result["allow_exact_email"] = bool(result.get("allow_exact_email")); result["allow_licensed_sources"] = bool(result.get("allow_licensed_sources"))
        result["jobs"] = self.db.all("SELECT * FROM source_jobs_149 WHERE plan_id=? ORDER BY priority DESC,created_at", (plan_id,))
        for job in result["jobs"]:
            job["anchor_types"] = loads(str(job.pop("anchor_types_json", "[]")))
        return result

    def list_plans(self, case_id: str) -> list[dict[str, Any]]:
        return [self.get_plan(case_id=case_id, plan_id=row["plan_id"]) for row in self.db.all("SELECT plan_id FROM source_plans_149 WHERE case_id=? ORDER BY created_at DESC", (case_id,))]

    # ---------- OPSEC ----------
    def assess_opsec(self, *, case_id: str, plan_id: str, actor: str) -> dict[str, Any]:
        plan = self.get_plan(case_id=case_id, plan_id=plan_id)
        findings: list[dict[str, Any]] = []; mitigations: list[str] = []
        blocked = False; exposure = 0.0
        selected = plan["selected_connectors"]; anchors = plan["anchors"]
        active = self._active_persona(case_id)
        sensitive_anchor_keys = {
            "health", "medical", "religion", "political_opinion", "sexual_orientation",
            "minor_data", "child_data", "biometric", "face_embedding", "password",
            "secret", "access_token", "full_case", "date_of_birth_exact",
        }
        anchor_blob = json.dumps(anchors, ensure_ascii=False).casefold()
        if any(str(key).casefold() in sensitive_anchor_keys for key in anchors) or any(
            marker in anchor_blob for marker in {"password", "access_token", "face_embedding", "full_case"}
        ):
            blocked = True; findings.append({"severity": "blocker", "code": "prohibited_sensitive_scope", "message": "Plan enthält eine gesperrte sensible, biometrische oder geheimnisbezogene Datenklasse."})
        email_selected = any("email" in item.get("anchor_types", []) for item in selected)
        if email_selected and not plan["allow_exact_email"]:
            blocked = True; findings.append({"severity": "blocker", "code": "exact_email_without_optin", "message": "Exakte E-Mail-Adressen dürfen nur nach expliziter Freigabe an dafür vorgesehene Quellen gegeben werden."})
        if email_selected:
            invalid = [item["source_key"] for item in selected if "email" in item.get("anchor_types", []) and item["source_key"] not in EXACT_EMAIL_SOURCES]
            if invalid:
                blocked = True; findings.append({"severity": "blocker", "code": "email_to_broad_source", "message": "Exakte E-Mail-Adresse würde an eine nicht dafür vorgesehene Quelle übertragen.", "sources": invalid})
        persona_sources = [item["source_key"] for item in selected if item.get("persona_required")]
        if persona_sources and not active:
            findings.append({"severity": "warning", "code": "persona_required_before_execution", "message": "Einige Quellen benötigen vor Ausführung eine aktive freigegebene Research-Persona-Sitzung.", "sources": persona_sources})
            mitigations.append("Vor jeder betroffenen Ausführung Persona- und Egress-Sitzung erneut prüfen.")
        licensed = [item["source_key"] for item in selected if item.get("access_tier") in {"licensed", "auth_required"}]
        if licensed:
            findings.append({"severity": "warning", "code": "licensed_sources_selected", "message": "Lizenzierte oder authentifizierungspflichtige Quellen benötigen akzeptierte Verträge und Vault-Secrets.", "sources": licensed})
            mitigations.append("Vertrag, Lizenz, Zweckbindung und Secret-Lease vor Ausführung prüfen.")
        watchlists = [item["source_key"] for item in selected if item.get("source_family") == "sanctions_watchlist"]
        if watchlists:
            findings.append({"severity": "warning", "code": "watchlist_false_positive_risk", "message": "Namensähnlichkeit in Sanktions- oder Fahndungslisten ist kein Identitäts-, Schuld- oder Verurteilungsnachweis.", "sources": watchlists})
            mitigations.append("Watchlist-Treffer nur mit unabhängigen Identitätsmerkmalen und Originalquelle bewerten.")
        family_counts: dict[str, int] = {}
        for item in selected:
            family_counts[item["source_family"]] = family_counts.get(item["source_family"], 0) + 1
            exposure += min(1.0, len(item.get("anchor_types", [])) / 3.0) * ({"low":0.4,"medium":0.65,"high":0.85,"restricted":1.0}[item["risk_level"]])
        if selected and max(family_counts.values(), default=0) / len(selected) > 0.5:
            findings.append({"severity": "warning", "code": "source_family_concentration", "message": "Mehr als die Hälfte des Plans stammt aus einer einzigen Quellenfamilie."})
            mitigations.append("Mindestens eine unabhängige Quellenfamilie ergänzen.")
        if int(plan["max_external_actions"]) > 12:
            findings.append({"severity": "warning", "code": "large_action_budget", "message": "Außenaktionsbudget ist höher als der empfohlene Standardwert 12."})
        if not selected:
            blocked = True; findings.append({"severity": "blocker", "code": "no_safe_sources", "message": "Der lokale Planer konnte keine sichere kompatible Quelle auswählen."})
        exposure = round(exposure / max(1, len(selected)), 3)
        risk = "restricted" if blocked else "high" if watchlists or any(item["risk_level"] in {"high","restricted"} for item in selected) else "medium" if exposure >= 0.55 else "low"
        result = {"risk_level": risk, "blocked": blocked, "exposure_score": exposure, "findings": findings, "mitigations": _dedupe(mitigations), "active_persona_session_id": str((active or {}).get("session_id") or ""), "external_ai_calls": 0, "automatic_actions": 0}
        assessment_id = new_id("opsec149")
        self.db.execute("INSERT INTO source_opsec_assessments_149(assessment_id,plan_id,case_id,risk_level,blocked,exposure_score,findings_json,mitigations_json,active_persona_session_id,assessed_by,assessed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (assessment_id, plan_id, case_id, risk, int(blocked), exposure, dumps(findings), dumps(result["mitigations"]), result["active_persona_session_id"], _safe(actor,120), now_ts()))
        self.db.execute("UPDATE source_plans_149 SET opsec_assessment_json=?,risk_level=?,updated_at=? WHERE plan_id=?", (dumps(result), risk, now_ts(), plan_id))
        self._event(event_type="source_plan_opsec_assessed_149", actor=actor, case_id=case_id, plan_id=plan_id, payload={"risk_level": risk, "blocked": blocked, "exposure_score": exposure, "finding_codes": [x["code"] for x in findings]})
        return {"assessment_id": assessment_id, **result}

    # ---------- approval and execution ----------
    def approve_plan(self, *, case_id: str, plan_id: str, confirmation: str, actor: str) -> dict[str, Any]:
        if _safe(confirmation,100) != PLAN_CONFIRMATION:
            raise PermissionError(f"Freigabephrase erforderlich: {PLAN_CONFIRMATION}")
        plan = self.get_plan(case_id=case_id, plan_id=plan_id)
        if plan["status"] not in {"draft", "review_required"}:
            raise ValueError("Nur ein Entwurf kann freigegeben werden")
        assessment = self.assess_opsec(case_id=case_id, plan_id=plan_id, actor=actor)
        if assessment["blocked"]:
            raise PermissionError("OPSEC-Prüfung blockiert diesen Quellenplan")
        created = 0; stamp = now_ts()
        for item in plan["selected_connectors"][:int(plan["max_external_actions"])]:
            digest = hashlib.sha256(f"{plan_id}|{_norm(item['query'])}".encode("utf-8")).hexdigest()
            existing = self.db.one("SELECT job_id FROM source_jobs_149 WHERE case_id=? AND connector_id=? AND query_sha256=?", (case_id, item["connector_id"], digest))
            if existing:
                continue
            job_id = new_id("job149")
            self.db.execute("INSERT INTO source_jobs_149(job_id,plan_id,case_id,target_id,connector_id,source_key,source_family,query_text,anchor_types_json,query_sha256,priority,expected_value,risk_level,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'planned',?,?,?)", (job_id, plan_id, case_id, plan.get("target_id"), item["connector_id"], item["source_key"], item["source_family"], item["query"], dumps(item["anchor_types"]), digest, int(round(float(item["expected_value"]))), float(item["expected_value"]), item["risk_level"], _safe(actor,120), stamp, stamp))
            created += 1
        expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(self.clock()) + 8 * 3600))
        self.db.execute("UPDATE source_plans_149 SET status='approved',approved_by=?,approved_at=?,expires_at=?,updated_at=? WHERE plan_id=?", (_safe(actor,120), stamp, expires_at, stamp, plan_id))
        self._event(event_type="source_plan_approved_149", actor=actor, case_id=case_id, plan_id=plan_id, payload={"jobs_created": created, "manual_execution_required": True})
        return self.get_plan(case_id=case_id, plan_id=plan_id)

    def _job(self, case_id: str, job_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM source_jobs_149 WHERE case_id=? AND job_id=?", (case_id, job_id))
        if not row:
            raise KeyError("Quellenjob nicht gefunden oder falscher Fall")
        result = dict(row); result["anchor_types"] = loads(str(result.pop("anchor_types_json", "[]")))
        return result

    def execute_job(self, *, case_id: str, job_id: str, confirmation: str, actor: str, mode: str = "dry_run", local_redirect_origin: str = "http://127.0.0.1:8765") -> dict[str, Any]:
        if _safe(confirmation,100) != JOB_CONFIRMATION:
            raise PermissionError(f"Freigabephrase erforderlich: {JOB_CONFIRMATION}")
        job = self._job(case_id, job_id); plan = self.get_plan(case_id=case_id, plan_id=job["plan_id"])
        if plan["status"] != "approved":
            raise PermissionError("Quellenplan ist nicht freigegeben")
        if plan.get("expires_at") and str(plan["expires_at"]) <= now_ts():
            self.db.execute("UPDATE source_plans_149 SET status='expired',updated_at=? WHERE plan_id=?", (now_ts(), plan["plan_id"]))
            raise PermissionError("Quellenplan ist abgelaufen und muss neu geprüft werden")
        if job.get("status") not in {"planned", "retryable_failed"}:
            raise PermissionError("Quellenjob wurde bereits verarbeitet oder ist nicht erneut ausführbar")
        source = self.get_source(job["source_key"])
        if source["persona_required"]:
            active = self._active_persona(case_id)
            if not active:
                raise PermissionError("Quelle benötigt eine aktive freigegebene Research-Persona-Sitzung")
        if source["risk_level"] == "restricted" and mode != "dry_run":
            raise PermissionError("Restricted-Quellen bleiben in Build 149 auf manuelle oder Dry-Run-Nutzung begrenzt")
        connector = self.build148.get_connector(job["connector_id"])
        if connector["health_state"] in {"quarantined", "offline", "changed_contract", "terms_review_required", "authentication_required"}:
            raise PermissionError(f"Connector ist aktuell nicht ausführbar: {connector['health_state']}")
        validate_public_scope(job["query_text"], plan["purpose"])
        # Claim only after all fail-closed preconditions have passed. A rejected
        # contract or OPSEC gate must not strand the job in a running state.
        claimed = self.db.execute(
            "UPDATE source_jobs_149 SET status='running',run_attempts=run_attempts+1,updated_at=? WHERE job_id=? AND case_id=? AND status IN ('planned','retryable_failed')",
            (now_ts(), job_id, case_id),
        )
        if int(claimed.rowcount or 0) != 1:
            raise PermissionError("Quellenjob wurde bereits von einem anderen Ablauf übernommen")
        try:
            result = self.build148.execute_connector(case_id=case_id, target_id=str(job.get("target_id") or ""), connector_id=job["connector_id"], input_data={"query": job["query_text"], "max_results": 25}, purpose=plan["purpose"], actor=actor, confirmation=RUN_CONFIRMATION, mode=mode, local_redirect_origin=local_redirect_origin)
        except Exception:
            self.db.execute("UPDATE source_jobs_149 SET status='retryable_failed',completed_at='',updated_at=? WHERE job_id=? AND status='running'", (now_ts(), job_id))
            self._event(event_type="source_job_failed_149", actor=actor, case_id=case_id, plan_id=job["plan_id"], job_id=job_id, source_key=job["source_key"], payload={"mode": mode, "retryable": True})
            raise
        status = str(result.get("status") or "completed")
        mapped = "opened_manual_review" if status == "opened_manual_review" else "completed" if status in {"completed", "dry_run_completed", "reference_completed"} else status
        completed_at = now_ts() if mapped in {"completed", "opened_manual_review"} else ""
        self.db.execute("UPDATE source_jobs_149 SET status=?,build148_run_id=?,result_count=?,quarantine_count=?,completed_at=?,updated_at=? WHERE job_id=? AND status='running'", (mapped, str(result.get("run_id") or ""), int(result.get("result_count") or 0), int(result.get("quarantine_count") or 0), completed_at, now_ts(), job_id))
        self._event(event_type="source_job_executed_149", actor=actor, case_id=case_id, plan_id=job["plan_id"], job_id=job_id, source_key=job["source_key"], payload={"mode": mode, "status": mapped, "result_count": result.get("result_count",0), "candidate_only": True})
        return {"job_id": job_id, "source_key": job["source_key"], **result}

    # ---------- independence and deduplication ----------
    @staticmethod
    def _cluster_material(row: Mapping[str, Any]) -> str:
        title = re.sub(r"[^a-z0-9äöüß]+", " ", _norm(str(row.get("title") or "")))
        snippet = re.sub(r"[^a-z0-9äöüß]+", " ", _norm(str(row.get("snippet") or "")))[:800]
        # URLs are deliberately excluded so mirrors/copies can cluster.
        return " ".join((title, snippet)).strip()

    def cluster_case_results(self, *, case_id: str, confirmation: str, actor: str) -> dict[str, Any]:
        if _safe(confirmation,100) != CLUSTER_CONFIRMATION:
            raise PermissionError(f"Freigabephrase erforderlich: {CLUSTER_CONFIRMATION}")
        self._case(case_id)
        rows = self.db.all("SELECT q.*,COALESCE(p.source_family,'unknown') source_family FROM connector_quarantine_148 q LEFT JOIN source_portfolio_149 p ON p.connector_id=q.connector_id WHERE q.case_id=? ORDER BY q.created_at", (case_id,))
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            material = self._cluster_material(row)
            if not material:
                continue
            fingerprint = hashlib.sha256(material.encode("utf-8")).hexdigest()
            groups.setdefault(fingerprint, []).append(row)
        self.db.execute("DELETE FROM source_result_cluster_members_149 WHERE cluster_id IN (SELECT cluster_id FROM source_result_clusters_149 WHERE case_id=?)", (case_id,))
        self.db.execute("DELETE FROM source_result_clusters_149 WHERE case_id=?", (case_id,))
        stamp = now_ts(); clusters = 0; duplicate_members = 0
        for fingerprint, members in groups.items():
            if len(members) < 2:
                continue
            cluster_id = new_id("cluster149")
            hosts = {str(m.get("source_host") or "").casefold() for m in members if m.get("source_host")}
            families = {str(m.get("source_family") or "unknown") for m in members}
            assessment = "cross_family_duplicate" if len(families) > 1 else "same_family_duplicate"
            self.db.execute("INSERT INTO source_result_clusters_149(cluster_id,case_id,cluster_fingerprint,representative_title,member_count,independent_host_count,independent_family_count,assessment,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (cluster_id, case_id, fingerprint, _safe(members[0].get("title"),500), len(members), len(hosts), len(families), assessment, stamp, stamp))
            for member in members:
                self.db.execute("INSERT INTO source_result_cluster_members_149(cluster_id,quarantine_id,connector_id,source_family,source_host,content_fingerprint,created_at) VALUES(?,?,?,?,?,?,?)", (cluster_id, member["quarantine_id"], member["connector_id"], member.get("source_family") or "unknown", member.get("source_host") or "", member.get("content_fingerprint") or "", stamp))
            clusters += 1; duplicate_members += len(members)
        self._event(event_type="source_results_clustered_149", actor=actor, case_id=case_id, payload={"clusters": clusters, "duplicate_members": duplicate_members, "automatic_evidence_write": False})
        return {"case_id": case_id, "clusters": clusters, "duplicate_members": duplicate_members, "candidate_only": True, "automatic_evidence_write": False}

    # ---------- dashboard ----------
    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        sources = self.list_sources()
        family_counts: dict[str, int] = {}; access_counts: dict[str, int] = {}; health_counts: dict[str, int] = {}; native = 0
        for source in sources:
            family_counts[source["source_family"]] = family_counts.get(source["source_family"], 0) + 1
            access_counts[source["access_tier"]] = access_counts.get(source["access_tier"], 0) + 1
            health = str(source.get("health_state") or "unknown")
            health_counts[health] = health_counts.get(health, 0) + 1
            native += int(source["access_tier"] == "public_native")
        result: dict[str, Any] = {
            "build": self.BUILD, "total_sources": len(sources), "new_sources_149": len(NEW_SOURCES_149),
            "native_or_api_sources": native, "source_families": family_counts, "access_tiers": access_counts,
            "health": health_counts, "sources": sources, "external_ai_calls": 0, "automatic_external_actions": 0,
            "automatic_identity_claims": 0, "automatic_evidence_writes": 0, "automatic_account_creation": 0,
            "exact_email_default": "blocked", "watchlist_default": "objective_gated_candidate_only",
        }
        if case_id:
            result["plans"] = self.list_plans(case_id)
            result["jobs"] = self.db.all("SELECT * FROM source_jobs_149 WHERE case_id=? ORDER BY created_at DESC LIMIT 200", (case_id,))
            result["clusters"] = self.db.all("SELECT * FROM source_result_clusters_149 WHERE case_id=? ORDER BY member_count DESC,updated_at DESC LIMIT 100", (case_id,))
        return result
