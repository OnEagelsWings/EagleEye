from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .models import CrawlPolicyModel
from .policy import url_in_scope, validate_network_target


class PlaywrightCaptureRunner105:
    def __init__(self, policy: CrawlPolicyModel):
        self.policy = policy

    def run(self, url: str, output_dir: str | Path) -> dict[str, Any]:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright is not installed. Run: pip install -r requirements.txt") from exc

        target = validate_network_target(url, self.policy)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        html_path = output_dir / "page.html"
        text_path = output_dir / "visible_text.txt"
        screenshot_path = output_dir / "full_page.png"
        trace_path = output_dir / "trace.zip"
        network_events: list[dict[str, Any]] = []
        redirect_chain: list[str] = []

        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as exc:
                raise RuntimeError("Playwright Chromium is unavailable. Run: playwright install chromium") from exc
            context = browser.new_context(
                accept_downloads=False,
                service_workers="block",
                ignore_https_errors=False,
                java_script_enabled=True,
                user_agent=self.policy.user_agent,
                viewport={"width": 1440, "height": 1000},
                locale="de-DE",
            )
            if self.policy.browser_trace:
                context.tracing.start(screenshots=True, snapshots=True, sources=False)
            page = context.new_page()
            page.on("dialog", lambda dialog: dialog.dismiss())
            page.on("requestfailed", lambda request: network_events.append({"type": "request_failed", "url": request.url, "error": request.failure or ""}))

            def guard_route(route, request):
                try:
                    if request.method.upper() != "GET":
                        route.abort("blockedbyclient")
                        return
                    if request.resource_type in {"document", "iframe"}:
                        validate_network_target(request.url, self.policy)
                    else:
                        # Third-party assets may be loaded for faithful rendering, but are never
                        # followed as crawl targets or persisted as separate evidence.
                        from eagleeye_pro.security.url_policy import URLPolicy
                        decision = URLPolicy.evaluate_live_fetch_url(request.url)
                        if not decision.get("ok"):
                            raise ValueError(decision.get("blocked_reason") or "blocked subresource")
                        if not self.policy.allow_third_party_assets:
                            ok, _ = url_in_scope(request.url, self.policy)
                            if not ok:
                                raise ValueError("third_party_assets_disabled")
                    if request.resource_type in {"media", "font", "websocket", "eventsource"}:
                        route.abort("blockedbyclient")
                        return
                    route.continue_()
                except Exception:
                    route.abort("blockedbyclient")

            page.route("**/*", guard_route)
            try:
                response = page.goto(target["canonical_url"], wait_until="domcontentloaded", timeout=self.policy.request_timeout_seconds * 1000)
                if response:
                    request = response.request
                    chain: list[str] = []
                    while request:
                        chain.append(request.url)
                        request = request.redirected_from
                    redirect_chain = list(reversed(chain))
                try:
                    page.wait_for_load_state("networkidle", timeout=min(self.policy.request_timeout_seconds * 1000, 15_000))
                except PlaywrightTimeoutError:
                    network_events.append({"type": "networkidle_timeout"})
                if self.policy.browser_wait_after_load_ms:
                    page.wait_for_timeout(self.policy.browser_wait_after_load_ms)
                if self.policy.browser_auto_scroll and self.policy.browser_scroll_steps:
                    for _ in range(self.policy.browser_scroll_steps):
                        page.evaluate("window.scrollBy(0, Math.max(600, window.innerHeight * 0.85))")
                        page.wait_for_timeout(150)
                        at_bottom = page.evaluate("window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4")
                        if at_bottom:
                            break
                final_url = page.url
                ok, canonical_or_reason = url_in_scope(final_url, self.policy)
                if not ok:
                    raise ValueError(f"final URL left crawl scope: {canonical_or_reason}")
                validate_network_target(final_url, self.policy)
                html = page.content()
                text = page.locator("body").inner_text(timeout=10_000) if page.locator("body").count() else ""
                if len(html.encode("utf-8")) > self.policy.max_response_bytes:
                    raise ValueError("browser HTML exceeds max_response_bytes")
                html_path.write_text(html, encoding="utf-8")
                text_path.write_text(text, encoding="utf-8")
                screenshot_stored = ""
                if self.policy.capture_screenshots:
                    try:
                        page.screenshot(path=str(screenshot_path), full_page=True, animations="disabled")
                    except Exception:
                        page.screenshot(path=str(screenshot_path), full_page=False, animations="disabled")
                    screenshot_stored = str(screenshot_path)
                links = page.locator("a[href]").evaluate_all("els => els.map(e => e.href).filter(Boolean)")
                scoped_links: list[str] = []
                for link in links:
                    ok, candidate = url_in_scope(str(link), self.policy)
                    if ok and candidate not in scoped_links:
                        scoped_links.append(candidate)
                title = page.title()[:240]
                status_code = response.status if response else 0
                headers = response.headers if response else {}
                mime_type = (headers.get("content-type") or "text/html").split(";", 1)[0]
            finally:
                if self.policy.browser_trace:
                    context.tracing.stop(path=str(trace_path))
                context.close()
                browser.close()

        return {
            "url": url,
            "final_url": final_url,
            "depth": 0,
            "parent_url": "",
            "status_code": status_code,
            "mime_type": mime_type,
            "title": title,
            "body_path": str(html_path),
            "text_path": str(text_path),
            "screenshot_path": screenshot_stored,
            "headers": dict(headers),
            "links": scoped_links,
            "fetched_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "browser_metadata": {
                "redirect_chain": redirect_chain,
                "network_events": network_events[:200],
                "trace_path": str(trace_path) if trace_path.exists() else "",
                "html_sha256": hashlib.sha256(html_path.read_bytes()).hexdigest(),
                "text_sha256": hashlib.sha256(text_path.read_bytes()).hexdigest(),
            },
        }
