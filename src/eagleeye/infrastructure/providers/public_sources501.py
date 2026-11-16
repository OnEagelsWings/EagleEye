"""Free public sources using the canonical bounded, review-only provider contract.

No credentials, scraped contact directories, automatic identity merges or graph
writes. Returned records are source-local candidates, not statements of truth.
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote, urlencode

from .contracts import (
    NormalizedProviderItem, ProviderAdapter, ProviderDefinition, ProviderHttpRequest,
    ProviderRunRequest, ProviderTransportResponse, ProviderValidationError,
)


def _object(response):
    try:
        data = json.loads(response.body.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise ProviderValidationError("Source returned invalid JSON") from exc
    if not isinstance(data, dict) or data.get("error"):
        raise ProviderValidationError("Source returned an error or unexpected JSON")
    return data


def _rows(value):
    if not isinstance(value, list):
        raise ProviderValidationError("Source result list is missing or malformed")
    return [row for row in value if isinstance(row, dict)]


def _text(value, limit=800):
    return " ".join(str(value or "").split())[:limit]


def _phrase(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _definition(key, label, kind, host, documentation, license_note, **options):
    return ProviderDefinition(
        provider_key=key, label=label, provider_type=kind, allowed_hosts=(host,),
        rate_limit_per_minute=options.pop("rate", 15),
        min_interval_seconds=options.pop("interval", 1.0),
        terms_profile=license_note,
        metadata={"build": "501-source-expansion", "documentation": documentation,
                  "candidate_only": True, "input_types": options.pop("inputs", ["keyword"])},
        **options,
    )


class LobidGndPersonsAdapter(ProviderAdapter):
    definition = _definition(
        "lobid_gnd_persons_public_501", "GND / lobid – Personen", "authority_identity",
        "lobid.org", "https://lobid.org/gnd/api", "CC0; bibliographic person candidates; identity review required.",
        inputs=["name", "alias"],
    )

    def build_requests(self, request):
        # Search names rather than matching the name in arbitrary biographies.
        names = " AND ".join(_phrase(part) for part in request.query.split())
        return (ProviderHttpRequest("https://lobid.org/gnd/search?" + urlencode({
            "q": "preferredName:(" + names + ") OR variantName:(" + names + ")",
            "filter": "type:DifferentiatedPerson", "format": "json", "size": min(request.max_results, 50),
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response, request):
        out = []
        for row in _rows(_object(response).get("member"))[:request.max_results]:
            if "DifferentiatedPerson" not in row.get("type", []):
                continue
            source_id = _text(row.get("gndIdentifier"), 120)
            if not source_id:
                continue
            name = _text(row.get("preferredName"), 300)
            variants = [_text(x, 180) for x in (row.get("variantName") or [])[:12] if isinstance(x, str)]
            occupations = [_text(x.get("label"), 120) for x in _rows(row.get("professionOrOccupation", []))[:8]]
            # Deliberate field allowlist: no birth dates, gender, private contacts,
            # family links or sensitive attributes from the full authority record.
            selected = {"source_record_id": source_id, "name": name, "aliases": variants,
                        "occupations": occupations, "license": "CC0", "identity_confirmed": False}
            out.append(NormalizedProviderItem(
                title="GND-Personenkandidat: " + name,
                url="https://d-nb.info/gnd/" + quote(source_id, safe="-"),
                snippet="; ".join(["GND: " + source_id, ", ".join(occupations), "Varianten: " + ", ".join(variants)]),
                source_type="public_authority_identity", raw_payload=selected,
            ))
        return tuple(out)


class AbgeordnetenwatchPersonsAdapter(ProviderAdapter):
    definition = _definition(
        "abgeordnetenwatch_persons_public_501", "Abgeordnetenwatch – öffentliche Mandatsträger", "public_office",
        "www.abgeordnetenwatch.de", "https://www.abgeordnetenwatch.de/api", "CC0; public-office candidates; roles may be historical.",
        inputs=["name"], interval=2.1, rate=28,
    )

    def build_requests(self, request):
        return (ProviderHttpRequest("https://www.abgeordnetenwatch.de/api/v2/politicians?" + urlencode({
            "label[cn]": request.query.strip(), "range_end": min(request.max_results, 50),
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response, request):
        data = _object(response)
        if data.get("meta", {}).get("status") != "ok":
            raise ProviderValidationError("Abgeordnetenwatch returned an unsuccessful response")
        out = []
        for row in _rows(data.get("data"))[:request.max_results]:
            url = _text(row.get("abgeordnetenwatch_url"), 2000)
            if not url.startswith("https://www.abgeordnetenwatch.de/"):
                continue
            selected = {k: row[k] for k in ("id", "label", "occupation", "qid_wikidata", "ext_id_bundestagsverwaltung") if k in row}
            selected.update(license="CC0", identity_confirmed=False, role_currency="not independently checked")
            out.append(NormalizedProviderItem(
                title="Öffentlicher Personenkandidat: " + _text(row.get("label"), 300), url=url,
                snippet="; ".join(x for x in [_text(row.get("occupation")), "Rolle und Zeitraum im Original prüfen", _text(row.get("qid_wikidata"))] if x),
                source_type="public_office_candidate", raw_payload=selected,
            ))
        return tuple(out)


class HdxCatalogAdapter(ProviderAdapter):
    definition = _definition(
        "hdx_catalog_public_501", "HDX – humanitäre Datensätze", "humanitarian_catalog",
        "data.humdata.org", "https://centre.humdata.org/ufaqs/about-the-humanitarian-data-exchange-api/",
        "Free public catalog; license and access rights are dataset-specific; no automatic attachment download.",
    )

    def build_requests(self, request):
        return (ProviderHttpRequest("https://data.humdata.org/api/3/action/package_search?" + urlencode({
            "q": request.query.strip(), "rows": min(request.max_results, 50),
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response, request):
        data = _object(response)
        if data.get("success") is not True:
            raise ProviderValidationError("HDX search was not successful")
        out = []
        for row in _rows((data.get("result") or {}).get("results"))[:request.max_results]:
            if row.get("private") or not row.get("name"):
                continue
            selected = {k: row.get(k) for k in ("id", "title", "name", "license_id", "license_title", "metadata_modified", "dataset_source", "caveats")}
            selected["resources"] = [{k: r.get(k) for k in ("id", "name", "format", "url")} for r in _rows(row.get("resources", []))[:20]]
            out.append(NormalizedProviderItem(
                title=_text(row.get("title"), 500),
                url="https://data.humdata.org/dataset/" + quote(str(row["name"]), safe="-"),
                snippet="; ".join(x for x in [_text(row.get("dataset_source")), _text(row.get("license_title")), _text(row.get("notes"), 800)] if x),
                source_type="public_dataset_catalog", raw_payload=selected,
            ))
        return tuple(out)


class CrossrefTopicsAdapter(ProviderAdapter):
    definition = _definition(
        "crossref_topics_public_501", "Crossref – Themen und Veröffentlichungen", "scholarly_metadata",
        "api.crossref.org", "https://www.crossref.org/documentation/retrieve-metadata/rest-api/",
        "Free bibliographic metadata; abstract and full-text rights remain with the original source.",
    )

    def build_requests(self, request):
        return (ProviderHttpRequest("https://api.crossref.org/works?" + urlencode({
            "query.bibliographic": request.query.strip(), "rows": min(request.max_results, 50),
            "select": "DOI,title,author,published,URL,publisher,type",
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response, request):
        out = []
        for row in _rows((_object(response).get("message") or {}).get("items"))[:request.max_results]:
            doi = _text(row.get("DOI"), 300)
            if not doi:
                continue
            titles = row.get("title") or [doi]
            authors = [_text(" ".join([str(a.get("given") or ""), str(a.get("family") or "")]), 180) for a in _rows(row.get("author", []))[:12]]
            date_parts = (row.get("published") or {}).get("date-parts") or []
            published = "-".join(str(x) for x in date_parts[0]) if date_parts and isinstance(date_parts[0], list) else ""
            out.append(NormalizedProviderItem(
                title=_text(titles[0], 800), url="https://doi.org/" + quote(doi, safe="/"),
                snippet="; ".join([", ".join(authors), _text(row.get("publisher")), published]),
                published_at=published, source_type="public_scholarly_metadata", raw_payload=row,
            ))
        return tuple(out)


class OpenAlexWorksAdapter(ProviderAdapter):
    definition = _definition(
        "openalex_works_public_501", "OpenAlex – Forschungsarbeiten", "scholarly_metadata",
        "api.openalex.org", "https://help.openalex.org/api/authentication/",
        "Free keyless quota only; no paid fallback; publisher full-text licenses apply separately.",
        rate=10, interval=5.0,
    )

    def build_requests(self, request):
        return (ProviderHttpRequest("https://api.openalex.org/works?" + urlencode({
            "search": request.query.strip(), "per_page": min(request.max_results, 25),
            "select": "id,doi,title,publication_date,authorships,primary_location,open_access",
        }), headers={"Accept": "application/json"}),)

    def normalize(self, response, request):
        out = []
        for row in _rows(_object(response).get("results"))[:request.max_results]:
            source_id = str(row.get("id") or "")
            if not re.fullmatch(r"https://openalex.org/W\d+", source_id):
                continue
            authors = [_text((a.get("author") or {}).get("display_name"), 180) for a in _rows(row.get("authorships", []))[:12]]
            out.append(NormalizedProviderItem(
                title=_text(row.get("title"), 800), url=source_id,
                snippet="; ".join([", ".join(authors), _text(row.get("publication_date")), _text(row.get("doi"))]),
                published_at=_text(row.get("publication_date")), source_type="public_scholarly_metadata",
                raw_payload={k: row[k] for k in ("id", "doi", "title", "publication_date", "primary_location", "open_access") if k in row},
            ))
        return tuple(out)


class CommonCrawlIndexAdapter(ProviderAdapter):
    definition = _definition(
        "commoncrawl_index_public_501", "Common Crawl – URL-Archivindex", "web_archive",
        "index.commoncrawl.org", "https://index.commoncrawl.org/",
        "Free archive index; query requires an explicit crawl collection and public URL; original content rights apply.",
        inputs=["crawl_collection_and_url"], rate=6, interval=10.0,
        supports_replay=False,
    )

    @staticmethod
    def parts(query):
        from .policy import PublicEndpointPolicy
        match = re.fullmatch(r"(CC-MAIN-20\d{2}-\d{2})\s+(https?://\S+)", query.strip())
        if not match:
            raise ProviderValidationError("Common Crawl expects CC-MAIN-YYYY-NN https://public.example/page")
        PublicEndpointPolicy().validate_url(match[2])
        if any(x in match[2] for x in ("*", "[", "]")):
            raise ProviderValidationError("Common Crawl lookup requires one exact public URL")
        return match[1], match[2]

    def validate_request(self, request):
        super().validate_request(request)
        self.parts(request.query)

    def build_requests(self, request):
        collection, url = self.parts(request.query)
        return (ProviderHttpRequest("https://index.commoncrawl.org/" + collection + "-index?" + urlencode({
            "url": url, "matchType": "exact", "output": "json", "filter": "status:200",
        }), headers={"Accept": "application/x-ndjson,application/json"}),)

    def normalize(self, response, request):
        collection, _ = self.parts(request.query)
        out = []
        for line in response.body.decode("utf-8-sig").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError as exc:
                raise ProviderValidationError("Common Crawl returned invalid JSON Lines") from exc
            if not isinstance(row, dict) or not row.get("url"):
                raise ProviderValidationError("Malformed Common Crawl index record")
            filename = str(row.get("filename") or "")
            if not filename.startswith("crawl-data/") or ".." in filename or not filename.endswith(".warc.gz"):
                raise ProviderValidationError("Common Crawl record has no valid archive file")
            selected = {k: row.get(k) for k in ("url", "timestamp", "mime", "status", "digest", "filename", "offset", "length")}
            selected["crawl_collection"] = collection
            selected["archive_file_url"] = "https://data.commoncrawl.org/" + quote(filename, safe="/")
            out.append(NormalizedProviderItem(
                title="Common-Crawl-Archivhinweis: " + _text(row["url"], 500),
                # Opening a candidate should show its index, not download a
                # potentially enormous shared WARC. The exact archive location
                # and byte range remain available in the candidate metadata.
                url=response.requested_url,
                snippet=f"Original: {row['url']}; Archivzeit: {row.get('timestamp', '')}; Sammlung: {collection}",
                source_type="public_web_archive_index", raw_payload=selected,
            ))
            if len(out) >= request.max_results:
                break
        return tuple(out)


def additional_adapters():
    return (LobidGndPersonsAdapter(), AbgeordnetenwatchPersonsAdapter(), HdxCatalogAdapter(),
            CrossrefTopicsAdapter(), OpenAlexWorksAdapter(), CommonCrawlIndexAdapter())
