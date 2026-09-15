from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from .contracts import (
    ProviderHttpRequest,
    ProviderTransportError,
    ProviderTransportResponse,
    ProviderValidationError,
)
from .policy import PublicEndpointPolicy


class _ValidatingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, policy: PublicEndpointPolicy, allowed_hosts: tuple[str, ...]) -> None:
        super().__init__()
        self.policy = policy
        self.allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        self.policy.validate_url(newurl, allowed_hosts=self.allowed_hosts, resolve_dns=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibPublicTransport:
    """Minimal GET-only transport with DNS and redirect SSRF validation."""

    def __init__(self, policy: PublicEndpointPolicy | None = None) -> None:
        self.policy = policy or PublicEndpointPolicy()

    def fetch(
        self,
        request: ProviderHttpRequest,
        *,
        allowed_hosts: tuple[str, ...],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> ProviderTransportResponse:
        canonical = self.policy.validate_url(
            request.url,
            allowed_hosts=allowed_hosts,
            resolve_dns=True,
        )
        proxy_url = os.environ.get("EAGLEEYE_OUTBOUND_PROXY", "").strip()
        # Never inherit ambient HTTP(S)_PROXY variables. Only the explicit EagleEye
        # egress setting is trusted for provider traffic.
        proxy_handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url}) if proxy_url else urllib.request.ProxyHandler()
        handlers = [proxy_handler, _ValidatingRedirectHandler(self.policy, allowed_hosts)]
        opener = urllib.request.build_opener(*handlers)
        headers = {str(key): str(value) for key, value in request.headers.items()}
        headers.setdefault("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0")
        headers.setdefault("DNT", "1")
        headers.setdefault("Sec-GPC", "1")
        headers.pop("Referer", None)
        started = time.perf_counter()
        try:
            with opener.open(
                urllib.request.Request(canonical, headers=headers, method="GET"),
                timeout=timeout_seconds,
            ) as response:
                body = response.read(max_response_bytes + 1)
                if len(body) > max_response_bytes:
                    raise ProviderTransportError("provider response exceeds configured byte limit")
                final_url = self.policy.validate_url(
                    response.geturl(),
                    allowed_hosts=allowed_hosts,
                    resolve_dns=True,
                )
                safe_headers = {
                    str(key): str(value)
                    for key, value in response.headers.items()
                    if str(key).casefold() not in {"set-cookie", "authorization", "proxy-authorization"}
                }
                return ProviderTransportResponse(
                    requested_url=canonical,
                    final_url=final_url,
                    status_code=int(response.status),
                    headers=safe_headers,
                    body=body,
                    elapsed_ms=int((time.perf_counter() - started) * 1000),
                )
        except ProviderTransportError:
            raise
        except urllib.error.HTTPError as exc:
            body = exc.read(max_response_bytes + 1)
            if len(body) > max_response_bytes:
                raise ProviderTransportError("provider error response exceeds configured byte limit") from exc
            final_url = self.policy.validate_url(
                exc.geturl(),
                allowed_hosts=allowed_hosts,
                resolve_dns=True,
            )
            return ProviderTransportResponse(
                requested_url=canonical,
                final_url=final_url,
                status_code=int(exc.code),
                headers={str(k): str(v) for k, v in exc.headers.items() if str(k).casefold() != "set-cookie"},
                body=body,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
            )
        except (urllib.error.URLError, TimeoutError, OSError, ProviderValidationError) as exc:
            raise ProviderTransportError(str(exc)) from exc
