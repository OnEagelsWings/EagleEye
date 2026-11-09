"""Weitere Online-Quellen (Schritt 1): Wirtschaft, Register, Beziehungen, Domains, Sanktionen.

Jeder Konnektor liefert neben Titel/Ausschnitt strukturierte Aussagen (``claims``), aus denen
das Faktenmodell, der Graph und das Dossier aufgebaut werden.
"""
from __future__ import annotations

import base64
import re
from typing import Any
from urllib.parse import quote, urlencode, urlsplit

from .facts import claim
from .matching import name_similarity
from .sources import Http, Source, SourceError, _clean, api_key

CH_HOST = "api.company-information.service.gov.uk"
CH_WEB = "https://find-and-update.company-information.service.gov.uk"


def _json(resp) -> Any:
    if resp.status == 404:
        return None
    if resp.status != 200:
        raise SourceError(f"HTTP {resp.status}")
    return resp.json()


def _host_of(kind: str, value: str) -> str:
    value = value.strip()
    if kind == "email":
        return value.split("@", 1)[-1].casefold()
    if "://" in value:
        value = urlsplit(value).hostname or ""
    return value.casefold().strip().strip(".").removeprefix("www.")


# --------------------------------------------------------------------------- UK Companies House

def _companies_house(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    key = api_key(http, src.key)
    auth = {"Authorization": "Basic " + base64.b64encode(f"{key}:".encode()).decode()}
    data = _json(src.get(http, f"https://{CH_HOST}/search/officers?" + urlencode({"q": value, "items_per_page": 20}), auth)) or {}
    out = []
    for item in [i for i in data.get("items", []) if name_similarity(i.get("title", ""), value) >= 0.85][:6]:
        name = item.get("title", "")
        dob = item.get("date_of_birth") or {}
        dob_s = f"{dob['year']:04d}-{dob['month']:02d}" if dob.get("year") and dob.get("month") else ""
        claims = []
        if dob_s:
            claims.append(claim("geburtsdatum", dob_s, attrs_precision="Monat"))
        if item.get("address_snippet"):
            claims.append(claim("adresse", item["address_snippet"], "ort"))
        link = (item.get("links") or {}).get("self", "")
        if link:
            appts = _json(src.get(http, f"https://{CH_HOST}{link}?items_per_page=50", auth)) or {}
            for a in appts.get("items", [])[:50]:
                comp = a.get("appointed_to") or {}
                if comp.get("company_name"):
                    claims.append(claim("funktion_bei", comp["company_name"].title(), "organisation", a.get("appointed_on", ""), a.get("resigned_on", ""),
                                        rolle=(a.get("officer_role") or "").replace("-", " "), firmennummer=comp.get("company_number"),
                                        firmenstatus=comp.get("company_status"), register="UK Companies House"))
        roles = sum(1 for c in claims if c["predicate"] == "funktion_bei")
        out.append({"title": f"Companies House: {name}" + (f" (geb. {dob_s})" if dob_s else ""), "url": CH_WEB + link if link else CH_WEB,
                    "snippet": _clean(f"{roles} Funktionen · {item.get('address_snippet', '')}"), "category": "Wirtschaft",
                    "names": [name], "locations": [item.get("address_snippet", "")], "data": {"geburtsdatum": dob_s}, "claims": claims})
    return out


# --------------------------------------------------------------------------- OpenCorporates

def _opencorporates(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    params = {"q": value, "per_page": 30}
    key = api_key(http, src.key)
    if key:
        params["api_token"] = key
    data = _json(src.get(http, "https://api.opencorporates.com/v0.4/officers/search?" + urlencode(params))) or {}
    groups: dict[str, dict] = {}
    for wrap in (data.get("results") or {}).get("officers", []):
        o = wrap.get("officer") or {}
        name = o.get("name") or ""
        if name_similarity(name, value) < 0.85:
            continue
        g = groups.setdefault(name.casefold(), {"name": name.title(), "claims": [], "urls": [], "addr": o.get("address") or ""})
        comp = o.get("company") or {}
        if comp.get("name"):
            g["claims"].append(claim("funktion_bei", comp["name"].title(), "organisation", o.get("start_date") or "", o.get("end_date") or "",
                                     rolle=o.get("position"), firmennummer=comp.get("company_number"), register=f"OpenCorporates ({comp.get('jurisdiction_code', '').upper()})",
                                     quelle_url=comp.get("opencorporates_url")))
        if o.get("date_of_birth"):
            g["claims"].append(claim("geburtsdatum", o["date_of_birth"]))
        if o.get("nationality"):
            g["claims"].append(claim("staatsangehoerigkeit", o["nationality"]))
        if o.get("opencorporates_url"):
            g["urls"].append(o["opencorporates_url"])
    out = []
    for g in groups.values():
        n = sum(1 for c in g["claims"] if c["predicate"] == "funktion_bei")
        out.append({"title": f"OpenCorporates: {g['name']} – {n} Funktion(en)", "url": (g["urls"] or ["https://opencorporates.com/"])[0],
                    "snippet": _clean(", ".join(c["object"] for c in g["claims"] if c["predicate"] == "funktion_bei")),
                    "category": "Wirtschaft", "names": [g["name"]], "locations": [g["addr"]], "claims": g["claims"]})
    return out


# --------------------------------------------------------------------------- GLEIF

def _gleif_record_name(rec: dict) -> str:
    return ((rec.get("attributes") or {}).get("entity") or {}).get("legalName", {}).get("name", "")


def _gleif(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    data = _json(src.get(http, "https://api.gleif.org/api/v1/lei-records?" + urlencode({"filter[fulltext]": value, "page[size]": 5}))) or {}
    out = []
    for rec in data.get("data", [])[:5]:
        attrs = rec.get("attributes") or {}
        ent = attrs.get("entity") or {}
        name = _gleif_record_name(rec)
        lei = attrs.get("lei") or rec.get("id", "")
        addr = ent.get("legalAddress") or {}
        addr_s = ", ".join(x for x in [" ".join(addr.get("addressLines") or []), addr.get("postalCode", ""), addr.get("city", ""), addr.get("country", "")] if x)
        claims = [claim("firmensitz", addr_s, "ort", subject=name, subject_type="organisation"),
                  claim("registriert_als", f"LEI {lei}" + (f" · {ent['registeredAs']}" if ent.get("registeredAs") else ""), subject=name, subject_type="organisation"),
                  claim("firmenstatus", (ent.get("status") or "").lower(), subject=name, subject_type="organisation")]
        for rel, pred in (("direct-parent", "tochter_von"), ("ultimate-parent", "oberste_mutter")):
            parent = _json(src.get(http, f"https://api.gleif.org/api/v1/lei-records/{quote(lei)}/{rel}"))
            if parent and parent.get("data"):
                pname = _gleif_record_name(parent["data"])
                if pname and pname != name:
                    claims.append(claim(pred, pname, "organisation", subject=name, subject_type="organisation", lei=parent["data"].get("id")))
        out.append({"title": f"GLEIF: {name} ({lei})", "url": f"https://search.gleif.org/#/record/{lei}", "snippet": _clean(addr_s),
                    "category": "Wirtschaft", "names": [], "locations": [addr_s], "claims": [c for c in claims if c["object"]],
                    "data": {"lei": lei, "organisation": name}})
    return out


# --------------------------------------------------------------------------- Wikidata (Beziehungen per SPARQL)

WD_PROPS = {
    "P569": ("geburtsdatum", "wert"), "P19": ("geburtsort", "ort"), "P27": ("staatsangehoerigkeit", "wert"), "P21": ("geschlecht", "wert"),
    "P26": ("verheiratet_mit", "person"), "P22": ("elternteil", "person"), "P25": ("elternteil", "person"), "P40": ("kind", "person"),
    "P3373": ("geschwister", "person"), "P108": ("arbeitet_bei", "organisation"), "P463": ("mitglied_von", "organisation"),
    "P102": ("partei", "organisation"), "P69": ("ausbildung", "organisation"), "P39": ("amt", "wert"),
}


def _wikidata_rel(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    found = _json(src.get(http, "https://www.wikidata.org/w/api.php?" + urlencode({
        "action": "wbsearchentities", "search": value, "language": "de", "uselang": "de", "type": "item", "limit": 6, "format": "json"}))) or {}
    items = {i["id"]: i for i in found.get("search", []) if name_similarity(i.get("label", ""), value) >= 0.85}
    if not items:
        return []
    values = " ".join(f"wd:{q}" for q in list(items)[:4])
    props = " ".join(f'("{p}" p:{p} ps:{p})' for p in WD_PROPS)
    query = f"""SELECT ?item ?prop ?value ?valueLabel ?start ?end WHERE {{
  VALUES ?item {{ {values} }}
  ?item wdt:P31 wd:Q5 .
  VALUES (?prop ?p ?ps) {{ {props} }}
  ?item ?p ?st . ?st ?ps ?value .
  OPTIONAL {{ ?st pq:P580 ?start }} OPTIONAL {{ ?st pq:P582 ?end }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
}} LIMIT 400"""
    res = _json(src.get(http, "https://query.wikidata.org/sparql?" + urlencode({"query": query, "format": "json"}),
                        {"Accept": "application/sparql-results+json"})) or {}
    by_item: dict[str, list] = {}
    for b in (res.get("results") or {}).get("bindings", []):
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        pred, otype = WD_PROPS.get(b["prop"]["value"], (None, None))
        if not pred:
            continue
        label = (b.get("valueLabel") or b.get("value") or {}).get("value", "")
        if pred == "geburtsdatum":
            label = label[:10]
        if re.fullmatch(r"Q\d+", label):  # ohne Beschriftung nicht verwertbar
            continue
        by_item.setdefault(qid, []).append(claim(pred, label, otype, (b.get("start") or {}).get("value", "")[:10],
                                                 (b.get("end") or {}).get("value", "")[:10], wikidata=qid))
    out = []
    for qid, claims in by_item.items():
        it = items[qid]
        out.append({"title": f"Wikidata: {it.get('label')} – {it.get('description', '')}".rstrip(" –"), "url": f"https://www.wikidata.org/wiki/{qid}",
                    "snippet": _clean(", ".join(f"{c['predicate'].replace('_', ' ')}: {c['object']}" for c in claims[:8])),
                    "category": "Öffentliche Person", "names": [it.get("label", "")], "claims": claims, "data": {"wikidata_id": qid}})
    return out


# --------------------------------------------------------------------------- crt.sh (Zertifikatstransparenz)

def _crtsh(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    if kind == "email":
        q, label = value.strip(), value.strip()
    else:
        host = _host_of(kind, value)
        if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", host):
            raise SourceError("Keine gültige Domain")
        q, label = f"%.{host}", host
    resp = src.get(http, "https://crt.sh/?" + urlencode({"q": q, "output": "json"}))
    rows = _json(resp) or []
    names: dict[str, str] = {}
    for r in rows[:2000]:
        for n in str(r.get("name_value", "")).split("\n"):
            n = n.strip().casefold().lstrip("*.")
            if n and "@" not in n:
                first = str(r.get("not_before") or r.get("entry_timestamp") or "")[:10]
                if n not in names or first < names[n]:
                    names[n] = first
    if not names:
        return []
    pred = "zertifikat_fuer" if kind == "email" else "subdomain"
    claims = [claim(pred, n, "domain", first, subject=label, subject_type="domain" if kind != "email" else "") for n, first in sorted(names.items())[:60]]
    return [{"title": f"crt.sh: {len(names)} Namen in Zertifikaten für {label}", "url": "https://crt.sh/?" + urlencode({"q": q}),
             "snippet": _clean(", ".join(sorted(names)[:15])), "category": "Online & Technik", "claims": claims, "data": {"domain": label}}]


# --------------------------------------------------------------------------- RDAP (Domain-Register)

def _vcard_fn(entity: dict) -> str:
    for row in (entity.get("vcardArray") or [None, []])[1]:
        if row and row[0] == "fn":
            return str(row[3])
    return ""


def _rdap(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    host = _host_of(kind, value)
    parts = host.split(".")
    domain = ".".join(parts[-2:]) if len(parts) > 2 and parts[-2] not in {"co", "com", "org", "net", "gov", "ac"} else ".".join(parts[-3:]) if len(parts) > 2 else host
    data = _json(src.get(http, f"https://rdap.org/domain/{quote(domain)}", {"Accept": "application/rdap+json"}))
    if not data:
        return []
    claims = []
    for ev in data.get("events", []):
        if ev.get("eventAction") == "registration":
            claims.append(claim("domain_registriert_am", str(ev.get("eventDate", ""))[:10], subject=domain, subject_type="domain"))
    for ent in data.get("entities", []):
        fn = _vcard_fn(ent)
        roles = ent.get("roles") or []
        if fn and "registrar" in roles:
            claims.append(claim("domain_registrar", fn, "organisation", subject=domain, subject_type="domain"))
        if fn and "registrant" in roles and not re.search(r"redacted|privacy|not disclosed", fn, re.I):
            claims.append(claim("domain_inhaber", fn, "person", subject=domain, subject_type="domain"))
    for ns in data.get("nameservers", [])[:6]:
        if ns.get("ldhName"):
            claims.append(claim("nameserver", ns["ldhName"].casefold(), subject=domain, subject_type="domain"))
    return [{"title": f"RDAP: {domain}", "url": f"https://rdap.org/domain/{domain}", "category": "Online & Technik",
             "snippet": _clean("; ".join(f"{c['predicate'].replace('_', ' ')}: {c['object']}" for c in claims)), "claims": claims,
             "data": {"domain": domain, "status": data.get("status", [])}}]


# --------------------------------------------------------------------------- OpenSanctions (online)

def _opensanctions(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    data = _json(src.get(http, "https://api.opensanctions.org/search/default?" + urlencode({"q": value, "limit": 10}),
                         {"Authorization": f"ApiKey {api_key(http, src.key)}"})) or {}
    return [opensanctions_finding(r) for r in data.get("results", []) if name_similarity(r.get("caption", ""), value) >= 0.8]


def opensanctions_finding(r: dict[str, Any], local: bool = False) -> dict[str, Any]:
    props = r.get("properties") or {}
    topics = set(props.get("topics") or []) | set(r.get("topics") or [])
    claims = []
    if "sanction" in topics or r.get("sanctioned"):
        claims.append(claim("sanktioniert", ", ".join(r.get("datasets") or []) or "Sanktionsliste"))
    if any(t.startswith("role.pep") for t in topics) or r.get("pep"):
        claims.append(claim("pep", ", ".join(props.get("position") or []) or "PEP"))
    for d in (props.get("birthDate") or [])[:2]:
        claims.append(claim("geburtsdatum", d))
    for n in (props.get("nationality") or props.get("country") or [])[:3]:
        claims.append(claim("staatsangehoerigkeit", n.upper()))
    for ds in (r.get("datasets") or [])[:5]:
        claims.append(claim("gelistet_in", ds))
    for a in (props.get("alias") or [])[:5]:
        claims.append(claim("alias", a))
    caption = r.get("caption") or r.get("name") or ""
    flag = "SANKTIONIERT" if any(c["predicate"] == "sanktioniert" for c in claims) else "PEP" if any(c["predicate"] == "pep" for c in claims) else "gelistet"
    return {"title": f"OpenSanctions ({flag}): {caption}", "url": f"https://www.opensanctions.org/entities/{r.get('id')}/",
            "snippet": _clean(f"{r.get('schema', '')} · " + ", ".join(r.get("datasets") or [])), "category": "Risiko",
            "names": [caption] + list(props.get("alias") or [])[:3], "claims": claims,
            "data": {"opensanctions_id": r.get("id"), "schema": r.get("schema"), "lokal": local}}


# --------------------------------------------------------------------------- Registrierung

ONLINE_SOURCES: list[Source] = [
    Source("companies_house", "UK Companies House", "Geschäftsführer/Direktoren britischer Firmen mit allen Funktionen, Zeiträumen und Geburtsmonat.",
           ("name",), (CH_HOST,), "Wirtschaft", 1.0, "Wirtschaft & Register", _companies_house, requires_key=True,
           key_help="Kostenloser Schlüssel: developer.company-information.service.gov.uk → „Create an application“ → REST API key.",
           license="Open Government Licence (UK)", reliability="A", docs="https://developer-specs.company-information.service.gov.uk/", rate_per_min=60),
    Source("opencorporates", "OpenCorporates", "Weltweite Firmenregister: Funktionen von Personen in über 140 Jurisdiktionen.",
           ("name",), ("api.opencorporates.com",), "Wirtschaft", 1.0, "Wirtschaft & Register", _opencorporates, requires_key=True, key_optional=True,
           key_help="API-Token unter opencorporates.com/api_accounts (für Journalismus/NGOs oft kostenfrei). Ohne Token stark begrenzt.",
           license="ODbL – Quellenangabe Pflicht", cost="kostenlos (begrenzt) / Lizenz", reliability="B", docs="https://api.opencorporates.com/documentation/API-Reference", rate_per_min=20),
    Source("gleif", "GLEIF (LEI-Register)", "Juristische Personen mit Sitz, Registernummer sowie direkter und oberster Muttergesellschaft.",
           ("employer",), ("api.gleif.org",), "Wirtschaft", 1.0, "Wirtschaft & Register", _gleif,
           license="CC0", reliability="A", docs="https://www.gleif.org/en/lei-data/gleif-api", rate_per_min=60, test_query=("employer", "Siemens")),
    Source("wikidata_rel", "Wikidata – Beziehungen", "Familie, Arbeitgeber, Mitgliedschaften, Ämter, Ausbildung und Lebensdaten (strukturiert).",
           ("name",), ("www.wikidata.org", "query.wikidata.org"), "Öffentliche Person", 0.9, "Register & Wissen", _wikidata_rel,
           license="CC0", reliability="C", docs="https://query.wikidata.org/", rate_per_min=30),
    Source("crtsh", "crt.sh (Zertifikate)", "Subdomains und Namen aus der Zertifikatstransparenz – auch historische Domains einer E-Mail-Identität.",
           ("domain", "url", "email"), ("crt.sh",), "Online & Technik", 1.0, "Domains & Technik", _crtsh,
           license="frei nutzbar (Sectigo)", reliability="B", docs="https://crt.sh/", rate_per_min=10, test_query=("domain", "example.com")),
    Source("rdap", "RDAP (Domain-Register)", "Registrierungsdatum, Registrar, Nameserver und – falls nicht geschwärzt – Inhaber einer Domain.",
           ("domain", "url"), ("rdap.org",), "Online & Technik", 1.0, "Domains & Technik", _rdap,
           license="öffentliche Registerauskunft", reliability="B", docs="https://about.rdap.org/", rate_per_min=20, test_query=("domain", "example.com")),
    Source("opensanctions", "OpenSanctions (online)", "Sanktionslisten, politisch exponierte Personen (PEP) und Strafverfolgungslisten weltweit.",
           ("name",), ("api.opensanctions.org",), "Risiko", 1.1, "Risiko & Compliance", _opensanctions, requires_key=True,
           key_help="API-Schlüssel unter opensanctions.org/api (kommerzielle Nutzung lizenzpflichtig). Alternative: lokale Gesamtdaten importieren.",
           license="CC BY-NC 4.0 (nicht kommerziell) / kommerzielle Lizenz", cost="Lizenz für kommerzielle Nutzung", reliability="B",
           docs="https://www.opensanctions.org/docs/api/", rate_per_min=30),
]
