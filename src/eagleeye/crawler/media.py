from __future__ import annotations

import html as htmlmod
import json
from html.parser import HTMLParser
from typing import Any, Callable, Sequence
from urllib.parse import urljoin, urlsplit

from eagleeye.crawler.engine import CrawlTransport, FetchResponse, _clean_url
from eagleeye.image_intelligence.agent import ImageIntelligenceAgent353, ImageInspectionError

POLICY_VERSION = "phase15.governed-crawler.v5.media-images"
MAX_DISCOVERED_MEDIA_PER_PAGE = 100
MAX_MEDIA_FETCH_BYTES = 20 * 1024 * 1024


class _MediaHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[str] = []

    def _add(self, value: str) -> None:
        v = str(value or "").strip()
        if v and v not in self.refs and len(self.refs) < MAX_DISCOVERED_MEDIA_PER_PAGE:
            self.refs.append(v)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {str(k).casefold(): (v or "") for k, v in attrs}
        t = tag.casefold()
        if t == "img":
            self._add(a.get("src", ""))
            srcset = a.get("srcset", "")
            for part in srcset.split(",")[:20]:
                candidate = part.strip().split(" ", 1)[0]
                self._add(candidate)
        elif t == "source":
            self._add(a.get("src", ""))
            for part in a.get("srcset", "").split(",")[:20]:
                self._add(part.strip().split(" ", 1)[0])
        elif t == "meta" and a.get("property", "").casefold() in {"og:image", "og:image:url", "twitter:image"}:
            self._add(a.get("content", ""))
        elif t == "link" and "image_src" in {x.strip().casefold() for x in a.get("rel", "").split()}:
            self._add(a.get("href", ""))


def discover_image_urls(body: bytes, *, base_url: str, allowed_hosts: set[str]) -> list[str]:
    try:
        text = bytes(body[:2_000_000]).decode("utf-8", errors="replace")
    except Exception:
        return []
    parser = _MediaHTMLParser()
    try:
        parser.feed(text)
    except Exception:
        return []
    out: list[str] = []
    for ref in parser.refs:
        try:
            url = _clean_url(urljoin(base_url, htmlmod.unescape(ref)))
        except Exception:
            continue
        host = (urlsplit(url).hostname or "").lower()
        if host in allowed_hosts and url not in out:
            out.append(url)
        if len(out) >= MAX_DISCOVERED_MEDIA_PER_PAGE:
            break
    return out


class MediaCrawler353:
    """Controlled image-media handoff for Build 353.

    Discovery reads already stored HTML evidence. Fetch execution is explicit, job-backed,
    capsule/OPSEC-gated, and never broadens the source host allowlist.
    """

    def __init__(self, db: Any, *, build352: Any, image_agent: ImageIntelligenceAgent353, actor: str = "local-analyst") -> None:
        self.db = db
        self.build352 = build352
        self.image_agent = image_agent
        self.actor = actor

    def _policy(self, source_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase15_crawler_policies WHERE source_id=?", (source_id,))
        if not row:
            raise KeyError(source_id)
        source = self.db.one("SELECT * FROM phase15_sources WHERE source_id=?", (source_id,))
        if not source or source["review_status"] != "approved_read_only":
            raise PermissionError("reviewed read-only source required")
        return row | {"source_kind": source["source_kind"], "review_status": source["review_status"]}

    def discover_for_crawl(self, crawl_run_id: str) -> dict[str, Any]:
        run = self.db.one("SELECT * FROM phase15_crawl_runs WHERE crawl_run_id=?", (crawl_run_id,))
        if not run:
            raise KeyError(crawl_run_id)
        policy = self._policy(run["source_id"])
        allowed_hosts = {str(x).lower() for x in json.loads(policy["allowed_hosts_json"] or "[]")}
        found: list[str] = []
        html_rows = self.db.all(
            "SELECT url,object_id,content_type,disposition FROM phase15_crawl_fetches WHERE crawl_run_id=? AND object_id<>'' ORDER BY created_at ASC",
            (crawl_run_id,),
        )
        pages_scanned = 0
        for row in html_rows:
            ctype = str(row.get("content_type") or "").split(";", 1)[0].strip().lower()
            if ctype not in {"text/html", "application/xhtml+xml"}:
                continue
            try:
                body = self.build352.artifact_bytes(row["object_id"])
            except Exception:
                continue
            pages_scanned += 1
            for url in discover_image_urls(body, base_url=row["url"], allowed_hosts=allowed_hosts):
                if url not in found:
                    found.append(url)
        return {
            "crawl_run_id": crawl_run_id,
            "source_id": run["source_id"],
            "case_id": run["case_id"],
            "search_run_id": run["search_run_id"],
            "pages_scanned": pages_scanned,
            "media_urls": found[:1000],
            "policy": POLICY_VERSION,
        }

    def enqueue_for_crawl(self, crawl_run_id: str) -> dict[str, Any]:
        discovery = self.discover_for_crawl(crawl_run_id)
        jobs: list[dict[str, Any]] = []
        source_id = discovery["source_id"]
        policy = self._policy(source_id)
        max_bytes = min(int(policy.get("max_response_bytes") or MAX_MEDIA_FETCH_BYTES), MAX_MEDIA_FETCH_BYTES)
        rpm = max(1, min(int(policy.get("requests_per_minute") or 10), 60))
        for url in discovery["media_urls"]:
            key = f"media353:{crawl_run_id}:{url}"
            job = self.build352.enqueue_job(
                job_type="media_image_fetch_v1",
                payload={
                    "policy": POLICY_VERSION,
                    "crawl_run_id": crawl_run_id,
                    "source_id": source_id,
                    "request_url": url,
                    "network_execution_by_build353": False,
                    "requires_worker_gateway": True,
                },
                case_id=discovery["case_id"],
                search_run_id=discovery["search_run_id"],
                idempotency_key=key,
                max_attempts=3,
                priority=80,
                resource_budget={"max_runtime_seconds": 120, "max_memory_mb": 512, "max_output_bytes": max_bytes},
                rate_budget={"max_requests": 1, "requests_per_minute": rpm},
            )
            jobs.append(job)
        return discovery | {"jobs": jobs, "jobs_enqueued": len(jobs)}

    def _claim_media_job(self, worker_id: str) -> dict[str, Any] | None:
        # Avoid claiming unrelated jobs: recover stale leases and atomically claim the next media job.
        import datetime as _dt
        now = _dt.datetime.now(_dt.timezone.utc)
        now_s = now.isoformat(timespec="seconds")
        expiry = (now + _dt.timedelta(seconds=120)).isoformat(timespec="seconds")
        with self.db.transaction(immediate=True):
            self.db.execute("UPDATE phase15_jobs SET status='queued',lease_owner='',lease_expires_at='',updated_at=? WHERE job_type='media_image_fetch_v1' AND status='running' AND lease_expires_at<>'' AND lease_expires_at<?", (now_s, now_s))
            row = self.db.one("SELECT job_id FROM phase15_jobs WHERE job_type='media_image_fetch_v1' AND status='queued' AND available_at<=? ORDER BY priority ASC,created_at ASC LIMIT 1", (now_s,))
            if not row:
                return None
            cur = self.db.execute("UPDATE phase15_jobs SET status='running',attempts=attempts+1,lease_owner=?,lease_expires_at=?,updated_at=? WHERE job_id=? AND status='queued'", (worker_id[:120], expiry, now_s, row["job_id"]))
            if cur.rowcount != 1:
                return None
        return self.db.one("SELECT * FROM phase15_jobs WHERE job_id=?", (row["job_id"],))

    def fetch_next(self, *, worker_id: str, transport: CrawlTransport, resolver: Callable[[str], Sequence[str]] | None = None) -> dict[str, Any] | None:
        job = self._claim_media_job(worker_id)
        if not job:
            return None
        payload = json.loads(job["payload_json"] or "{}")
        source_id = str(payload.get("source_id") or "")
        url = _clean_url(str(payload.get("request_url") or ""))
        policy = self._policy(source_id)
        allowed_hosts = {str(x).lower() for x in json.loads(policy["allowed_hosts_json"] or "[]")}
        if (urlsplit(url).hostname or "").lower() not in allowed_hosts:
            return self.build352.fail_job(job["job_id"], "media_url_outside_allowlist", worker_id=worker_id, retry_delay_seconds=0)
        search_run_id = str(job["search_run_id"] or "")
        source = self.db.one("SELECT source_kind FROM phase15_sources WHERE source_id=?", (source_id,))
        is_darknet = bool(source and source["source_kind"] == "darknet_onion")
        if is_darknet and getattr(transport, "transport_kind", "") == "urllib_read_only":
            return self.build352.fail_job(job["job_id"], "built_in_clearnet_transport_refuses_onion", worker_id=worker_id, retry_delay_seconds=0)
        try:
            ips: list[str] = []
            if not is_darknet:
                host = (urlsplit(url).hostname or "").lower()
                if resolver is None:
                    raise PermissionError("resolver evidence required for clearnet media fetch")
                ips = [str(x) for x in resolver(host)]
            preflight = self.build352.preflight_request(
                search_run_id,
                url=url,
                source_id=source_id,
                resolved_ips=ips,
                browser_webrtc_disabled=True,
                dns_via_approved_profile=True,
            )
            if preflight.get("final_disposition") != "allow_for_gateway":
                raise PermissionError("opsec_preflight_blocked_media")
            self.build352.consume_job_request_budget(job["job_id"], worker_id=worker_id, units=1)
            response: FetchResponse = transport.fetch(url, headers={}, max_bytes=MAX_MEDIA_FETCH_BYTES, timeout_seconds=30)
            if response.status in {301, 302, 303, 307, 308}:
                raise PermissionError("media_redirect_requires_separate_reviewed_job")
            if response.status < 200 or response.status >= 300:
                raise ValueError(f"media_http_status_{response.status}")
            if len(response.body) > MAX_MEDIA_FETCH_BYTES:
                raise ValueError("media_response_too_large")
            declared = str(response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
            inspection = self.image_agent.inspect_bytes(response.body, declared_media_type=declared, filename=url.rsplit("/", 1)[-1])
            return {
                "job": job,
                "response": response,
                "inspection": inspection,
                "source_id": source_id,
                "case_id": job["case_id"],
                "search_run_id": search_run_id,
                "url": url,
                "is_darknet": is_darknet,
            }
        except Exception as exc:
            return {"failed_job": self.build352.fail_job(job["job_id"], f"{type(exc).__name__}:{exc}", worker_id=worker_id, retry_delay_seconds=0), "error": f"{type(exc).__name__}:{exc}"}

    def complete_fetch(self, payload: dict[str, Any], *, object_id: str, media_id: str, worker_id: str) -> dict[str, Any]:
        job = payload["job"]
        result = {
            "policy": POLICY_VERSION,
            "object_id": object_id,
            "media_id": media_id,
            "url": payload["url"],
            "sha256": payload["inspection"]["sha256"],
            "format": payload["inspection"]["format"],
            "quarantine_required": bool(payload["is_darknet"] or payload["inspection"]["disposition"] == "quarantine"),
        }
        return self.build352.complete_job(job["job_id"], result, worker_id=worker_id)

    def status(self) -> dict[str, Any]:
        rows = self.db.all("SELECT status,COUNT(*) c FROM phase15_jobs WHERE job_type='media_image_fetch_v1' GROUP BY status")
        return {
            "policy": POLICY_VERSION,
            "job_counts": {r["status"]: int(r["c"]) for r in rows},
            "same_host_only": True,
            "explicit_worker_claim": True,
            "redirect_auto_follow": False,
            "max_media_bytes": MAX_MEDIA_FETCH_BYTES,
            "built_in_live_tor_transport": False,
            "autonomous_background_fetch": False,
        }
