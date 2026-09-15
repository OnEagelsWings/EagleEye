from __future__ import annotations

import heapq
import html as htmlmod
import json
import re
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin, urlsplit

from eagleeye.crawler.delta_sync import DeltaSyncCrawler351, USER_AGENT_351
from eagleeye.crawler.engine import (
    CrawlTransport,
    FetchResponse,
    RobotsRules,
    TEXT_TYPES,
    VALID_ONION,
    _clean_url,
    _now,
    _sha,
)

POLICY_VERSION = "phase15.governed-crawler.v4.frontier-resume"
USER_AGENT_352 = "EagleEye-GovernedCrawler/352.0 (+frontier-resume; local-review-first)"
MAX_FRONTIER_ITEMS = 5000
MAX_SITEMAP_URLS = 2000
MAX_SEEN_CHECKPOINT = 5000


def canonical_url(url: str) -> str:
    """Conservative canonicalization: absolute HTTP(S), no userinfo, no fragment.

    Query strings are deliberately retained verbatim because parameter order/values can
    be semantically meaningful. _clean_url lowercases scheme/host and removes fragments.
    """
    return _clean_url(url)


def _same_allowed_host(url: str, allowed_hosts: set[str]) -> bool:
    try:
        return (urlsplit(canonical_url(url)).hostname or "").lower() in allowed_hosts
    except Exception:
        return False


def parse_sitemap_xml(body: bytes, *, base_url: str, allowed_hosts: set[str], limit: int = MAX_SITEMAP_URLS) -> list[str]:
    raw = bytes(body[:4_000_000])
    upper = raw[:100_000].upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("DTD/ENTITY forbidden in sitemap XML")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError(f"invalid sitemap XML: {exc}") from exc
    out: list[str] = []
    for elem in root.iter():
        tag = elem.tag.rsplit("}", 1)[-1].casefold()
        if tag != "loc" or not (elem.text or "").strip():
            continue
        try:
            target = canonical_url(urljoin(base_url, (elem.text or "").strip()))
        except Exception:
            continue
        if _same_allowed_host(target, allowed_hosts) and target not in out:
            out.append(target)
            if len(out) >= max(1, min(int(limit), MAX_SITEMAP_URLS)):
                break
    return out


def robots_sitemaps(text: str, *, base_url: str, allowed_hosts: set[str], limit: int = 20) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip().casefold() != "sitemap":
            continue
        try:
            target = canonical_url(urljoin(base_url, value.strip()))
        except Exception:
            continue
        if _same_allowed_host(target, allowed_hosts) and target not in out:
            out.append(target)
            if len(out) >= max(1, min(int(limit), 100)):
                break
    return out


class _DiscoveryHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.canonical: str = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {str(k).casefold(): (v or "") for k, v in attrs}
        t = tag.casefold()
        if t == "a" and a.get("href"):
            self.links.append(a["href"])
        if t == "link" and "canonical" in {v.strip().casefold() for v in a.get("rel", "").split()} and a.get("href"):
            self.canonical = a["href"]


@dataclass(order=True)
class FrontierItem:
    priority: int
    seq: int
    url: str
    depth: int
    kind: str = "discovered"

    def as_dict(self) -> dict[str, Any]:
        return {"priority": int(self.priority), "seq": int(self.seq), "url": self.url, "depth": int(self.depth), "kind": self.kind}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FrontierItem":
        return cls(
            max(0, min(int(value.get("priority", 100)), 10000)),
            max(0, int(value.get("seq", 0))),
            canonical_url(str(value.get("url") or "")),
            max(0, min(int(value.get("depth", 0)), 64)),
            str(value.get("kind") or "discovered")[:40],
        )


class WorkerInterrupted(RuntimeError):
    """Controlled test/worker interruption used to exercise durable resume semantics."""


class FrontierCrawler352(DeltaSyncCrawler351):
    """Build-352 improvement: durable prioritized frontier + sitemap/archive discovery.

    The frontier is checkpointed in the existing persistent job row; no new per-build
    table is created. Resume is at-least-once for the in-flight URL but exact content
    dedup/conditional fetch prevent duplicate evidence promotion.
    """

    policy_version = POLICY_VERSION

    def _source(self, source_id: str) -> dict[str, Any]:
        row = super()._source(source_id)
        for key in ("sitemap_urls_json", "archive_seed_urls_json"):
            raw = row.get(key, "[]")
            try:
                row[key[:-5]] = json.loads(raw or "[]")
            except Exception:
                row[key[:-5]] = []
        try:
            row["frontier_policy"] = json.loads(row.get("frontier_policy_json") or "{}")
        except Exception:
            row["frontier_policy"] = {}
        return row

    @staticmethod
    def _frontier_push(heap: list[FrontierItem], queued: set[str], *, url: str, depth: int, priority: int, kind: str, seq: int, allowed_hosts: set[str]) -> int:
        target = canonical_url(url)
        if not _same_allowed_host(target, allowed_hosts) or target in queued:
            return seq
        if len(heap) >= MAX_FRONTIER_ITEMS:
            return seq
        item = FrontierItem(priority=max(0, min(int(priority), 10000)), seq=seq, url=target, depth=max(0, int(depth)), kind=str(kind)[:40])
        heapq.heappush(heap, item)
        queued.add(target)
        return seq + 1

    @staticmethod
    def _restore_checkpoint(job: Mapping[str, Any], crawl_run_id: str, *, allowed_hosts: set[str]) -> tuple[list[FrontierItem], set[str], int, dict[str, int], str]:
        try:
            cp = json.loads(str(job.get("checkpoint_json") or "{}"))
        except Exception:
            cp = {}
        if cp.get("policy") != POLICY_VERSION or cp.get("crawl_run_id") != crawl_run_id:
            return [], set(), 0, {}, ""
        heap: list[FrontierItem] = []
        queued: set[str] = set()
        for raw in list(cp.get("frontier") or [])[:MAX_FRONTIER_ITEMS]:
            try:
                item = FrontierItem.from_dict(raw)
            except Exception:
                continue
            if _same_allowed_host(item.url, allowed_hosts) and item.url not in queued:
                heapq.heappush(heap, item); queued.add(item.url)
        seen: set[str] = set()
        for u in list(cp.get("seen_canonical") or [])[:MAX_SEEN_CHECKPOINT]:
            try:
                cu = canonical_url(str(u))
            except Exception:
                continue
            if _same_allowed_host(cu, allowed_hosts): seen.add(cu)
        counters = {str(k): int(v) for k, v in dict(cp.get("counters") or {}).items() if isinstance(v, (int, float))}
        return heap, seen, max(0, int(cp.get("seq", 0))), counters, str(cp.get("inflight_url") or "")

    def _checkpoint_frontier(self, job_id: str, *, worker_id: str, crawl_run_id: str, heap: list[FrontierItem], seen: set[str], seq: int, counters: Mapping[str, int], inflight_url: str = "") -> None:
        # Persist only bounded URL/state material; no response bodies, cookies or secrets.
        frontier = [x.as_dict() for x in sorted(heap)[:MAX_FRONTIER_ITEMS]]
        payload = {
            "policy": POLICY_VERSION,
            "crawl_run_id": crawl_run_id,
            "frontier": frontier,
            "seen_canonical": sorted(seen)[:MAX_SEEN_CHECKPOINT],
            "seq": int(seq),
            "counters": {str(k): int(v) for k, v in counters.items()},
            "inflight_url": str(inflight_url)[:2000],
        }
        self.build348.checkpoint_job(job_id, payload, worker_id=worker_id)

    def _fetch_discovery(self, *, source: dict[str, Any], crawl_run_id: str, search_run_id: str, job_id: str, worker_id: str, url: str, transport: CrawlTransport, resolver: Callable[[str], Sequence[str]] | None) -> FetchResponse:
        previous = self._latest_fetch(source["source_id"], url)
        return self._fetch_conditional(source=source, search_run_id=search_run_id, job_id=job_id, worker_id=worker_id, url=url, transport=transport, resolver=resolver, previous=previous)

    def _load_sitemap(self, *, sitemap_url: str, source: dict[str, Any], crawl_run_id: str, search_run_id: str, job_id: str, worker_id: str, transport: CrawlTransport, resolver: Callable[[str], Sequence[str]] | None, allowed_hosts: set[str]) -> list[str]:
        if not _same_allowed_host(sitemap_url, allowed_hosts):
            return []
        response = self._fetch_discovery(source=source, crawl_run_id=crawl_run_id, search_run_id=search_run_id, job_id=job_id, worker_id=worker_id, url=sitemap_url, transport=transport, resolver=resolver)
        if response.status == 304:
            self._record_fetch351(crawl_run_id=crawl_run_id, url=sitemap_url, response=response, disposition="sitemap_not_modified", reason="http_304", change_state="unchanged_304")
            return []
        if response.status >= 400:
            self._record_fetch351(crawl_run_id=crawl_run_id, url=sitemap_url, response=response, disposition="sitemap_error", reason=f"http_{response.status}", change_state="error")
            return []
        urls = parse_sitemap_xml(response.body, base_url=sitemap_url, allowed_hosts=allowed_hosts)
        self._record_fetch351(crawl_run_id=crawl_run_id, url=sitemap_url, response=response, disposition="sitemap_discovery", reason=f"urls={len(urls)}", change_state="discovery")
        return urls

    def execute_claimed_job(self, *, job_id: str, worker_id: str, transport: CrawlTransport, resolver: Callable[[str], Sequence[str]] | None = None) -> dict[str, Any]:
        job = self.build348.jobs.get(job_id) if hasattr(self.build348, "jobs") else self.db.one("SELECT * FROM phase15_jobs WHERE job_id=?", (job_id,))
        if not job or job["status"] != "running" or job["lease_owner"] != worker_id:
            raise PermissionError("active crawler worker lease required")
        if job["job_type"] not in {"governed_crawl_v1", "governed_tor_crawl_v370"}:
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

        allowed_hosts = {str(h).lower() for h in source["allowed_hosts"]}
        heap, seen, seq, restored_counts, inflight = self._restore_checkpoint(job, crawl_run_id, allowed_hosts=allowed_hosts)
        resumed = bool(heap or seen or restored_counts or inflight)
        queued = {x.url for x in heap}
        if inflight:
            try:
                seq = self._frontier_push(heap, queued, url=inflight, depth=0, priority=0, kind="resume_inflight", seq=seq, allowed_hosts=allowed_hosts)
            except Exception:
                pass
        if not heap:
            for u in source["seed_urls"]:
                seq = self._frontier_push(heap, queued, url=u, depth=0, priority=10, kind="seed", seq=seq, allowed_hosts=allowed_hosts)
            for u in source.get("archive_seed_urls", []):
                seq = self._frontier_push(heap, queued, url=u, depth=0, priority=60, kind="archive_seed", seq=seq, allowed_hosts=allowed_hosts)

        stored = int(restored_counts.get("pages_stored", 0)); fetched = int(restored_counts.get("pages_fetched", 0)); total_bytes = int(restored_counts.get("bytes_fetched", 0)); errors = int(restored_counts.get("errors", 0))
        new_count = int(restored_counts.get("new", 0)); changed_count = int(restored_counts.get("changed", 0)); not_modified = int(restored_counts.get("not_modified", 0)); deduplicated = int(restored_counts.get("deduplicated", 0)); bytes_saved = int(restored_counts.get("bytes_saved", 0))
        sitemaps_discovered = int(restored_counts.get("sitemaps_discovered", 0)); canonical_hints = int(restored_counts.get("canonical_hints", 0)); frontier_dedup = int(restored_counts.get("frontier_dedup", 0))
        robots_by_host: dict[str, RobotsRules] = {}
        sitemap_done = set(restored_counts.get("sitemap_done", [])) if isinstance(restored_counts.get("sitemap_done"), list) else set()
        self.db.execute("UPDATE phase15_crawl_runs SET status='running',completed_at=NULL,started_at=COALESCE(started_at,?) WHERE crawl_run_id=?", (_now(), crawl_run_id))

        def counts() -> dict[str, int]:
            return {"pages_stored": stored, "pages_fetched": fetched, "bytes_fetched": total_bytes, "errors": errors, "new": new_count, "changed": changed_count, "not_modified": not_modified, "deduplicated": deduplicated, "bytes_saved": bytes_saved, "sitemaps_discovered": sitemaps_discovered, "canonical_hints": canonical_hints, "frontier_dedup": frontier_dedup}

        try:
            # Explicit sitemap discovery is bounded and runs once per job attempt. URLs are
            # frontier candidates only; sitemap documents are not promoted as evidence.
            for sm in list(source.get("sitemap_urls", []))[:20]:
                if sm in sitemap_done:
                    continue
                try:
                    urls = self._load_sitemap(sitemap_url=sm, source=source, crawl_run_id=crawl_run_id, search_run_id=search_run_id, job_id=job_id, worker_id=worker_id, transport=transport, resolver=resolver, allowed_hosts=allowed_hosts)
                    for u in urls:
                        before = len(queued)
                        seq = self._frontier_push(heap, queued, url=u, depth=0, priority=25, kind="sitemap", seq=seq, allowed_hosts=allowed_hosts)
                        if len(queued) == before: frontier_dedup += 1
                    sitemaps_discovered += len(urls)
                    sitemap_done.add(sm)
                except WorkerInterrupted:
                    raise
                except Exception as exc:
                    errors += 1
                    self._record_fetch351(crawl_run_id=crawl_run_id, url=sm, response=None, disposition="sitemap_error", reason=f"{type(exc).__name__}:{exc}", change_state="error")

            while heap and fetched < int(source["max_pages"]):
                item = heapq.heappop(heap); queued.discard(item.url)
                url = canonical_url(item.url)
                if url in seen:
                    frontier_dedup += 1
                    continue
                if item.depth > int(source["max_depth"]):
                    continue
                self._checkpoint_frontier(job_id, worker_id=worker_id, crawl_run_id=crawl_run_id, heap=heap, seen=seen, seq=seq, counters=counts(), inflight_url=url)
                parsed = urlsplit(url); host = (parsed.hostname or "").lower()
                if host not in allowed_hosts:
                    continue
                if host not in robots_by_host:
                    # Fetch robots through the governed path; also harvest same-host Sitemap lines.
                    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
                    try:
                        rresp = self._fetch_conditional(source=source, search_run_id=search_run_id, job_id=job_id, worker_id=worker_id, url=robots_url, transport=transport, resolver=resolver, previous=self._latest_fetch(source["source_id"], robots_url))
                        if rresp.status in {404, 410}:
                            rtext = ""
                            robots_by_host[host] = RobotsRules("")
                            disposition = "robots_absent"
                        elif 200 <= int(rresp.status) < 300:
                            rtext = rresp.body.decode("utf-8", errors="replace")[:500000]
                            robots_by_host[host] = RobotsRules(rtext)
                            disposition = "robots_checked"
                        else:
                            rtext = ""
                            robots_by_host[host] = RobotsRules.fail_closed(f"robots_http_{rresp.status}")
                            disposition = "robots_fail_closed"
                            errors += 1
                        self._record_fetch351(crawl_run_id=crawl_run_id, url=robots_url, response=rresp, disposition=disposition, reason=(robots_by_host[host].failure_reason or ""), depth=0, change_state="discovery" if disposition != "robots_fail_closed" else "blocked")
                        if disposition == "robots_checked":
                            for sm in robots_sitemaps(rtext, base_url=robots_url, allowed_hosts=allowed_hosts):
                                if sm not in sitemap_done and len(sitemap_done) < 20:
                                    try:
                                        urls = self._load_sitemap(sitemap_url=sm, source=source, crawl_run_id=crawl_run_id, search_run_id=search_run_id, job_id=job_id, worker_id=worker_id, transport=transport, resolver=resolver, allowed_hosts=allowed_hosts)
                                        for u in urls:
                                            seq = self._frontier_push(heap, queued, url=u, depth=0, priority=25, kind="robots_sitemap", seq=seq, allowed_hosts=allowed_hosts)
                                        sitemaps_discovered += len(urls); sitemap_done.add(sm)
                                    except Exception:
                                        errors += 1
                    except WorkerInterrupted:
                        raise
                    except Exception as exc:
                        errors += 1
                        robots_by_host[host] = RobotsRules.fail_closed(f"robots_fetch_error:{type(exc).__name__}")
                        self._record_fetch351(crawl_run_id=crawl_run_id, url=robots_url, response=None, disposition="robots_fail_closed", reason=robots_by_host[host].failure_reason, depth=0, change_state="blocked")
                robots_target=(parsed.path or "/") + (("?" + parsed.query) if parsed.query else "")
                if not robots_by_host[host].allowed(robots_target):
                    self._record_fetch351(crawl_run_id=crawl_run_id, url=url, response=None, disposition="robots_block", reason="disallowed_by_robots", depth=item.depth, change_state="blocked")
                    seen.add(url); continue

                previous = self._latest_fetch(source["source_id"], url)
                try:
                    response = self._fetch_conditional(source=source, search_run_id=search_run_id, job_id=job_id, worker_id=worker_id, url=url, transport=transport, resolver=resolver, previous=previous)
                except WorkerInterrupted:
                    raise
                except Exception as exc:
                    errors += 1; seen.add(url)
                    self._record_fetch351(crawl_run_id=crawl_run_id, url=url, response=None, disposition="fetch_error", reason=f"{type(exc).__name__}:{exc}", depth=item.depth, previous=previous, change_state="error")
                    self._checkpoint_frontier(job_id, worker_id=worker_id, crawl_run_id=crawl_run_id, heap=heap, seen=seen, seq=seq, counters=counts())
                    continue

                fetched += 1
                if response.status == 304:
                    if previous:
                        not_modified += 1; bytes_saved += int(previous.get("size_bytes") or 0)
                        self._record_fetch351(crawl_run_id=crawl_run_id, url=url, response=response, disposition="not_modified", reason="http_304", depth=item.depth, previous=previous, canonical_url=str(previous.get("canonical_url") or url), change_state="unchanged_304", retained_content_sha256=str(previous.get("content_sha256") or ""))
                    else:
                        errors += 1; self._record_fetch351(crawl_run_id=crawl_run_id, url=url, response=response, disposition="invalid_304", reason="304_without_previous_validator_state", depth=item.depth, change_state="error")
                    seen.add(url); self._checkpoint_frontier(job_id, worker_id=worker_id, crawl_run_id=crawl_run_id, heap=heap, seen=seen, seq=seq, counters=counts()); continue

                total_bytes += len(response.body)
                if response.status in {301,302,303,307,308}:
                    location = response.headers.get("location", "")
                    if location:
                        try: nxt = canonical_url(urljoin(url, location))
                        except Exception: nxt = ""
                        if nxt and _same_allowed_host(nxt, allowed_hosts):
                            seq = self._frontier_push(heap, queued, url=nxt, depth=item.depth, priority=5, kind="redirect", seq=seq, allowed_hosts=allowed_hosts)
                        else:
                            self._record_fetch351(crawl_run_id=crawl_run_id, url=url, response=response, disposition="redirect_block", reason="redirect_outside_allowlist", depth=item.depth, previous=previous, change_state="blocked")
                    seen.add(url); self._checkpoint_frontier(job_id, worker_id=worker_id, crawl_run_id=crawl_run_id, heap=heap, seen=seen, seq=seq, counters=counts()); continue

                body_sha = _sha(response.body)
                if previous and body_sha == str(previous.get("content_sha256") or ""):
                    deduplicated += 1; bytes_saved += len(response.body); seen.add(url)
                    self._record_fetch351(crawl_run_id=crawl_run_id, url=url, response=response, disposition="deduplicated_unchanged", reason="exact_sha256_match", depth=item.depth, previous=previous, canonical_url=str(previous.get("canonical_url") or url), change_state="unchanged_hash")
                    self._checkpoint_frontier(job_id, worker_id=worker_id, crawl_run_id=crawl_run_id, heap=heap, seen=seen, seq=seq, counters=counts()); continue

                ctype = str(response.headers.get("content-type", "application/octet-stream")).split(";", 1)[0].strip().lower()
                text = response.body.decode("utf-8", errors="replace") if (ctype.startswith(TEXT_TYPES) or not ctype) else ""
                inspection = self.build348.build347.inspect_content(search_run_id, content_text=text[:500000], content_type=ctype or "application/octet-stream", source_url=url, declared_download=False, attachment_name="")
                security_state = "quarantined" if inspection["disposition"] == "quarantine" or source["source_kind"] == "darknet_onion" else "review_pending"
                resolved_canonical = url
                links: list[str] = []
                if text and ctype in {"text/html", "application/xhtml+xml"}:
                    p = _DiscoveryHTMLParser(); p.feed(text[:2_000_000]); links = p.links[:1000]
                    if p.canonical:
                        try:
                            hint = canonical_url(urljoin(url, htmlmod.unescape(p.canonical)))
                            if _same_allowed_host(hint, allowed_hosts): resolved_canonical = hint; canonical_hints += int(hint != url)
                        except Exception:
                            pass
                change_state = "new" if not previous else "changed"
                obj = self.build348.ingest_artifact(case_id=run["case_id"], content=response.body, media_type=ctype or "application/octet-stream", search_run_id=search_run_id, source_id=source["source_id"], security_state=security_state, provenance={"crawler_policy": POLICY_VERSION, "crawl_run_id": crawl_run_id, "url": url, "canonical_url": resolved_canonical, "frontier_kind": item.kind, "status": response.status, "headers_sha256": _sha(dict(response.headers)), "parser_version": source["parser_version"], "transport_kind": transport.transport_kind, "delta_state": change_state, "previous_fetch_id": str((previous or {}).get("fetch_id") or ""), "previous_content_sha256": str((previous or {}).get("content_sha256") or ""), "etag": str(response.headers.get("etag") or ""), "last_modified": str(response.headers.get("last-modified") or "")})
                stored += 1; new_count += int(change_state == "new"); changed_count += int(change_state == "changed")
                self._record_fetch351(crawl_run_id=crawl_run_id, url=url, response=response, disposition="stored_quarantine" if obj["quarantined"] else "stored_review_pending", object_id=obj["object_id"], depth=item.depth, previous=previous, canonical_url=resolved_canonical, change_state=change_state)
                seen.add(url); seen.add(resolved_canonical)

                if links and item.depth < int(source["max_depth"]):
                    for href in links:
                        try: nxt = canonical_url(urljoin(url, htmlmod.unescape(href)))
                        except Exception: continue
                        before = len(queued)
                        seq = self._frontier_push(heap, queued, url=nxt, depth=item.depth + 1, priority=100 + (item.depth + 1) * 10, kind="html_link", seq=seq, allowed_hosts=allowed_hosts)
                        if len(queued) == before and nxt not in seen: frontier_dedup += 1

                self._checkpoint_frontier(job_id, worker_id=worker_id, crawl_run_id=crawl_run_id, heap=heap, seen=seen, seq=seq, counters=counts())

            summary = {**counts(), "seen_urls": len(seen), "remaining_frontier": len(heap), "frontier_policy": POLICY_VERSION, "resumed_from_checkpoint": resumed, "crash_safe_resume": True, "sitemap_discovery": True, "archive_seeds": bool(source.get("archive_seed_urls")), "canonical_url_hints": True, "bounded": True, "transport_kind": transport.transport_kind, "external_transport": bool(transport.externally_configured)}
            self.db.execute("UPDATE phase15_crawl_runs SET status='succeeded',pages_fetched=?,pages_stored=?,bytes_fetched=?,completed_at=?,summary_json=? WHERE crawl_run_id=?", (fetched, stored, total_bytes, _now(), json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")), crawl_run_id))
            self.db.execute("UPDATE phase15_crawler_policies SET source_health=?,updated_at=? WHERE source_id=?", ("healthy" if errors == 0 else "degraded", _now(), source["source_id"]))
            return self.build348.complete_job(job_id, summary, worker_id=worker_id)
        except WorkerInterrupted as exc:
            self.db.execute("UPDATE phase15_crawl_runs SET status='paused',summary_json=? WHERE crawl_run_id=?", (json.dumps({"interrupted": True, "reason": str(exc), **counts()}, ensure_ascii=False, sort_keys=True, separators=(",", ":")), crawl_run_id))
            return self.build348.fail_job(job_id, f"WorkerInterrupted:{exc}", worker_id=worker_id, retry_delay_seconds=0)
        except Exception as exc:
            self.db.execute("UPDATE phase15_crawl_runs SET status='failed',completed_at=?,summary_json=? WHERE crawl_run_id=?", (_now(), json.dumps({"error": f"{type(exc).__name__}:{exc}", **counts()}, ensure_ascii=False, sort_keys=True, separators=(",", ":")), crawl_run_id))
            return self.build348.fail_job(job_id, f"{type(exc).__name__}:{exc}", worker_id=worker_id, retry_delay_seconds=30)

    def frontier_status(self) -> dict[str, Any]:
        rows = self.db.all("SELECT checkpoint_json,status FROM phase15_jobs WHERE job_type='governed_crawl_v1'")
        persisted = resumed = pending = 0
        for row in rows:
            try: cp = json.loads(row.get("checkpoint_json") or "{}")
            except Exception: cp = {}
            if cp.get("policy") == POLICY_VERSION:
                persisted += 1; pending += len(cp.get("frontier") or []); resumed += int(bool(cp.get("seen_canonical") or cp.get("inflight_url")))
        return {"policy": POLICY_VERSION, "persisted_frontiers": persisted, "resume_capable_jobs": resumed, "pending_frontier_items": pending, "max_frontier_items": MAX_FRONTIER_ITEMS, "sitemap_discovery": True, "archive_seed_discovery": True, "canonicalization": "conservative_same-host", "automatic_cross_host_expansion": False, "built_in_onion_transport": False}
