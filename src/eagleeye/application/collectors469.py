"""Build 469: allowlisted OSINT JSON collectors (not a general-purpose URL fetcher).

Third-party services receive submitted domain/DOI. The operator must avoid secret,
personal or other sensitive indicators. Outputs are unverified source snapshots.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import re
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

MAX_RESPONSE = 256 * 1024
MAX_CAPTURE = 200 * 1024
PROVIDERS = {
    "dns": "Google DNS-over-HTTPS: A records",
    "rdap_com": "Verisign RDAP: .com domains",
    "crossref": "Crossref: DOI metadata",
}
_HOSTS = {
    "dns": "dns.google",
    "rdap_com": "rdap.verisign.com",
    "crossref": "api.crossref.org",
}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def normalize_indicator(provider: str, indicator: str) -> str:
    if provider not in PROVIDERS:
        raise ValueError("Unbekannte Quelle")
    val = str(indicator).strip()
    if provider == "crossref":
        if len(val) > 256 or not re.fullmatch(r"10\.\d{4,9}/[A-Za-z0-9._;()/:+-]+", val):
            raise ValueError("Ungültiger DOI")
        return val
    if not val or len(val) > 253:
        raise ValueError("Ungültiger Domainname")
    try:
        val = val.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("Ungültiger Domainname") from exc
    labels = val.split(".")
    if labels[-1].isdigit():
        raise ValueError("IP-Adressen sind kein Domain-Indikator")
    if len(labels) < 2 or any(not (1 <= len(v) <= 63) or
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", v) for v in labels):
        raise ValueError("Ungültiger Domainname")
    if provider == "rdap_com" and not val.endswith(".com"):
        raise ValueError("RDAP unterstützt derzeit nur .com")
    return val

def endpoint(provider: str, normalized: str) -> str:
    if provider == "dns":
        return "https://dns.google/resolve?" + urlencode({"name": normalized, "type": "A"})
    if provider == "rdap_com":
        return "https://rdap.verisign.com/com/v1/domain/" + quote(normalized, safe="")
    if provider == "crossref":
        return "https://api.crossref.org/works/" + quote(normalized, safe="")
    raise ValueError("Unbekannte Quelle")

def _fetch_fixed_json(url: str) -> dict:
    host = urlsplit(url).hostname
    if host not in _HOSTS.values() or urlsplit(url).scheme != "https":
        raise ValueError("Nicht freigegebene Quelle")
    opener = build_opener(NoRedirect)
    req = Request(url, headers={"User-Agent": "EagleEye/469 (authorized public-source research)",
                                "Accept": "application/json, application/rdap+json"})
    with opener.open(req, timeout=8) as response:
        content_type = response.headers.get("Content-Type", "").lower()
        if "json" not in content_type:
            raise ValueError("Quelle lieferte kein JSON")
        raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError("Quelldokument zu groß")
    decoded = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Ungültige JSON-Antwort")
    return decoded

def collect(provider: str, indicator: str, *, fetcher=None):
    name = normalize_indicator(provider, indicator)
    url = endpoint(provider, name)
    fetch = fetcher or _fetch_fixed_json
    obj = fetch(url)
    captured = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    if len(raw) > MAX_CAPTURE:
        raise ValueError("Metadatenauszug zu groß")
    prefix = (f"Public source snapshot – unverified\nProvider: {provider}\n"
              f"Indicator: {name}\nCapture time UTC: {captured}\n"
              f"Original endpoint: {url}\n\n").encode()
    return {"provider": provider, "indicator": name, "source_url": url,
            "title": f"{PROVIDERS[provider]} – {name}", "filename": f"{provider}_snapshot.txt",
            "raw": prefix + raw, "captured_at_utc": captured,
            "verified_claim": False}
