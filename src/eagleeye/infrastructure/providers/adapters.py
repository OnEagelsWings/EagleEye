from __future__ import annotations

import json
import re
from typing import Any, Sequence
from urllib.parse import quote, urlencode, urlsplit

from .contracts import (
    NormalizedProviderItem,
    ProviderAdapter,
    ProviderDefinition,
    ProviderHttpRequest,
    ProviderRunRequest,
    ProviderTransportResponse,
    ProviderValidationError,
)


def _json(response: ProviderTransportResponse) -> Any:
    try:
        return json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderValidationError("provider returned invalid JSON") from exc


class RdapPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="rdap_public_120",
        label="Public RDAP",
        provider_type="domain_registry",
        allowed_hosts=("rdap.org",),
        rate_limit_per_minute=20,
        min_interval_seconds=0.25,
        terms_profile="Public RDAP bootstrap; domain infrastructure context only.",
    )

    def validate_request(self, request: ProviderRunRequest) -> None:
        super().validate_request(request)
        domain = request.query.casefold().strip().rstrip(".")
        if domain.startswith(("http://", "https://")):
            domain = (urlsplit(domain).hostname or "").casefold()
        if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", domain):
            raise ProviderValidationError("RDAP query must be a public domain name")

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        domain = request.query.casefold().strip().rstrip(".")
        if domain.startswith(("http://", "https://")):
            domain = (urlsplit(domain).hostname or "").casefold()
        return (ProviderHttpRequest(f"https://rdap.org/domain/{quote(domain, safe='.-')}", headers={"Accept": "application/rdap+json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        data = _json(response)
        domain = str(data.get("ldhName") or data.get("unicodeName") or request.query).strip()
        statuses = ", ".join(str(item) for item in data.get("status", [])[:10])
        nameservers = ", ".join(
            str(item.get("ldhName") or "") for item in data.get("nameservers", [])[:20] if isinstance(item, dict)
        )
        snippet = "; ".join(part for part in (f"status: {statuses}" if statuses else "", f"nameservers: {nameservers}" if nameservers else "") if part)
        return (NormalizedProviderItem(
            title=f"RDAP record: {domain}",
            url=response.final_url,
            snippet=snippet,
            source_type="public_registry",
            raw_payload=data if isinstance(data, dict) else {"payload": data},
        ),)


class GithubPublicProfileAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="github_public_profile_120",
        label="GitHub public profile",
        provider_type="public_code_profile",
        allowed_hosts=("api.github.com",),
        rate_limit_per_minute=30,
        min_interval_seconds=0.25,
        terms_profile="Unauthenticated public GitHub profile metadata; username equality is not identity proof.",
    )

    def validate_request(self, request: ProviderRunRequest) -> None:
        super().validate_request(request)
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", request.query.strip()):
            raise ProviderValidationError("invalid public GitHub username")

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        username = request.query.strip()
        return (ProviderHttpRequest(
            f"https://api.github.com/users/{quote(username, safe='-._')}",
            headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        ),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        data = _json(response)
        login = str(data.get("login") or request.query)
        url = str(data.get("html_url") or response.final_url)
        fields = [data.get("name"), data.get("company"), data.get("location"), data.get("bio")]
        return (NormalizedProviderItem(
            title=f"GitHub public profile: {login}",
            url=url,
            snippet=" | ".join(str(item) for item in fields if item),
            source_type="public_code_profile",
            raw_payload=data,
        ),)


class GitlabPublicProfileAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="gitlab_public_profile_120",
        label="GitLab public profile",
        provider_type="public_code_profile",
        allowed_hosts=("gitlab.com",),
        rate_limit_per_minute=30,
        min_interval_seconds=0.25,
        terms_profile="Public GitLab user search; exact username candidate only.",
    )

    def validate_request(self, request: ProviderRunRequest) -> None:
        super().validate_request(request)
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", request.query.strip()):
            raise ProviderValidationError("invalid public GitLab username")

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://gitlab.com/api/v4/users?" + urlencode({"username": request.query.strip()})),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        if not isinstance(payload, list):
            raise ProviderValidationError("GitLab provider returned unexpected JSON")
        exact = [item for item in payload if isinstance(item, dict) and str(item.get("username") or "").casefold() == request.query.casefold()]
        return tuple(
            NormalizedProviderItem(
                title=f"GitLab public profile: {item.get('username', request.query)}",
                url=str(item.get("web_url") or response.final_url),
                snippet=str(item.get("name") or ""),
                source_type="public_code_profile",
                raw_payload=item,
            )
            for item in exact[: request.max_results]
        )


class WaybackCdxPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="wayback_cdx_public_120",
        label="Wayback CDX public index",
        provider_type="web_archive",
        allowed_hosts=("web.archive.org",),
        rate_limit_per_minute=15,
        min_interval_seconds=0.5,
        timeout_seconds=30,
        max_response_bytes=5_000_000,
        terms_profile="Public archive index metadata; archived content requires separate capture and review.",
    )

    def validate_request(self, request: ProviderRunRequest) -> None:
        super().validate_request(request)
        parts = urlsplit(request.query.strip())
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ProviderValidationError("Wayback query must be a public HTTP(S) URL")

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        params = [
            ("url", request.query.strip()),
            ("output", "json"),
            ("fl", "timestamp,original,statuscode,mimetype,digest"),
            ("filter", "statuscode:200"),
            ("collapse", "digest"),
            ("limit", str(min(request.max_results, 100))),
        ]
        return (ProviderHttpRequest("https://web.archive.org/cdx/search/cdx?" + urlencode(params)),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        if not isinstance(payload, list) or not payload:
            return ()
        header = [str(item) for item in payload[0]] if isinstance(payload[0], list) else []
        items: list[NormalizedProviderItem] = []
        for row in payload[1 : request.max_results + 1]:
            if not isinstance(row, list):
                continue
            data = dict(zip(header, row))
            timestamp = str(data.get("timestamp") or "")
            original = str(data.get("original") or request.query)
            archive_url = f"https://web.archive.org/web/{timestamp}/{original}" if timestamp else response.final_url
            items.append(NormalizedProviderItem(
                title=f"Archived snapshot: {original}",
                url=archive_url,
                snippet=f"timestamp={timestamp}; mimetype={data.get('mimetype', '')}; digest={data.get('digest', '')}",
                source_type="public_web_archive",
                published_at=timestamp,
                raw_payload=data,
            ))
        return tuple(items)



class CrossrefWorksPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="crossref_works_public_128",
        label="Crossref public works",
        provider_type="scholarly_metadata",
        allowed_hosts=("api.crossref.org",),
        rate_limit_per_minute=30,
        min_interval_seconds=0.25,
        terms_profile="Public scholarly metadata; author-name matches require human review.",
        metadata={"build": "128.0", "input_types": ["name", "organisation", "identifier"]},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://api.crossref.org/works?" + urlencode({
            "query.author": request.query.strip(), "rows": str(min(request.max_results, 50)),
            "select": "DOI,title,author,published,URL,publisher,type,score",
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        items = ((payload or {}).get("message") or {}).get("items") if isinstance(payload, dict) else []
        out: list[NormalizedProviderItem] = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            titles = item.get("title") or []
            title = str(titles[0] if isinstance(titles, list) and titles else item.get("DOI") or request.query)
            doi = str(item.get("DOI") or "")
            url = str(item.get("URL") or (f"https://doi.org/{doi}" if doi else response.final_url))
            authors = ", ".join(" ".join(filter(None, [str(a.get("given") or ""), str(a.get("family") or "")])).strip() for a in (item.get("author") or [])[:8] if isinstance(a, dict))
            snippet = "; ".join(x for x in [authors, str(item.get("publisher") or ""), str(item.get("type") or "")] if x)
            out.append(NormalizedProviderItem(title=title, url=url, snippet=snippet, source_type="public_scholarly_index", raw_payload=item))
        return tuple(out[:request.max_results])


class OpenAlexAuthorsPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="openalex_authors_public_128",
        label="OpenAlex public authors",
        provider_type="scholarly_identity",
        allowed_hosts=("api.openalex.org",),
        rate_limit_per_minute=30,
        min_interval_seconds=0.25,
        terms_profile="Open scholarly metadata; author profiles remain candidates until reviewed.",
        metadata={"build": "128.0", "input_types": ["name", "organisation", "identifier"]},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://api.openalex.org/authors?" + urlencode({
            "search": request.query.strip(), "per-page": str(min(request.max_results, 50)),
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.get("results", []) if isinstance(payload, dict) else []
        out: list[NormalizedProviderItem] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            name = str(item.get("display_name") or request.query)
            insts = item.get("last_known_institutions") or []
            institutions = ", ".join(str(i.get("display_name") or "") for i in insts[:5] if isinstance(i, dict))
            orcid = str(item.get("orcid") or "")
            snippet = "; ".join(x for x in [institutions, f"ORCID: {orcid}" if orcid else "", f"works: {item.get('works_count', 0)}"] if x)
            out.append(NormalizedProviderItem(title=f"OpenAlex author candidate: {name}", url=str(item.get("id") or response.final_url), snippet=snippet, source_type="public_scholarly_identity", raw_payload=item))
        return tuple(out[:request.max_results])


class InternetArchivePublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="internet_archive_public_128",
        label="Internet Archive public search",
        provider_type="public_archive",
        allowed_hosts=("archive.org",),
        rate_limit_per_minute=20,
        min_interval_seconds=0.5,
        timeout_seconds=30,
        max_response_bytes=5_000_000,
        terms_profile="Public archive metadata; item content requires separate capture and review.",
        metadata={"build": "128.0", "input_types": ["name", "organisation", "keyword"]},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        params = [("q", request.query.strip()), ("fl[]", "identifier"), ("fl[]", "title"), ("fl[]", "creator"), ("fl[]", "date"), ("rows", str(min(request.max_results, 50))), ("page", "1"), ("output", "json")]
        return (ProviderHttpRequest("https://archive.org/advancedsearch.php?" + urlencode(params)),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        docs = ((payload or {}).get("response") or {}).get("docs") if isinstance(payload, dict) else []
        out = []
        for item in docs or []:
            if not isinstance(item, dict):
                continue
            identifier = str(item.get("identifier") or "")
            title = str(item.get("title") or identifier or request.query)
            creator = item.get("creator")
            if isinstance(creator, list):
                creator = ", ".join(str(x) for x in creator[:8])
            snippet = "; ".join(x for x in [str(creator or ""), str(item.get("date") or "")] if x)
            out.append(NormalizedProviderItem(title=title, url=f"https://archive.org/details/{quote(identifier, safe='-._')}" if identifier else response.final_url, snippet=snippet, source_type="public_archive_item", raw_payload=item))
        return tuple(out[:request.max_results])


class WikidataEntitiesPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="wikidata_entities_public_128",
        label="Wikidata public entity search",
        provider_type="knowledge_base",
        allowed_hosts=("www.wikidata.org",),
        rate_limit_per_minute=30,
        min_interval_seconds=0.25,
        terms_profile="Community-maintained public metadata; never an identity confirmation.",
        metadata={"build": "128.0", "input_types": ["name", "alias", "organisation", "location"]},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://www.wikidata.org/w/api.php?" + urlencode({
            "action": "wbsearchentities", "search": request.query.strip(), "language": "en",
            "uselang": "en", "format": "json", "limit": str(min(request.max_results, 50)), "type": "item",
        })),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.get("search", []) if isinstance(payload, dict) else []
        out = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            entity_id = str(item.get("id") or "")
            out.append(NormalizedProviderItem(title=str(item.get("label") or entity_id or request.query), url=str(item.get("concepturi") or (f"https://www.wikidata.org/wiki/{entity_id}" if entity_id else response.final_url)), snippet=str(item.get("description") or ""), source_type="public_knowledge_base", raw_payload=item))
        return tuple(out[:request.max_results])


class EuropePmcPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="europe_pmc_public_128",
        label="Europe PMC public search",
        provider_type="scholarly_metadata",
        allowed_hosts=("www.ebi.ac.uk",),
        rate_limit_per_minute=30,
        min_interval_seconds=0.25,
        terms_profile="Public biomedical literature metadata; author-name matches require review.",
        metadata={"build": "128.0", "input_types": ["name", "organisation", "identifier"]},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        query = f'AUTH:"{request.query.strip()}"'
        return (ProviderHttpRequest("https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urlencode({
            "query": query, "format": "json", "pageSize": str(min(request.max_results, 50)),
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = ((payload or {}).get("resultList") or {}).get("result") if isinstance(payload, dict) else []
        out = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            pmid = str(item.get("pmid") or "")
            doi = str(item.get("doi") or "")
            url = f"https://europepmc.org/article/MED/{pmid}" if pmid else f"https://doi.org/{doi}" if doi else response.final_url
            snippet = "; ".join(x for x in [str(item.get("authorString") or ""), str(item.get("journalTitle") or ""), str(item.get("pubYear") or "")] if x)
            out.append(NormalizedProviderItem(title=str(item.get("title") or request.query), url=url, snippet=snippet, source_type="public_scholarly_index", published_at=str(item.get("firstPublicationDate") or item.get("pubYear") or ""), raw_payload=item))
        return tuple(out[:request.max_results])


class OpenLibraryAuthorsPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="openlibrary_authors_public_128",
        label="Open Library public authors",
        provider_type="bibliographic_identity",
        allowed_hosts=("openlibrary.org",),
        rate_limit_per_minute=30,
        min_interval_seconds=0.25,
        terms_profile="Public bibliographic metadata; author-name matches remain candidates.",
        metadata={"build": "128.0", "input_types": ["name", "alias"]},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://openlibrary.org/search/authors.json?" + urlencode({
            "q": request.query.strip(), "limit": str(min(request.max_results, 50)),
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.get("docs", []) if isinstance(payload, dict) else []
        out = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "")
            top_work = str(item.get("top_work") or "")
            snippet = "; ".join(x for x in [top_work, f"works: {item.get('work_count', 0)}"] if x)
            out.append(NormalizedProviderItem(title=f"Open Library author candidate: {item.get('name') or request.query}", url=f"https://openlibrary.org/authors/{quote(key, safe='-._')}" if key else response.final_url, snippet=snippet, source_type="public_bibliographic_identity", raw_payload=item))
        return tuple(out[:request.max_results])



class GleifLeiPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="gleif_lei_public_135",
        label="GLEIF LEI public search",
        provider_type="company_registry",
        allowed_hosts=("api.gleif.org",),
        rate_limit_per_minute=20,
        min_interval_seconds=0.35,
        timeout_seconds=25,
        max_response_bytes=5_000_000,
        terms_profile="Official public GLEIF API; legal-entity matches remain candidates.",
        metadata={"build": "135.0", "input_types": ["organisation", "identifier"]},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        query = request.query.strip()
        if re.fullmatch(r"[A-Z0-9]{20}", query.upper()):
            url = f"https://api.gleif.org/api/v1/lei-records/{quote(query.upper(), safe='')}"
        else:
            url = "https://api.gleif.org/api/v1/lei-records?" + urlencode({
                "filter[entity.legalName]": query,
                "page[size]": str(min(request.max_results, 50)),
            })
        return (ProviderHttpRequest(url, headers={"Accept": "application/vnd.api+json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        if isinstance(rows, dict):
            rows = [rows]
        out: list[NormalizedProviderItem] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            attrs = item.get("attributes") or {}
            entity = attrs.get("entity") or {}
            legal_name = entity.get("legalName") or {}
            name = str(legal_name.get("name") or item.get("id") or request.query)
            lei = str(attrs.get("lei") or item.get("id") or "")
            legal_address = entity.get("legalAddress") or {}
            address = ", ".join(str(x) for x in [legal_address.get("city"), legal_address.get("country")] if x)
            status = str((entity.get("status") or ""))
            url = f"https://api.gleif.org/api/v1/lei-records/{quote(lei, safe='')}" if lei else response.final_url
            snippet = "; ".join(x for x in [f"LEI: {lei}" if lei else "", status, address] if x)
            out.append(NormalizedProviderItem(title=f"GLEIF legal-entity candidate: {name}", url=url, snippet=snippet, source_type="public_company_registry", raw_payload=item))
        return tuple(out[:request.max_results])


class SecEdgarPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="sec_edgar_public_135",
        label="SEC EDGAR company index",
        provider_type="company_filings",
        allowed_hosts=("www.sec.gov",),
        rate_limit_per_minute=10,
        min_interval_seconds=0.5,
        timeout_seconds=25,
        max_response_bytes=10_000_000,
        terms_profile="Official public SEC company index; descriptive User-Agent required.",
        metadata={"build": "135.0", "input_types": ["organisation", "identifier"]},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"Accept": "application/json", "User-Agent": "EagleEye-PersonOSINT/135 local-research-tool"},
        ),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.values() if isinstance(payload, dict) else []
        needle = request.query.strip().casefold()
        exact: list[dict[str, Any]] = []
        partial: list[dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "")
            ticker = str(item.get("ticker") or "")
            cik = str(item.get("cik_str") or "")
            hay = {title.casefold(), ticker.casefold(), cik.lstrip("0").casefold()}
            if needle in hay:
                exact.append(item)
            elif needle and needle in title.casefold():
                partial.append(item)
        out: list[NormalizedProviderItem] = []
        for item in (exact + partial)[:request.max_results]:
            cik = str(item.get("cik_str") or "").zfill(10)
            title = str(item.get("title") or request.query)
            ticker = str(item.get("ticker") or "")
            url = f"https://www.sec.gov/edgar/browse/?CIK={quote(cik, safe='')}&owner=exclude" if cik else response.final_url
            out.append(NormalizedProviderItem(title=f"SEC company candidate: {title}", url=url, snippet=f"CIK: {cik}; ticker: {ticker}", source_type="public_company_filing_index", raw_payload=item))
        return tuple(out)


class GoogleBooksPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="google_books_public_135",
        label="Google Books public volumes",
        provider_type="bibliographic_metadata",
        allowed_hosts=("www.googleapis.com",),
        rate_limit_per_minute=30,
        min_interval_seconds=0.2,
        terms_profile="Official public Books API; author-name matches remain candidates.",
        metadata={"build": "135.0", "input_types": ["name", "identifier", "work"]},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://www.googleapis.com/books/v1/volumes?" + urlencode({
            "q": request.query.strip(),
            "maxResults": str(min(request.max_results, 40)),
            "printType": "all",
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.get("items", []) if isinstance(payload, dict) else []
        out: list[NormalizedProviderItem] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            info = item.get("volumeInfo") or {}
            title = str(info.get("title") or request.query)
            authors = ", ".join(str(x) for x in (info.get("authors") or [])[:10])
            identifiers = ", ".join(str(i.get("identifier") or "") for i in (info.get("industryIdentifiers") or [])[:5] if isinstance(i, dict))
            snippet = "; ".join(x for x in [authors, str(info.get("publishedDate") or ""), identifiers] if x)
            out.append(NormalizedProviderItem(title=title, url=str(info.get("infoLink") or item.get("selfLink") or response.final_url), snippet=snippet, source_type="public_bibliographic_metadata", published_at=str(info.get("publishedDate") or ""), raw_payload=item))
        return tuple(out[:request.max_results])


class CourtListenerPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="courtlistener_public_135",
        label="CourtListener public search",
        provider_type="case_law",
        allowed_hosts=("www.courtlistener.com",),
        rate_limit_per_minute=15,
        min_interval_seconds=0.5,
        timeout_seconds=25,
        max_response_bytes=5_000_000,
        terms_profile="Public CourtListener REST search; authentication may be required and results remain candidates.",
        metadata={"build": "135.0", "input_types": ["name", "organisation", "docket"]},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://www.courtlistener.com/api/rest/v3/search/?" + urlencode({
            "q": request.query.strip(),
            "type": "r",
            "page_size": str(min(request.max_results, 20)),
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.get("results", []) if isinstance(payload, dict) else []
        out: list[NormalizedProviderItem] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("caseName") or item.get("case_name") or item.get("docketNumber") or request.query)
            absolute_url = str(item.get("absolute_url") or "")
            url = f"https://www.courtlistener.com{absolute_url}" if absolute_url.startswith("/") else absolute_url or response.final_url
            snippet = "; ".join(x for x in [str(item.get("court_citation_string") or ""), str(item.get("dateFiled") or item.get("date_filed") or ""), str(item.get("docketNumber") or "")] if x)
            out.append(NormalizedProviderItem(title=f"CourtListener candidate: {title}", url=url, snippet=snippet, source_type="public_case_law", published_at=str(item.get("dateFiled") or item.get("date_filed") or ""), raw_payload=item))
        return tuple(out[:request.max_results])


class DataCitePublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="datacite_public_135",
        label="DataCite public DOI metadata",
        provider_type="scholarly_metadata",
        allowed_hosts=("api.datacite.org",),
        rate_limit_per_minute=30,
        min_interval_seconds=0.25,
        terms_profile="Official public DataCite API; creator-name matches require independent review.",
        metadata={"build": "135.0", "input_types": ["name", "organisation", "identifier"]},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://api.datacite.org/dois?" + urlencode({
            "query": f'creators.name:"{request.query.strip()}"',
            "page[size]": str(min(request.max_results, 50)),
        }), headers={"Accept": "application/vnd.api+json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        out: list[NormalizedProviderItem] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            attrs = item.get("attributes") or {}
            titles = attrs.get("titles") or []
            title = str((titles[0] or {}).get("title") if titles and isinstance(titles[0], dict) else item.get("id") or request.query)
            creators = ", ".join(str(c.get("name") or "") for c in (attrs.get("creators") or [])[:10] if isinstance(c, dict))
            doi = str(attrs.get("doi") or item.get("id") or "")
            url = str(attrs.get("url") or (f"https://doi.org/{doi}" if doi else response.final_url))
            out.append(NormalizedProviderItem(title=title, url=url, snippet="; ".join(x for x in [creators, str(attrs.get("publisher") or ""), str(attrs.get("published") or "")] if x), source_type="public_scholarly_metadata", published_at=str(attrs.get("published") or ""), raw_payload=item))
        return tuple(out[:request.max_results])



class BlueskyActorSearchPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="bluesky_actor_search_public_147",
        label="Bluesky public actor search",
        provider_type="public_social_profile",
        allowed_hosts=("public.api.bsky.app",),
        rate_limit_per_minute=30,
        min_interval_seconds=0.25,
        terms_profile="Official public Bluesky AppView actor search; profile results are candidate-only.",
        metadata={"build": "147.0", "input_types": ["name", "username", "keyword"], "no_auth": True},
    )

    def validate_request(self, request: ProviderRunRequest) -> None:
        super().validate_request(request)
        query = request.query.strip()
        if len(query) > 200 or any(ord(ch) < 32 for ch in query):
            raise ProviderValidationError("invalid Bluesky search query")

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://public.api.bsky.app/xrpc/app.bsky.actor.searchActors?" + urlencode({
            "q": request.query.strip(), "limit": str(min(request.max_results, 100)),
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.get("actors", []) if isinstance(payload, dict) else []
        out: list[NormalizedProviderItem] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            handle = str(item.get("handle") or "").strip()
            did = str(item.get("did") or "").strip()
            if not handle and not did:
                continue
            profile_key = handle or did
            url = f"https://bsky.app/profile/{quote(profile_key, safe=':.-_')}"
            display = str(item.get("displayName") or handle or did)
            description = str(item.get("description") or "")
            snippet = " | ".join(part for part in (handle, did, description) if part)
            out.append(NormalizedProviderItem(title=f"Bluesky profile candidate: {display}", url=url, snippet=snippet, source_type="public_social_profile", raw_payload=item))
        return tuple(out[:request.max_results])


class MastodonSocialSearchPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="mastodon_social_search_public_147",
        label="Mastodon.social public account search",
        provider_type="public_social_profile",
        allowed_hosts=("mastodon.social",),
        rate_limit_per_minute=20,
        min_interval_seconds=0.35,
        terms_profile="Official Mastodon v2 public search on mastodon.social; status full-text search is not performed.",
        metadata={"build": "147.0", "input_types": ["name", "username", "hashtag"], "instance_scope": "mastodon.social"},
    )

    def validate_request(self, request: ProviderRunRequest) -> None:
        super().validate_request(request)
        query = request.query.strip()
        if len(query) > 200 or any(ord(ch) < 32 for ch in query):
            raise ProviderValidationError("invalid Mastodon search query")

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://mastodon.social/api/v2/search?" + urlencode({
            "q": request.query.strip(), "type": "accounts", "limit": str(min(request.max_results, 40)), "resolve": "false",
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.get("accounts", []) if isinstance(payload, dict) else []
        out: list[NormalizedProviderItem] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            acct = str(item.get("acct") or item.get("username") or "").strip()
            url = str(item.get("url") or "").strip()
            if not acct or not url.startswith("https://"):
                continue
            display = str(item.get("display_name") or acct)
            note = re.sub(r"<[^>]+>", " ", str(item.get("note") or ""))
            snippet = " | ".join(part for part in (acct, re.sub(r"\s+", " ", note).strip()) if part)
            out.append(NormalizedProviderItem(title=f"Mastodon profile candidate: {display}", url=url, snippet=snippet, source_type="public_social_profile", raw_payload=item))
        return tuple(out[:request.max_results])


# -------------------- Build 149 data ecosystem adapters --------------------

def _xml_root(response: ProviderTransportResponse):
    """Parse bounded, non-DTD XML returned by an allowlisted public provider."""
    import xml.etree.ElementTree as ET

    body = response.body
    probe = body[:4096].upper()
    if b"<!DOCTYPE" in probe or b"<!ENTITY" in probe:
        raise ProviderValidationError("provider XML with DTD/entities is prohibited")
    try:
        return ET.fromstring(body)
    except ET.ParseError as exc:
        raise ProviderValidationError("provider returned invalid XML") from exc


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


class DblpAuthorsPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="dblp_authors_public_149",
        label="DBLP public author search",
        provider_type="scholarly_identity",
        allowed_hosts=("dblp.org",),
        rate_limit_per_minute=20,
        min_interval_seconds=0.35,
        terms_profile="Official DBLP author search API; names and publication profiles remain candidate-only.",
        metadata={"build": "149.0", "input_types": ["name"], "official_api": True},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://dblp.org/search/author/api?" + urlencode({
            "q": request.query.strip(), "format": "json", "h": str(min(request.max_results, 100)),
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        hits = (((payload or {}).get("result") or {}).get("hits") or {}).get("hit", []) if isinstance(payload, dict) else []
        if isinstance(hits, dict):
            hits = [hits]
        out: list[NormalizedProviderItem] = []
        for hit in hits or []:
            info = hit.get("info") if isinstance(hit, dict) else None
            if not isinstance(info, dict):
                continue
            name = str(info.get("author") or request.query)
            url = str(info.get("url") or response.final_url)
            notes = info.get("notes") or {}
            note = str(notes.get("note") or "") if isinstance(notes, dict) else str(notes or "")
            out.append(NormalizedProviderItem(
                title=f"DBLP author candidate: {name}", url=url,
                snippet="; ".join(x for x in [str(info.get("aliases") or ""), note] if x),
                source_type="public_scholarly_identity", raw_payload=info,
            ))
        return tuple(out[:request.max_results])


class SemanticScholarAuthorsPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="semantic_scholar_authors_public_149",
        label="Semantic Scholar public author search",
        provider_type="scholarly_identity",
        allowed_hosts=("api.semanticscholar.org",),
        rate_limit_per_minute=15,
        min_interval_seconds=0.5,
        terms_profile="Official Semantic Scholar Academic Graph author search; API key may raise quotas but is not sent by this public adapter.",
        metadata={"build": "149.0", "input_types": ["name", "organisation"], "official_api": True},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://api.semanticscholar.org/graph/v1/author/search?" + urlencode({
            "query": request.query.strip(), "limit": str(min(request.max_results, 100)),
            "fields": "name,url,affiliations,paperCount,citationCount,hIndex",
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        out: list[NormalizedProviderItem] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or request.query)
            author_id = str(item.get("authorId") or "")
            url = str(item.get("url") or (f"https://www.semanticscholar.org/author/{quote(author_id, safe='')}" if author_id else response.final_url))
            affiliations = ", ".join(str(x) for x in (item.get("affiliations") or [])[:8])
            snippet = "; ".join(x for x in [affiliations, f"papers: {item.get('paperCount', 0)}", f"citations: {item.get('citationCount', 0)}", f"h-index: {item.get('hIndex', 0)}"] if x)
            out.append(NormalizedProviderItem(title=f"Semantic Scholar author candidate: {name}", url=url, snippet=snippet, source_type="public_scholarly_identity", raw_payload=item))
        return tuple(out[:request.max_results])


class ArxivAuthorPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="arxiv_author_public_149",
        label="arXiv public author search",
        provider_type="scholarly_metadata",
        allowed_hosts=("export.arxiv.org", "arxiv.org"),
        rate_limit_per_minute=10,
        min_interval_seconds=1.0,
        timeout_seconds=30,
        terms_profile="Official arXiv API query by author; metadata matches remain candidate-only.",
        metadata={"build": "149.0", "input_types": ["name"], "official_api": True},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        query = request.query.strip().replace('"', "")
        return (ProviderHttpRequest("https://export.arxiv.org/api/query?" + urlencode({
            "search_query": f'au:"{query}"', "start": "0", "max_results": str(min(request.max_results, 50)),
        }), headers={"Accept": "application/atom+xml"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        root = _xml_root(response)
        out: list[NormalizedProviderItem] = []
        for entry in root.iter():
            if _local_name(entry.tag) != "entry":
                continue
            children = {_local_name(child.tag): child for child in list(entry)}
            title = re.sub(r"\s+", " ", str((children.get("title").text if children.get("title") is not None else "") or request.query)).strip()
            url = str((children.get("id").text if children.get("id") is not None else "") or response.final_url)
            published = str((children.get("published").text if children.get("published") is not None else "") or "")
            authors = [re.sub(r"\s+", " ", str(node.text or "")).strip() for node in entry.iter() if _local_name(node.tag) == "name"]
            summary = re.sub(r"\s+", " ", str((children.get("summary").text if children.get("summary") is not None else "") or "")).strip()
            out.append(NormalizedProviderItem(title=title, url=url, snippet="; ".join(x for x in [", ".join(authors[:10]), summary[:700]] if x), source_type="public_scholarly_metadata", published_at=published, raw_payload={"title": title, "authors": authors, "published": published, "summary": summary[:5000]}))
        return tuple(out[:request.max_results])


class NcbiPubmedAuthorPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="ncbi_pubmed_author_public_149",
        label="NCBI PubMed author search",
        provider_type="biomedical_literature",
        allowed_hosts=("eutils.ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov"),
        rate_limit_per_minute=10,
        min_interval_seconds=0.4,
        terms_profile="Official NCBI E-utilities PubMed search; identifiers are candidates and require citation review.",
        metadata={"build": "149.0", "input_types": ["name"], "official_api": True},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        query = request.query.strip().replace("[", "").replace("]", "")
        return (ProviderHttpRequest("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urlencode({
            "db": "pubmed", "term": f'"{query}"[Author]', "retmode": "json", "retmax": str(min(request.max_results, 100)),
            "tool": "EagleEyePersonOSINT",
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        result = payload.get("esearchresult", {}) if isinstance(payload, dict) else {}
        ids = result.get("idlist", []) if isinstance(result, dict) else []
        return tuple(NormalizedProviderItem(
            title=f"PubMed author-query candidate PMID {pmid}",
            url=f"https://pubmed.ncbi.nlm.nih.gov/{quote(str(pmid), safe='')}/",
            snippet=f"Author query: {request.query}; PMID: {pmid}",
            source_type="public_biomedical_literature", raw_payload={"pmid": str(pmid), "query_translation": result.get("querytranslation", "")},
        ) for pmid in ids[:request.max_results])


class ZenodoRecordsPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="zenodo_records_public_149",
        label="Zenodo public records search",
        provider_type="research_repository",
        allowed_hosts=("zenodo.org",),
        rate_limit_per_minute=20,
        min_interval_seconds=0.4,
        terms_profile="Official Zenodo published-record search; anonymous requests are rate-limited and records remain candidates.",
        metadata={"build": "149.0", "input_types": ["name", "organisation", "keyword", "identifier"], "official_api": True},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://zenodo.org/api/records?" + urlencode({
            "q": request.query.strip(), "size": str(min(request.max_results, 25)), "sort": "bestmatch",
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        hits_obj = payload.get("hits", {}) if isinstance(payload, dict) else {}
        rows = hits_obj.get("hits", []) if isinstance(hits_obj, dict) else (payload if isinstance(payload, list) else [])
        out: list[NormalizedProviderItem] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            meta = item.get("metadata") or {}
            title = str(meta.get("title") or item.get("id") or request.query)
            creators = ", ".join(str(c.get("name") or "") for c in (meta.get("creators") or [])[:10] if isinstance(c, dict))
            links = item.get("links") or {}
            url = str(links.get("html") or links.get("self_html") or item.get("doi_url") or response.final_url)
            out.append(NormalizedProviderItem(title=title, url=url, snippet="; ".join(x for x in [creators, str(meta.get("publication_date") or ""), str(meta.get("doi") or "")] if x), source_type="public_research_repository", published_at=str(meta.get("publication_date") or ""), raw_payload=item))
        return tuple(out[:request.max_results])


class HalPublicationsPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="hal_publications_public_149",
        label="HAL public repository search",
        provider_type="research_repository",
        allowed_hosts=("api.archives-ouvertes.fr", "hal.science"),
        rate_limit_per_minute=20,
        min_interval_seconds=0.4,
        terms_profile="Official HAL search API; author and affiliation fields are public metadata and remain candidate-only.",
        metadata={"build": "149.0", "input_types": ["name", "organisation", "keyword"], "official_api": True},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://api.archives-ouvertes.fr/search/?" + urlencode({
            "q": request.query.strip(), "wt": "json", "rows": str(min(request.max_results, 100)),
            "fl": "docid,title_s,authFullName_s,producedDateY_i,uri_s,doiId_s,structName_s",
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = ((payload or {}).get("response") or {}).get("docs", []) if isinstance(payload, dict) else []
        out: list[NormalizedProviderItem] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            title_value = item.get("title_s") or request.query
            title = str(title_value[0] if isinstance(title_value, list) and title_value else title_value)
            authors = item.get("authFullName_s") or []
            if not isinstance(authors, list):
                authors = [authors]
            structures = item.get("structName_s") or []
            if not isinstance(structures, list):
                structures = [structures]
            url = str(item.get("uri_s") or response.final_url)
            out.append(NormalizedProviderItem(title=title, url=url, snippet="; ".join(x for x in [", ".join(str(x) for x in authors[:10]), ", ".join(str(x) for x in structures[:6]), str(item.get("producedDateY_i") or ""), str(item.get("doiId_s") or "")] if x), source_type="public_research_repository", published_at=str(item.get("producedDateY_i") or ""), raw_payload=item))
        return tuple(out[:request.max_results])


class LibraryOfCongressPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="library_of_congress_public_149",
        label="Library of Congress public search",
        provider_type="public_archive_catalog",
        allowed_hosts=("www.loc.gov",),
        rate_limit_per_minute=15,
        min_interval_seconds=0.5,
        terms_profile="Official loc.gov JSON API; heterogeneous catalog metadata may be incomplete and requires source review.",
        metadata={"build": "149.0", "input_types": ["name", "organisation", "keyword", "location"], "official_api": True},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://www.loc.gov/search/?" + urlencode({
            "q": request.query.strip(), "fo": "json", "c": str(min(request.max_results, 50)), "at": "results,pagination",
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.get("results", []) if isinstance(payload, dict) else []
        out: list[NormalizedProviderItem] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or request.query)
            url = str(item.get("id") or item.get("url") or response.final_url)
            contributors = item.get("contributor") or item.get("contributors") or []
            if not isinstance(contributors, list):
                contributors = [contributors]
            dates = item.get("date") or item.get("dates") or ""
            out.append(NormalizedProviderItem(title=title, url=url, snippet="; ".join(x for x in [", ".join(str(x) for x in contributors[:10]), str(dates), str(item.get("description") or "")[:700]] if x), source_type="public_archive_catalog", published_at=str(dates), raw_payload=item))
        return tuple(out[:request.max_results])


class StackExchangeUsersPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="stackexchange_users_public_149",
        label="Stack Exchange public users search",
        provider_type="technical_community_profile",
        allowed_hosts=("api.stackexchange.com", "stackoverflow.com"),
        rate_limit_per_minute=20,
        min_interval_seconds=0.35,
        terms_profile="Official Stack Exchange API user-name filtering on Stack Overflow; name equality is not identity proof.",
        metadata={"build": "149.0", "input_types": ["name", "username"], "official_api": True},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://api.stackexchange.com/2.3/users?" + urlencode({
            "site": "stackoverflow", "inname": request.query.strip(), "pagesize": str(min(request.max_results, 100)), "order": "desc", "sort": "reputation",
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.get("items", []) if isinstance(payload, dict) else []
        out: list[NormalizedProviderItem] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("display_name") or request.query)
            url = str(item.get("link") or response.final_url)
            out.append(NormalizedProviderItem(title=f"Stack Overflow user candidate: {name}", url=url, snippet="; ".join(x for x in [str(item.get("location") or ""), str(item.get("website_url") or ""), f"reputation: {item.get('reputation', 0)}"] if x), source_type="public_technical_profile", raw_payload=item))
        return tuple(out[:request.max_results])


class GdeltDocPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="gdelt_doc_public_149",
        label="GDELT DOC public news search",
        provider_type="news_archive",
        allowed_hosts=("api.gdeltproject.org",),
        rate_limit_per_minute=10,
        min_interval_seconds=1.0,
        terms_profile="Official GDELT DOC API; article results are media candidates and source independence must be assessed.",
        metadata={"build": "149.0", "input_types": ["name", "organisation", "keyword", "location"], "official_api": True},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://api.gdeltproject.org/api/v2/doc/doc?" + urlencode({
            "query": request.query.strip(), "mode": "ArtList", "format": "json", "maxrecords": str(min(request.max_results, 250)), "sort": "HybridRel",
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.get("articles", []) if isinstance(payload, dict) else []
        out: list[NormalizedProviderItem] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or request.query)
            url = str(item.get("url") or response.final_url)
            snippet = "; ".join(x for x in [str(item.get("domain") or ""), str(item.get("sourcecountry") or ""), str(item.get("language") or ""), str(item.get("seendate") or "")] if x)
            out.append(NormalizedProviderItem(title=title, url=url, snippet=snippet, source_type="public_news_candidate", published_at=str(item.get("seendate") or ""), raw_payload=item))
        return tuple(out[:request.max_results])


class WikimediaCommonsPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="wikimedia_commons_public_149",
        label="Wikimedia Commons public media search",
        provider_type="public_media_archive",
        allowed_hosts=("commons.wikimedia.org", "upload.wikimedia.org"),
        rate_limit_per_minute=15,
        min_interval_seconds=0.5,
        terms_profile="Official MediaWiki API on Wikimedia Commons; media identity and licensing require manual review.",
        metadata={"build": "149.0", "input_types": ["name", "organisation", "keyword", "location"], "official_api": True, "automatic_download": False},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://commons.wikimedia.org/w/api.php?" + urlencode({
            "action": "query", "generator": "search", "gsrsearch": request.query.strip(), "gsrnamespace": "6",
            "gsrlimit": str(min(request.max_results, 50)), "prop": "imageinfo", "iiprop": "url|extmetadata", "format": "json", "formatversion": "2",
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = ((payload or {}).get("query") or {}).get("pages", []) if isinstance(payload, dict) else []
        if isinstance(rows, dict):
            rows = list(rows.values())
        out: list[NormalizedProviderItem] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            info = (item.get("imageinfo") or [{}])[0]
            if not isinstance(info, dict):
                info = {}
            metadata = info.get("extmetadata") or {}
            page_id = item.get("pageid")
            url = f"https://commons.wikimedia.org/?curid={page_id}" if page_id else str(info.get("descriptionurl") or response.final_url)
            artist = ((metadata.get("Artist") or {}).get("value") if isinstance(metadata.get("Artist"), dict) else "")
            license_name = ((metadata.get("LicenseShortName") or {}).get("value") if isinstance(metadata.get("LicenseShortName"), dict) else "")
            out.append(NormalizedProviderItem(title=str(item.get("title") or request.query), url=url, snippet="; ".join(x for x in [re.sub(r"<[^>]+>", " ", str(artist)), str(license_name), str(info.get("url") or "")] if x), source_type="public_media_candidate", raw_payload={"page": item, "imageinfo": info}))
        return tuple(out[:request.max_results])


class RipeStatWhoisPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="ripestat_whois_public_149",
        label="RIPEstat public Whois",
        provider_type="network_infrastructure",
        allowed_hosts=("stat.ripe.net",),
        rate_limit_per_minute=20,
        min_interval_seconds=0.35,
        terms_profile="Official RIPEstat Data API; infrastructure records do not establish control by a person.",
        metadata={"build": "149.0", "input_types": ["domain", "ip", "asn"], "official_api": True},
    )

    def validate_request(self, request: ProviderRunRequest) -> None:
        super().validate_request(request)
        query = request.query.strip()
        if len(query) > 253 or any(ord(ch) < 32 for ch in query):
            raise ProviderValidationError("invalid RIPEstat resource")

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://stat.ripe.net/data/whois/data.json?" + urlencode({"resource": request.query.strip()}), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        records = data.get("records", []) if isinstance(data, dict) else []
        snippets: list[str] = []
        for group in records[:20] if isinstance(records, list) else []:
            if not isinstance(group, list):
                continue
            for item in group[:20]:
                if isinstance(item, dict):
                    key = str(item.get("key") or "")
                    value = str(item.get("value") or "")
                    if key and value:
                        snippets.append(f"{key}: {value}")
        return (NormalizedProviderItem(title=f"RIPEstat Whois candidate: {request.query}", url=response.final_url, snippet="; ".join(snippets[:30]), source_type="public_network_registry", raw_payload=data if isinstance(data, dict) else {"data": data}),)


class DnbSruPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="dnb_sru_public_149",
        label="Deutsche Nationalbibliothek SRU",
        provider_type="national_library_catalog",
        allowed_hosts=("services.dnb.de", "portal.dnb.de"),
        rate_limit_per_minute=15,
        min_interval_seconds=0.5,
        terms_profile="Official DNB SRU catalog interface; bibliographic matches remain candidates.",
        metadata={"build": "149.0", "input_types": ["name", "organisation", "keyword", "identifier"], "official_api": True},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://services.dnb.de/sru/dnb?" + urlencode({
            "version": "1.1", "operation": "searchRetrieve", "query": request.query.strip(),
            "recordSchema": "MARC21-xml", "maximumRecords": str(min(request.max_results, 50)),
        }), headers={"Accept": "application/xml"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        root = _xml_root(response)
        out: list[NormalizedProviderItem] = []
        for record in root.iter():
            if _local_name(record.tag) != "recordData":
                continue
            title = ""; authors: list[str] = []; identifiers: list[str] = []
            for node in record.iter():
                tag = _local_name(node.tag)
                code = str(node.attrib.get("code") or "")
                parent_tag = _local_name(record.tag)
                value = re.sub(r"\s+", " ", str(node.text or "")).strip()
                if not value:
                    continue
                if tag == "subfield" and code == "a":
                    # MARC control is deliberately heuristic; it remains candidate-only.
                    if not title:
                        title = value
                    elif len(authors) < 8:
                        authors.append(value)
                elif tag == "controlfield" and str(node.attrib.get("tag") or "") in {"001", "003"}:
                    identifiers.append(value)
            if not title:
                title = f"DNB catalog candidate: {request.query}"
            ident = identifiers[0] if identifiers else ""
            url = f"https://d-nb.info/{quote(ident, safe='')}" if ident else response.final_url
            out.append(NormalizedProviderItem(title=title, url=url, snippet="; ".join(x for x in [", ".join(authors[:8]), ", ".join(identifiers[:4])] if x), source_type="public_national_library_catalog", raw_payload={"title": title, "authors": authors, "identifiers": identifiers}))
        return tuple(out[:request.max_results])


class ViafAutoSuggestPublicAdapter(ProviderAdapter):
    definition = ProviderDefinition(
        provider_key="viaf_autosuggest_public_149",
        label="VIAF public authority search",
        provider_type="authority_identity",
        allowed_hosts=("viaf.org",),
        rate_limit_per_minute=15,
        min_interval_seconds=0.5,
        terms_profile="Public VIAF autosuggest endpoint; authority records aggregate library data and require identity review.",
        metadata={"build": "149.0", "input_types": ["name"], "official_public_endpoint": True},
    )

    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        return (ProviderHttpRequest("https://viaf.org/viaf/AutoSuggest?" + urlencode({"query": request.query.strip()}), headers={"Accept": "application/json"}),)

    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        payload = _json(response)
        rows = payload.get("result", []) if isinstance(payload, dict) else []
        out: list[NormalizedProviderItem] = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            viafid = str(item.get("viafid") or "")
            term = str(item.get("term") or request.query)
            url = f"https://viaf.org/viaf/{quote(viafid, safe='')}/" if viafid else response.final_url
            out.append(NormalizedProviderItem(title=f"VIAF authority candidate: {term}", url=url, snippet="; ".join(x for x in [str(item.get("nametype") or ""), str(item.get("score") or "")] if x), source_type="public_authority_identity", raw_payload=item))
        return tuple(out[:request.max_results])


def default_adapters() -> tuple[ProviderAdapter, ...]:
    return (
        RdapPublicAdapter(),
        GithubPublicProfileAdapter(),
        GitlabPublicProfileAdapter(),
        WaybackCdxPublicAdapter(),
        CrossrefWorksPublicAdapter(),
        OpenAlexAuthorsPublicAdapter(),
        InternetArchivePublicAdapter(),
        WikidataEntitiesPublicAdapter(),
        EuropePmcPublicAdapter(),
        OpenLibraryAuthorsPublicAdapter(),
        GleifLeiPublicAdapter(),
        SecEdgarPublicAdapter(),
        GoogleBooksPublicAdapter(),
        CourtListenerPublicAdapter(),
        DataCitePublicAdapter(),
        BlueskyActorSearchPublicAdapter(),
        MastodonSocialSearchPublicAdapter(),
        DblpAuthorsPublicAdapter(),
        SemanticScholarAuthorsPublicAdapter(),
        ArxivAuthorPublicAdapter(),
        NcbiPubmedAuthorPublicAdapter(),
        ZenodoRecordsPublicAdapter(),
        HalPublicationsPublicAdapter(),
        LibraryOfCongressPublicAdapter(),
        StackExchangeUsersPublicAdapter(),
        GdeltDocPublicAdapter(),
        WikimediaCommonsPublicAdapter(),
        RipeStatWhoisPublicAdapter(),
        DnbSruPublicAdapter(),
        ViafAutoSuggestPublicAdapter(),
    )
