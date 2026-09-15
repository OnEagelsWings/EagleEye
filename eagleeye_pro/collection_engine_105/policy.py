from __future__ import annotations

import ipaddress
import re
import socket
from functools import lru_cache
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from eagleeye_pro.security.url_policy import TRACKING_KEYS, URLPolicy

from .models import CrawlPolicyModel, CrawlProfile, RobotsPolicy


BLOCKED_PATH_RE = re.compile(
    r"/(?:login|log-in|signin|sign-in|signup|sign-up|register|account|accounts|auth|oauth|password|reset-password|"
    r"checkout|cart|basket|payment|billing|subscribe|subscription|paywall|members?|private|admin|wp-admin|"
    r"captcha|challenge)(?:/|$|[?#])",
    re.I,
)
BLOCKED_QUERY_KEYS = {
    "password", "passwd", "token", "access_token", "auth", "authorization", "session", "sessionid",
    "sid", "phpsessid", "jsessionid", "captcha", "otp", "code",
}
DEFAULT_DENY_EXTENSIONS = {
    ".7z", ".apk", ".avi", ".bin", ".bz2", ".dmg", ".exe", ".flv", ".gif", ".gz", ".ico",
    ".iso", ".jar", ".jpeg", ".jpg", ".m4a", ".m4v", ".mkv", ".mov", ".mp3", ".mp4", ".mpeg",
    ".mpg", ".msi", ".ogg", ".otf", ".png", ".rar", ".svg", ".tar", ".tif", ".tiff", ".ttf",
    ".wav", ".webm", ".webp", ".woff", ".woff2", ".xz", ".zip",
}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".json", ".xml"}
# Conservative fallback when a Public Suffix List library is unavailable. This blocks
# frequently used registry-level domains from being accepted as crawl scopes.
COMMON_REGISTRY_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au",
    "co.nz", "org.nz", "co.jp", "co.kr", "com.br", "com.mx", "com.tr",
    "com.cn", "com.hk", "com.sg", "co.za", "com.ar", "com.pl", "com.ua",
}


def profile_policy(profile: CrawlProfile | str, *, explicit_scope_confirmation: bool = True, operator_controls_domain: bool = False) -> CrawlPolicyModel:
    profile = CrawlProfile(profile)
    common = dict(profile=profile, explicit_scope_confirmation=explicit_scope_confirmation, operator_controls_domain=operator_controls_domain)
    if profile == CrawlProfile.FOCUSED:
        return CrawlPolicyModel(max_pages=150, max_depth=3, max_runtime_seconds=900, max_total_bytes=250 * 1024 * 1024,
                                concurrent_requests=3, concurrent_requests_per_domain=1, download_delay_seconds=1.0,
                                autothrottle_target_concurrency=0.75, browser_scroll_steps=10, **common)
    if profile == CrawlProfile.EXTENDED_PUBLIC:
        return CrawlPolicyModel(max_pages=2500, max_depth=8, max_runtime_seconds=7200, max_total_bytes=2 * 1024**3,
                                concurrent_requests=8, concurrent_requests_per_domain=2, download_delay_seconds=0.35,
                                autothrottle_target_concurrency=1.5, browser_scroll_steps=18, **common)
    if profile == CrawlProfile.MAXIMUM_PUBLIC:
        return CrawlPolicyModel(max_pages=10_000, max_depth=12, max_runtime_seconds=21_600, max_total_bytes=5 * 1024**3,
                                max_response_bytes=35 * 1024**2, concurrent_requests=12,
                                concurrent_requests_per_domain=3, download_delay_seconds=0.20,
                                autothrottle_target_concurrency=2.0, retry_times=3,
                                max_query_variants_per_path=25, browser_scroll_steps=32, **common)
    return CrawlPolicyModel(max_pages=100_000, max_depth=25, max_runtime_seconds=86_400, max_total_bytes=20 * 1024**3,
                            max_response_bytes=100 * 1024**2, concurrent_requests=32,
                            concurrent_requests_per_domain=8, download_delay_seconds=0.05,
                            autothrottle_target_concurrency=6.0, retry_times=5,
                            max_query_variants_per_path=100, browser_scroll_steps=80,
                            robots_policy=RobotsPolicy.OWNER_AUTHORIZED_OVERRIDE, **common)


def canonical_for_crawl(url: str) -> str:
    decision = URLPolicy.normalize_public_url(url)
    if not decision.get("ok"):
        raise ValueError(decision.get("blocked_reason") or "URL blocked")
    parsed = urlparse(decision["canonical_url"])
    query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        lower = key.lower()
        if lower in TRACKING_KEYS or lower in BLOCKED_QUERY_KEYS or lower.startswith("utm_"):
            continue
        query.append((key, value))
    query.sort()
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", urlencode(query, doseq=True), ""))



def validate_allowed_domain(domain: str) -> str:
    domain = (domain or "").strip().lower().strip(".")
    if domain.startswith("www."):
        domain = domain[4:]
    if not domain or URLPolicy.is_private_or_local_host(domain):
        raise ValueError("allowed domain must be a public hostname")
    try:
        import tldextract
        parsed = tldextract.TLDExtract(suffix_list_urls=())(domain)
        if not parsed.domain or not parsed.suffix:
            raise ValueError("allowed domain may not be a public suffix or single-label hostname")
    except ImportError:
        if "." not in domain or domain in COMMON_REGISTRY_SUFFIXES:
            raise ValueError("allowed domain may not be a public suffix or single-label hostname")
    return domain

def host_in_scope(host: str, policy: CrawlPolicyModel) -> bool:
    host = (host or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    allowed = list(policy.allowed_domains) + list(policy.extra_allowed_domains)
    for domain in allowed:
        if host == domain:
            return True
        if policy.allow_subdomains and host.endswith("." + domain):
            return True
    return False


def url_in_scope(url: str, policy: CrawlPolicyModel) -> tuple[bool, str]:
    try:
        canonical = canonical_for_crawl(url)
    except ValueError as exc:
        return False, str(exc)
    parsed = urlparse(canonical)
    if not host_in_scope(parsed.hostname or "", policy):
        return False, "offsite_domain"
    probe = parsed.path + ("?" + parsed.query if parsed.query else "")
    if BLOCKED_PATH_RE.search(probe):
        return False, "blocked_login_private_or_paywall_path"
    if policy.include_path_prefixes and not any(parsed.path.startswith(prefix) for prefix in policy.include_path_prefixes):
        return False, "outside_included_path_prefixes"
    for pattern in policy.exclude_path_patterns:
        if re.search(pattern, probe, re.I):
            return False, "excluded_path_pattern"
    suffix = Path(parsed.path).suffix.lower()
    if suffix in DEFAULT_DENY_EXTENSIONS:
        return False, "blocked_binary_asset_extension"
    if suffix in DOCUMENT_EXTENSIONS and not policy.capture_documents:
        return False, "document_capture_disabled"
    if parsed.query and not policy.follow_query_links:
        return False, "query_links_disabled"
    return True, canonical


@lru_cache(maxsize=4096)
def resolve_public_host(host: str) -> tuple[str, ...]:
    addresses: list[str] = []
    for result in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM):
        address = result[4][0]
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise ValueError(f"blocked_non_public_dns_resolution:{address}")
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise ValueError("dns_resolution_empty")
    return tuple(addresses)


def validate_network_target(url: str, policy: CrawlPolicyModel, resolver: Callable[[str], tuple[str, ...]] | None = None) -> dict:
    ok, canonical_or_reason = url_in_scope(url, policy)
    if not ok:
        raise ValueError(canonical_or_reason)
    canonical = canonical_or_reason
    host = urlparse(canonical).hostname or ""
    addresses = (resolver or resolve_public_host)(host)
    return {"canonical_url": canonical, "host": host, "addresses": list(addresses)}
