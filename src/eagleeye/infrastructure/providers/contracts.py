from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence


class ProviderFrameworkError(RuntimeError):
    """Base class for controlled provider failures."""


class ProviderValidationError(ProviderFrameworkError, ValueError):
    pass


class ProviderAuthorizationError(ProviderFrameworkError, PermissionError):
    pass


class ProviderRateLimitError(ProviderFrameworkError):
    pass


class ProviderCircuitOpenError(ProviderFrameworkError):
    pass


class ProviderTransportError(ProviderFrameworkError):
    pass


class ProviderReplayError(ProviderFrameworkError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    provider_key: str
    label: str
    provider_type: str
    public_only: bool = True
    supports_live: bool = True
    supports_replay: bool = True
    allowed_hosts: tuple[str, ...] = ()
    rate_limit_per_minute: int = 30
    min_interval_seconds: float = 0.0
    timeout_seconds: float = 15.0
    max_attempts: int = 3
    backoff_base_seconds: float = 0.25
    circuit_failure_threshold: int = 3
    circuit_cooldown_seconds: float = 60.0
    max_response_bytes: int = 2_000_000
    terms_profile: str = "public-only"
    enabled: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        key = self.provider_key.strip()
        if not key or not key.replace("_", "").replace("-", "").isalnum():
            raise ProviderValidationError("provider_key must be a safe identifier")
        if not self.label.strip() or not self.provider_type.strip():
            raise ProviderValidationError("provider label and type are required")
        if not self.public_only:
            raise ProviderValidationError("Build 120 accepts public-only providers")
        if self.rate_limit_per_minute < 1 or self.rate_limit_per_minute > 600:
            raise ProviderValidationError("rate limit outside safe bounds")
        if not 0 <= self.min_interval_seconds <= 3600:
            raise ProviderValidationError("minimum interval outside safe bounds")
        if not 1 <= self.timeout_seconds <= 120:
            raise ProviderValidationError("timeout outside safe bounds")
        if not 1 <= self.max_attempts <= 5:
            raise ProviderValidationError("max_attempts outside safe bounds")
        if not 1 <= self.circuit_failure_threshold <= 20:
            raise ProviderValidationError("circuit threshold outside safe bounds")
        if not 1 <= self.max_response_bytes <= 25_000_000:
            raise ProviderValidationError("response size outside safe bounds")
        normalized_hosts = tuple(host.casefold().strip(".") for host in self.allowed_hosts)
        if any(not host or ":" in host or "/" in host or "*" in host for host in normalized_hosts):
            raise ProviderValidationError("allowed_hosts must contain exact DNS host names only")
        if self.supports_live and not normalized_hosts:
            raise ProviderValidationError("live providers require an explicit host allowlist")
        if not self.supports_live and not self.supports_replay:
            raise ProviderValidationError("provider must support live or replay execution")
        object.__setattr__(self, "allowed_hosts", normalized_hosts)

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["allowed_hosts"] = list(self.allowed_hosts)
        result["metadata"] = dict(self.metadata)
        return result


@dataclass(frozen=True, slots=True)
class ProviderRunRequest:
    case_id: str
    provider_key: str
    query: str
    purpose: str
    approved_by: str
    target_id: str = ""
    search_intent_id: str = ""
    search_query_id: str = ""
    max_results: int = 50
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderHttpRequest:
    url: str
    method: str = "GET"
    headers: Mapping[str, str] = field(default_factory=dict)
    label: str = ""

    def __post_init__(self) -> None:
        if self.method.upper() != "GET":
            raise ProviderValidationError("Build 120 providers are GET-only")
        forbidden = {
            "api-key", "authorization", "cookie", "proxy-authorization", "set-cookie",
            "x-api-key", "x-auth-token", "x-authorization",
        }
        if any(str(key).casefold() in forbidden for key in self.headers):
            raise ProviderValidationError("credential-bearing request headers are prohibited")


@dataclass(frozen=True, slots=True)
class ProviderTransportResponse:
    requested_url: str
    final_url: str
    status_code: int
    headers: Mapping[str, str]
    body: bytes
    elapsed_ms: int = 0


@dataclass(frozen=True, slots=True)
class NormalizedProviderItem:
    title: str
    url: str
    snippet: str = ""
    source_type: str = "public_web"
    published_at: str = ""
    raw_payload: Mapping[str, Any] = field(default_factory=dict)


class ProviderAdapter(ABC):
    """Uniform public-provider contract used by Build 120."""

    definition: ProviderDefinition

    def capabilities(self) -> dict[str, Any]:
        return self.definition.as_dict()

    def validate_request(self, request: ProviderRunRequest) -> None:
        if not request.query.strip():
            raise ProviderValidationError("provider query is required")

    @abstractmethod
    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        raise NotImplementedError

    @abstractmethod
    def normalize(
        self,
        response: ProviderTransportResponse,
        request: ProviderRunRequest,
    ) -> Sequence[NormalizedProviderItem]:
        raise NotImplementedError

    def health_check(self) -> dict[str, Any]:
        return {"provider_key": self.definition.provider_key, "configuration": "valid"}
