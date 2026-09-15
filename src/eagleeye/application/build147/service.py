from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, quote, quote_plus, urlencode, urlsplit, urlunsplit

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

PLAN_CONFIRMATION = "RECHERCHEPLAN 147 FREIGEBEN"
JOB_APPROVAL = "RECHERCHEJOB 147 AUSFÜHREN"
SENSITIVE_PATTERNS = (
    "health", "religion", "political", "sexual_orientation", "minor", "child",
    "biometric", "face_embedding", "password", "secret", "access_token",
)


def _safe(value: Any, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _dedupe(values: Iterable[str], limit: int = 30) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _safe(value, 500)
        key = unicodedata.normalize("NFKC", text).casefold()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _canonical_url(value: str) -> str:
    parts = urlsplit(_safe(value, 4000))
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Profil- und Quellenadressen müssen öffentliche HTTPS-URLs ohne eingebettete Zugangsdaten sein")
    secret_keys = {"token", "access_token", "api_key", "apikey", "secret", "signature", "sig", "auth", "password"}
    tracking = {"fbclid", "gclid", "msclkid", "mc_cid", "mc_eid"}
    query: list[tuple[str, str]] = []
    for key, item in parse_qsl(parts.query, keep_blank_values=True):
        normalized = key.casefold()
        if normalized in secret_keys or normalized.endswith(("_token", "_secret")):
            raise ValueError("URL enthält möglicherweise Zugangsdaten oder signierte Parameter")
        if normalized.startswith("utm_") or normalized in tracking:
            continue
        query.append((key, item))
    return urlunsplit(("https", parts.netloc.casefold(), parts.path or "/", urlencode(query, doseq=True), ""))


@dataclass(frozen=True, slots=True)
class Source147:
    key: str
    label: str
    group: str
    category: str
    mode: str
    official_url: str
    search_template: str = ""
    provider_key: str = ""
    hosts: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ("name", "username")
    auth: str = "none"
    terms: str = "official_public_interface"
    risk: str = "low"
    persona: bool = False
    native: bool = False
    priority: int = 50
    metadata: Mapping[str, Any] | None = None


SOCIAL_SOURCES: tuple[Source147, ...] = (
    Source147("bluesky_profiles", "Bluesky Profile Search", "social", "social_profile", "native_public_api", "https://bsky.app/", "https://bsky.app/search?q={query}", "bluesky_actor_search_public_147", ("public.api.bsky.app", "bsky.app"), ("name", "username", "keyword"), priority=92, native=True, metadata={"public_api": True, "candidate_only": True}),
    Source147("mastodon_profiles", "Mastodon.social Search", "social", "federated_social", "native_public_api", "https://mastodon.social/", "https://mastodon.social/search?q={query}", "mastodon_social_search_public_147", ("mastodon.social",), ("name", "username", "hashtag"), priority=86, native=True, metadata={"instance_scope": "mastodon.social", "status_search_may_require_auth": True}),
    Source147("youtube", "YouTube", "social", "video_social", "guided_browser", "https://www.youtube.com/", "https://www.youtube.com/results?search_query={query}", hosts=("www.youtube.com", "youtube.com"), inputs=("name", "username", "keyword", "organisation"), auth="optional_api_key", risk="medium", persona=True, priority=84),
    Source147("reddit", "Reddit", "social", "forum_social", "guided_browser", "https://www.reddit.com/", "https://www.reddit.com/search/?q={query}", hosts=("www.reddit.com", "reddit.com"), inputs=("username", "name", "keyword"), auth="account_or_oauth_for_extended_access", risk="medium", persona=True, priority=82),
    Source147("x", "X", "social", "microblog", "guided_browser", "https://x.com/", "https://x.com/search?q={query}&src=typed_query", hosts=("x.com",), inputs=("username", "name", "keyword"), auth="account_or_paid_api", risk="high", persona=True, priority=80),
    Source147("linkedin", "LinkedIn", "social", "professional_network", "guided_browser", "https://www.linkedin.com/", "https://www.linkedin.com/search/results/people/?keywords={query}", hosts=("www.linkedin.com", "linkedin.com"), inputs=("name", "organisation", "location"), auth="account_required", risk="high", persona=True, priority=80),
    Source147("facebook", "Facebook", "social", "social_network", "guided_browser", "https://www.facebook.com/", "https://www.facebook.com/search/people/?q={query}", hosts=("www.facebook.com", "facebook.com"), inputs=("name", "username", "location"), auth="account_required", risk="high", persona=True, priority=78),
    Source147("instagram", "Instagram", "social", "image_social", "guided_browser_manual", "https://www.instagram.com/", "https://www.instagram.com/", hosts=("www.instagram.com", "instagram.com"), inputs=("username", "name"), auth="account_often_required", risk="high", persona=True, priority=78),
    Source147("threads", "Threads", "social", "microblog", "guided_browser_manual", "https://www.threads.com/", "https://www.threads.com/", hosts=("www.threads.com", "threads.com"), inputs=("username", "name", "keyword"), auth="account_often_required", risk="high", persona=True, priority=74),
    Source147("tiktok", "TikTok", "social", "video_social", "guided_browser", "https://www.tiktok.com/", "https://www.tiktok.com/search?q={query}", hosts=("www.tiktok.com", "tiktok.com"), inputs=("username", "name", "keyword"), auth="account_or_approved_research_api", terms="official_ui_or_approved_research_tools", risk="high", persona=True, priority=76),
    Source147("telegram", "Telegram public channels", "social", "messaging_public", "guided_browser_manual", "https://t.me/", "https://t.me/{query}", hosts=("t.me",), inputs=("username", "channel"), auth="public_channels_only", risk="high", persona=True, priority=66),
    Source147("pinterest", "Pinterest", "social", "image_social", "guided_browser", "https://www.pinterest.com/", "https://www.pinterest.com/search/pins/?q={query}", hosts=("www.pinterest.com", "pinterest.com"), inputs=("name", "username", "keyword"), auth="account_often_required", risk="medium", persona=True, priority=62),
    Source147("tumblr", "Tumblr", "social", "blog_social", "guided_browser", "https://www.tumblr.com/", "https://www.tumblr.com/search/{query}", hosts=("www.tumblr.com", "tumblr.com"), inputs=("username", "name", "keyword"), auth="optional_api_key", risk="medium", persona=True, priority=60),
    Source147("flickr", "Flickr", "social", "photo_social", "guided_browser", "https://www.flickr.com/", "https://www.flickr.com/search/?text={query}", hosts=("www.flickr.com", "flickr.com"), inputs=("name", "username", "keyword"), auth="optional_api_key", risk="medium", persona=True, priority=58),
    Source147("vimeo", "Vimeo", "social", "video_social", "guided_browser", "https://vimeo.com/", "https://vimeo.com/search?q={query}", hosts=("vimeo.com",), inputs=("name", "username", "keyword"), auth="optional_token", risk="medium", persona=True, priority=56),
    Source147("medium", "Medium", "social", "publishing_social", "guided_browser", "https://medium.com/", "https://medium.com/search?q={query}", hosts=("medium.com",), inputs=("name", "username", "keyword"), auth="optional_account", risk="medium", persona=True, priority=54),
    Source147("stackoverflow", "Stack Overflow", "social", "technical_community", "guided_browser", "https://stackoverflow.com/", "https://stackoverflow.com/search?q={query}", hosts=("stackoverflow.com",), inputs=("name", "username", "keyword"), auth="none", risk="low", priority=60),
    Source147("github", "GitHub public profiles", "social", "code_profile", "native_public_api", "https://github.com/", "https://github.com/search?q={query}&type=users", "github_public_profile_120", ("api.github.com", "github.com"), ("username",), native=True, priority=78),
    Source147("gitlab", "GitLab public profiles", "social", "code_profile", "native_public_api", "https://gitlab.com/", "https://gitlab.com/search?search={query}&nav_source=navbar", "gitlab_public_profile_120", ("gitlab.com",), ("username",), native=True, priority=70),
)

DATABASE_SOURCES: tuple[Source147, ...] = (
    Source147("gleif", "GLEIF LEI", "database", "company_registry", "native_public_api", "https://www.gleif.org/en/lei/search", provider_key="gleif_lei_public_135", hosts=("api.gleif.org", "www.gleif.org"), inputs=("organisation", "identifier"), native=True, priority=95),
    Source147("sec_edgar", "SEC EDGAR", "database", "company_filings", "native_public_api", "https://www.sec.gov/edgar/search/", provider_key="sec_edgar_public_135", hosts=("www.sec.gov", "data.sec.gov"), inputs=("organisation", "identifier"), native=True, priority=90),
    Source147("openalex", "OpenAlex", "database", "research_metadata", "native_public_api", "https://openalex.org/", provider_key="openalex_authors_public_128", hosts=("api.openalex.org",), inputs=("name", "organisation"), native=True, priority=88),
    Source147("crossref", "Crossref", "database", "research_metadata", "native_public_api", "https://search.crossref.org/", provider_key="crossref_works_public_128", hosts=("api.crossref.org",), inputs=("name", "organisation", "identifier"), native=True, priority=86),
    Source147("datacite", "DataCite", "database", "research_metadata", "native_public_api", "https://commons.datacite.org/", provider_key="datacite_public_135", hosts=("api.datacite.org",), inputs=("name", "organisation", "identifier"), native=True, priority=84),
    Source147("europe_pmc", "Europe PMC", "database", "research_metadata", "native_public_api", "https://europepmc.org/", provider_key="europe_pmc_public_128", hosts=("www.ebi.ac.uk",), inputs=("name", "organisation", "identifier"), native=True, priority=82),
    Source147("wikidata", "Wikidata", "database", "knowledge_base", "native_public_api", "https://www.wikidata.org/", provider_key="wikidata_entities_public_128", hosts=("www.wikidata.org",), inputs=("name", "alias", "organisation", "location"), native=True, priority=74),
    Source147("courtlistener", "CourtListener", "database", "case_law", "native_public_api", "https://www.courtlistener.com/", provider_key="courtlistener_public_135", hosts=("www.courtlistener.com",), inputs=("name", "organisation", "docket"), auth="recommended_token", native=True, risk="medium", priority=74),
    Source147("google_books", "Google Books", "database", "bibliographic", "native_public_api", "https://books.google.com/", provider_key="google_books_public_135", hosts=("www.googleapis.com",), inputs=("name", "work", "identifier"), native=True, priority=68),
    Source147("open_library", "Open Library", "database", "bibliographic", "native_public_api", "https://openlibrary.org/", provider_key="openlibrary_authors_public_128", hosts=("openlibrary.org",), inputs=("name", "alias"), native=True, priority=66),
    Source147("internet_archive", "Internet Archive", "database", "archive", "native_public_api", "https://archive.org/", provider_key="internet_archive_public_128", hosts=("archive.org",), inputs=("name", "organisation", "keyword"), native=True, priority=64),
    Source147("wayback", "Wayback Machine", "database", "archive", "native_public_api", "https://web.archive.org/", provider_key="wayback_cdx_public_120", hosts=("web.archive.org",), inputs=("url", "domain"), native=True, priority=64),
    Source147("rdap", "Public RDAP", "database", "domain_registry", "native_public_api", "https://rdap.org/", provider_key="rdap_public_120", hosts=("rdap.org",), inputs=("domain",), native=True, priority=62),
    Source147("handelsregister", "Deutsches Handelsregister", "database", "company_registry", "guided_browser_manual", "https://www.handelsregister.de/", "https://www.handelsregister.de/", hosts=("www.handelsregister.de",), inputs=("organisation", "person"), auth="official_browser_interface", risk="low", priority=88),
    Source147("unternehmensregister", "Unternehmensregister", "database", "company_registry", "guided_browser_manual", "https://www.unternehmensregister.de/", "https://www.unternehmensregister.de/", hosts=("www.unternehmensregister.de",), inputs=("organisation", "person"), auth="official_browser_interface", risk="low", priority=84),
    Source147("bundesanzeiger", "Bundesanzeiger", "database", "official_publications", "guided_browser_manual", "https://www.bundesanzeiger.de/", "https://www.bundesanzeiger.de/", hosts=("www.bundesanzeiger.de",), inputs=("organisation", "person"), auth="official_browser_interface", risk="low", priority=80),
    Source147("orcid", "ORCID", "database", "research_identity", "guided_browser", "https://orcid.org/", "https://orcid.org/orcid-search/search?searchQuery={query}", hosts=("orcid.org",), inputs=("name", "identifier", "organisation"), auth="public_search", risk="low", priority=82),
    Source147("companies_house", "Companies House", "database", "company_registry", "guided_browser", "https://find-and-update.company-information.service.gov.uk/", "https://find-and-update.company-information.service.gov.uk/search?q={query}", hosts=("find-and-update.company-information.service.gov.uk",), inputs=("organisation", "person"), auth="optional_api_key", risk="low", priority=80),
)


class Build147Service:
    """Durable research planning, social/database access matrix and OPSEC guard.

    Build 147 does not scrape authenticated pages, automate login, create accounts,
    bypass anti-bot controls, or send a case to an external AI. Native provider
    results remain candidate-only in the existing intake zone. Guided sources are
    opened in the already isolated case browser and require manual human review.
    """

    BUILD = "147.0"

    def __init__(self, db: Any, audit: Any, *, build146: Any, build143: Any, build140: Any, build136: Any, providers: Any, clock: Any | None = None) -> None:
        self.db = db
        self.audit = audit
        self.build146 = build146
        self.build143 = build143
        self.build140 = build140
        self.build136 = build136
        self.providers = providers
        self.clock = clock or time.time
        self.seed_sources()
        self.release_expired_leases()

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
        return row

    def _event(self, *, case_id: str, event_type: str, object_type: str, object_id: str, actor: str, payload: Mapping[str, Any] | None = None) -> None:
        previous = self.db.one("SELECT event_hash FROM build147_events WHERE case_id=? ORDER BY sequence DESC LIMIT 1", (case_id,))
        previous_hash = str((previous or {}).get("event_hash") or "GENESIS")
        safe_payload = dict(payload or {})
        for key in list(safe_payload):
            if any(marker in key.casefold() for marker in ("password", "secret", "token", "cookie", "credential")):
                safe_payload[key] = "[redacted]"
        event_id, stamp = new_id("evt147"), now_ts()
        canonical = dumps({"event_id": event_id, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "payload": safe_payload, "previous_hash": previous_hash, "actor": actor, "created_at": stamp})
        event_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.db.execute("INSERT INTO build147_events(event_id,case_id,event_type,object_type,object_id,payload_json,previous_hash,event_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (event_id, case_id, event_type, object_type, object_id, dumps(safe_payload), previous_hash, event_hash, _safe(actor, 120), stamp))
        self.audit.log(event_type, object_type, object_id, case_id, safe_payload)

    def seed_sources(self) -> None:
        stamp = now_ts()
        for item in SOCIAL_SOURCES + DATABASE_SOURCES:
            self.db.execute(
                """INSERT INTO research_sources_147(source_key,label,source_group,category,access_mode,official_url,search_url_template,provider_key,allowed_hosts_json,input_types_json,auth_requirement,terms_profile,risk_level,persona_recommended,native_execution,enabled,priority,metadata_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source_key) DO UPDATE SET label=excluded.label,source_group=excluded.source_group,category=excluded.category,access_mode=excluded.access_mode,official_url=excluded.official_url,search_url_template=excluded.search_url_template,provider_key=excluded.provider_key,allowed_hosts_json=excluded.allowed_hosts_json,input_types_json=excluded.input_types_json,auth_requirement=excluded.auth_requirement,terms_profile=excluded.terms_profile,risk_level=excluded.risk_level,persona_recommended=excluded.persona_recommended,native_execution=excluded.native_execution,priority=excluded.priority,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",
                (item.key, item.label, item.group, item.category, item.mode, item.official_url, item.search_template, item.provider_key, dumps(list(item.hosts)), dumps(list(item.inputs)), item.auth, item.terms, item.risk, int(item.persona), int(item.native), 1, item.priority, dumps(dict(item.metadata or {})), stamp, stamp),
            )

    def list_sources(self, group: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM research_sources_147 WHERE enabled=1"
        params: tuple[Any, ...] = ()
        if group in {"social", "database"}:
            sql += " AND source_group=?"; params = (group,)
        sql += " ORDER BY source_group,priority DESC,label"
        rows = self.db.all(sql, params)
        for row in rows:
            row["allowed_hosts"] = loads(row.pop("allowed_hosts_json", "[]"), [])
            row["input_types"] = loads(row.pop("input_types_json", "[]"), [])
            row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
            row["persona_recommended"] = bool(row.get("persona_recommended"))
            row["native_execution"] = bool(row.get("native_execution"))
        return rows

    def source(self, source_key: str) -> dict[str, Any]:
        matches = [row for row in self.list_sources() if row["source_key"] == source_key]
        if not matches:
            raise KeyError("Recherchequelle nicht gefunden")
        return matches[0]

    @staticmethod
    def _anchor_parts(*, full_name: str, username: str, email: str, organisation: str, location: str, aliases: Iterable[str]) -> dict[str, list[str]]:
        return {
            "name": _dedupe([full_name, *aliases], 8),
            "username": _dedupe([username], 3),
            "email": _dedupe([email], 2),
            "organisation": _dedupe([organisation], 3),
            "location": _dedupe([location], 3),
        }

    def _query_variants(self, anchors: Mapping[str, list[str]], objective: str, budget: int) -> list[dict[str, Any]]:
        variants: list[dict[str, Any]] = []
        names, usernames = anchors["name"], anchors["username"]
        orgs, locations, emails = anchors["organisation"], anchors["location"], anchors["email"]
        def add(text: str, types: list[str], exposure: int, rationale: str) -> None:
            if text and exposure <= budget:
                variants.append({"query": text, "anchor_types": types, "exposure": exposure, "rationale": rationale})
        for username in usernames:
            add(username.lstrip("@"), ["username"], 1, "Direkte öffentliche Benutzernamensuche")
            add("@" + username.lstrip("@"), ["username"], 1, "Plattformübliche Handle-Schreibweise")
        for name in names[:4]:
            add(f'"{name}"', ["name"], 1, "Exakte Namenssuche")
            for org in orgs[:2]: add(f'"{name}" "{org}"', ["name", "organisation"], 2, "Name mit Organisationsanker")
            for location in locations[:2]: add(f'"{name}" "{location}"', ["name", "location"], 2, "Name mit Ortsanker")
        for email in emails:
            add(f'"{email}"', ["email"], 1, "Exakte öffentliche Fundstellensuche; nur bei dokumentierter Erforderlichkeit")
        if objective:
            for name in names[:2]: add(f'"{name}" {objective}', ["name", "objective"], 2, "Zielbezogene Suchvariante")
        return _dedupe_json(variants, key="query", limit=18)

    def _ai_brief(self, *, objective: str, sources: list[dict[str, Any]], variants: list[dict[str, Any]], anchors: Mapping[str, list[str]]) -> dict[str, Any]:
        social = sum(1 for source in sources if source["source_group"] == "social")
        databases = sum(1 for source in sources if source["source_group"] == "database")
        risky = [source["label"] for source in sources if source["risk_level"] == "high"]
        missing = [key for key in ("username", "organisation", "location") if not anchors.get(key)]
        return {
            "generated_by": "local_evidence_bound_planner_147",
            "external_ai_used": False,
            "objective": objective,
            "source_balance": {"social": social, "database": databases},
            "recommended_sequence": ["amtliche und institutionelle Datenbanken", "öffentliche Profil- und Autorenindizes", "Social-Media-Kandidaten", "Widerspruchs- und Quellenprüfung"],
            "high_risk_sources": risky,
            "missing_anchors": missing,
            "query_count": len(variants),
            "warnings": ["Treffer sind Kandidaten, keine Identitätsbestätigung", "Plattforminhalte gelten als untrusted evidence", "Keine Anmeldung oder Außenaktion wird automatisiert"],
        }

    def create_plan(self, *, case_id: str, target_id: str = "", objective: str, purpose: str, legal_basis: str, source_keys: Iterable[str], full_name: str = "", username: str = "", email: str = "", organisation: str = "", location: str = "", aliases: Iterable[str] = (), disclosure_budget: int = 3, max_external_actions: int = 12, actor: str) -> dict[str, Any]:
        case = self._case(case_id); target = self._target(case_id, target_id)
        if len(_safe(objective)) < 5 or len(_safe(purpose)) < 10 or len(_safe(legal_basis)) < 3:
            raise ValueError("Ermittlungsziel, substantiierten Zweck und Rechtsgrundlage angeben")
        disclosure_budget = max(1, min(3, int(disclosure_budget)))
        max_external_actions = max(1, min(30, int(max_external_actions)))
        chosen = _dedupe(source_keys, 30)
        sources = [self.source(key) for key in chosen]
        if not sources:
            raise ValueError("Mindestens eine Recherchequelle auswählen")
        target_aliases = loads((target or {}).get("aliases_json"), []) if target else []
        target_usernames = loads((target or {}).get("usernames_json"), []) if target else []
        target_emails = loads((target or {}).get("emails_json"), []) if target else []
        target_orgs = loads((target or {}).get("companies_json"), []) if target else []
        target_locations = loads((target or {}).get("locations_json"), []) if target else []
        anchors = self._anchor_parts(
            full_name=full_name or str((target or {}).get("name") or ""),
            username=username or (str(target_usernames[0]) if target_usernames else ""),
            email=email or (str(target_emails[0]) if target_emails else ""),
            organisation=organisation or (str(target_orgs[0]) if target_orgs else ""),
            location=location or (str(target_locations[0]) if target_locations else ""),
            aliases=[*target_aliases, *aliases],
        )
        if not any(anchors.values()):
            raise ValueError("Mindestens einen Identitätsanker angeben")
        variants = self._query_variants(anchors, _safe(objective, 100), disclosure_budget)
        ai_brief = self._ai_brief(objective=_safe(objective, 500), sources=sources, variants=variants, anchors=anchors)
        plan_id, stamp = new_id("plan147"), now_ts()
        self.db.execute(
            """INSERT INTO research_plans_147(plan_id,case_id,target_id,objective,purpose,legal_basis,full_name,username,email,organisation,location,aliases_json,source_keys_json,query_variants_json,ai_brief_json,disclosure_budget,max_external_actions,risk_level,status,created_by,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'draft',?,?,?)""",
            (plan_id, case_id, target_id or None, _safe(objective, 1000), _safe(purpose, 2000), _safe(legal_basis, 500), anchors["name"][0] if anchors["name"] else "", anchors["username"][0] if anchors["username"] else "", anchors["email"][0] if anchors["email"] else "", anchors["organisation"][0] if anchors["organisation"] else "", anchors["location"][0] if anchors["location"] else "", dumps(anchors["name"][1:]), dumps(chosen), dumps(variants), dumps(ai_brief), disclosure_budget, max_external_actions, "medium", _safe(actor, 120), stamp, stamp),
        )
        assessment = self.assess_opsec(case_id=case_id, plan_id=plan_id, actor=actor)
        self._event(case_id=case_id, event_type="research_plan_created_147", object_type="research_plan_147", object_id=plan_id, actor=actor, payload={"sources": len(sources), "queries": len(variants), "risk_level": assessment["risk_level"], "external_ai_used": False})
        return self.get_plan(case_id=case_id, plan_id=plan_id)

    def get_plan(self, *, case_id: str, plan_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM research_plans_147 WHERE case_id=? AND plan_id=?", (case_id, plan_id))
        if not row:
            raise KeyError("Rechercheplan nicht gefunden oder falscher Fall")
        for key in ("aliases_json", "source_keys_json", "query_variants_json", "opsec_findings_json"):
            row[key[:-5]] = loads(row.pop(key, "[]"), [])
        row["ai_brief"] = loads(row.pop("ai_brief_json", "{}"), {})
        return row

    def active_persona_session(self, case_id: str) -> dict[str, Any] | None:
        return self.db.one("SELECT * FROM research_persona_sessions_143 WHERE case_id=? AND status='active' AND expires_epoch>? ORDER BY launched_at DESC LIMIT 1", (case_id, int(self.clock())))

    def assess_opsec(self, *, case_id: str, plan_id: str, actor: str) -> dict[str, Any]:
        plan = self.get_plan(case_id=case_id, plan_id=plan_id)
        sources = [self.source(key) for key in plan["source_keys"]]
        active_session = self.active_persona_session(case_id)
        findings: list[dict[str, Any]] = []
        mitigations: list[str] = ["Fallgebundenes Firefox-Profil verwenden", "Treffer nur candidate-only übernehmen", "Keine Konto- oder Login-Automation"]
        blocked = False
        exposure = max((int(v.get("exposure") or 0) for v in plan["query_variants"]), default=0) / 3.0
        if plan.get("email"):
            exposure = min(1.0, exposure + 0.2)
            findings.append({"severity": "warning", "code": "exact_email_disclosure", "message": "Exakte E-Mail-Suche erhöht die Wiedererkennbarkeit der Recherche."})
        high_risk = [source for source in sources if source["risk_level"] == "high"]
        account_required = [source for source in sources if "account_required" in source["auth_requirement"]]
        if high_risk and not active_session:
            findings.append({"severity": "warning", "code": "persona_session_missing", "message": "Für risikoreiche Social-Media-Recherche ist keine aktive freigegebene Research-Persona-Sitzung vorhanden."})
            mitigations.append("Vor Öffnung risikoreicher Plattformen eine Build-143-Persona-/Egress-Sitzung starten")
        if account_required and not active_session:
            blocked = True
            findings.append({"severity": "blocker", "code": "account_source_without_persona", "message": "Accountpflichtige Plattformen werden ohne aktive freigegebene Research-Persona-Sitzung nicht in Jobs übernommen."})
        joined = dumps(plan).casefold()
        if any(marker in joined for marker in SENSITIVE_PATTERNS):
            blocked = True
            findings.append({"severity": "blocker", "code": "prohibited_data_class", "message": "Plan enthält eine gesperrte sensible oder geheimnisbezogene Datenklasse."})
        if int(plan["max_external_actions"]) > 20:
            findings.append({"severity": "warning", "code": "large_action_budget", "message": "Das Außenaktionsbudget ist hoch und sollte weiter minimiert werden."})
        risk = "high" if blocked or high_risk else "medium" if exposure >= 0.5 or any(s["persona_recommended"] for s in sources) else "low"
        assessment_id = new_id("opsec147")
        self.db.execute("INSERT INTO opsec_assessments_147(assessment_id,plan_id,case_id,risk_level,blocked,findings_json,mitigations_json,active_persona_session_id,query_exposure_score,checked_by,checked_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (assessment_id, plan_id, case_id, risk, int(blocked), dumps(findings), dumps(_dedupe(mitigations)), str((active_session or {}).get("session_id") or ""), round(exposure, 3), _safe(actor, 120), now_ts()))
        self.db.execute("UPDATE research_plans_147 SET opsec_findings_json=?,risk_level=?,updated_at=? WHERE plan_id=?", (dumps(findings), risk, now_ts(), plan_id))
        return {"assessment_id": assessment_id, "risk_level": risk, "blocked": blocked, "findings": findings, "mitigations": _dedupe(mitigations), "active_persona_session_id": str((active_session or {}).get("session_id") or ""), "query_exposure_score": round(exposure, 3)}

    def approve_plan(self, *, case_id: str, plan_id: str, confirmation: str, actor: str) -> dict[str, Any]:
        if _safe(confirmation, 100) != PLAN_CONFIRMATION:
            raise PermissionError(f"Freigabephrase erforderlich: {PLAN_CONFIRMATION}")
        plan = self.get_plan(case_id=case_id, plan_id=plan_id)
        assessment = self.assess_opsec(case_id=case_id, plan_id=plan_id, actor=actor)
        if assessment["blocked"]:
            raise PermissionError("OPSEC-Prüfung blockiert diesen Rechercheplan")
        sources = [self.source(key) for key in plan["source_keys"]]
        variants = plan["query_variants"]
        created = 0; skipped = 0
        for source in sources:
            compatible = [
                variant for variant in variants
                if set(variant["anchor_types"]) & set(source["input_types"])
            ]
            # A generic keyword capability must never act as a wildcard for exact
            # e-mail or other unnecessary anchors. Fallback is limited to the
            # least-disclosing name/username variant.
            if not compatible:
                compatible = [
                    variant for variant in variants
                    if set(variant["anchor_types"]) <= {"name", "username"}
                ][:1]
            for variant in compatible[:3]:
                if created >= int(plan["max_external_actions"]):
                    break
                query = str(variant["query"]); digest = hashlib.sha256(query.casefold().encode("utf-8")).hexdigest()
                existing = self.db.one("SELECT job_id FROM research_jobs_147 WHERE case_id=? AND source_key=? AND query_sha256=?", (case_id, source["source_key"], digest))
                if existing:
                    skipped += 1; continue
                mode = "native_provider" if source["native_execution"] and source["provider_key"] else "guided_browser"
                self.db.execute("INSERT INTO research_jobs_147(job_id,plan_id,case_id,target_id,source_key,query_text,query_sha256,execution_mode,status,priority,max_attempts,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (new_id("job147"), plan_id, case_id, plan.get("target_id"), source["source_key"], query, digest, mode, "queued", int(source["priority"]), 3, _safe(actor, 120), now_ts(), now_ts()))
                created += 1
        self.db.execute("UPDATE research_plans_147 SET status='approved',approved_by=?,approved_at=?,updated_at=? WHERE plan_id=?", (_safe(actor, 120), now_ts(), now_ts(), plan_id))
        self._event(case_id=case_id, event_type="research_plan_approved_147", object_type="research_plan_147", object_id=plan_id, actor=actor, payload={"created_jobs": created, "deduplicated": skipped, "max_external_actions": plan["max_external_actions"]})
        return {"plan_id": plan_id, "status": "approved", "created_jobs": created, "deduplicated": skipped}

    def release_expired_leases(self) -> int:
        now = int(self.clock())
        row = self.db.one("SELECT COUNT(*) AS n FROM research_jobs_147 WHERE status='leased' AND lease_expires_epoch<=?", (now,)) or {}
        count = int(row.get("n") or 0)
        if count:
            self.db.execute("UPDATE research_jobs_147 SET status='queued',lease_owner='',lease_expires_epoch=0,updated_at=? WHERE status='leased' AND lease_expires_epoch<=?", (now_ts(), now))
        return count

    def lease_next_job(self, *, case_id: str, worker_id: str, lease_seconds: int = 120) -> dict[str, Any] | None:
        self._case(case_id); self.release_expired_leases(); now = int(self.clock())
        with self.db.transaction(immediate=True):
            row = self.db.one("SELECT * FROM research_jobs_147 WHERE case_id=? AND status='queued' AND not_before_epoch<=? ORDER BY priority DESC,created_at LIMIT 1", (case_id, now))
            if not row:
                return None
            expires = now + max(30, min(600, int(lease_seconds)))
            self.db.execute("UPDATE research_jobs_147 SET status='leased',lease_owner=?,lease_expires_epoch=?,updated_at=? WHERE job_id=? AND status='queued'", (_safe(worker_id, 120), expires, now_ts(), row["job_id"]))
        return self.get_job(case_id=case_id, job_id=row["job_id"])

    def get_job(self, *, case_id: str, job_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT j.*,s.label,s.access_mode,s.search_url_template,s.provider_key,s.auth_requirement,s.risk_level AS source_risk FROM research_jobs_147 j JOIN research_sources_147 s ON s.source_key=j.source_key WHERE j.case_id=? AND j.job_id=?", (case_id, job_id))
        if not row:
            raise KeyError("Recherchejob nicht gefunden oder falscher Fall")
        return row

    def execute_job(self, *, case_id: str, job_id: str, confirmation: str, actor: str, local_redirect_origin: str, mode: str = "replay") -> dict[str, Any]:
        if _safe(confirmation, 100) != JOB_APPROVAL:
            raise PermissionError(f"Freigabephrase erforderlich: {JOB_APPROVAL}")
        job = self.get_job(case_id=case_id, job_id=job_id)
        if job["status"] not in {"queued", "leased", "failed_retryable"}:
            raise ValueError("Job befindet sich nicht in einem ausführbaren Zustand")
        plan = self.get_plan(case_id=case_id, plan_id=job["plan_id"])
        assessment = self.assess_opsec(case_id=case_id, plan_id=job["plan_id"], actor=actor)
        source = self.source(job["source_key"])
        if assessment["blocked"]:
            self.db.execute("UPDATE research_jobs_147 SET status='blocked',blocked_reason=?,updated_at=? WHERE job_id=?", ("OPSEC plan blocked", now_ts(), job_id))
            raise PermissionError("OPSEC-Prüfung blockiert den Recherchejob")
        if source["risk_level"] == "high" and source["persona_recommended"] and not assessment["active_persona_session_id"]:
            raise PermissionError("Für diese risikoreiche Plattform ist vor Ausführung eine aktive Research-Persona-Sitzung erforderlich")
        self.db.execute("UPDATE research_jobs_147 SET status='running',attempt_count=attempt_count+1,lease_owner='',lease_expires_epoch=0,updated_at=? WHERE job_id=?", (now_ts(), job_id))
        try:
            if job["execution_mode"] == "native_provider":
                result = self.providers.execute(case_id=case_id, provider_key=job["provider_key"], query=job["query_text"], purpose=plan["purpose"], approved_by=actor, confirmation=self.providers.APPROVAL_PHRASE, mode=mode, target_id=str(job.get("target_id") or ""), max_results=25)
                self.db.execute("UPDATE research_jobs_147 SET status='completed',provider_run_id=?,result_count=?,updated_at=? WHERE job_id=?", (str(result.get("run_id") or ""), int(result.get("result_count") or 0), now_ts(), job_id))
                output = {"execution_mode": "native_provider", **result}
            else:
                template = str(job.get("search_url_template") or source["official_url"])
                if "{query}" in template:
                    destination = template.replace("{query}", quote_plus(job["query_text"]))
                else:
                    destination = template
                destination = _canonical_url(destination)
                task_id = str(job.get("browser_task_id") or "") or new_id("task147")
                if not job.get("browser_task_id"):
                    self.db.execute("INSERT INTO search_tasks(task_id,case_id,target_id,category,query,engine,url,status,created_at) VALUES(?,?,?,?,?,?,?,'planned',?)", (task_id, case_id, job.get("target_id"), "social_database_research_147", job["query_text"], job["label"], destination, now_ts()))
                launched = self.build136.launch_research_task(case_id=case_id, task_id=task_id, actor=actor, local_redirect_origin=local_redirect_origin)
                self.db.execute("UPDATE research_jobs_147 SET status='opened_manual_review',browser_task_id=?,browser_order_id=?,updated_at=? WHERE job_id=?", (task_id, str(launched.get("order_id") or ""), now_ts(), job_id))
                output = {"execution_mode": "guided_browser", "task_id": task_id, **launched}
            self._event(case_id=case_id, event_type="research_job_executed_147", object_type="research_job_147", object_id=job_id, actor=actor, payload={"source_key": job["source_key"], "execution_mode": output["execution_mode"], "automatic_login": False, "automatic_identity_claim": False})
            return output
        except Exception as exc:
            current = self.get_job(case_id=case_id, job_id=job_id)
            retryable = int(current["attempt_count"]) < int(current["max_attempts"])
            self.db.execute("UPDATE research_jobs_147 SET status=?,blocked_reason=?,not_before_epoch=?,updated_at=? WHERE job_id=?", ("failed_retryable" if retryable else "failed", _safe(exc, 500), int(self.clock()) + (30 * max(1, int(current["attempt_count"]))) if retryable else 0, now_ts(), job_id))
            self._event(case_id=case_id, event_type="research_job_failed_147", object_type="research_job_147", object_id=job_id, actor=actor, payload={"source_key": job["source_key"], "retryable": retryable, "error_type": type(exc).__name__})
            raise

    def complete_manual_job(self, *, case_id: str, job_id: str, result_count: int, actor: str) -> dict[str, Any]:
        job = self.get_job(case_id=case_id, job_id=job_id)
        if job["status"] not in {"opened_manual_review", "running"}:
            raise ValueError("Job ist nicht zur manuellen Abschlussdokumentation offen")
        count = max(0, min(500, int(result_count)))
        self.db.execute("UPDATE research_jobs_147 SET status='completed',result_count=?,updated_at=? WHERE job_id=?", (count, now_ts(), job_id))
        self._event(case_id=case_id, event_type="research_job_completed_147", object_type="research_job_147", object_id=job_id, actor=actor, payload={"result_count": count, "manual_review": True})
        return self.get_job(case_id=case_id, job_id=job_id)

    def add_social_candidate(self, *, case_id: str, source_key: str, profile_url: str, actor: str, target_id: str = "", plan_id: str = "", job_id: str = "", username: str = "", display_name: str = "", bio: str = "", location: str = "", profile_identifier: str = "", source_context: str = "", confidence: float = 0.2, metrics: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._case(case_id); self._target(case_id, target_id); source = self.source(source_key)
        if source["source_group"] != "social":
            raise ValueError("Kandidatenprofil muss aus einer Social-Media-Quelle stammen")
        canonical = _canonical_url(profile_url)
        if (urlsplit(canonical).hostname or "").casefold() not in {str(h).casefold() for h in source["allowed_hosts"]}:
            raise PermissionError("Profil-URL gehört nicht zur ausgewählten offiziellen Plattform")
        confidence = max(0.0, min(0.95, float(confidence)))
        stamp = now_ts(); candidate_id = new_id("social147")
        existing = self.db.one("SELECT candidate_id FROM social_profile_candidates_147 WHERE case_id=? AND source_key=? AND canonical_url=?", (case_id, source_key, canonical))
        if existing:
            candidate_id = existing["candidate_id"]
            self.db.execute("UPDATE social_profile_candidates_147 SET target_id=?,plan_id=?,job_id=?,username=?,display_name=?,bio=?,location=?,profile_identifier=?,metrics_json=?,source_context=?,confidence=?,updated_at=? WHERE candidate_id=?", (target_id or None, plan_id or None, job_id or None, _safe(username, 120), _safe(display_name, 300), _safe(bio, 4000), _safe(location, 300), _safe(profile_identifier, 300), dumps(dict(metrics or {})), _safe(source_context, 4000), confidence, stamp, candidate_id))
        else:
            self.db.execute("INSERT INTO social_profile_candidates_147(candidate_id,case_id,target_id,plan_id,job_id,source_key,profile_url,canonical_url,username,display_name,bio,location,profile_identifier,metrics_json,source_context,confidence,review_status,candidate_only,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'unreviewed',1,?,?,?)", (candidate_id, case_id, target_id or None, plan_id or None, job_id or None, source_key, canonical, canonical, _safe(username, 120), _safe(display_name, 300), _safe(bio, 4000), _safe(location, 300), _safe(profile_identifier, 300), dumps(dict(metrics or {})), _safe(source_context, 4000), confidence, _safe(actor, 120), stamp, stamp))
        self._event(case_id=case_id, event_type="social_candidate_recorded_147", object_type="social_profile_candidate_147", object_id=candidate_id, actor=actor, payload={"source_key": source_key, "candidate_only": True, "confidence": confidence})
        return self.db.one("SELECT * FROM social_profile_candidates_147 WHERE candidate_id=?", (candidate_id,)) or {}

    def review_candidate(self, *, case_id: str, candidate_id: str, status: str, reason: str, actor: str) -> dict[str, Any]:
        if status not in {"unreviewed", "plausible", "needs_more_evidence", "rejected", "supported_context_only"}:
            raise ValueError("Ungültiger Prüfstatus")
        if len(_safe(reason)) < 8:
            raise ValueError("Nachvollziehbare Prüfbegründung erforderlich")
        row = self.db.one("SELECT * FROM social_profile_candidates_147 WHERE case_id=? AND candidate_id=?", (case_id, candidate_id))
        if not row:
            raise KeyError("Social-Media-Kandidat nicht gefunden oder falscher Fall")
        self.db.execute("UPDATE social_profile_candidates_147 SET review_status=?,source_context=?,updated_at=? WHERE candidate_id=?", (status, _safe(reason, 4000), now_ts(), candidate_id))
        self._event(case_id=case_id, event_type="social_candidate_reviewed_147", object_type="social_profile_candidate_147", object_id=candidate_id, actor=actor, payload={"status": status, "candidate_only": True})
        return self.db.one("SELECT * FROM social_profile_candidates_147 WHERE candidate_id=?", (candidate_id,)) or {}

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        source_counts = {row["source_group"]: int(row["n"]) for row in self.db.all("SELECT source_group,COUNT(*) AS n FROM research_sources_147 WHERE enabled=1 GROUP BY source_group")}
        result: dict[str, Any] = {
            "build": self.BUILD,
            "sources": source_counts,
            "native_sources": int((self.db.one("SELECT COUNT(*) AS n FROM research_sources_147 WHERE enabled=1 AND native_execution=1") or {}).get("n") or 0),
            "guided_sources": int((self.db.one("SELECT COUNT(*) AS n FROM research_sources_147 WHERE enabled=1 AND native_execution=0") or {}).get("n") or 0),
            "external_ai_calls": 0,
            "automatic_logins": 0,
            "automatic_account_creation": 0,
            "automatic_identity_claims": 0,
        }
        if case_id:
            result.update({
                "plans": self.db.all("SELECT plan_id,objective,status,risk_level,created_by,created_at FROM research_plans_147 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (case_id,)),
                "jobs": self.db.all("SELECT j.job_id,j.plan_id,j.source_key,s.label,j.query_text,j.execution_mode,j.status,j.priority,j.attempt_count,j.result_count,j.blocked_reason,j.created_at FROM research_jobs_147 j JOIN research_sources_147 s ON s.source_key=j.source_key WHERE j.case_id=? ORDER BY j.created_at DESC LIMIT 100", (case_id,)),
                "candidates": self.db.all("SELECT c.*,s.label FROM social_profile_candidates_147 c JOIN research_sources_147 s ON s.source_key=c.source_key WHERE c.case_id=? ORDER BY c.created_at DESC LIMIT 100", (case_id,)),
                "active_persona_session": self.active_persona_session(case_id) or {},
            })
        return result


def _dedupe_json(values: Iterable[dict[str, Any]], *, key: str, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        marker = str(value.get(key) or "").casefold()
        if marker and marker not in seen:
            seen.add(marker); out.append(value)
        if len(out) >= limit:
            break
    return out
