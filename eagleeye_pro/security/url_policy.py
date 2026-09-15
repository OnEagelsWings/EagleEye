from __future__ import annotations

import ipaddress
from dataclasses import dataclass, asdict
from typing import Any, Dict, List
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse, urlunparse

TRACKING_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "yclid", "msclkid"}
ALLOWED_SCHEMES = {"http", "https"}
LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}

@dataclass(frozen=True)
class URLPolicyDecision:
    ok: bool
    normalized_url: str = ""
    canonical_url: str = ""
    scheme: str = ""
    host: str = ""
    warnings: List[str] | None = None
    blocked_reason: str = ""
    def as_dict(self) -> Dict[str, Any]:
        data = asdict(self); data["warnings"] = list(self.warnings or []); return data

class URLPolicy:
    """Build 63.0 central public-URL policy."""
    @staticmethod
    def normalize_public_url(url: str) -> Dict[str, Any]:
        raw = (url or "").strip().strip('"\'<>')
        if raw.startswith("www."):
            raw = "https://" + raw
        parsed = urlparse(raw)
        scheme = (parsed.scheme or "").lower()
        host_norm = URLPolicy._normalize_host(parsed.hostname or "")
        warnings: List[str] = []
        if not scheme:
            return URLPolicyDecision(False, warnings=[], blocked_reason="blocked_scheme:empty").as_dict()
        if scheme not in ALLOWED_SCHEMES:
            return URLPolicyDecision(False, scheme=scheme, host=host_norm, warnings=[], blocked_reason=f"blocked_scheme:{scheme}").as_dict()
        if not host_norm:
            return URLPolicyDecision(False, scheme=scheme, warnings=[], blocked_reason="blocked_missing_host").as_dict()
        if URLPolicy.is_private_or_local_host(host_norm):
            return URLPolicyDecision(False, scheme=scheme, host=host_norm, warnings=[], blocked_reason="blocked_private_or_local_host").as_dict()
        path = quote(unquote(parsed.path or "/"), safe="/%:@+~#=;,&-._")
        if path != "/": path = path.rstrip("/") or "/"
        query_pairs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False) if k.lower() not in TRACKING_KEYS]
        netloc = host_norm
        if parsed.port and not ((scheme == "http" and parsed.port == 80) or (scheme == "https" and parsed.port == 443)):
            netloc = f"{netloc}:{parsed.port}"
        canonical = urlunparse((scheme, netloc, path, "", urlencode(query_pairs, doseq=True), ""))
        if len(canonical) > 2000: warnings.append("long_url_review")
        return URLPolicyDecision(True, canonical, canonical, scheme, host_norm, warnings, "").as_dict()
    @staticmethod
    def canonicalize_url(url: str) -> str:
        return URLPolicy.normalize_public_url(url).get("canonical_url") or ""
    @staticmethod
    def validate_capture_url(url: str) -> Dict[str, Any]: return URLPolicy.normalize_public_url(url)
    @staticmethod
    def evaluate_capture_url(url: str) -> Dict[str, Any]: return URLPolicy.validate_capture_url(url)
    @staticmethod
    def evaluate_live_fetch_url(url: str) -> Dict[str, Any]:
        decision = URLPolicy.normalize_public_url(url)
        if decision.get("ok"):
            decision["warnings"] = list(decision.get("warnings") or []) + ["live_fetch_requires_network_egress_guard"]
        return decision
    @staticmethod
    def is_private_or_local_host(host: str) -> bool:
        h = (host or "").strip().strip("[]").lower().rstrip(".")
        if h in LOCAL_HOSTNAMES or h.endswith(".localhost"): return True
        try:
            ip = ipaddress.ip_address(h)
            return bool(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified)
        except ValueError:
            return False
    @staticmethod
    def _normalize_host(host: str) -> str:
        h = (host or "").strip().strip("[]").lower().rstrip(".")
        if not h: return ""
        try: return str(ipaddress.ip_address(h))
        except ValueError: pass
        try: h = h.encode("idna").decode("ascii")
        except Exception: h = h.lower()
        return h[4:] if h.startswith("www.") else h
