from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import signal
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from eagleeye_pro.core.database import new_id, now_ts
from eagleeye_pro.core_recomposition_104_1.models import ArtifactKind, ArtifactModel, EventType

from .models import BrowserCaptureRequestModel, CollectionJobRequestModel, CollectionPageResultModel, CrawlEngine, CrawlPolicyModel, CrawlProfile
from .playwright_runner import PlaywrightCaptureRunner105
from .policy import canonical_for_crawl, profile_policy, url_in_scope, validate_allowed_domain, validate_network_target
from .repository import CollectionRepository105
from .scrapy_runner import run_scrapy_job


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return "\n".join(self.parts)


class CollectionEngine105Service:
    BUILD = "105.0"

    def __init__(self, *, db_path: str | Path, project_root: str | Path, data_dir: str | Path,
                 platform: Any, core: Any, audit: Any):
        self.db_path = Path(db_path)
        self.project_root = Path(project_root)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.platform = platform
        self.core = core
        self.audit = audit
        self.repository = CollectionRepository105(self.db_path)

    def close(self) -> None:
        self.repository.close()

    def profiles(self) -> list[dict[str, Any]]:
        result = []
        for profile in (CrawlProfile.FOCUSED, CrawlProfile.EXTENDED_PUBLIC, CrawlProfile.MAXIMUM_PUBLIC):
            policy = profile_policy(profile)
            result.append({"profile": profile.value, "policy": policy.model_dump(mode="json"), "public_only": True,
                           "robots_obeyed": True, "bypass_features": []})
        owner = profile_policy(CrawlProfile.OWNER_AUTHORIZED, operator_controls_domain=True)
        result.append({"profile": CrawlProfile.OWNER_AUTHORIZED.value, "policy": owner.model_dump(mode="json"),
                       "public_only": True, "robots_obeyed": False,
                       "restriction": "only for domains controlled by or explicitly authorized to the operator"})
        return result

    def readiness(self) -> dict[str, Any]:
        packages: dict[str, str] = {}
        for package in ("Scrapy", "playwright"):
            try:
                packages[package.lower()] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                packages[package.lower()] = "missing"
        browser_status = "unavailable"
        if packages["playwright"] != "missing":
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as pw:
                    browser_status = "installed" if Path(pw.chromium.executable_path).exists() else "missing_run_playwright_install_chromium"
            except Exception as exc:
                browser_status = f"unavailable:{type(exc).__name__}"
        return {
            "build": self.BUILD,
            "scrapy": packages["scrapy"],
            "playwright": packages["playwright"],
            "playwright_browser": browser_status,
            "engines": ["scrapy", "playwright"],
            "public_only": True,
            "hard_blocks": ["login bypass", "CAPTCHA bypass", "paywall bypass", "private accounts", "credential use", "form submission"],
            "profiles": [p["profile"] for p in self.profiles()],
        }

    def _legal_scope_approved(self, case_id: str) -> bool:
        row = self.platform.db.one("SELECT review_id FROM legal_reviews WHERE case_id=? AND approved=1 ORDER BY created_at DESC LIMIT 1", [case_id])
        if row:
            return True
        case = self.platform.db.one("SELECT status FROM cases WHERE case_id=?", [case_id])
        return bool(case and case.get("status") in {"active", "approved", "open"})

    def _prepare_policy(self, seed_urls: list[str], policy: CrawlPolicyModel) -> tuple[list[str], CrawlPolicyModel]:
        seeds = [canonical_for_crawl(url) for url in seed_urls]
        seed_domains: list[str] = []
        for seed in seeds:
            host = (urlparse(seed).hostname or "").lower()
            if host.startswith("www."):
                host = host[4:]
            if host not in seed_domains:
                seed_domains.append(host)
        allowed = [validate_allowed_domain(domain) for domain in dict.fromkeys(policy.allowed_domains or seed_domains)]
        extra = [validate_allowed_domain(domain) for domain in policy.extra_allowed_domains]
        for host in seed_domains:
            if not any(host == domain or (policy.allow_subdomains and host.endswith("." + domain)) for domain in allowed):
                raise ValueError(f"seed domain is not in allowed_domains: {host}")
        prepared = policy.model_copy(update={"allowed_domains": allowed, "extra_allowed_domains": extra})
        for seed in seeds:
            ok, reason = url_in_scope(seed, prepared)
            if not ok:
                raise ValueError(f"seed outside crawl scope: {reason}")
        return seeds, prepared

    def create_job(self, request: CollectionJobRequestModel | dict[str, Any]) -> dict[str, Any]:
        request = request if isinstance(request, CollectionJobRequestModel) else CollectionJobRequestModel.model_validate(request)
        case_id = self.platform.resolve_case_id(request.case_id)
        if not self._legal_scope_approved(case_id):
            raise PermissionError("approved legal scope is required before live collection")
        seeds, policy = self._prepare_policy(request.seed_urls, request.policy)
        job = {
            "job_id": new_id("crawl105"), "case_id": case_id, "engine": request.engine.value,
            "title": request.title or f"{request.engine.value} collection", "status": "planned",
            "seed_urls": seeds, "policy": policy.model_dump(mode="json"), "stats": {}, "notes": request.notes,
            "error": "", "worker_pid": None, "created_at": now_ts(), "started_at": None, "completed_at": None,
        }
        self.repository.save_job(job)
        for seed in seeds:
            self.repository.add_robots_decision({
                "decision_id": new_id("robots105"), "job_id": job["job_id"], "case_id": case_id, "url": seed,
                "policy": policy.robots_policy.value, "allowed": 1,
                "reason": "robots enforcement enabled in Scrapy" if policy.robots_policy.value == "strict" else "owner-authorized override attested",
                "created_at": now_ts(),
            })
        self.audit.log("collection_job_created", "collection_job_105", job["job_id"], case_id,
                       {"engine": job["engine"], "seed_count": len(seeds), "profile": policy.profile.value})
        return self.repository.get_job(job["job_id"])

    def start_background(self, job_id: str) -> dict[str, Any]:
        job = self.repository.get_job(job_id)
        if job["status"] not in {"planned", "failed", "cancelled"}:
            raise ValueError(f"job cannot be started from status {job['status']}")
        worker = self.project_root / "EAGLEEYE_COLLECTION_WORKER_105.py"
        if not worker.exists():
            raise FileNotFoundError(worker)
        process = subprocess.Popen(
            [sys.executable, str(worker), "--base-dir", str(self.project_root), "--job-id", job_id],
            cwd=str(self.project_root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=(os.name != "nt"), creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
        )
        job.update({"status": "queued", "worker_pid": process.pid, "started_at": now_ts(), "error": ""})
        return self.repository.save_job(job)

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        job = self.repository.get_job(job_id)
        pid = job.get("worker_pid")
        if pid and job["status"] in {"queued", "running"}:
            try:
                if os.name == "nt":
                    os.kill(pid, signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        job.update({"status": "cancelled", "completed_at": now_ts(), "error": "cancelled_by_operator"})
        self.audit.log("collection_job_cancelled", "collection_job_105", job_id, job["case_id"], {})
        return self.repository.save_job(job)

    def execute_job(self, job_id: str) -> dict[str, Any]:
        job = self.repository.get_job(job_id)
        if job["status"] == "completed":
            return job
        policy = CrawlPolicyModel.model_validate(job["policy"])
        job_dir = self.data_dir / job["case_id"] / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        job.update({"status": "running", "started_at": job.get("started_at") or now_ts(), "error": ""})
        self.repository.save_job(job)
        self.core.events.publish(case_id=job["case_id"], event_type=EventType.COLLECTION_STARTED,
                                 producer="collection_engine_105", payload={"job_id": job_id, "engine": job["engine"]})
        try:
            for seed in job["seed_urls"]:
                validate_network_target(seed, policy)
            engine_stats: dict[str, Any] = {}
            if job["engine"] == CrawlEngine.SCRAPY.value:
                result = run_scrapy_job(job, job_dir)
                records = result["records"]
                engine_stats = {"scrapy": result.get("scrapy_stats") or {}}
            elif job["engine"] == CrawlEngine.PLAYWRIGHT.value:
                records = []
                runner = PlaywrightCaptureRunner105(policy)
                for index, seed in enumerate(job["seed_urls"]):
                    records.append(runner.run(seed, job_dir / f"browser_{index:04d}"))
            else:
                raise ValueError(f"unsupported collection engine: {job['engine']}")
            stats = self._import_records(job, records)
            stats.update(engine_stats)
            job.update({"status": "completed", "stats": stats, "completed_at": now_ts(), "worker_pid": None})
            self.repository.save_job(job)
            self.core.events.publish(case_id=job["case_id"], event_type=EventType.COLLECTION_COMPLETED,
                                     producer="collection_engine_105", payload={"job_id": job_id, "stats": stats})
            self.audit.log("collection_job_completed", "collection_job_105", job_id, job["case_id"], stats)
        except Exception as exc:
            job.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}", "completed_at": now_ts(), "worker_pid": None})
            self.repository.save_job(job)
            self.core.events.publish(case_id=job["case_id"], event_type=EventType.COLLECTION_FAILED,
                                     producer="collection_engine_105", payload={"job_id": job_id, "error": job["error"]})
            self.audit.log("collection_job_failed", "collection_job_105", job_id, job["case_id"], {"error": job["error"]})
            raise
        return self.repository.get_job(job_id)

    def capture_browser(self, request: BrowserCaptureRequestModel | dict[str, Any]) -> dict[str, Any]:
        request = request if isinstance(request, BrowserCaptureRequestModel) else BrowserCaptureRequestModel.model_validate(request)
        job_request = CollectionJobRequestModel(case_id=request.case_id, engine=CrawlEngine.PLAYWRIGHT,
                                                seed_urls=[request.url], policy=request.policy, title=request.title,
                                                notes=request.notes, explicit_live_confirmation=request.explicit_live_confirmation)
        job = self.create_job(job_request)
        return self.execute_job(job["job_id"])

    def ingest_test_records(self, job_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        """Deterministic integration hook used by tests and offline import tools."""
        job = self.repository.get_job(job_id)
        stats = self._import_records(job, records)
        job.update({"status": "completed", "stats": stats, "started_at": job.get("started_at") or now_ts(), "completed_at": now_ts()})
        self.repository.save_job(job)
        return self.repository.get_job(job_id)

    def _import_records(self, job: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
        policy = CrawlPolicyModel.model_validate(job["policy"])
        stats = {"records_seen": len(records), "pages_stored": 0, "errors": 0, "deduplicated": 0,
                 "bytes_stored": 0, "html": 0, "documents": 0, "json_text": 0}
        for raw in records:
            if not raw.get("body_path"):
                stats["errors"] += 1
                continue
            try:
                page = self._ingest_page(job, policy, CollectionPageResultModel.model_validate(raw))
                stats["pages_stored"] += 1
                stats["bytes_stored"] += page["byte_size"]
                mime = page["mime_type"]
                if "html" in mime:
                    stats["html"] += 1
                elif any(token in mime for token in ("json", "text", "xml")):
                    stats["json_text"] += 1
                else:
                    stats["documents"] += 1
                if page.get("deduplicated"):
                    stats["deduplicated"] += 1
            except Exception as exc:
                stats["errors"] += 1
                self.audit.log("collection_page_rejected", "collection_job_105", job["job_id"], job["case_id"],
                               {"url": raw.get("url", ""), "error": f"{type(exc).__name__}: {exc}"})
        return stats

    def _ingest_page(self, job: dict[str, Any], policy: CrawlPolicyModel, result: CollectionPageResultModel) -> dict[str, Any]:
        ok, canonical_or_reason = url_in_scope(result.final_url or result.url, policy)
        if not ok:
            raise ValueError(canonical_or_reason)
        canonical_url = canonical_or_reason
        existing_page = self.repository.get_page_by_url(job["job_id"], canonical_url)
        if existing_page:
            existing_page["deduplicated"] = True
            return existing_page
        body_path = Path(result.body_path)
        if not body_path.exists() or not body_path.is_file():
            raise FileNotFoundError(body_path)
        body = body_path.read_bytes()
        if len(body) > policy.max_response_bytes:
            raise ValueError("stored response exceeds max_response_bytes")
        sha = hashlib.sha256(body).hexdigest()
        mime = (result.mime_type or "application/octet-stream").split(";", 1)[0].lower()
        capture_id = finding_id = artifact_id = ""
        deduplicated = False
        text_value = ""
        html_value = ""
        if "html" in mime:
            html_value = body.decode("utf-8", errors="replace")
            text_path_value = str((result.model_extra or {}).get("text_path", ""))
            text_path = Path(text_path_value) if text_path_value else None
            if text_path is not None and text_path.exists() and text_path.is_file():
                text_value = text_path.read_text(encoding="utf-8", errors="replace")
            else:
                parser = _TextExtractor()
                parser.feed(html_value)
                text_value = parser.text()
        elif any(token in mime for token in ("json", "text", "xml", "javascript")):
            text_value = body.decode("utf-8", errors="replace")

        if html_value or text_value:
            included = self.core.include_finding(
                case_id=job["case_id"], url=canonical_url, text=text_value, html_snapshot=html_value,
                title=result.title or canonical_url, source_label=f"collection_engine_105:{job['engine']}",
                screenshot_path=result.screenshot_path, input_kind="browser_capture" if job["engine"] == "playwright" else "crawl",
                run_security=False, run_ai_triage=False,
                metadata={"collection_job_id": job["job_id"], "depth": result.depth, "parent_url": result.parent_url,
                          "status_code": result.status_code, "mime_type": mime, "raw_body_path": str(body_path),
                          "response_headers": result.headers, "candidate_not_claim": True},
            )
            capture_id = included.get("capture_id", "")
            finding_id = included.get("finding_id", "")
            artifact_id = (included.get("artifact_104_1") or {}).get("artifact_id", "")
            deduplicated = bool(included.get("deduplicated"))
        else:
            existing = next((a for a in self.core.repository.list_artifacts(job["case_id"], 10_000)
                             if a.sha256 == sha and a.source_url == canonical_url), None)
            if existing:
                artifact_id = existing.artifact_id
                deduplicated = True
            else:
                artifact = ArtifactModel(
                    artifact_id=new_id("art105"), case_id=job["case_id"], kind=ArtifactKind.DOCUMENT,
                    storage_uri=str(body_path), sha256=sha, mime_type=mime, byte_size=len(body),
                    source_url=canonical_url, title=result.title or canonical_url,
                    metadata={"collection_job_id": job["job_id"], "status": "candidate_not_claim", "raw_response": True},
                )
                self.core.repository.upsert_artifact(artifact)
                artifact_id = artifact.artifact_id
                self.core.events.publish(case_id=job["case_id"], event_type=EventType.ARTIFACT_CREATED,
                                         producer="collection_engine_105", artifact_id=artifact_id,
                                         payload={"job_id": job["job_id"], "url": canonical_url})
        page = {
            "page_id": new_id("page105"), "job_id": job["job_id"], "case_id": job["case_id"],
            "url": result.url, "canonical_url": canonical_url, "final_url": result.final_url or canonical_url,
            "parent_url": result.parent_url, "depth": result.depth, "status_code": result.status_code,
            "mime_type": mime, "byte_size": len(body), "sha256": sha, "body_path": str(body_path),
            "screenshot_path": result.screenshot_path, "capture_id": capture_id or None, "artifact_id": artifact_id or None,
            "finding_id": finding_id or None, "title": result.title, "headers": result.headers, "links": result.links,
            "metadata": {"browser": result.browser_metadata, "status": "candidate_not_claim", "deduplicated": deduplicated},
            "fetched_at": result.fetched_at or now_ts(), "deduplicated": deduplicated,
        }
        self.repository.add_page(page)
        self.core.events.publish(case_id=job["case_id"], event_type=EventType.COLLECTION_PAGE_CAPTURED,
                                 producer="collection_engine_105", artifact_id=artifact_id or None,
                                 payload={"job_id": job["job_id"], "page_id": page["page_id"], "url": canonical_url,
                                          "capture_id": capture_id, "status": "candidate_not_claim"})
        return page

    def get_job(self, job_id: str) -> dict[str, Any]:
        job = self.repository.get_job(job_id)
        job["pages"] = self.repository.list_pages(job_id, 1000)
        job["robots"] = self.repository.list_robots_decisions(job_id)
        return job

    def list_jobs(self, case_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        if case_id:
            case_id = self.platform.resolve_case_id(case_id)
        return self.repository.list_jobs(case_id, limit)
