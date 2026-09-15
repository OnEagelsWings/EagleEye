from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class CrawlEngine(StrEnum):
    SCRAPY = "scrapy"
    PLAYWRIGHT = "playwright"


class CrawlProfile(StrEnum):
    FOCUSED = "focused"
    EXTENDED_PUBLIC = "extended_public"
    MAXIMUM_PUBLIC = "maximum_public"
    OWNER_AUTHORIZED = "owner_authorized"


class RobotsPolicy(StrEnum):
    STRICT = "strict"
    OWNER_AUTHORIZED_OVERRIDE = "owner_authorized_override"


class CrawlPolicyModel(BaseModel):
    """Typed crawl boundary contract.

    The public profiles are intentionally broad, but never permit login, CAPTCHA,
    paywall or private-account bypass.  The owner-authorized profile may relax
    robots.txt only when the operator explicitly attests control of the domain.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    profile: CrawlProfile = CrawlProfile.EXTENDED_PUBLIC
    max_pages: int = Field(default=2500, ge=1, le=100_000)
    max_depth: int = Field(default=8, ge=0, le=25)
    max_runtime_seconds: int = Field(default=7200, ge=10, le=86_400)
    max_response_bytes: int = Field(default=20 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    max_total_bytes: int = Field(default=2 * 1024 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024 * 1024)
    concurrent_requests: int = Field(default=8, ge=1, le=32)
    concurrent_requests_per_domain: int = Field(default=2, ge=1, le=8)
    download_delay_seconds: float = Field(default=0.35, ge=0.05, le=30.0)
    autothrottle_target_concurrency: float = Field(default=1.5, ge=0.25, le=8.0)
    request_timeout_seconds: int = Field(default=35, ge=5, le=180)
    retry_times: int = Field(default=2, ge=0, le=5)
    allowed_domains: list[str] = Field(default_factory=list)
    extra_allowed_domains: list[str] = Field(default_factory=list)
    allow_subdomains: bool = True
    include_path_prefixes: list[str] = Field(default_factory=list)
    exclude_path_patterns: list[str] = Field(default_factory=list)
    follow_query_links: bool = True
    max_query_variants_per_path: int = Field(default=10, ge=1, le=100)
    discover_sitemaps: bool = True
    capture_documents: bool = True
    capture_json: bool = True
    capture_screenshots: bool = True
    allow_third_party_assets: bool = True
    browser_auto_scroll: bool = True
    browser_scroll_steps: int = Field(default=18, ge=0, le=80)
    browser_wait_after_load_ms: int = Field(default=750, ge=0, le=10_000)
    browser_trace: bool = False
    robots_policy: RobotsPolicy = RobotsPolicy.STRICT
    operator_controls_domain: bool = False
    explicit_scope_confirmation: bool = False
    user_agent: str = "EagleEye-PublicOSINT/105 (+local analyst; public-only; review-first)"

    @field_validator("allowed_domains", "extra_allowed_domains")
    @classmethod
    def normalize_domains(cls, values: list[str]) -> list[str]:
        out: list[str] = []
        for value in values:
            host = (value or "").strip().lower().strip(".")
            if host.startswith("www."):
                host = host[4:]
            if host and host not in out:
                out.append(host)
        return out

    @model_validator(mode="after")
    def enforce_profile_constraints(self) -> "CrawlPolicyModel":
        if self.robots_policy == RobotsPolicy.OWNER_AUTHORIZED_OVERRIDE:
            if not self.operator_controls_domain or not self.explicit_scope_confirmation:
                raise ValueError("robots override requires operator_controls_domain and explicit_scope_confirmation")
        if self.profile != CrawlProfile.OWNER_AUTHORIZED and self.robots_policy != RobotsPolicy.STRICT:
            raise ValueError("public crawl profiles must obey robots.txt")
        if not self.explicit_scope_confirmation:
            raise ValueError("explicit_scope_confirmation is required for every live crawl")
        return self


class CollectionJobRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: str = ""
    engine: CrawlEngine = CrawlEngine.SCRAPY
    seed_urls: list[str]
    policy: CrawlPolicyModel
    title: str = ""
    notes: str = ""
    explicit_live_confirmation: bool = False

    @field_validator("seed_urls")
    @classmethod
    def validate_seeds(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("at least one seed URL is required")
        checked: list[str] = []
        for value in values:
            checked.append(str(HttpUrl(value)))
        return checked

    @model_validator(mode="after")
    def require_confirmation(self) -> "CollectionJobRequestModel":
        if not self.explicit_live_confirmation:
            raise ValueError("explicit_live_confirmation is required")
        return self


class BrowserCaptureRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: str = ""
    url: str
    policy: CrawlPolicyModel
    title: str = ""
    notes: str = ""
    explicit_live_confirmation: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return str(HttpUrl(value))

    @model_validator(mode="after")
    def require_confirmation(self) -> "BrowserCaptureRequestModel":
        if not self.explicit_live_confirmation:
            raise ValueError("explicit_live_confirmation is required")
        return self


class CollectionPageResultModel(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    url: str
    final_url: str
    depth: int = 0
    parent_url: str = ""
    status_code: int = 0
    mime_type: str = "application/octet-stream"
    title: str = ""
    body_path: str
    screenshot_path: str = ""
    headers: dict[str, Any] = Field(default_factory=dict)
    links: list[str] = Field(default_factory=list)
    fetched_at: str = ""
    browser_metadata: dict[str, Any] = Field(default_factory=dict)
