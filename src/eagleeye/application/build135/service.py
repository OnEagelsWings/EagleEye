from __future__ import annotations

import hashlib
import html
import json
import re
import secrets
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts


HEALTH_STATUSES = {
    "operational", "degraded", "rate_limited", "authentication_required",
    "terms_review_required", "changed_contract", "quarantined", "offline",
}
REVIEW_STATUSES = {"unconfirmed", "supported", "contradictory"}
MARITAL_STATUSES = {"single", "married", "separated", "divorced", "widowed", "unknown"}
LIFE_STATUSES = {"alive", "deceased", "unknown"}


def _sha(value: Any) -> str:
    return hashlib.sha256(dumps(value).encode("utf-8")).hexdigest()


def _json_fields(value: Any) -> list[str]:
    if isinstance(value, dict):
        return sorted(str(key) for key in value.keys())
    if isinstance(value, list):
        first = next((item for item in value if isinstance(item, dict)), None)
        return sorted(str(key) for key in first.keys()) if first else ["[]"]
    return [type(value).__name__]


def _safe_text(value: Any, limit: int = 1000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


@dataclass(frozen=True, slots=True)
class Source135:
    key: str
    label: str
    category: str
    mode: str
    official_url: str
    hosts: tuple[str, ...]
    anchors: tuple[str, ...]
    data_classes: tuple[str, ...]
    auth: str = "none"
    terms: str = "official_public"
    health_url: str = ""
    expected_fields: tuple[str, ...] = ()
    provider_key: str = ""
    priority: int = 50
    notes: str = ""


SOURCES_135: tuple[Source135, ...] = (
    Source135("orcid", "ORCID Public Registry", "research_identity", "native_api", "https://orcid.org/orcid-search/search", ("orcid.org", "pub.orcid.org"), ("name", "birth_year", "organisation"), ("researcher_id", "employment", "works"), "oauth_read_public", "official_public_api", "https://pub.orcid.org/v3.0/search/?q=orcid&rows=1", ("num-found", "result"), priority=90, notes="Search token required; name matches remain candidate-only."),
    Source135("gleif_lei", "GLEIF LEI", "company_registry", "native_api", "https://www.gleif.org/en/lei/search", ("api.gleif.org", "www.gleif.org"), ("organisation", "identifier"), ("legal_entity", "address", "ownership"), health_url="https://api.gleif.org/api/v1/lei-records?page[size]=1", expected_fields=("data", "links", "meta"), provider_key="gleif_lei_public_135", priority=95),
    Source135("companies_house", "UK Companies House", "company_registry", "native_api", "https://find-and-update.company-information.service.gov.uk/", ("api.company-information.service.gov.uk", "find-and-update.company-information.service.gov.uk"), ("organisation", "name"), ("company", "officer", "filing"), "api_key", "official_public_api", "https://api.company-information.service.gov.uk/search/companies?q=EagleEye", ("items", "items_per_page", "total_results"), priority=90),
    Source135("sec_edgar", "SEC EDGAR", "company_filings", "native_api", "https://www.sec.gov/edgar/search/", ("www.sec.gov", "data.sec.gov"), ("organisation", "identifier"), ("company", "filing", "xbrl"), "none", "official_public_api_user_agent_required", "https://www.sec.gov/files/company_tickers.json", (), provider_key="sec_edgar_public_135", priority=90),
    Source135("google_books", "Google Books", "bibliographic", "native_api", "https://books.google.com/", ("www.googleapis.com", "books.google.com"), ("name", "identifier"), ("author", "book", "isbn"), "optional_api_key", "official_public_api", "https://www.googleapis.com/books/v1/volumes?q=EagleEye&maxResults=1", ("kind", "totalItems"), provider_key="google_books_public_135", priority=70),
    Source135("courtlistener", "CourtListener", "case_law", "native_api", "https://www.courtlistener.com/", ("www.courtlistener.com",), ("name", "organisation"), ("case_law", "docket", "judge", "party"), "recommended_token", "official_public_api", "https://www.courtlistener.com/api/rest/v3/overview/", (), provider_key="courtlistener_public_135", priority=65),
    Source135("eu_vies", "EU VIES VAT Validation", "tax_registry", "guided_browser", "https://ec.europa.eu/taxation_customs/vies/", ("ec.europa.eu",), ("vat_id", "organisation"), ("vat_validity", "company_name", "address"), "none", "terms_review_required", priority=80),
    Source135("openalex", "OpenAlex", "research_metadata", "native_api", "https://openalex.org/", ("api.openalex.org", "openalex.org"), ("name", "organisation", "identifier"), ("author", "works", "institution"), health_url="https://api.openalex.org/works?per-page=1&select=id", expected_fields=("meta", "results"), provider_key="openalex_authors_public_128", priority=85),
    Source135("crossref", "Crossref", "research_metadata", "native_api", "https://search.crossref.org/", ("api.crossref.org", "search.crossref.org"), ("name", "identifier", "organisation"), ("works", "doi", "publisher"), health_url="https://api.crossref.org/works?rows=0", expected_fields=("message", "message-type", "status"), provider_key="crossref_works_public_128", priority=80),
    Source135("wikidata", "Wikidata", "knowledge_base", "native_api", "https://www.wikidata.org/", ("www.wikidata.org",), ("name", "alias", "organisation", "location"), ("entity", "identifier", "relationships"), health_url="https://www.wikidata.org/w/api.php?action=query&meta=siteinfo&format=json", expected_fields=("batchcomplete", "query"), provider_key="wikidata_entities_public_128", priority=55),
    Source135("github", "GitHub Public Profiles", "code_identity", "native_api", "https://github.com/", ("api.github.com", "github.com"), ("username",), ("profile", "repositories", "organisation"), "optional_token", "official_public_api", "https://api.github.com/rate_limit", ("rate", "resources"), provider_key="github_public_profile_120", priority=60),
    Source135("gitlab", "GitLab Public Profiles", "code_identity", "native_api", "https://gitlab.com/", ("gitlab.com",), ("username",), ("profile", "projects"), health_url="https://gitlab.com/api/v4/version", provider_key="gitlab_public_profile_120", priority=55),
    Source135("datacite", "DataCite", "research_metadata", "native_api", "https://commons.datacite.org/", ("api.datacite.org", "commons.datacite.org"), ("name", "identifier", "organisation"), ("doi", "creator", "publisher"), health_url="https://api.datacite.org/dois?page[size]=1", expected_fields=("data", "links", "meta"), provider_key="datacite_public_135", priority=75),
    Source135("europe_pmc", "Europe PMC", "research_metadata", "native_api", "https://europepmc.org/", ("www.ebi.ac.uk", "europepmc.org"), ("name", "identifier", "organisation"), ("publication", "author", "affiliation"), health_url="https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=malaria&format=json&pageSize=1", expected_fields=("hitCount", "resultList"), provider_key="europe_pmc_public_128", priority=75),
    Source135("open_library", "Open Library Authors", "bibliographic", "native_api", "https://openlibrary.org/", ("openlibrary.org",), ("name", "alias"), ("author", "works"), health_url="https://openlibrary.org/search/authors.json?q=orwell&limit=1", expected_fields=("docs", "numFound"), provider_key="openlibrary_authors_public_128", priority=55),
    Source135("internet_archive", "Internet Archive", "archive", "native_api", "https://archive.org/", ("archive.org",), ("name", "organisation", "keyword"), ("archive_item", "creator", "date"), health_url="https://archive.org/advancedsearch.php?q=identifier%3Ametadata_test_item&fl%5B%5D=identifier&rows=1&output=json", expected_fields=("response",), provider_key="internet_archive_public_128", priority=55),
    Source135("wayback", "Wayback Machine CDX", "archive", "native_api", "https://web.archive.org/", ("web.archive.org",), ("domain", "url"), ("snapshot", "timestamp"), health_url="https://web.archive.org/cdx/search/cdx?url=example.org&output=json&limit=1", provider_key="wayback_cdx_public_120", priority=60),
    Source135("rdap", "Public RDAP", "domain_registry", "native_api", "https://rdap.org/", ("rdap.org",), ("domain",), ("registration", "nameserver", "status"), health_url="https://rdap.org/domain/example.org", expected_fields=("objectClassName", "ldhName"), provider_key="rdap_public_120", priority=60),
    Source135("handelsregister_de", "Deutsches Handelsregister", "company_registry", "guided_browser", "https://www.handelsregister.de/", ("www.handelsregister.de",), ("organisation", "location"), ("company", "register_document", "officer"), terms="official_guided_browser", priority=95),
    Source135("unternehmensregister_de", "Unternehmensregister", "company_registry", "guided_browser", "https://www.unternehmensregister.de/", ("www.unternehmensregister.de",), ("organisation", "location"), ("company", "filing", "accounts"), terms="official_guided_browser", priority=90),
    Source135("bundesanzeiger", "Bundesanzeiger", "official_publication", "guided_browser", "https://www.bundesanzeiger.de/", ("www.bundesanzeiger.de",), ("organisation", "name"), ("publication", "filing", "notice"), terms="official_guided_browser", priority=85),
    Source135("eu_transparency", "EU Transparency Register", "lobby_registry", "guided_browser", "https://transparency-register.europa.eu/", ("transparency-register.europa.eu",), ("organisation", "name"), ("organisation", "representative", "interest"), terms="official_guided_browser", priority=75),
    Source135("eu_business_registers", "EU e-Justice Business Registers", "company_registry", "guided_browser", "https://e-justice.europa.eu/topics/registers-business-insolvency-land/business-registers-search-company-eu/general-information-find-company_en", ("e-justice.europa.eu",), ("organisation", "location"), ("company", "register"), terms="official_guided_browser", priority=80),
    Source135("dpma_register", "DPMAregister", "ip_registry", "guided_browser", "https://register.dpma.de/DPMAregister/Uebersicht", ("register.dpma.de",), ("name", "organisation", "identifier"), ("trademark", "patent", "design", "owner"), terms="official_guided_browser", priority=70),
    Source135("dnb", "Deutsche Nationalbibliothek", "bibliographic", "guided_browser", "https://portal.dnb.de/", ("portal.dnb.de",), ("name", "identifier"), ("authority_record", "publication"), terms="official_guided_browser", priority=60),
    Source135("kvk", "Karlsruher Virtueller Katalog", "bibliographic", "guided_browser", "https://kvk.bibliothek.kit.edu/", ("kvk.bibliothek.kit.edu",), ("name", "identifier"), ("publication", "catalogue"), terms="official_guided_browser", priority=55),
)


class Build135Service:
    """Person Profile Pro, persistent Firefox tabs and provider trust for Build 135."""

    COMPANION_ACTIVE_SECONDS = 10.0
    ORDER_TTL_SECONDS = 180.0

    def __init__(
        self,
        db: Any,
        audit: Any,
        base_dir: str | Path,
        *,
        protection: Any,
        providers: Any,
        launcher: Callable[[list[str]], Any] | None = None,
        clock: Callable[[], float] | None = None,
        fetcher: Callable[[str, Mapping[str, str], float, int], tuple[int, bytes, str, int]] | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.protection = protection
        self.providers = providers
        self.launcher = launcher or protection.launcher
        self.clock = clock or time.time
        self.fetcher = fetcher or self._fetch
        self._bootstrap_tickets: dict[str, dict[str, Any]] = {}
        self.seed_sources()

    # ---------- profile ----------
    def _validate_target(self, case_id: str, target_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT target_id,case_id,name FROM targets WHERE target_id=?", (target_id,))
        if not row or row["case_id"] != case_id:
            raise ValueError("Zielperson gehört nicht zu diesem Fall")
        return row

    def create_source(self, *, case_id: str, target_id: str, source_title: str, source_url: str, actor: str, source_type: str = "investigator_statement", metadata: Mapping[str, Any] | None = None) -> str:
        self._validate_target(case_id, target_id)
        source_url = _safe_text(source_url, 2000)
        if source_url:
            parts = urlsplit(source_url)
            if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
                raise ValueError("Profilquellen müssen öffentliche HTTPS-URLs ohne Zugangsdaten sein")
        source_id = new_id("psrc135")
        self.db.execute(
            "INSERT INTO person_profile_sources_135(source_id,case_id,target_id,source_type,source_title,source_url,captured_at,created_by,metadata_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (source_id, case_id, target_id, _safe_text(source_type, 80), _safe_text(source_title, 300), source_url, now_ts(), _safe_text(actor, 120), dumps(dict(metadata or {}))),
        )
        return source_id

    def upsert_attribute(self, *, case_id: str, target_id: str, attribute_key: str, value: Any, known: bool, approximate: bool, review_status: str, confidence: float, source_id: str = "", investigator_note: str = "", effective_from: str = "", effective_to: str = "", actor: str = "local-analyst", reason: str = "profile_update") -> dict[str, Any]:
        self._validate_target(case_id, target_id)
        attribute_key = re.sub(r"[^a-z0-9_]+", "", attribute_key.casefold())[:80]
        if not attribute_key:
            raise ValueError("Attributschlüssel fehlt")
        if review_status not in REVIEW_STATUSES:
            raise ValueError("Ungültiger Reviewstatus")
        confidence = max(0.0, min(float(confidence), 1.0))
        if source_id:
            source = self.db.one("SELECT source_id FROM person_profile_sources_135 WHERE source_id=? AND case_id=? AND target_id=?", (source_id, case_id, target_id))
            if not source:
                raise ValueError("Profilquelle gehört nicht zur Zielperson")
        old = self.db.one("SELECT * FROM person_profile_attributes_135 WHERE target_id=? AND attribute_key=?", (target_id, attribute_key))
        value_json = dumps(value)
        ts = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        if old:
            attribute_id = old["attribute_id"]
            self.db.execute(
                """UPDATE person_profile_attributes_135 SET value_json=?,known=?,approximate=?,review_status=?,confidence=?,source_id=?,investigator_note=?,effective_from=?,effective_to=?,updated_at=? WHERE attribute_id=?""",
                (value_json, int(bool(known)), int(bool(approximate)), review_status, confidence, source_id or None, _safe_text(investigator_note, 3000), _safe_text(effective_from, 30), _safe_text(effective_to, 30), ts, attribute_id),
            )
            old_value = old.get("value_json", "")
            old_status = old.get("review_status", "")
        else:
            attribute_id = new_id("pattr135")
            self.db.execute(
                """INSERT INTO person_profile_attributes_135(attribute_id,case_id,target_id,attribute_key,value_json,known,approximate,review_status,confidence,source_id,investigator_note,effective_from,effective_to,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (attribute_id, case_id, target_id, attribute_key, value_json, int(bool(known)), int(bool(approximate)), review_status, confidence, source_id or None, _safe_text(investigator_note, 3000), _safe_text(effective_from, 30), _safe_text(effective_to, 30), _safe_text(actor, 120), ts, ts),
            )
            old_value, old_status = "", ""
        self.db.execute(
            "INSERT INTO person_profile_history_135(history_id,attribute_id,case_id,target_id,old_value_json,new_value_json,old_status,new_status,change_reason,changed_by,changed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (new_id("phist135"), attribute_id, case_id, target_id, old_value, value_json, old_status, review_status, _safe_text(reason, 300), _safe_text(actor, 120), ts),
        )
        self.audit.log("profile_update", "person_profile_attribute_135", attribute_id, case_id, {"target_id": target_id, "attribute_key": attribute_key, "review_status": review_status, "known": bool(known), "approximate": bool(approximate)})
        return self.db.one("SELECT * FROM person_profile_attributes_135 WHERE attribute_id=?", (attribute_id,)) or {}

    @staticmethod
    def _parse_partial_date(value: str) -> tuple[int | None, int | None, int | None]:
        text = str(value or "").strip()
        if not text:
            return None, None, None
        if not re.fullmatch(r"\d{4}(?:-\d{2})?(?:-\d{2})?", text):
            raise ValueError("Geburtsdatum muss YYYY, YYYY-MM oder YYYY-MM-DD entsprechen")
        parts = [int(item) for item in text.split("-")]
        year = parts[0]
        month = parts[1] if len(parts) > 1 else None
        day = parts[2] if len(parts) > 2 else None
        if not 1850 <= year <= date.today().year:
            raise ValueError("Geburtsjahr liegt außerhalb des zulässigen Bereichs")
        if month is not None and not 1 <= month <= 12:
            raise ValueError("Ungültiger Geburtsmonat")
        if day is not None:
            date(year, month or 1, day)
        return year, month, day

    @staticmethod
    def calculated_age(birth_date: str, today: date | None = None) -> int | None:
        year, month, day = Build135Service._parse_partial_date(birth_date)
        if year is None:
            return None
        today = today or date.today()
        if month is None:
            return max(0, today.year - year)
        birthday_passed = (today.month, today.day) >= (month, day or 1)
        return max(0, today.year - year - (0 if birthday_passed else 1))

    def save_profile_form(self, *, case_id: str, target_id: str, form: Mapping[str, Any], actor: str) -> dict[str, Any]:
        self._validate_target(case_id, target_id)
        review_status = str(form.get("profile_review_status") or "unconfirmed")
        confidence = float(form.get("profile_confidence") or 0.5)
        source_id = self.create_source(
            case_id=case_id, target_id=target_id,
            source_title=str(form.get("profile_source_title") or "Ermittlerangabe"),
            source_url=str(form.get("profile_source_url") or ""), actor=actor,
            metadata={"build": "135.0", "form": "person_profile_pro"},
        )
        occupation = {
            "title": _safe_text(form.get("occupation_title"), 300),
            "organisation": _safe_text(form.get("occupation_organisation"), 300),
            "from": _safe_text(form.get("occupation_from"), 30),
            "to": _safe_text(form.get("occupation_to"), 30),
            "current": bool(form.get("occupation_current")),
        }
        marital = str(form.get("marital_status") or "unknown").casefold()
        life = str(form.get("life_status") or "unknown").casefold()
        if marital not in MARITAL_STATUSES or life not in LIFE_STATUSES:
            raise ValueError("Ungültiger Familien- oder Lebensstatus")
        birth = str(form.get("birth_date") or "").strip()
        if birth:
            self._parse_partial_date(birth)
        age_min = int(form.get("age_estimate_min") or 0)
        age_max = int(form.get("age_estimate_max") or 0)
        if age_min < 0 or age_max < 0 or age_min > 130 or age_max > 130 or (age_min and age_max and age_min > age_max):
            raise ValueError("Ungültiger Altersschätzbereich")
        height = int(form.get("height_cm") or 0)
        if height and not 80 <= height <= 250:
            raise ValueError("Körpergröße muss zwischen 80 und 250 cm liegen")
        children_known = bool(form.get("children_known"))
        no_children_known = bool(form.get("no_children_known"))
        children_count = int(form.get("children_count") or 0)
        if children_count < 0 or children_count > 30:
            raise ValueError("Ungültige Kinderzahl")
        common_note = _safe_text(form.get("profile_note"), 3000)
        attrs = {
            "occupation": (occupation, bool(form.get("occupation_known")), bool(form.get("occupation_approximate"))),
            "marital_status": (marital, bool(form.get("marital_known")), bool(form.get("marital_approximate"))),
            "life_status": (life, bool(form.get("life_known")), bool(form.get("life_approximate"))),
            "birth_date": (birth, bool(form.get("birth_known")), bool(form.get("birth_approximate"))),
            "age_estimate": ({"min": age_min or None, "max": age_max or None}, bool(form.get("age_known")), True if (age_min or age_max) else bool(form.get("age_approximate"))),
            "height_cm": (height or None, bool(form.get("height_known")), bool(form.get("height_approximate"))),
            "children": ({"count": 0 if no_children_known else children_count, "none_known": no_children_known, "unknown": not children_known}, children_known, bool(form.get("children_approximate"))),
        }
        stored = []
        for key, (value, known, approximate) in attrs.items():
            stored.append(self.upsert_attribute(case_id=case_id, target_id=target_id, attribute_key=key, value=value, known=known, approximate=approximate, review_status=review_status, confidence=confidence, source_id=source_id, investigator_note=common_note, effective_from=occupation.get("from", "") if key == "occupation" else "", effective_to=occupation.get("to", "") if key == "occupation" else "", actor=actor, reason="person_profile_pro_form"))
        contradictions = self.analyse_contradictions(case_id=case_id, target_id=target_id, actor=actor)
        return {"target_id": target_id, "source_id": source_id, "attributes": len(stored), "contradictions": len(contradictions)}

    def profile(self, case_id: str, target_id: str) -> dict[str, Any]:
        target = self._validate_target(case_id, target_id)
        rows = self.db.all("SELECT * FROM person_profile_attributes_135 WHERE target_id=? ORDER BY attribute_key", (target_id,))
        attrs: dict[str, Any] = {}
        for row in rows:
            decoded = dict(row)
            decoded["value"] = loads(decoded.pop("value_json", ""), None)
            decoded["known"] = bool(decoded.get("known"))
            decoded["approximate"] = bool(decoded.get("approximate"))
            attrs[decoded["attribute_key"]] = decoded
        birth = attrs.get("birth_date", {}).get("value") or ""
        dynamic_age = self.calculated_age(birth) if birth else None
        sources = self.db.all("SELECT * FROM person_profile_sources_135 WHERE target_id=? ORDER BY captured_at DESC LIMIT 50", (target_id,))
        history = self.db.all("SELECT * FROM person_profile_history_135 WHERE target_id=? ORDER BY changed_at DESC LIMIT 100", (target_id,))
        contradictions = self.db.all("SELECT * FROM attribute_contradictions_135 WHERE target_id=? AND status='open' ORDER BY created_at DESC", (target_id,))
        return {"target": target, "attributes": attrs, "dynamic_age": dynamic_age, "calculated_age": dynamic_age, "sources": sources, "history": history, "contradictions": contradictions}

    def analyse_contradictions(self, *, case_id: str, target_id: str, actor: str = "local-analyst") -> list[dict[str, Any]]:
        prof = self.profile(case_id, target_id)
        attrs = prof["attributes"]
        findings: list[tuple[str, str, list[str], str, str]] = []
        birth_age = prof.get("dynamic_age")
        estimate = attrs.get("age_estimate", {}).get("value") or {}
        amin, amax = estimate.get("min"), estimate.get("max")
        if birth_age is not None and (amin is not None or amax is not None):
            low = amin if amin is not None else amax
            high = amax if amax is not None else amin
            if low is not None and high is not None and not int(low) <= int(birth_age) <= int(high):
                findings.append(("birth_age_mismatch", "high", ["birth_date", "age_estimate"], f"Das aus dem Geburtsdatum berechnete Alter ({birth_age}) liegt außerhalb der Schätzung {low}–{high}.", "Geburtsdatum und Altersschätzung anhand unabhängiger Quellen verifizieren."))
        life = attrs.get("life_status", {}).get("value")
        occupation = attrs.get("occupation", {}).get("value") or {}
        if life == "deceased" and occupation.get("current"):
            findings.append(("life_occupation_mismatch", "high", ["life_status", "occupation"], "Lebensstatus ist verstorben, die Beschäftigung ist zugleich als aktuell markiert.", "Beschäftigungszeitraum oder Lebensstatus korrigieren und Quelle prüfen."))
        children = attrs.get("children", {}).get("value") or {}
        if children.get("none_known") and int(children.get("count") or 0) > 0:
            findings.append(("children_count_mismatch", "medium", ["children"], "Keine Kinder bekannt und positive Kinderzahl wurden gleichzeitig gespeichert.", "Kinderangabe manuell prüfen."))
        for key, row in attrs.items():
            if row.get("review_status") == "contradictory":
                findings.append(("attribute_marked_contradictory", "medium", [key], f"Das Attribut {key} ist als widersprüchlich markiert.", "Gegenbeleg und unabhängige Zweitquelle erfassen."))
        self.db.execute("UPDATE attribute_contradictions_135 SET status='superseded' WHERE target_id=? AND status='open'", (target_id,))
        out = []
        for ctype, severity, keys, summary, action in findings:
            cid = new_id("contra135")
            self.db.execute("INSERT INTO attribute_contradictions_135(contradiction_id,case_id,target_id,contradiction_type,severity,attribute_keys_json,summary,suggested_action,status,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (cid, case_id, target_id, ctype, severity, dumps(keys), summary, action, "open", actor, now_ts()))
            out.append({"contradiction_id": cid, "type": ctype, "severity": severity, "summary": summary, "suggested_action": action})
        self.audit.log("analyse", "attribute_contradictions_135", target_id, case_id, {"count": len(out)})
        return out

    def analyze_contradictions(self, *, case_id: str, target_id: str, actor: str = "local-analyst") -> dict[str, Any]:
        findings = self.analyse_contradictions(case_id=case_id, target_id=target_id, actor=actor)
        return {"target_id": target_id, "contradictions": findings, "count": len(findings)}

    # ---------- source catalog and health ----------
    def seed_sources(self) -> dict[str, int]:
        ts = now_ts()
        for source in SOURCES_135:
            self.db.execute(
                """INSERT INTO provider_sources_135(source_key,label,source_category,execution_mode,provider_key,official_url,allowed_hosts_json,required_anchor_types_json,data_classes_json,auth_profile,terms_profile,expected_contract_json,health_url,enabled,candidate_only,priority,metadata_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source_key) DO UPDATE SET label=excluded.label,source_category=excluded.source_category,execution_mode=excluded.execution_mode,provider_key=excluded.provider_key,official_url=excluded.official_url,allowed_hosts_json=excluded.allowed_hosts_json,required_anchor_types_json=excluded.required_anchor_types_json,data_classes_json=excluded.data_classes_json,auth_profile=excluded.auth_profile,terms_profile=excluded.terms_profile,expected_contract_json=excluded.expected_contract_json,health_url=excluded.health_url,priority=excluded.priority,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",
                (source.key, source.label, source.category, source.mode, source.provider_key, source.official_url, dumps(source.hosts), dumps(source.anchors), dumps(source.data_classes), source.auth, source.terms, dumps({"top_level_fields": source.expected_fields}), source.health_url, 1, 1, source.priority, dumps({"notes": source.notes, "build": "135.0"}), ts, ts),
            )
        return {"sources": len(SOURCES_135), "native": sum(1 for item in SOURCES_135 if item.mode == "native_api"), "guided": sum(1 for item in SOURCES_135 if item.mode == "guided_browser")}

    def list_sources(self) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM provider_sources_135 WHERE enabled=1 ORDER BY priority DESC,label")
        latest = {row["source_key"]: row for row in self.db.all("SELECT h.* FROM provider_health_135 h JOIN (SELECT source_key,MAX(checked_at) checked_at FROM provider_health_135 GROUP BY source_key) x ON x.source_key=h.source_key AND x.checked_at=h.checked_at")}
        for row in rows:
            for key in ("allowed_hosts_json", "required_anchor_types_json", "data_classes_json", "expected_contract_json", "metadata_json"):
                row[key.removesuffix("_json")] = loads(row.pop(key, ""), [] if key.endswith("s_json") else {})
            row["health"] = latest.get(row["source_key"], {"status": self._static_health_status(row)})
        return rows

    @staticmethod
    def _static_health_status(source: Mapping[str, Any]) -> str:
        if source.get("terms_profile") == "terms_review_required":
            return "terms_review_required"
        if str(source.get("auth_profile") or "none") not in {"none", "optional_api_key", "optional_token", "recommended_token"}:
            return "authentication_required"
        if source.get("execution_mode") == "guided_browser":
            return "operational"
        return "degraded" if not source.get("health_url") else "offline"

    @staticmethod
    def _fetch(url: str, headers: Mapping[str, str], timeout: float, max_bytes: int) -> tuple[int, bytes, str, int]:
        start = time.monotonic()
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler())
        with opener.open(request, timeout=timeout) as response:
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise ValueError("Health-Antwort überschreitet Größenlimit")
            return int(response.status), body, str(response.geturl()), int((time.monotonic() - start) * 1000)

    def run_health(self, source_key: str, *, actor: str = "local-analyst") -> dict[str, Any]:
        source = self.db.one("SELECT * FROM provider_sources_135 WHERE source_key=? AND enabled=1", (source_key,))
        if not source:
            raise KeyError(source_key)
        static = self._static_health_status(source)
        status, http_status, latency, fields, detail, contract = static, None, 0, [], "", ""
        if static in {"authentication_required", "terms_review_required"} or source.get("execution_mode") == "guided_browser":
            detail = "Kein personenbezogener Live-Probe-Request; Status aus Auth-/Terms-Profil abgeleitet."
        elif not source.get("health_url"):
            status, detail = "degraded", "Kein datensparsamer Health-Endpunkt hinterlegt."
        else:
            try:
                headers = {"Accept": "application/json", "User-Agent": "EagleEye-PersonOSINT-Pro/135.0 compliance-contact=local"}
                code, body, final_url, latency = self.fetcher(str(source["health_url"]), headers, 12.0, 1_500_000)
                http_status = code
                final_host = (urlsplit(final_url).hostname or "").casefold()
                allowed = set(loads(source.get("allowed_hosts_json"), []))
                if final_host not in allowed:
                    status, detail = "quarantined", f"Unerwarteter Redirect-Host: {final_host}"
                elif code == 429:
                    status, detail = "rate_limited", "Provider meldet Rate Limit."
                elif code in {401, 403}:
                    status, detail = "authentication_required", f"HTTP {code}; Zugangsdaten oder Providerfreigabe erforderlich."
                elif not 200 <= code < 300:
                    status, detail = "degraded", f"HTTP {code}"
                else:
                    payload = json.loads(body.decode("utf-8"))
                    fields = _json_fields(payload)
                    contract = _sha(fields)
                    baseline = self.db.one("SELECT * FROM provider_contract_baselines_135 WHERE source_key=?", (source_key,))
                    expected = (loads(source.get("expected_contract_json"), {}) or {}).get("top_level_fields") or []
                    missing = [field for field in expected if field not in fields]
                    if baseline and baseline.get("contract_sha256") != contract:
                        status, detail = "changed_contract", "Beobachtete Top-Level-Felder weichen von der akzeptierten Baseline ab."
                        self.db.execute("INSERT INTO provider_contract_events_135(event_id,source_key,previous_sha256,observed_sha256,status,details_json,created_at) VALUES(?,?,?,?,?,?,?)", (new_id("pce135"), source_key, baseline.get("contract_sha256", ""), contract, status, dumps({"fields": fields, "missing_expected": missing}), now_ts()))
                    elif missing:
                        status, detail = "changed_contract", "Erwartete Antwortfelder fehlen: " + ", ".join(missing)
                    else:
                        status, detail = "operational", "Datensparsamer Health- und Contract-Probe erfolgreich."
            except urllib.error.HTTPError as exc:
                http_status = int(exc.code)
                if exc.code == 429:
                    status = "rate_limited"
                elif exc.code in {401, 403}:
                    status = "authentication_required"
                else:
                    status = "degraded"
                detail = f"HTTP {exc.code}"
            except Exception as exc:
                status, detail = "offline", f"{type(exc).__name__}: {_safe_text(exc, 400)}"
        if status not in HEALTH_STATUSES:
            status = "degraded"
        health_id = new_id("health135")
        self.db.execute("INSERT INTO provider_health_135(health_id,source_key,status,http_status,latency_ms,contract_sha256,response_fields_json,detail,checked_at) VALUES(?,?,?,?,?,?,?,?,?)", (health_id, source_key, status, http_status, latency, contract, dumps(fields), detail, now_ts()))
        self.audit.log("health_check", "provider_source_135", source_key, None, {"status": status, "http_status": http_status, "latency_ms": latency, "actor": actor})
        return {"health_id": health_id, "source_key": source_key, "status": status, "http_status": http_status, "latency_ms": latency, "fields": fields, "detail": detail, "contract_sha256": contract}

    def run_all_health(self, *, actor: str = "local-analyst", live_limit: int = 20) -> dict[str, Any]:
        results = []
        live_count = 0
        for source in self.db.all("SELECT source_key,execution_mode,health_url FROM provider_sources_135 WHERE enabled=1 ORDER BY priority DESC,label"):
            if source["execution_mode"] == "native_api" and source.get("health_url"):
                if live_count >= max(1, min(int(live_limit), 25)):
                    continue
                live_count += 1
            results.append(self.run_health(source["source_key"], actor=actor))
        counts: dict[str, int] = {}
        for item in results:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        return {"checked": len(results), "live_checked": live_count, "counts": counts, "results": results}

    def accept_contract_baseline(self, source_key: str, *, actor: str) -> dict[str, Any]:
        health = self.db.one("SELECT * FROM provider_health_135 WHERE source_key=? AND contract_sha256!='' ORDER BY checked_at DESC LIMIT 1", (source_key,))
        if not health:
            raise ValueError("Kein erfolgreicher Contract-Probe vorhanden")
        self.db.execute("INSERT INTO provider_contract_baselines_135(source_key,contract_sha256,response_fields_json,baseline_status,accepted_by,accepted_at) VALUES(?,?,?,?,?,?) ON CONFLICT(source_key) DO UPDATE SET contract_sha256=excluded.contract_sha256,response_fields_json=excluded.response_fields_json,baseline_status='accepted',accepted_by=excluded.accepted_by,accepted_at=excluded.accepted_at", (source_key, health["contract_sha256"], health["response_fields_json"], "accepted", actor, now_ts()))
        return self.db.one("SELECT * FROM provider_contract_baselines_135 WHERE source_key=?", (source_key,)) or {}

    def route_sources(self, *, case_id: str, target_id: str, objective: str, actor: str = "local-analyst") -> dict[str, Any]:
        target = self._validate_target(case_id, target_id)
        prof = self.profile(case_id, target_id)
        objective_clean = _safe_text(objective, 2000)
        objective_low = objective_clean.casefold()
        anchors: dict[str, Any] = {"name": target["name"]}
        legacy = self.db.one("SELECT * FROM targets WHERE target_id=?", (target_id,)) or {}
        for key, column in (("alias", "aliases_json"), ("username", "usernames_json"), ("email", "emails_json"), ("location", "locations_json"), ("organisation", "companies_json"), ("domain", "domains_json")):
            values = loads(legacy.get(column), [])
            if values:
                anchors[key] = values[:3]
        attrs = prof["attributes"]
        birth = attrs.get("birth_date", {}).get("value")
        if birth:
            anchors["birth_year"] = str(birth)[:4]
        occupation = attrs.get("occupation", {}).get("value") or {}
        if occupation.get("organisation"):
            anchors.setdefault("organisation", [occupation["organisation"]])
        requested_classes: set[str] = set()
        keyword_map = {
            "beruf": {"employment", "researcher_id", "officer", "author"}, "arbeit": {"employment", "officer"},
            "firma": {"company", "legal_entity", "filing"}, "unternehmen": {"company", "legal_entity", "filing"},
            "publikation": {"works", "publication", "doi", "book"}, "buch": {"book", "author", "isbn"},
            "gericht": {"case_law", "docket", "party"}, "prozess": {"case_law", "docket", "party"},
            "domain": {"registration", "snapshot"}, "webseite": {"snapshot", "archive_item"},
            "marke": {"trademark", "owner"}, "patent": {"patent", "owner"},
        }
        for word, classes in keyword_map.items():
            if word in objective_low:
                requested_classes.update(classes)
        recommendations, omitted = [], []
        for source in self.list_sources():
            required = set(source.get("required_anchor_types") or [])
            available = set(anchors)
            anchor_fit = sorted(required & available)
            class_fit = sorted(set(source.get("data_classes") or []) & requested_classes)
            if required and not anchor_fit:
                omitted.append({"source_key": source["source_key"], "reason": "Kein passender geprüfter Ankertyp"})
                continue
            health = (source.get("health") or {}).get("status", "offline")
            if health in {"quarantined", "changed_contract", "offline"}:
                omitted.append({"source_key": source["source_key"], "reason": f"Providerstatus {health}"})
                continue
            if requested_classes and not class_fit and source["priority"] < 80:
                continue
            disclosure = self._minimal_disclosure(source, anchors)
            score = int(source["priority"]) + 8 * len(class_fit) + 4 * len(anchor_fit) - 3 * max(0, len(disclosure) - 2)
            recommendations.append({
                "source_key": source["source_key"], "label": source["label"], "execution_mode": source["execution_mode"],
                "provider_key": source.get("provider_key", ""), "health_status": health, "score": score,
                "minimal_disclosure": disclosure, "matched_classes": class_fit, "candidate_only": True,
                "official_url": source["official_url"], "requires_manual_approval": True,
            })
        recommendations.sort(key=lambda item: (-item["score"], item["label"]))
        route_id = new_id("route135")
        self.db.execute("INSERT INTO ai_source_routes_135(route_id,case_id,target_id,objective,disclosed_anchors_json,recommendations_json,omitted_sources_json,review_status,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (route_id, case_id, target_id, objective_clean, dumps(anchors), dumps(recommendations[:12]), dumps(omitted), "candidate_only", actor, now_ts()))
        self.audit.log("route", "ai_source_route_135", route_id, case_id, {"target_id": target_id, "recommended": len(recommendations[:12]), "omitted": len(omitted), "external_actions": 0})
        return {"route_id": route_id, "target_id": target_id, "objective": objective_clean, "recommendations": recommendations[:12], "omitted": omitted, "external_actions": 0, "candidate_only": True}

    @staticmethod
    def _minimal_disclosure(source: Mapping[str, Any], anchors: Mapping[str, Any]) -> dict[str, Any]:
        required = list(source.get("required_anchor_types") or [])
        ordered = required + ["name", "birth_year", "organisation", "username", "identifier", "domain", "location"]
        result: dict[str, Any] = {}
        for key in ordered:
            if key in result or key not in anchors:
                continue
            result[key] = anchors[key]
            if len(result) >= 3:
                break
        return result

    def build_guided_url(self, source_key: str, query: str) -> str:
        source = self.db.one("SELECT * FROM provider_sources_135 WHERE source_key=?", (source_key,))
        if not source:
            raise KeyError(source_key)
        base = str(source["official_url"])
        q = _safe_text(query, 500)
        if source_key == "handelsregister_de":
            return base
        if source_key == "bundesanzeiger":
            return base
        if source_key == "dnb":
            return "https://portal.dnb.de/opac/simpleSearch?query=" + quote(q)
        if source_key == "kvk":
            return base
        if source_key == "eu_transparency":
            return base
        return base

    # ---------- persistent Firefox tab router ----------
    def _session(self, case_id: str) -> dict[str, Any] | None:
        return self.db.one("SELECT * FROM firefox_case_sessions_135 WHERE case_id=?", (case_id,))

    def _compartment(self, case_id: str) -> tuple[dict[str, Any], Path]:
        compartment, profile = self.protection._write_firefox_profile(case_id, persistent_session=True)
        digest = hashlib.sha256(str(profile.resolve()).encode("utf-8")).hexdigest()
        self.db.execute("INSERT INTO firefox_case_sessions_135(case_id,compartment_id,profile_path_sha256,updated_at) VALUES(?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET compartment_id=excluded.compartment_id,profile_path_sha256=excluded.profile_path_sha256,updated_at=excluded.updated_at", (case_id, compartment["compartment_id"], digest, now_ts()))
        return compartment, profile

    def companion_active(self, case_id: str) -> bool:
        row = self._session(case_id)
        return bool(row and row.get("companion_token_hash") and self.clock() - float(row.get("last_heartbeat_epoch") or 0) <= self.COMPANION_ACTIVE_SECONDS)

    def _new_order(self, *, case_id: str, task_ids: list[str], urls: list[str], engines: list[str], hosts: list[str], actor: str, mode: str) -> str:
        order_id = new_id("tabs135")
        self.db.execute("INSERT INTO firefox_tab_orders_135(order_id,case_id,task_ids_json,urls_json,engines_json,destination_hosts_json,status,dispatch_mode,created_by,created_at,expires_epoch) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (order_id, case_id, dumps(task_ids), dumps(urls), dumps(engines), dumps(hosts), "queued" if mode == "companion_queue" else "fallback_dispatched", mode, actor, now_ts(), self.clock() + self.ORDER_TTL_SECONDS))
        return order_id

    def _bootstrap_ticket(self, *, case_id: str, first_url: str, port: int) -> str:
        ticket = secrets.token_urlsafe(32)
        self._bootstrap_tickets[ticket] = {"case_id": case_id, "first_url": first_url, "port": int(port), "expires": self.clock() + 90.0, "registered": False}
        return ticket

    def bootstrap_view(self, ticket: str) -> dict[str, Any]:
        item = self._bootstrap_tickets.get(ticket)
        if not item or self.clock() > float(item["expires"]):
            raise KeyError("Companion-Bootstrap ist abgelaufen")
        return dict(item)

    def register_companion(self, ticket: str) -> dict[str, Any]:
        item = self.bootstrap_view(ticket)
        case_id = item["case_id"]
        token = secrets.token_urlsafe(40)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        self.db.execute("UPDATE firefox_case_sessions_135 SET companion_token_hash=?,companion_status='registered',last_heartbeat_epoch=?,last_port=?,registered_at=?,updated_at=? WHERE case_id=?", (token_hash, self.clock(), int(item["port"]), now_ts(), now_ts(), case_id))
        item["registered"] = True
        self._bootstrap_tickets.pop(ticket, None)
        return {"ok": True, "case_id": case_id, "token": token, "poll_path": "/api/firefox-companion/orders", "ack_path": "/api/firefox-companion/ack", "heartbeat_seconds": 3}

    def _verify_companion(self, case_id: str, token: str) -> dict[str, Any]:
        row = self._session(case_id)
        if not row or not row.get("companion_token_hash"):
            raise PermissionError("Companion ist nicht registriert")
        supplied = hashlib.sha256(str(token).encode("utf-8")).hexdigest()
        if not secrets.compare_digest(supplied, str(row["companion_token_hash"])):
            raise PermissionError("Ungültiges Companion-Token")
        return row

    def poll_orders(self, *, case_id: str, token: str, port: int = 0) -> dict[str, Any]:
        self._verify_companion(case_id, token)
        now = self.clock()
        self.db.execute("UPDATE firefox_case_sessions_135 SET companion_status='active',last_heartbeat_epoch=?,last_port=CASE WHEN ?>0 THEN ? ELSE last_port END,updated_at=? WHERE case_id=?", (now, int(port), int(port), now_ts(), case_id))
        rows = self.db.all("SELECT * FROM firefox_tab_orders_135 WHERE case_id=? AND status IN ('queued','delivered') AND expires_epoch>? ORDER BY created_at LIMIT 20", (case_id, now))
        orders = []
        for row in rows:
            if row["status"] == "delivered" and row.get("delivered_at"):
                try:
                    delivered_epoch = datetime.fromisoformat(str(row["delivered_at"]).replace("Z", "+00:00")).timestamp()
                except Exception:
                    delivered_epoch = now
                if now - delivered_epoch < 15:
                    continue
            self.db.execute("UPDATE firefox_tab_orders_135 SET status='delivered',delivered_at=? WHERE order_id=?", (now_ts(), row["order_id"]))
            orders.append({"order_id": row["order_id"], "urls": loads(row["urls_json"], []), "engines": loads(row["engines_json"], []), "case_id": case_id})
        self.db.execute("UPDATE firefox_tab_orders_135 SET status='expired',error_text='order expired before acknowledgement' WHERE case_id=? AND status IN ('queued','delivered') AND expires_epoch<=?", (case_id, now))
        return {"ok": True, "case_id": case_id, "orders": orders, "server_epoch": now}

    def acknowledge_order(self, *, case_id: str, token: str, order_id: str, status: str, error_text: str = "") -> dict[str, Any]:
        self._verify_companion(case_id, token)
        if status not in {"opened", "failed"}:
            raise ValueError("Ungültiger Acknowledgement-Status")
        row = self.db.one("SELECT order_id FROM firefox_tab_orders_135 WHERE order_id=? AND case_id=?", (order_id, case_id))
        if not row:
            raise KeyError(order_id)
        final = "acknowledged" if status == "opened" else "failed"
        self.db.execute("UPDATE firefox_tab_orders_135 SET status=?,acknowledged_at=?,error_text=? WHERE order_id=?", (final, now_ts(), _safe_text(error_text, 1000), order_id))
        return {"ok": True, "order_id": order_id, "status": final}

    @staticmethod
    def _sanitize_external_query_text(value: str) -> str:
        """Remove internal confidence/precision tokens from public search text.

        Scores remain in EagleEye metadata and must never be transmitted as search
        terms. The sanitizer also repairs legacy semicolon/comma serialisations such
        as ``Person X; 0,75, Ort`` while preserving years and ordinary numbers.
        """
        text = " ".join(str(value or "").replace("\u00a0", " ").split())
        # Explicit labels plus their numeric value.
        text = re.sub(r"(?i)\b(?:confidence|konfidenz|präzision|praezision|reliability|zuverlässigkeit|zuverlaessigkeit|score|prüfzahl|pruefzahl)\s*[:=]?\s*(?:0?[.,]\d{1,4}|1(?:[.,]0{1,4})?|\d{1,3}\s*%)\b", " ", text)
        # Standalone 0..1 decimal tokens separated as metadata fields.
        text = re.sub(r"(?:(?<=^)|(?<=[;,|]))\s*(?:0?[.,]\d{1,4}|1[.,]0{1,4})\s*(?=$|[;,|])", " ", text)
        text = re.sub(r"\s*[;|]\s*", " ", text)
        text = re.sub(r"\s*,\s*,+", ", ", text)
        text = re.sub(r"\s+,\s+", " ", text)
        text = re.sub(r"\s{2,}", " ", text).strip(" ,;|")
        return text

    @classmethod
    def _sanitize_external_url(cls, url: str) -> str:
        parts = urlsplit(str(url or ""))
        pairs=[]
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key.casefold() in {"q", "query", "text", "search", "keyword", "keywords"}:
                value = cls._sanitize_external_query_text(value)
            pairs.append((key, value))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs, doseq=True), parts.fragment))

    def _launch_urls(self, *, case_id: str, task_ids: list[str], urls: list[str], engines: list[str], hosts: list[str], actor: str, local_port: int) -> dict[str, Any]:
        if not urls or len(urls) > 12:
            raise ValueError("Ungültige Tabanzahl")
        compartment, _profile = self._compartment(case_id)
        firefox = self.protection._find_firefox()
        if firefox is None:
            raise PermissionError("Firefox wurde nicht gefunden")
        clean_urls = [self._sanitize_external_url(url) for url in urls]
        order_id = self._new_order(case_id=case_id, task_ids=task_ids, urls=clean_urls, engines=engines, hosts=hosts, actor=actor, mode="existing_firefox_tabs")
        # Deliberately omit -no-remote, -profile and -private-window. Firefox then
        # routes every -new-tab request into the already running user profile, so
        # existing logins/cookies remain available and no duplicate browser instance
        # is created.
        try:
            for url in clean_urls:
                self.launcher([str(firefox), "-new-tab", url])
        except Exception as exc:
            self.db.execute("UPDATE firefox_tab_orders_135 SET status='failed',error_text=? WHERE order_id=?", (_safe_text(str(exc), 1000), order_id))
            raise
        ts = now_ts()
        for task_id, host in zip(task_ids, hosts):
            self.db.execute("UPDATE search_tasks SET status='opened' WHERE task_id=? AND case_id=?", (task_id, case_id))
            self.db.execute("INSERT INTO protected_research_launches_124(launch_id,case_id,task_id,compartment_id,browser_mode,destination_host,destination_fingerprint,status,launched_at) VALUES(?,?,?,?,?,?,?,?,?)", (new_id("launch135"), case_id, task_id, compartment["compartment_id"], "existing_firefox_tabs", host, hashlib.sha256(host.encode("utf-8")).hexdigest(), "launched", ts))
        self.db.execute("UPDATE firefox_tab_orders_135 SET status='opened',acknowledged_at=? WHERE order_id=?", (ts, order_id))
        self.audit.log("launch", "persistent_firefox_tabs_135", order_id, case_id, {"count": len(clean_urls), "engines": engines, "dispatch_mode": "existing_firefox_tabs", "query_scores_transmitted": False})
        return {"order_id": order_id, "status": "launched", "count": len(clean_urls), "engines": engines, "dispatch_mode": "existing_firefox_tabs", "compartment_id": compartment["compartment_id"]}

    def launch_research_task(self, *, case_id: str, task_id: str, actor: str, local_redirect_origin: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM search_tasks WHERE task_id=? AND case_id=?", (task_id, case_id))
        if not row:
            raise KeyError("Suchaufgabe nicht gefunden oder falscher Fall")
        parts = urlsplit(str(row.get("url") or ""))
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise PermissionError("Geschützter Recherchebrowser erlaubt nur öffentliche HTTPS-Ziele")
        origin = self.protection._validated_loopback_origin(local_redirect_origin)
        clean_destination = self._sanitize_external_url(str(row["url"]))
        ticket = self.protection._issue_research_redirect(case_id=case_id, task_id=task_id, destination_url=clean_destination)
        local_url = origin + "/security/research-redirect?" + urlencode({"ticket": ticket})
        port = urlsplit(origin).port or 8765
        result = self._launch_urls(case_id=case_id, task_ids=[task_id], urls=[local_url], engines=[str(row.get("engine") or "Search")], hosts=[parts.hostname.casefold()], actor=actor, local_port=port)
        result["destination_host"] = parts.hostname.casefold()
        return result

    def launch_research_tasks_parallel(self, *, case_id: str, seed_task_id: str, actor: str, local_redirect_origin: str, preferred_engines: tuple[str, ...] = ("Google", "Bing", "DuckDuckGo", "Brave", "Startpage"), max_engines: int = 5) -> dict[str, Any]:
        seed = self.db.one("SELECT * FROM search_tasks WHERE task_id=? AND case_id=?", (seed_task_id, case_id))
        if not seed:
            raise KeyError("Suchaufgabe nicht gefunden oder falscher Fall")
        rows = self.db.all("SELECT * FROM search_tasks WHERE case_id=? AND target_id=? AND query=? ORDER BY created_at DESC", (case_id, str(seed.get("target_id") or ""), str(seed.get("query") or "")))
        by_engine: dict[str, dict[str, Any]] = {}
        for row in rows:
            engine = str(row.get("engine") or "")
            if engine and engine not in by_engine:
                by_engine[engine] = row
        selected = [by_engine[key] for key in preferred_engines if key in by_engine][:max(1, min(int(max_engines), 5))]
        if len(selected) < 2:
            raise PermissionError("Für diese Suchanfrage fehlen parallele Suchmaschinen-Aufgaben")
        origin = self.protection._validated_loopback_origin(local_redirect_origin)
        urls, hosts, task_ids, engines = [], [], [], []
        for row in selected:
            parts = urlsplit(str(row.get("url") or ""))
            if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
                raise PermissionError("Ungültige Suchmaschinen-URL")
            clean_destination = self._sanitize_external_url(str(row["url"]))
            ticket = self.protection._issue_research_redirect(case_id=case_id, task_id=str(row["task_id"]), destination_url=clean_destination)
            urls.append(origin + "/security/research-redirect?" + urlencode({"ticket": ticket}))
            hosts.append(parts.hostname.casefold())
            task_ids.append(str(row["task_id"]))
            engines.append(str(row.get("engine") or ""))
        return self._launch_urls(case_id=case_id, task_ids=task_ids, urls=urls, engines=engines, hosts=hosts, actor=actor, local_port=urlsplit(origin).port or 8765)

    def browser_status(self, case_id: str) -> dict[str, Any]:
        session = self._session(case_id) or {}
        orders = self.db.all("SELECT order_id,status,dispatch_mode,engines_json,created_at,acknowledged_at,error_text FROM firefox_tab_orders_135 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (case_id,)) if case_id else []
        for row in orders:
            row["engines"] = loads(row.pop("engines_json", "[]"), [])
        return {"case_id": case_id, "companion_active": self.companion_active(case_id) if case_id else False, "session": session, "orders": orders}

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        sources = self.list_sources()
        status_counts: dict[str, int] = {}
        for source in sources:
            status = (source.get("health") or {}).get("status", "offline")
            status_counts[status] = status_counts.get(status, 0) + 1
        profile_count = 0
        if case_id:
            row = self.db.one("SELECT COUNT(DISTINCT target_id) count FROM person_profile_attributes_135 WHERE case_id=?", (case_id,))
            profile_count = int((row or {}).get("count", 0))
        return {
            "build": "135.0", "source_count": len(sources),
            "native_source_count": sum(1 for item in sources if item["execution_mode"] == "native_api"),
            "guided_source_count": sum(1 for item in sources if item["execution_mode"] == "guided_browser"),
            "health_counts": status_counts, "sources": sources,
            "profile_count": profile_count, "browser": self.browser_status(case_id) if case_id else {},
            "recent_routes": self.db.all("SELECT route_id,target_id,objective,review_status,created_at FROM ai_source_routes_135 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,)) if case_id else [],
            "recent_contradictions": self.db.all("SELECT contradiction_id,target_id,contradiction_type,severity,summary,status,created_at FROM attribute_contradictions_135 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (case_id,)) if case_id else [],
        }
