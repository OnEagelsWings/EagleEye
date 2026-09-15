from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from .models import CrawlPolicyModel
from .policy import canonical_for_crawl, url_in_scope, validate_network_target


class PublicNetworkGuardMiddleware105:
    """SSRF/redirect guard used before every Scrapy request and response."""

    def __init__(self, policy: CrawlPolicyModel):
        self.policy = policy

    @classmethod
    def from_crawler(cls, crawler):
        return cls(CrawlPolicyModel.model_validate(crawler.settings.getdict("EAGLEEYE_POLICY")))

    def process_request(self, request, spider):
        validate_network_target(request.url, self.policy)
        if request.method.upper() != "GET":
            from scrapy.exceptions import IgnoreRequest
            raise IgnoreRequest("EagleEye Collection 105 only permits GET requests")
        return None

    def process_response(self, request, response, spider):
        validate_network_target(response.url, self.policy)
        location = response.headers.get("Location")
        if location:
            target = urljoin(response.url, location.decode("latin-1", errors="replace"))
            validate_network_target(target, self.policy)
        return response


class EagleEyePublicSpider105:
    """Factory wrapper: returns a Scrapy Spider class only when Scrapy is installed."""

    @staticmethod
    def build():
        import scrapy
        from scrapy.exceptions import CloseSpider
        from scrapy.linkextractors import LinkExtractor
        from w3lib.html import remove_tags, replace_escape_chars

        class PublicSpider(scrapy.Spider):
            name = "eagleeye_public_105"

            def __init__(self, *, job: dict[str, Any], output_dir: str, **kwargs):
                super().__init__(**kwargs)
                self.job = job
                self.policy = CrawlPolicyModel.model_validate(job["policy"])
                self.start_urls = list(job["seed_urls"])
                self.allowed_domains = list(dict.fromkeys(self.policy.allowed_domains + self.policy.extra_allowed_domains))
                self.output_dir = Path(output_dir)
                self.output_dir.mkdir(parents=True, exist_ok=True)
                self.records_path = self.output_dir / "pages.jsonl"
                self.total_bytes = 0
                self.query_variants: dict[str, set[str]] = {}
                self.link_extractor = LinkExtractor(unique=True, deny_extensions=[])

            def start_requests(self):
                for url in self.start_urls:
                    yield scrapy.Request(url, callback=self.parse, errback=self.errback, meta={"depth": 0, "parent_url": ""}, dont_filter=False)
                if self.policy.discover_sitemaps:
                    seen = set()
                    for seed in self.start_urls:
                        parsed = urlparse(seed)
                        candidate = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
                        if candidate not in seen:
                            seen.add(candidate)
                            yield scrapy.Request(candidate, callback=self.parse_sitemap, errback=self.errback, meta={"depth": 0, "parent_url": seed, "sitemap_probe": True}, dont_filter=False)

            def _write_record(self, record: dict[str, Any]) -> None:
                with self.records_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n")

            def _body_path(self, response) -> Path:
                digest = hashlib.sha256(response.url.encode("utf-8")).hexdigest()[:20]
                content_type = response.headers.get("Content-Type", b"").decode("latin-1", errors="replace").split(";", 1)[0].lower()
                suffix = ".html" if "html" in content_type else ".json" if "json" in content_type else ".xml" if "xml" in content_type else ".pdf" if "pdf" in content_type else ".bin"
                return self.output_dir / "raw" / f"{digest}{suffix}"

            def parse_sitemap(self, response):
                content_type = response.headers.get("Content-Type", b"").decode("latin-1", errors="replace").lower()
                if response.status >= 400 or ("xml" not in content_type and not response.url.lower().endswith(".xml")):
                    return
                text = response.text
                for loc in re.findall(r"<loc[^>]*>(.*?)</loc>", text, flags=re.I | re.S):
                    target = replace_escape_chars(remove_tags(loc)).strip()
                    ok, canonical_or_reason = url_in_scope(target, self.policy)
                    if ok:
                        yield scrapy.Request(canonical_or_reason, callback=self.parse, errback=self.errback, meta={"depth": 0, "parent_url": response.url}, dont_filter=False)

            def parse(self, response):
                body = bytes(response.body)
                self.total_bytes += len(body)
                if self.total_bytes > self.policy.max_total_bytes:
                    raise CloseSpider("max_total_bytes")
                body_path = self._body_path(response)
                body_path.parent.mkdir(parents=True, exist_ok=True)
                body_path.write_bytes(body)
                content_type = response.headers.get("Content-Type", b"application/octet-stream").decode("latin-1", errors="replace").split(";", 1)[0].lower()
                title = ""
                links: list[str] = []
                if "html" in content_type:
                    title = (response.css("title::text").get() or "").strip()[:240]
                    for link in self.link_extractor.extract_links(response):
                        ok, canonical_or_reason = url_in_scope(link.url, self.policy)
                        if not ok:
                            continue
                        canonical = canonical_or_reason
                        parsed = urlparse(canonical)
                        key = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        variants = self.query_variants.setdefault(key, set())
                        if parsed.query and parsed.query not in variants and len(variants) >= self.policy.max_query_variants_per_path:
                            continue
                        variants.add(parsed.query)
                        links.append(canonical)
                record = {
                    "url": response.request.url, "final_url": response.url,
                    "depth": int(response.meta.get("depth", 0)), "parent_url": response.meta.get("parent_url", ""),
                    "status_code": int(response.status), "mime_type": content_type, "title": title,
                    "body_path": str(body_path), "screenshot_path": "",
                    "headers": {k.decode("latin-1", errors="replace"): ", ".join(x.decode("latin-1", errors="replace") for x in v) for k, v in response.headers.items()},
                    "links": links, "fetched_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                    "browser_metadata": {},
                }
                self._write_record(record)
                if "html" in content_type:
                    for target in links:
                        yield scrapy.Request(target, callback=self.parse, errback=self.errback,
                                             meta={"parent_url": response.url}, dont_filter=False)

            def errback(self, failure):
                request = failure.request
                self._write_record({
                    "url": request.url, "final_url": request.url, "depth": int(request.meta.get("depth", 0)),
                    "parent_url": request.meta.get("parent_url", ""), "status_code": 0,
                    "mime_type": "application/x-eagleeye-error", "title": "", "body_path": "", "screenshot_path": "",
                    "headers": {}, "links": [],
                    "fetched_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                    "browser_metadata": {"error": str(failure.value)},
                })

        return PublicSpider


def run_scrapy_job(job: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    try:
        from scrapy.crawler import CrawlerProcess
    except ImportError as exc:
        raise RuntimeError("Scrapy is not installed. Run: pip install -r requirements.txt") from exc

    policy = CrawlPolicyModel.model_validate(job["policy"])
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "pages.jsonl"
    records_path.unlink(missing_ok=True)
    settings = {
        "LOG_ENABLED": False,
        "ROBOTSTXT_OBEY": policy.robots_policy.value == "strict",
        "USER_AGENT": policy.user_agent,
        "COOKIES_ENABLED": False,
        "TELNETCONSOLE_ENABLED": False,
        "DOWNLOAD_TIMEOUT": policy.request_timeout_seconds,
        "DOWNLOAD_MAXSIZE": policy.max_response_bytes,
        "DOWNLOAD_WARNSIZE": min(policy.max_response_bytes, 8 * 1024 * 1024),
        "RETRY_ENABLED": policy.retry_times > 0,
        "RETRY_TIMES": policy.retry_times,
        "REDIRECT_MAX_TIMES": 10,
        "CONCURRENT_REQUESTS": policy.concurrent_requests,
        "CONCURRENT_REQUESTS_PER_DOMAIN": policy.concurrent_requests_per_domain,
        "DOWNLOAD_DELAY": policy.download_delay_seconds,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": max(0.25, policy.download_delay_seconds),
        "AUTOTHROTTLE_MAX_DELAY": 30.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": policy.autothrottle_target_concurrency,
        "DEPTH_LIMIT": policy.max_depth,
        "DEPTH_PRIORITY": 1,
        "SCHEDULER_MEMORY_QUEUE": "scrapy.squeues.FifoMemoryQueue",
        "SCHEDULER_DISK_QUEUE": "scrapy.squeues.PickleFifoDiskQueue",
        "CLOSESPIDER_PAGECOUNT": policy.max_pages,
        "CLOSESPIDER_TIMEOUT": policy.max_runtime_seconds,
        "HTTPCACHE_ENABLED": False,
        "METAREFRESH_ENABLED": False,
        "AJAXCRAWL_ENABLED": False,
        "DOWNLOAD_FAIL_ON_DATALOSS": False,
        "EAGLEEYE_POLICY": policy.model_dump(mode="json"),
        "DOWNLOADER_MIDDLEWARES": {
            "eagleeye_pro.collection_engine_105.scrapy_runner.PublicNetworkGuardMiddleware105": 50,
        },
    }
    process = CrawlerProcess(settings=settings)
    crawler = process.create_crawler(EagleEyePublicSpider105.build())
    process.crawl(crawler, job=job, output_dir=str(output_dir))
    process.start(stop_after_crawl=True)
    records: list[dict[str, Any]] = []
    if records_path.exists():
        for line in records_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    raw_stats = crawler.stats.get_stats() if getattr(crawler, "stats", None) else {}
    stats = {str(key): value for key, value in raw_stats.items() if isinstance(value, (str, int, float, bool))}
    return {"records": records, "record_count": len(records), "engine": "scrapy", "scrapy_stats": stats}
