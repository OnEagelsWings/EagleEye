from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable, Iterable, Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .contracts import ProviderValidationError


SECRET_KEYS = {
    "access_token", "api_key", "apikey", "authorization", "cookie", "credential",
    "key", "password", "passwd", "proxy_authorization", "secret", "session", "token",
}
TRACKING_KEYS = {
    "fbclid", "gclid", "mc_cid", "mc_eid", "utm_campaign", "utm_content",
    "utm_medium", "utm_source", "utm_term",
}
BLOCKED_SCOPE_TERMS = {
    "bank account", "bankkonto", "captcha bypass", "credential", "credentials",
    "doxx", "doxxing", "home address", "login bypass", "password", "passwort",
    "paywall bypass", "private account", "private address", "privatadresse",
    "protected account", "wohnadresse",
}


def _host_allowed(host: str, allowed_hosts: Iterable[str]) -> bool:
    allowed = tuple(item.casefold().strip(".") for item in allowed_hosts)
    if not allowed:
        return True
    return host in allowed


def _is_public_ip(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


class PublicEndpointPolicy:
    """Rejects credentialed, internal and provider-escaping HTTP endpoints."""

    def __init__(self, resolver: Callable[..., Any] | None = None) -> None:
        self.resolver = resolver or socket.getaddrinfo

    def validate_url(
        self,
        url: str,
        *,
        allowed_hosts: Iterable[str] = (),
        resolve_dns: bool = False,
    ) -> str:
        try:
            parts = urlsplit((url or "").strip())
            port = parts.port
        except ValueError as exc:
            raise ProviderValidationError("malformed provider URL") from exc
        if parts.scheme.casefold() not in {"http", "https"}:
            raise ProviderValidationError("provider URL must use HTTP(S)")
        if parts.username or parts.password:
            raise ProviderValidationError("credentials in provider URL are prohibited")
        if any(key.casefold() in SECRET_KEYS for key, _ in parse_qsl(parts.query, keep_blank_values=True)):
            raise ProviderValidationError("secret-bearing provider query parameters are prohibited")
        if not parts.hostname:
            raise ProviderValidationError("provider URL requires a host")
        host = parts.hostname.casefold().strip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            raise ProviderValidationError("local provider host is prohibited")
        if not _host_allowed(host, allowed_hosts):
            raise ProviderValidationError(f"provider host outside allowlist: {host}")
        try:
            parsed_ip = ipaddress.ip_address(host)
        except ValueError:
            parsed_ip = None
        if parsed_ip is not None and not _is_public_ip(host):
            raise ProviderValidationError("non-public provider IP is prohibited")
        if resolve_dns:
            try:
                answers = self.resolver(host, port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
            except OSError as exc:
                raise ProviderValidationError(f"provider DNS resolution failed: {host}") from exc
            addresses = {str(answer[4][0]) for answer in answers if answer and len(answer) >= 5 and answer[4]}
            if not addresses or any(not _is_public_ip(address) for address in addresses):
                raise ProviderValidationError("provider DNS resolved to a non-public address")
        return canonicalize_public_url(url)


def canonicalize_public_url(url: str) -> str:
    try:
        parts = urlsplit((url or "").strip())
        port = parts.port
    except ValueError as exc:
        raise ProviderValidationError("malformed public URL") from exc
    scheme = parts.scheme.casefold()
    if scheme not in {"http", "https"} or not parts.hostname:
        raise ProviderValidationError("result URL must be public HTTP(S)")
    if parts.username or parts.password:
        raise ProviderValidationError("credentials in result URL are prohibited")
    host = parts.hostname.casefold().strip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ProviderValidationError("local result URL is prohibited")
    try:
        parsed_ip = ipaddress.ip_address(host)
    except ValueError:
        parsed_ip = None
    if parsed_ip is not None and not _is_public_ip(host):
        raise ProviderValidationError("non-public result URL is prohibited")
    port_part = ""
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        port_part = f":{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.casefold() not in TRACKING_KEYS
        )
    )
    return urlunsplit((scheme, host + port_part, path, query, ""))


def redact_url_secrets(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode([
        (key, "[REDACTED]" if key.casefold() in SECRET_KEYS else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def sanitize_mapping(value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        return "[MAX_DEPTH]"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.casefold().replace("-", "_") in SECRET_KEYS:
                result[key_text] = "[REDACTED]"
            else:
                result[key_text] = sanitize_mapping(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [sanitize_mapping(item, depth=depth + 1) for item in value]
    if isinstance(value, bytes):
        return f"[BYTES:{len(value)}]"
    text = str(value) if not isinstance(value, (str, int, float, bool, type(None))) else value
    if isinstance(text, str) and len(text) > 20_000:
        return text[:20_000] + "…[TRUNCATED]"
    return text


def validate_public_scope(*texts: str) -> None:
    combined = " ".join(texts).casefold()
    hit = next((term for term in sorted(BLOCKED_SCOPE_TERMS) if term in combined), None)
    if hit:
        raise ProviderValidationError(f"provider request contains prohibited scope: {hit}")
