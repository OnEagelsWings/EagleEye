from __future__ import annotations

import json
import uuid
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin, urlsplit

from eagleeye.crawler.engine import (
    CrawlTransport,
    FetchResponse,
    GovernedCrawler,
    RobotsRules,
    TEXT_TYPES,
    VALID_ONION,
    _HTMLSignals,
    _canon,
    _clean_url,
    _now,
    _sha,
)

POLICY_VERSION = "phase15.governed-crawler.v3.delta-sync"
USER_AGENT_351 = "EagleEye-GovernedCrawler/351.0 (+conditional-fetch; local-review-first)"


class DeltaSyncCrawler351(GovernedCrawler):
    """Build-351 crawler improvement: conditional fetch + exact delta sync.

    This worker retains every Build-349/350 boundary (human-reviewed source,
    Search Capsule, OPSEC-v2, bounded queue and read-only transport) and adds
    HTTP validators plus exact-content deduplication. It never treats a 304 or
    an identical body as new evidence and never bypasses quarantine/review.
    """

    policy_version = POLICY_VERSION

    def _latest_fetch(self, source_id: str, url: str) -> dict[str, Any] | None:
        return self.db.one(
            """SELECT f.* FROM phase15_crawl_fetches f
               JOIN phase15_crawl_runs r ON r.crawl_run_id=f.crawl_run_id
               WHERE r.source_id=? AND f.url=?
                 AND f.disposition NOT IN ('robots_checked','robots_block','fetch_error','redirect_block')
               ORDER BY f.created_at DESC, f.fetch_id DESC LIMIT 1""",
            (source_id, _clean_url(url)),
        )

    @staticmethod
    def _validator_headers(previous: Mapping[str, Any] | None) -> dict[str, str]:
        if not previous:
            return {}
        headers: dict[str, str] = {}
        etag = str(previous.get("etag") or "").strip()
        last_modified = str(previous.get("last_modified") or "").strip()
        if etag:
            headers["If-None-Match"] = etag[:1000]
        if last_modified:
            headers["If-Modified-Since"] = last_modified[:1000]
        return headers

    def _record_fetch351(
        self,
        *,
        crawl_run_id: str,
        url: str,
        response: FetchResponse | None,
        disposition: str,
        reason: str = "",
        object_id: str = "",
        depth: int = 0,
        previous: Mapping[str, Any] | None = None,
        canonical_url: str = "",
        change_state: str = "",
        retained_content_sha256: str = "",
    ) -> dict[str, Any]:
        created = _now()
        headers = dict(response.headers) if response else {}
        body = response.body if response else b""
        content_sha = _sha(body) if response and body else str(retained_content_sha256 or "")
        row = {
            "fetch_id": "fetch351_" + uuid.uuid4().hex[:20],
            "crawl_run_id": crawl_run_id,
            "url": _clean_url(url),
            "depth": int(depth),
            "status_code": int(response.status if response else 0),
            "content_type": str(headers.get("content-type", ""))[:200],
            "content_sha256": content_sha,
            "size_bytes": len(body),
            "elapsed_ms": int(response.elapsed_ms if response else 0),
            "disposition": disposition,
            "reason": reason[:1000],
            "object_id": object_id,
            "created_at": created,
            "etag": str(headers.get("etag") or (previous or {}).get("etag") or "")[:1000],
            "last_modified": str(headers.get("last-modified") or (previous or {}).get("last_modified") or "")[:1000],
            "canonical_url": _clean_url(canonical_url or url),
            "change_state": str(change_state or disposition)[:80],
            "previous_fetch_id": str((previous or {}).get("fetch_id") or "")[:80],
        }
        self.db.execute(
            """INSERT INTO phase15_crawl_fetches(
               fetch_id,crawl_run_id,url,depth,status_code,content_type,content_sha256,size_bytes,
               elapsed_ms,disposition,reason,object_id,created_at,etag,last_modified,canonical_url,
               change_state,previous_fetch_id,record_hash)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (*row.values(), _sha(row)),
        )
        return row

    def _fetch_conditional(
        self,
        *,
        source: dict[str, Any],
        search_run_id: str,
        job_id: str,
        worker_id: str,
        url: str,
        transport: CrawlTransport,
        resolver: Callable[[str], Sequence[str]] | None,
        previous: Mapping[str, Any] | None,
        redirect_from: str | None = None,
    ) -> FetchResponse:
        self._preflight(source=source, search_run_id=search_run_id, url=url, resolver=resolver, redirect_from=redirect_from)
        self.build348.consume_job_request_budget(job_id, worker_id=worker_id, units=1)
        headers = {"User-Agent": USER_AGENT_351, **self._validator_headers(previous)}
        return transport.fetch(
            url,
            method="GET",
            headers=headers,
            timeout_seconds=20,
            max_bytes=int(source["max_response_bytes"]),
        )

    def execute_claimed_job(
        self,
        *,
        job_id: str,
        worker_id: str,
        transport: CrawlTransport,
        resolver: Callable[[str], Sequence[str]] | None = None,
    ) -> dict[str, Any]:
        job = self.build348.jobs.get(job_id) if hasattr(self.build348, "jobs") else None
        if job is None:
            job = self.db.one("SELECT * FROM phase15_jobs WHERE job_id=?", (job_id,))
        if not job or job["status"] != "running" or job["lease_owner"] != worker_id:
            raise PermissionError("active crawler worker lease required")
        if job["job_type"] != "governed_crawl_v1":
            raise ValueError("not a governed crawl job")

        payload = json.loads(job["payload_json"])
        crawl_run_id = payload["crawl_run_id"]
        source = self._source(payload["source_id"])
        run = self.db.one("SELECT * FROM phase15_crawl_runs WHERE crawl_run_id=?", (crawl_run_id,))
        if not run:
            raise KeyError(crawl_run_id)
        search_run_id = run["search_run_id"]
        if source["source_kind"] == "darknet_onion" and not str(transport.transport_kind).startswith("tor_") and transport.transport_kind != "static_replay_v1":
            raise PermissionError("darknet crawl requires approved Tor gateway transport")

        self.db.execute("UPDATE phase15_crawl_runs SET status='running',started_at=COALESCE(started_at,?) WHERE crawl_run_id=?", (_now(), crawl_run_id))
        robots_by_host: dict[str, RobotsRules] = {}
        queue = [(u, 0) for u in source["seed_urls"]]
        seen: set[str] = set()
        stored = fetched = total_bytes = errors = 0
        new_count = changed_count = not_modified = deduplicated = 0
        bytes_saved = 0

        try:
            while queue and fetched < int(source["max_pages"]):
                url, depth = queue.pop(0)
                url = _clean_url(url)
                if url in seen:
                    continue
                seen.add(url)
                parsed = urlsplit(url)
                host = (parsed.hostname or "").lower()
                if host not in set(source["allowed_hosts"]):
                    continue

                if host not in robots_by_host:
                    # robots.txt remains a normal governance fetch and is deliberately
                    # not used as evidence/delta state.
                    robots_by_host[host] = self._robots_for(
                        source=source,
                        crawl_run_id=crawl_run_id,
                        search_run_id=search_run_id,
                        job_id=job_id,
                        worker_id=worker_id,
                        seed_url=url,
                        transport=transport,
                        resolver=resolver,
                    )
                if not robots_by_host[host].allowed(parsed.path or "/"):
                    self._record_fetch351(crawl_run_id=crawl_run_id, url=url, response=None, disposition="robots_block", reason="disallowed_by_robots", depth=depth, change_state="blocked")
                    continue

                previous = self._latest_fetch(source["source_id"], url)
                try:
                    response = self._fetch_conditional(
                        source=source,
                        search_run_id=search_run_id,
                        job_id=job_id,
                        worker_id=worker_id,
                        url=url,
                        transport=transport,
                        resolver=resolver,
                        previous=previous,
                    )
                except Exception as exc:
                    errors += 1
                    self._record_fetch351(crawl_run_id=crawl_run_id, url=url, response=None, disposition="fetch_error", reason=f"{type(exc).__name__}:{exc}", depth=depth, previous=previous, change_state="error")
                    continue

                fetched += 1
                if response.status == 304:
                    if not previous:
                        errors += 1
                        self._record_fetch351(crawl_run_id=crawl_run_id, url=url, response=response, disposition="invalid_304", reason="304_without_previous_validator_state", depth=depth, change_state="error")
                        continue
                    not_modified += 1
                    bytes_saved += int(previous.get("size_bytes") or 0)
                    self._record_fetch351(
                        crawl_run_id=crawl_run_id,
                        url=url,
                        response=response,
                        disposition="not_modified",
                        reason="http_304",
                        object_id="",
                        depth=depth,
                        previous=previous,
                        canonical_url=str(previous.get("canonical_url") or url),
                        change_state="unchanged_304",
                        retained_content_sha256=str(previous.get("content_sha256") or ""),
                    )
                    continue

                total_bytes += len(response.body)
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location", "")
                    if location:
                        nxt = _clean_url(urljoin(url, location))
                        nh = (urlsplit(nxt).hostname or "").lower()
                        if nh in set(source["allowed_hosts"]):
                            queue.insert(0, (nxt, depth))
                        else:
                            self._record_fetch351(crawl_run_id=crawl_run_id, url=url, response=response, disposition="redirect_block", reason="redirect_outside_allowlist", depth=depth, previous=previous, change_state="blocked")
                    continue

                body_sha = _sha(response.body)
                if previous and body_sha and body_sha == str(previous.get("content_sha256") or ""):
                    deduplicated += 1
                    bytes_saved += len(response.body)
                    self._record_fetch351(
                        crawl_run_id=crawl_run_id,
                        url=url,
                        response=response,
                        disposition="deduplicated_unchanged",
                        reason="exact_sha256_match",
                        object_id="",
                        depth=depth,
                        previous=previous,
                        canonical_url=str(previous.get("canonical_url") or url),
                        change_state="unchanged_hash",
                    )
                    continue

                ctype = str(response.headers.get("content-type", "application/octet-stream")).split(";", 1)[0].strip().lower()
                text = response.body.decode("utf-8", errors="replace") if (ctype.startswith(TEXT_TYPES) or not ctype) else ""
                inspection = self.build348.build347.inspect_content(
                    search_run_id,
                    content_text=text[:500000],
                    content_type=ctype or "application/octet-stream",
                    source_url=url,
                    declared_download=False,
                    attachment_name="",
                )
                security_state = "quarantined" if inspection["disposition"] == "quarantine" or source["source_kind"] == "darknet_onion" else "review_pending"
                change_state = "new" if not previous else "changed"
                obj = self.build348.ingest_artifact(
                    case_id=run["case_id"],
                    content=response.body,
                    media_type=ctype or "application/octet-stream",
                    search_run_id=search_run_id,
                    source_id=source["source_id"],
                    security_state=security_state,
                    provenance={
                        "crawler_policy": POLICY_VERSION,
                        "crawl_run_id": crawl_run_id,
                        "url": url,
                        "status": response.status,
                        "headers_sha256": _sha(dict(response.headers)),
                        "parser_version": source["parser_version"],
                        "transport_kind": transport.transport_kind,
                        "delta_state": change_state,
                        "previous_fetch_id": str((previous or {}).get("fetch_id") or ""),
                        "previous_content_sha256": str((previous or {}).get("content_sha256") or ""),
                        "etag": str(response.headers.get("etag") or ""),
                        "last_modified": str(response.headers.get("last-modified") or ""),
                    },
                )
                stored += 1
                if change_state == "new":
                    new_count += 1
                else:
                    changed_count += 1
                self._record_fetch351(
                    crawl_run_id=crawl_run_id,
                    url=url,
                    response=response,
                    disposition="stored_quarantine" if obj["quarantined"] else "stored_review_pending",
                    object_id=obj["object_id"],
                    depth=depth,
                    previous=previous,
                    canonical_url=url,
                    change_state=change_state,
                )

                if text and depth < int(source["max_depth"]) and ctype in {"text/html", "application/xhtml+xml"}:
                    parser = _HTMLSignals()
                    parser.feed(text[:2_000_000])
                    for href in parser.links[:1000]:
                        try:
                            nxt = _clean_url(urljoin(url, href))
                        except Exception:
                            continue
                        if (urlsplit(nxt).hostname or "").lower() in set(source["allowed_hosts"]) and nxt not in seen:
                            queue.append((nxt, depth + 1))

                self.build348.checkpoint_job(
                    job_id,
                    {
                        "crawl_run_id": crawl_run_id,
                        "seen": len(seen),
                        "pages_fetched": fetched,
                        "pages_stored": stored,
                        "new": new_count,
                        "changed": changed_count,
                        "not_modified": not_modified,
                        "deduplicated": deduplicated,
                        "bytes_fetched": total_bytes,
                        "bytes_saved": bytes_saved,
                        "queue": len(queue),
                    },
                    worker_id=worker_id,
                )

            summary = {
                "pages_fetched": fetched,
                "pages_stored": stored,
                "bytes_fetched": total_bytes,
                "errors": errors,
                "seen_urls": len(seen),
                "remaining_queue": len(queue),
                "new": new_count,
                "changed": changed_count,
                "not_modified": not_modified,
                "deduplicated": deduplicated,
                "bytes_saved_estimate": bytes_saved,
                "conditional_fetch": True,
                "etag_supported": True,
                "last_modified_supported": True,
                "exact_sha256_dedup": True,
                "bounded": True,
                "transport_kind": transport.transport_kind,
                "external_transport": bool(transport.externally_configured),
            }
            self.db.execute(
                "UPDATE phase15_crawl_runs SET status='succeeded',pages_fetched=?,pages_stored=?,bytes_fetched=?,completed_at=?,summary_json=? WHERE crawl_run_id=?",
                (fetched, stored, total_bytes, _now(), _canon(summary), crawl_run_id),
            )
            self.db.execute(
                "UPDATE phase15_crawler_policies SET source_health=?,updated_at=? WHERE source_id=?",
                ("healthy" if errors == 0 else "degraded", _now(), source["source_id"]),
            )
            return self.build348.complete_job(job_id, summary, worker_id=worker_id)
        except Exception as exc:
            self.db.execute(
                "UPDATE phase15_crawl_runs SET status='failed',completed_at=?,summary_json=? WHERE crawl_run_id=?",
                (_now(), _canon({"error": f"{type(exc).__name__}:{exc}", "pages_fetched": fetched, "pages_stored": stored}), crawl_run_id),
            )
            return self.build348.fail_job(job_id, f"{type(exc).__name__}:{exc}", worker_id=worker_id, retry_delay_seconds=30)

    def run_next(self, *, worker_id: str, transport: CrawlTransport, resolver: Callable[[str], Sequence[str]] | None = None) -> dict[str, Any] | None:
        job = self.build348.claim_job(worker_id=worker_id, lease_seconds=300)
        if not job:
            return None
        if job["job_type"] != "governed_crawl_v1":
            self.build348.fail_job(job["job_id"], "worker only accepts governed_crawl_v1", worker_id=worker_id, retry_delay_seconds=0)
            return None
        return self.execute_claimed_job(job_id=job["job_id"], worker_id=worker_id, transport=transport, resolver=resolver)

    def delta_status(self) -> dict[str, Any]:
        row = self.db.one(
            """SELECT COUNT(*) total,
               SUM(CASE WHEN change_state='new' THEN 1 ELSE 0 END) new_count,
               SUM(CASE WHEN change_state='changed' THEN 1 ELSE 0 END) changed_count,
               SUM(CASE WHEN change_state='unchanged_304' THEN 1 ELSE 0 END) not_modified,
               SUM(CASE WHEN change_state='unchanged_hash' THEN 1 ELSE 0 END) deduplicated
               FROM phase15_crawl_fetches"""
        ) or {}
        return {
            "policy": POLICY_VERSION,
            "fetch_records": int(row.get("total") or 0),
            "new": int(row.get("new_count") or 0),
            "changed": int(row.get("changed_count") or 0),
            "not_modified": int(row.get("not_modified") or 0),
            "deduplicated": int(row.get("deduplicated") or 0),
            "conditional_headers": ["If-None-Match", "If-Modified-Since"],
            "exact_content_dedup": True,
            "automatic_identity_or_fact_promotion": False,
        }
