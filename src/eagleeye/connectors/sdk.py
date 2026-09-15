from __future__ import annotations

import hashlib
import html as htmlmod
import json
import re
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Mapping, Sequence
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit

PARSER_POLICY_VERSION = "phase15.connector-parser.v1"
_MAX_BODY = 10_000_000
_MAX_TEXT = 2_000_000
_MAX_RECORDS = 5000
_MAX_LINKS = 2000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def canonical_url(url: str) -> str:
    p = urlsplit(str(url).strip())
    if p.scheme.lower() not in {"http", "https"} or not p.hostname:
        raise ValueError("absolute http/https URL required")
    if p.username is not None or p.password is not None:
        raise ValueError("userinfo in URL forbidden")
    host = p.hostname.lower().rstrip(".")
    port = p.port
    if port in {80, 443}:
        port = None
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit((p.scheme.lower(), netloc, p.path or "/", p.query, ""))


def detect_media_type(headers: Mapping[str, str] | None, body: bytes) -> str:
    raw = str((headers or {}).get("content-type", "")).split(";", 1)[0].strip().lower()
    if raw in {"text/html", "application/xhtml+xml", "application/json", "application/xml", "text/xml", "text/plain"}:
        return raw
    sample = bytes(body[:512]).lstrip()
    if sample[:1] in {b"{", b"["}:
        return "application/json"
    low = sample.lower()
    if low.startswith(b"<!doctype html") or b"<html" in low[:200]:
        return "text/html"
    if sample.startswith(b"<?xml") or (sample.startswith(b"<") and sample.endswith(b">") and b"\x00" not in sample):
        return "application/xml"
    try:
        sample.decode("utf-8")
        return "text/plain"
    except UnicodeDecodeError:
        return raw or "application/octet-stream"


@dataclass(frozen=True)
class ParseResult:
    parser_version: str
    media_type: str
    source_url: str
    canonical_url: str
    title: str
    text: str
    links: tuple[str, ...]
    records: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "parser_version": self.parser_version,
            "media_type": self.media_type,
            "source_url": self.source_url,
            "canonical_url": self.canonical_url,
            "title": self.title,
            "text": self.text,
            "links": list(self.links),
            "records": list(self.records),
            "warnings": list(self.warnings),
        }


class _HTMLDocument(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: list[str] = []
        self.text: list[str] = []
        self.links: list[str] = []
        self.canonical: str = ""
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower(); a = {str(k).lower(): (v or "") for k, v in attrs}
        if t in {"script", "style", "noscript", "template"}: self._skip += 1
        if t == "title": self._in_title = True
        if t == "a" and a.get("href") and len(self.links) < _MAX_LINKS: self.links.append(a["href"])
        if t == "link" and "canonical" in a.get("rel", "").lower().split() and a.get("href"): self.canonical = a["href"]

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "title": self._in_title = False
        if t in {"script", "style", "noscript", "template"} and self._skip: self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip: return
        value = " ".join(data.split())
        if not value: return
        if self._in_title: self.title.append(value)
        if sum(len(x) for x in self.text) < _MAX_TEXT: self.text.append(value)


OFFICIAL_CONNECTORS: dict[str, dict[str, Any]] = {
    "gleif_lei_api_v1": {
        "display_name": "GLEIF LEI API",
        "provider": "GLEIF",
        "source_class": "corporate_registry",
        "jurisdiction": "Global",
        "base_host": "api.gleif.org",
        "auth_type": "none",
        "parser_version": "gleif-json-v1",
        "terms_ref": "https://www.gleif.org/en/lei-data/gleif-api",
        "official_ref": "GLEIF API production service; Golden Copy-backed LEI data",
        "requests_per_minute": 20,
        "live_enabled_by_default": False,
    },
    "sec_edgar_submissions_v1": {
        "display_name": "SEC EDGAR Submissions API",
        "provider": "U.S. SEC",
        "source_class": "corporate_filings",
        "jurisdiction": "US",
        "base_host": "data.sec.gov",
        "auth_type": "none",
        "parser_version": "sec-submissions-json-v1",
        "terms_ref": "https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data",
        "official_ref": "SEC data APIs; declared operator User-Agent required for automated access",
        "requests_per_minute": 30,
        "requires_declared_user_agent": True,
        "live_enabled_by_default": False,
    },
    "companies_house_company_v1": {
        "display_name": "UK Companies House Company API",
        "provider": "Companies House",
        "source_class": "corporate_registry",
        "jurisdiction": "UK",
        "base_host": "api.company-information.service.gov.uk",
        "auth_type": "api_key",
        "parser_version": "companies-house-json-v1",
        "terms_ref": "https://developer.company-information.service.gov.uk/get-started",
        "official_ref": "Companies House REST API; API authentication required",
        "requests_per_minute": 20,
        "live_enabled_by_default": False,
    },
    "usaspending_award_v1": {
        "display_name": "USAspending Award API",
        "provider": "U.S. Treasury / USAspending.gov",
        "source_class": "public_spending_award",
        "jurisdiction": "US",
        "base_host": "api.usaspending.gov",
        "auth_type": "none",
        "parser_version": "usaspending-award-json-v1",
        "terms_ref": "https://api.usaspending.gov/docs/endpoints",
        "official_ref": "USAspending API v2 specific-award GET endpoint; public federal award and spending data",
        "requests_per_minute": 20,
        "live_enabled_by_default": False,
    },
    "ted_notice_xml_v1": {
        "display_name": "TED Published Notice XML",
        "provider": "Publications Office of the European Union / TED",
        "source_class": "public_procurement_notice",
        "jurisdiction": "EU/EEA",
        "base_host": "ted.europa.eu",
        "auth_type": "none",
        "parser_version": "ted-notice-xml-v1",
        "terms_ref": "https://docs.ted.europa.eu/ODS/latest/reuse/download-direct.html",
        "official_ref": "TED direct links for already-published notices; exact publication number; public XML download",
        "requests_per_minute": 12,
        "live_enabled_by_default": False,
    },
    "federal_register_document_v1": {
        "display_name": "Federal Register Document API",
        "provider": "Office of the Federal Register / FederalRegister.gov",
        "source_class": "government_legal_document",
        "jurisdiction": "US",
        "base_host": "www.federalregister.gov",
        "auth_type": "none",
        "parser_version": "federal-register-json-v1",
        "terms_ref": "https://www.federalregister.gov/developers/documentation/api/v1",
        "official_ref": "Federal Register API exact-document JSON lookup",
        "requests_per_minute": 12,
        "live_enabled_by_default": False,
    },
    "internet_archive_metadata_v1": {
        "display_name": "Internet Archive Item Metadata",
        "provider": "Internet Archive",
        "source_class": "public_archive_metadata",
        "jurisdiction": "Global",
        "base_host": "archive.org",
        "auth_type": "none",
        "parser_version": "internet-archive-metadata-json-v1",
        "terms_ref": "https://archive.org/developers/metadata-schema/",
        "official_ref": "Internet Archive metadata endpoint for exact public item identifiers",
        "requests_per_minute": 12,
        "live_enabled_by_default": False,
        "metadata_only": True,
    },
    "ofac_sdn_xml_v1": {
        "display_name": "OFAC SDN Consolidated Reference",
        "provider": "U.S. Treasury / OFAC",
        "source_class": "sanctions_reference",
        "jurisdiction": "US",
        "base_host": "sanctionslist.ofac.treas.gov",
        "auth_type": "none",
        "parser_version": "ofac-sanctions-xml-v1",
        "terms_ref": "https://ofac.treasury.gov/sanctions-list-service",
        "official_ref": "OFAC sanctions list service; Build 368 plan-only pending durable redirect provenance qualification",
        "requests_per_minute": 6,
        "live_enabled_by_default": False,
        "plan_only_reason": "signed_redirect_provenance_not_qualified",
    },
    "unsc_consolidated_xml_v1": {
        "display_name": "UN Security Council Consolidated Sanctions Reference",
        "provider": "United Nations Security Council",
        "source_class": "sanctions_reference",
        "jurisdiction": "UN/Global",
        "base_host": "main.un.org",
        "auth_type": "none",
        "parser_version": "unsc-sanctions-xml-v1",
        "terms_ref": "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list",
        "official_ref": "UNSC consolidated sanctions list; Build 368 plan-only pending stable export provenance qualification",
        "requests_per_minute": 6,
        "live_enabled_by_default": False,
        "plan_only_reason": "signed_or_transient_export_provenance_not_qualified",
    },
    "nara_catalog_v1": {
        "display_name": "National Archives Catalog API",
        "provider": "U.S. National Archives and Records Administration",
        "source_class": "government_archive_catalog",
        "jurisdiction": "US",
        "base_host": "catalog.archives.gov",
        "auth_type": "api_key",
        "parser_version": "generic-json-v1",
        "terms_ref": "https://www.archives.gov/research/catalog/help/api",
        "official_ref": "NARA Catalog API; API key required; API terms prohibit caching/storing returned content",
        "requests_per_minute": 6,
        "live_enabled_by_default": False,
        "plan_only_reason": "api_key_and_no_persistent_cache_terms",
    },
    "govinfo_package_v1": {
        "display_name": "GovInfo Package Summary API",
        "provider": "U.S. Government Publishing Office",
        "source_class": "government_legal_document",
        "jurisdiction": "US",
        "base_host": "api.govinfo.gov",
        "auth_type": "api_key",
        "parser_version": "generic-json-v1",
        "terms_ref": "https://www.govinfo.gov/developers",
        "official_ref": "GovInfo API package summary; api.data.gov key required",
        "requests_per_minute": 12,
        "live_enabled_by_default": False,
        "plan_only_reason": "api_key_execution_not_introduced_in_build368",
    },
    "ted_search_v3": {
        "display_name": "TED Search API v3",
        "provider": "Publications Office of the European Union / TED",
        "source_class": "public_procurement_search",
        "jurisdiction": "EU/EEA",
        "base_host": "ted.europa.eu",
        "auth_type": "none",
        "parser_version": "generic-json-v1",
        "terms_ref": "https://docs.ted.europa.eu/api/latest/search.html",
        "official_ref": "TED Search API POST /v3/notices/search; anonymous access for published notices",
        "requests_per_minute": 12,
        "request_method": "POST",
        "live_enabled_by_default": False,
    },
}


class ConnectorParserSDK:
    def __init__(self, db: Any, *, build349: Any, actor: str = "local-analyst") -> None:
        self.db = db; self.build349 = build349; self.actor = actor
        self.bootstrap_official_manifests()

    def bootstrap_official_manifests(self) -> None:
        now = _now()
        for key, spec in OFFICIAL_CONNECTORS.items():
            body = {
                "connector_key": key, "display_name": spec["display_name"], "provider": spec["provider"],
                "source_class": spec["source_class"], "jurisdiction": spec["jurisdiction"], "base_host": spec["base_host"],
                "auth_type": spec["auth_type"], "parser_version": spec["parser_version"], "terms_ref": spec["terms_ref"],
                "official_ref": spec["official_ref"], "status": "available_plan" if spec["auth_type"] == "none" else "auth_required",
                "config_json": _canon({k: v for k, v in spec.items() if k not in {"display_name","provider","source_class","jurisdiction","base_host","auth_type","parser_version","terms_ref","official_ref"}}),
                "created_at": now, "updated_at": now,
            }
            self.db.execute("INSERT OR IGNORE INTO phase15_connector_manifests(connector_key,display_name,provider,source_class,jurisdiction,base_host,auth_type,parser_version,terms_ref,official_ref,status,config_json,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*body.values(), _sha(body)))

    def manifests(self) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM phase15_connector_manifests ORDER BY connector_key")

    def source_plan(self, connector_key: str, identifier: str) -> dict[str, Any]:
        if connector_key not in OFFICIAL_CONNECTORS: raise KeyError(connector_key)
        spec = OFFICIAL_CONNECTORS[connector_key]; ident = str(identifier).strip()
        if connector_key == "gleif_lei_api_v1":
            if not re.fullmatch(r"[A-Z0-9]{20}", ident.upper()): raise ValueError("GLEIF source plan requires a 20-character LEI")
            url = f"https://api.gleif.org/api/v1/lei-records/{quote(ident.upper(), safe='')}"
        elif connector_key == "sec_edgar_submissions_v1":
            if not re.fullmatch(r"\d{1,10}", ident): raise ValueError("SEC source plan requires numeric CIK")
            url = f"https://data.sec.gov/submissions/CIK{int(ident):010d}.json"
        elif connector_key == "companies_house_company_v1":
            if not re.fullmatch(r"[A-Za-z0-9-]{1,16}", ident): raise ValueError("invalid Companies House company number")
            url = f"https://api.company-information.service.gov.uk/company/{quote(ident, safe='-')}"
        elif connector_key == "usaspending_award_v1":
            if not re.fullmatch(r"(?:CONT_(?:AWD|IDV)|ASST_(?:NON|AGG))_[A-Za-z0-9_.:-]{3,150}", ident, re.I): raise ValueError("USAspending source plan requires a specific generated award id")
            url = f"https://api.usaspending.gov/api/v2/awards/{quote(ident, safe='_.:-')}/"
        elif connector_key == "ted_notice_xml_v1":
            if not re.fullmatch(r"\d{6}-\d{4}", ident): raise ValueError("TED direct notice plan requires publication number NNNNNN-YYYY")
            url = f"https://ted.europa.eu/en/notice/{ident}/xml"
        elif connector_key == "federal_register_document_v1":
            if not re.fullmatch(r"\d{4}-\d{5}", ident): raise ValueError("Federal Register source plan requires document number YYYY-NNNNN")
            url = f"https://www.federalregister.gov/api/v1/documents/{quote(ident, safe='-')}.json"
        elif connector_key == "internet_archive_metadata_v1":
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", ident): raise ValueError("Internet Archive source plan requires exact item identifier")
            url = f"https://archive.org/metadata/{quote(ident, safe='._-')}"
        elif connector_key == "ofac_sdn_xml_v1":
            if ident.casefold() not in {"sdn", "consolidated"}: raise ValueError("OFAC plan accepts only the canonical SDN/consolidated reference")
            url = "https://sanctionslist.ofac.treas.gov/Home/SdnList"
        elif connector_key == "unsc_consolidated_xml_v1":
            if ident.casefold() not in {"consolidated", "unsc"}: raise ValueError("UNSC plan accepts only the consolidated-list reference")
            url = "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list"
        elif connector_key == "nara_catalog_v1":
            if not re.fullmatch(r"\d{1,20}", ident): raise ValueError("NARA plan requires exact numeric catalog identifier")
            url = f"https://catalog.archives.gov/id/{quote(ident, safe='')}"
        elif connector_key == "govinfo_package_v1":
            if not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", ident): raise ValueError("GovInfo plan requires exact package identifier")
            url = f"https://api.govinfo.gov/packages/{quote(ident, safe='._-')}/summary"
        elif connector_key == "ted_search_v3":
            if not ident or len(ident) > 500: raise ValueError("TED search plan requires a bounded expert query")
            url = "https://ted.europa.eu/api/v3/notices/search"
        else: raise KeyError(connector_key)
        return {"connector_key": connector_key, "url": canonical_url(url), "host": spec["base_host"], "auth_type": spec["auth_type"], "parser_version": spec["parser_version"], "terms_ref": spec["terms_ref"], "request_method": str(spec.get("request_method") or "GET").upper(), "requires_human_source_review": True, "live_fetch_automatically_started": False, "requires_declared_user_agent": bool(spec.get("requires_declared_user_agent", False))}

    def register_official_source(self, connector_key: str, identifier: str) -> dict[str, Any]:
        plan = self.source_plan(connector_key, identifier); spec = OFFICIAL_CONNECTORS[connector_key]
        if spec["auth_type"] != "none": raise PermissionError("authenticated connector is plan-only in Build 350")
        source = self.build349.register_crawler_source(display_name=f"{spec['display_name']} · {identifier}", seed_urls=[plan["url"]], terms_ref=spec["terms_ref"], jurisdiction=spec["jurisdiction"], source_class=spec["source_class"], max_depth=0, max_pages=1, requests_per_minute=int(spec["requests_per_minute"]), parser_version=spec["parser_version"])
        self.db.execute("INSERT OR REPLACE INTO phase15_connector_source_links(source_id,connector_key,identifier,created_at,record_hash) VALUES(?,?,?,?,?)", (source["source_id"],connector_key,str(identifier),_now(),_sha({"source_id":source["source_id"],"connector_key":connector_key,"identifier":str(identifier)})))
        return {"source": source, "plan": plan}

    def validate_transport_for_source(self, source_id: str, transport: Any) -> dict[str, Any]:
        link = self.db.one("SELECT connector_key FROM phase15_connector_source_links WHERE source_id=?", (source_id,))
        if not link: return {"allowed": True, "reason": "generic_governed_source"}
        spec = OFFICIAL_CONNECTORS[link["connector_key"]]
        if spec["auth_type"] != "none": return {"allowed": False, "reason": "authentication_required"}
        if spec.get("requires_declared_user_agent"):
            ua = str(getattr(transport, "user_agent", ""))
            if not ua or ua.startswith("EagleEye-GovernedCrawler/"):
                return {"allowed": False, "reason": "declared_operator_user_agent_required"}
        return {"allowed": True, "reason": "connector_transport_policy_satisfied"}

    def parse_bytes(self, body: bytes, *, source_url: str, media_type: str = "", parser_version: str = "auto-v1") -> ParseResult:
        data = bytes(body)
        if len(data) > _MAX_BODY: raise ValueError("parser input exceeds 10 MB")
        mt = detect_media_type({"content-type": media_type}, data)
        parser = parser_version or "auto-v1"
        if parser == "auto-v1":
            parser = {"application/json":"generic-json-v1","text/html":"html-safe-v1","application/xhtml+xml":"html-safe-v1","application/xml":"xml-safe-v1","text/xml":"xml-safe-v1"}.get(mt,"text-safe-v1")
        if parser in {"html-safe-v1","html-text-links-v1"}: return self._parse_html(data, source_url, mt, parser)
        if parser in {"xml-safe-v1","ted-notice-xml-v1","ofac-sanctions-xml-v1","unsc-sanctions-xml-v1"}: return self._parse_xml(data, source_url, mt, parser)
        if parser in {"generic-json-v1","gleif-json-v1","sec-submissions-json-v1","companies-house-json-v1","usaspending-award-json-v1","federal-register-json-v1","internet-archive-metadata-json-v1"}: return self._parse_json(data, source_url, mt, parser)
        if parser == "text-safe-v1":
            text=data.decode("utf-8",errors="replace")[:_MAX_TEXT]
            return ParseResult(parser,mt,canonical_url(source_url),canonical_url(source_url),"",text,(),(),())
        raise ValueError(f"unsupported parser_version: {parser}")

    def _parse_html(self, data: bytes, url: str, mt: str, parser: str) -> ParseResult:
        text=data.decode("utf-8",errors="replace")[:_MAX_TEXT]
        h=_HTMLDocument(); h.feed(text)
        links=[]
        for href in h.links:
            try: links.append(canonical_url(urljoin(url,htmlmod.unescape(href))))
            except Exception: continue
        canonical=canonical_url(url)
        if h.canonical:
            try:
                candidate=canonical_url(urljoin(url,h.canonical))
                if (urlsplit(candidate).hostname or "").lower()==(urlsplit(canonical).hostname or "").lower(): canonical=candidate
            except Exception: pass
        return ParseResult(parser,mt,canonical_url(url),canonical," ".join(h.title)[:500]," ".join(h.text)[:_MAX_TEXT],tuple(dict.fromkeys(links))[:_MAX_LINKS],(),())

    def _parse_xml(self, data: bytes, url: str, mt: str, parser: str) -> ParseResult:
        upper=data[:100000].upper()
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper: raise ValueError("DTD/entity declarations forbidden")
        root=ET.fromstring(data)
        if parser == "ted-notice-xml-v1":
            values: dict[str, list[str]] = {}
            text_parts=[]
            for i, elem in enumerate(root.iter()):
                if i >= _MAX_RECORDS: break
                tag=elem.tag.split("}")[-1] if isinstance(elem.tag,str) else str(elem.tag)
                value=" ".join((elem.text or "").split())[:2000]
                if value:
                    text_parts.append(value)
                    values.setdefault(tag, []).append(value)
            def first(*names: str) -> str:
                for name in names:
                    vals=values.get(name) or []
                    if vals: return vals[0]
                return ""
            def many(*names: str, limit: int = 30) -> list[str]:
                out=[]
                for name in names:
                    for value in values.get(name) or []:
                        if value and value not in out: out.append(value)
                        if len(out) >= limit: return out
                return out
            record={
                "entity_type":"ted_procurement_notice",
                "publication_number": first("PublicationNumber", "NO_DOC_OJS", "ID"),
                "notice_identifier": first("NoticeIdentifier", "ContractFolderID"),
                "procedure_title": first("ProcurementProjectName", "TITLE", "Name"),
                "buyer_names": many("PartyName", "OFFICIALNAME", "OrganizationName"),
                "winner_names": many("TendererParty", "WINNER", "WinnerName", "ContractorName"),
                "cpv_codes": many("ItemClassificationCode", "CPV_CODE", "MainCommodityClassification"),
                "currency": first("CurrencyID", "CURRENCY"),
                "amount_candidates": many("TaxExclusiveAmount", "PayableAmount", "ValueAmount", "VALUE", "EstimatedOverallContractAmount", limit=20),
                "publication_date": first("PublicationDate", "DATE_PUB"),
            }
            record={k:v for k,v in record.items() if v not in ("",[],None)}
            title=str(record.get("procedure_title") or record.get("publication_number") or "TED procurement notice")[:500]
            return ParseResult(parser,mt,canonical_url(url),canonical_url(url),title," ".join(text_parts)[:_MAX_TEXT],(),(record,),())
        if parser in {"ofac-sanctions-xml-v1","unsc-sanctions-xml-v1"}:
            values: dict[str,list[str]] = {}
            for i, elem in enumerate(root.iter()):
                if i >= _MAX_RECORDS: break
                tag=elem.tag.split("}")[-1] if isinstance(elem.tag,str) else str(elem.tag)
                value=" ".join((elem.text or "").split())[:2000]
                if value: values.setdefault(tag.casefold(),[]).append(value)
            def first(*names: str) -> str:
                for name in names:
                    vals=values.get(name.casefold()) or []
                    if vals: return vals[0]
                return ""
            def many(*names: str, limit: int=20) -> list[str]:
                out=[]
                for name in names:
                    for value in values.get(name.casefold()) or []:
                        if value and value not in out: out.append(value)
                        if len(out)>=limit: return out
                return out
            record={
                "entity_type":"sanctions_reference",
                "reference_id":first("uid","dataid","reference_number","id"),
                "name":first("fullname","first_name","name","last_name"),
                "list_name":"OFAC SDN" if parser=="ofac-sanctions-xml-v1" else "UNSC Consolidated",
                "programs":many("program","listed_on_list","un_list_type"),
                "listed_on":first("listed_on","publicationdate","date"),
                "source":"OFAC" if parser=="ofac-sanctions-xml-v1" else "UNSC",
            }
            record={k:v for k,v in record.items() if v not in ("",[],None)}
            return ParseResult(parser,mt,canonical_url(url),canonical_url(url),str(record.get("name") or record.get("reference_id") or record.get("list_name"))[:500],_canon(record)[:_MAX_TEXT],(),(record,),())
        records=[]; text_parts=[]
        for i, elem in enumerate(root.iter()):
            if i >= _MAX_RECORDS: break
            tag=elem.tag.split("}")[-1] if isinstance(elem.tag,str) else str(elem.tag)
            value=" ".join((elem.text or "").split())[:2000]
            if value: text_parts.append(value)
            if value or elem.attrib: records.append({"tag":tag,"text":value,"attributes":dict(list(elem.attrib.items())[:50])})
        warnings=("record_limit_reached",) if len(records)>=_MAX_RECORDS else ()
        return ParseResult(parser,mt,canonical_url(url),canonical_url(url),root.tag.split("}")[-1]," ".join(text_parts)[:_MAX_TEXT],(),tuple(records),warnings)

    def _parse_json(self, data: bytes, url: str, mt: str, parser: str) -> ParseResult:
        obj=json.loads(data.decode("utf-8"))
        warnings=[]; records: list[dict[str,Any]]=[]; title=""; text=""
        if parser=="gleif-json-v1":
            items=obj.get("data",[]) if isinstance(obj,dict) else []
            if isinstance(items,dict): items=[items]
            for item in items[:_MAX_RECORDS]:
                if not isinstance(item,dict): continue
                attr=item.get("attributes",{}) if isinstance(item.get("attributes"),dict) else {}; ent=attr.get("entity",{}) if isinstance(attr.get("entity"),dict) else {}
                legal=ent.get("legalName",{}) if isinstance(ent.get("legalName"),dict) else {}
                records.append({"entity_type":"legal_entity","lei":item.get("id") or attr.get("lei"),"legal_name":legal.get("name"),"entity_status":ent.get("status"),"legal_address":ent.get("legalAddress"),"headquarters_address":ent.get("headquartersAddress"),"registration_authority":ent.get("registeredAt")})
            title=(records[0].get("legal_name") or "GLEIF LEI") if records else "GLEIF LEI"
        elif parser=="sec-submissions-json-v1":
            if not isinstance(obj,dict): raise ValueError("SEC submissions response must be JSON object")
            recent=((obj.get("filings") or {}).get("recent") or {}) if isinstance(obj.get("filings"),dict) else {}
            forms=recent.get("form",[]) if isinstance(recent,dict) else []
            acc=recent.get("accessionNumber",[]) if isinstance(recent,dict) else []
            filed=recent.get("filingDate",[]) if isinstance(recent,dict) else []
            filings=[]
            for i in range(min(len(forms) if isinstance(forms,list) else 0, 500)):
                filings.append({"form":forms[i],"accession_number":acc[i] if isinstance(acc,list) and i<len(acc) else None,"filing_date":filed[i] if isinstance(filed,list) and i<len(filed) else None})
            records=[{"entity_type":"sec_filer","cik":obj.get("cik"),"name":obj.get("name"),"entity_type_sec":obj.get("entityType"),"sic":obj.get("sic"),"sic_description":obj.get("sicDescription"),"tickers":obj.get("tickers",[]),"exchanges":obj.get("exchanges",[]),"ein":obj.get("ein"),"addresses":obj.get("addresses",{}),"recent_filings":filings}]
            title=str(obj.get("name") or "SEC EDGAR")[:500]
        elif parser=="companies-house-json-v1":
            if not isinstance(obj,dict): raise ValueError("Companies House response must be JSON object")
            records=[{"entity_type":"uk_company","company_number":obj.get("company_number"),"company_name":obj.get("company_name"),"company_status":obj.get("company_status"),"company_type":obj.get("type"),"jurisdiction":obj.get("jurisdiction"),"date_of_creation":obj.get("date_of_creation"),"registered_office_address":obj.get("registered_office_address") }]
            title=str(obj.get("company_name") or "Companies House")[:500]
        elif parser=="federal-register-json-v1":
            if not isinstance(obj,dict): raise ValueError("Federal Register response must be JSON object")
            agencies=obj.get("agencies") if isinstance(obj.get("agencies"),list) else []
            agency_names=[str(a.get("name")) for a in agencies if isinstance(a,dict) and a.get("name")][:50]
            records=[{"entity_type":"federal_register_document","document_number":obj.get("document_number"),"title":obj.get("title"),"document_type":obj.get("type"),"abstract":obj.get("abstract"),"publication_date":obj.get("publication_date"),"agencies":agency_names,"html_url":obj.get("html_url"),"pdf_url":obj.get("pdf_url"),"regulation_id_numbers":obj.get("regulation_id_numbers",[]),"docket_ids":obj.get("docket_ids",[])}]
            title=str(obj.get("title") or obj.get("document_number") or "Federal Register document")[:500]
        elif parser=="internet-archive-metadata-json-v1":
            if not isinstance(obj,dict): raise ValueError("Internet Archive metadata response must be JSON object")
            meta=obj.get("metadata") if isinstance(obj.get("metadata"),dict) else {}
            records=[{"entity_type":"internet_archive_item_metadata","identifier":meta.get("identifier"),"title":meta.get("title"),"creator":meta.get("creator"),"date":meta.get("date"),"description":meta.get("description"),"mediatype":meta.get("mediatype"),"collection":meta.get("collection"),"subject":meta.get("subject"),"language":meta.get("language"),"publicdate":meta.get("publicdate"),"addeddate":meta.get("addeddate"),"item_size":obj.get("item_size")} ]
            title=str(meta.get("title") or meta.get("identifier") or "Internet Archive metadata")[:500]
        elif parser=="usaspending-award-json-v1":
            if not isinstance(obj,dict): raise ValueError("USAspending award response must be JSON object")
            recipient=obj.get("recipient") if isinstance(obj.get("recipient"),dict) else {}
            awarding=obj.get("awarding_agency") if isinstance(obj.get("awarding_agency"),dict) else {}
            funding=obj.get("funding_agency") if isinstance(obj.get("funding_agency"),dict) else {}
            contract=obj.get("latest_transaction_contract_data") if isinstance(obj.get("latest_transaction_contract_data"),dict) else {}
            performance=obj.get("period_of_performance") if isinstance(obj.get("period_of_performance"),dict) else {}
            def agency_name(value: dict[str,Any]) -> str:
                top=value.get("toptier_agency") if isinstance(value.get("toptier_agency"),dict) else {}
                sub=value.get("subtier_agency") if isinstance(value.get("subtier_agency"),dict) else {}
                return str(sub.get("name") or top.get("name") or value.get("office_agency_name") or "")
            records=[{
                "entity_type":"us_public_spending_award",
                "award_id":obj.get("generated_unique_award_id"),
                "piid":obj.get("piid"),
                "award_category":obj.get("category"),
                "award_type":obj.get("type"),
                "award_type_description":obj.get("type_description"),
                "description":obj.get("description"),
                "total_obligation":obj.get("total_obligation"),
                "total_outlay":obj.get("total_outlay"),
                "date_signed":obj.get("date_signed"),
                "performance_start":performance.get("start_date"),
                "performance_end":performance.get("end_date"),
                "recipient_name":recipient.get("recipient_name"),
                "recipient_uei":recipient.get("recipient_uei"),
                "parent_recipient_name":recipient.get("parent_recipient_name"),
                "parent_recipient_uei":recipient.get("parent_recipient_uei"),
                "awarding_agency":agency_name(awarding),
                "funding_agency":agency_name(funding),
                "number_of_offers_received":contract.get("number_of_offers_received"),
                "extent_competed":contract.get("extent_competed_description") or contract.get("extent_competed"),
                "solicitation_procedures":contract.get("solicitation_procedures_description") or contract.get("solicitation_procedures"),
                "naics":contract.get("naics"),
                "naics_description":contract.get("naics_description"),
                "product_or_service_code":contract.get("product_or_service_code"),
                "product_or_service_description":contract.get("product_or_service_description"),
            }]
            title=str(obj.get("description") or recipient.get("recipient_name") or obj.get("generated_unique_award_id") or "USAspending award")[:500]
        else:
            if isinstance(obj,list): records=[{"value":v} if not isinstance(v,dict) else v for v in obj[:_MAX_RECORDS]]
            elif isinstance(obj,dict): records=[obj]
            else: records=[{"value":obj}]
            title="JSON document"
        text=_canon(records)[:_MAX_TEXT]
        if len(records)>=_MAX_RECORDS: warnings.append("record_limit_reached")
        return ParseResult(parser,mt,canonical_url(url),canonical_url(url),title,text,(),tuple(records),tuple(warnings))

    def parse_object(self, object_id: str, *, parser_version: str | None = None) -> dict[str, Any]:
        meta=self.build349.artifact(object_id)
        if meta["security_state"]=="quarantined": raise PermissionError("quarantined object requires human safe review before parsing")
        prov=meta.get("provenance") or {}; source_url=str(prov.get("url") or prov.get("source_url") or "")
        if not source_url: raise ValueError("source URL missing from provenance")
        source=self.db.one("SELECT parser_version FROM phase15_crawler_policies WHERE source_id=?",(meta["source_id"],)) if meta.get("source_id") else None
        pv=parser_version or (source["parser_version"] if source else "auto-v1")
        body=self.build349.artifact_bytes(object_id)
        run_id="parse350_"+uuid.uuid4().hex[:20]; now=_now()
        try:
            result=self.parse_bytes(body,source_url=source_url,media_type=meta["media_type"],parser_version=pv)
            normalized=result.as_dict(); status="parsed"; error=""; count=len(result.records)
        except Exception as exc:
            normalized={}; status="parse_failed"; error=f"{type(exc).__name__}:{exc}"[:2000]; count=0
        row={"parse_run_id":run_id,"object_id":object_id,"source_id":meta.get("source_id") or "","parser_version":pv,"media_type":meta["media_type"],"status":status,"record_count":count,"normalized_json":_canon(normalized),"warnings_json":_canon(normalized.get("warnings",[]) if normalized else []),"error_text":error,"created_at":now}
        self.db.execute("INSERT INTO phase15_parse_runs(parse_run_id,object_id,source_id,parser_version,media_type,status,record_count,normalized_json,warnings_json,error_text,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (*row.values(),_sha(row)))
        return {**row,"normalized":normalized}

    def parse_crawl_run(self, crawl_run_id: str) -> dict[str, Any]:
        fetches=self.db.all("SELECT object_id FROM phase15_crawl_fetches WHERE crawl_run_id=? AND object_id<>'' ORDER BY created_at",(crawl_run_id,))
        parsed=failed=quarantined=0; runs=[]
        for f in fetches:
            meta=self.build349.artifact(f["object_id"])
            if meta["security_state"]=="quarantined": quarantined+=1; continue
            r=self.parse_object(f["object_id"]); runs.append(r["parse_run_id"]); parsed+=r["status"]=="parsed"; failed+=r["status"]!="parsed"
        return {"crawl_run_id":crawl_run_id,"parsed":int(parsed),"failed":int(failed),"quarantined_skipped":quarantined,"parse_runs":runs}

    def record_source_health(self, source_id: str, *, crawl_run_id: str = "") -> dict[str, Any]:
        fetches=self.db.all("SELECT status_code,elapsed_ms,disposition FROM phase15_crawl_fetches WHERE crawl_run_id=?",(crawl_run_id,)) if crawl_run_id else []
        parses=self.db.all("SELECT status FROM phase15_parse_runs WHERE source_id=? ORDER BY created_at DESC LIMIT 100",(source_id,))
        codes=[int(f["status_code"]) for f in fetches if int(f["status_code"])>0]
        if any(c==429 for c in codes): status="rate_limited"
        elif any(c in {401,403} for c in codes): status="authentication_required"
        elif codes and all(c>=500 for c in codes): status="offline"
        elif parses and any(p["status"]=="parse_failed" for p in parses): status="changed_contract"
        elif any(c>=400 for c in codes): status="degraded"
        elif codes: status="operational"
        else: status="not_run"
        detail={"crawl_run_id":crawl_run_id,"http_codes":codes[:100],"parse_failures":sum(1 for p in parses if p["status"]=="parse_failed"),"samples":len(codes)}
        event={"health_id":"health350_"+uuid.uuid4().hex[:20],"source_id":source_id,"status":status,"details_json":_canon(detail),"created_at":_now()}
        self.db.execute("INSERT INTO phase15_source_health_events(health_id,source_id,status,details_json,created_at,record_hash) VALUES(?,?,?,?,?,?)",(*event.values(),_sha(event)))
        self.db.execute("UPDATE phase15_crawler_policies SET source_health=?,updated_at=? WHERE source_id=?",(status,_now(),source_id))
        return {**event,"details":detail}

    def correlation_candidates(self, *, case_id: str) -> list[dict[str, Any]]:
        rows=self.db.all("SELECT p.parse_run_id,p.object_id,p.source_id,p.normalized_json,o.case_id FROM phase15_parse_runs p JOIN phase15_objects o ON o.object_id=p.object_id WHERE o.case_id=? AND p.status='parsed' ORDER BY p.created_at",(case_id,))
        items=[]
        def norm_name(v: Any)->str:
            return re.sub(r"[^a-z0-9]+","",str(v or "").casefold())
        for row in rows:
            try: doc=json.loads(row["normalized_json"])
            except Exception: continue
            for rec in doc.get("records",[]) if isinstance(doc,dict) else []:
                if not isinstance(rec,dict): continue
                identifiers={}
                for key in ("lei","cik","company_number"):
                    if rec.get(key): identifiers[key]=str(rec[key]).strip().upper()
                name=rec.get("legal_name") or rec.get("name") or rec.get("company_name") or ""
                items.append({"parse_run_id":row["parse_run_id"],"object_id":row["object_id"],"source_id":row["source_id"],"identifiers":identifiers,"name":str(name),"name_norm":norm_name(name)})
        leads=[]
        for i,a in enumerate(items):
            for b in items[i+1:]:
                if a["source_id"]==b["source_id"]: continue
                basis=[]
                for key in set(a["identifiers"]) & set(b["identifiers"]):
                    if a["identifiers"][key] and a["identifiers"][key]==b["identifiers"][key]: basis.append(f"exact_{key}")
                if a["name_norm"] and len(a["name_norm"])>=5 and a["name_norm"]==b["name_norm"]: basis.append("normalized_name_overlap")
                if basis:
                    leads.append({"lead_type":"entity_correlation_candidate","basis":basis,"identity_confirmed":False,"requires_human_review":True,"left":{"parse_run_id":a["parse_run_id"],"object_id":a["object_id"],"source_id":a["source_id"],"name":a["name"],"identifiers":a["identifiers"]},"right":{"parse_run_id":b["parse_run_id"],"object_id":b["object_id"],"source_id":b["source_id"],"name":b["name"],"identifiers":b["identifiers"]}})
        return leads[:1000]

    def parse_runs(self, *, source_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        n=max(1,min(int(limit),1000))
        if source_id: return self.db.all("SELECT * FROM phase15_parse_runs WHERE source_id=? ORDER BY created_at DESC LIMIT ?",(source_id,n))
        return self.db.all("SELECT * FROM phase15_parse_runs ORDER BY created_at DESC LIMIT ?",(n,))

    def status(self) -> dict[str, Any]:
        p=self.db.one("SELECT COUNT(*) c,SUM(CASE WHEN status='parsed' THEN 1 ELSE 0 END) ok,SUM(CASE WHEN status='parse_failed' THEN 1 ELSE 0 END) bad FROM phase15_parse_runs") or {"c":0,"ok":0,"bad":0}
        return {"policy":PARSER_POLICY_VERSION,"official_manifests":len(self.manifests()),"parse_runs":int(p["c"] or 0),"parsed":int(p["ok"] or 0),"parse_failed":int(p["bad"] or 0),"supported_media":["HTML","JSON","XML","text"],"dtd_entities_allowed":False,"quarantined_auto_parse":False,"authenticated_live_connector_supported":False}
