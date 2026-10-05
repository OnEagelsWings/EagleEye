from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit
import hashlib
import json
import secrets
import xml.etree.ElementTree as ET

from eagleeye_pro.phase20.retrieval_isolation451 import ProcessSurfaceTransport451

BUILD = "443.0"
POLICY_ID = "phase20.live-news-acquisition.v443"
LIVE_CONFIRM = "NEWS443_LIVE"
MAX_FEED_BYTES = 1_000_000
MAX_ITEMS_PER_RUN = 50
MAX_TEXT_CHARS = 12_000
ALLOWED_SOURCE_TYPES = {"rss", "news", "api"}
ALLOWED_ACCESS_MODES = {"public"}
FEED_MEDIA = {
    "application/rss+xml",
    "application/atom+xml",
    "application/xml",
    "text/xml",
    "application/json",
    "application/feed+json",
}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value):
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _iso(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        try:
            d = parsedate_to_datetime(raw)
        except Exception:
            return ""
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    else:
        d = d.astimezone(timezone.utc)
    return d.isoformat(timespec="seconds")


def _local(tag):
    return str(tag or "").rsplit("}", 1)[-1].casefold()


class _TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        value = str(data or "").strip()
        if value:
            self.parts.append(value)


def _plain(value):
    raw = str(value or "")
    parser = _TextOnly()
    try:
        parser.feed(raw)
        text = " ".join(parser.parts)
    except Exception:
        text = raw
    return " ".join(text.split())[:MAX_TEXT_CHARS]


class CapturingTransport443:
    """Thin wrapper that keeps responses in memory for feed parsing.

    Nothing from the raw body is persisted by this transport. Build 442 remains
    responsible for network safety and Build 425/422/423 remains responsible for
    provenance/content fingerprints.
    """

    transport_kind = "news443_memory_capture"

    def __init__(self, inner):
        self.inner = inner
        self.requires_resolved_ips = bool(getattr(inner, "requires_resolved_ips", False))
        self.externally_configured = bool(getattr(inner, "externally_configured", False))
        self.responses = []

    def fetch(self, url, **kwargs):
        response = self.inner.fetch(url, **kwargs)
        self.responses.append(response)
        return response

    def latest_for(self, url):
        target = str(url)
        for response in reversed(self.responses):
            if str(getattr(response, "url", "")) == target:
                return response
        return None


class LiveNewsAcquisition443:
    """Public feed acquisition through the hardened Build-442 retrieval path."""

    def __init__(
        self,
        db,
        audit,
        *,
        registry421,
        crawler425,
        events422,
        content423,
        news429,
        extraction430,
        provenance431,
        hardening442,
        governance,
        actor="local-analyst",
    ):
        self.db = db
        self.audit = audit
        self.registry421 = registry421
        self.crawler425 = crawler425
        self.events422 = events422
        self.content423 = content423
        self.news429 = news429
        self.extraction430 = extraction430
        self.provenance431 = provenance431
        self.hardening442 = hardening442
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS news_acquisition_run_443(
            run_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            feed_url TEXT NOT NULL,
            feed_kind TEXT NOT NULL,
            parsed_items INTEGER NOT NULL,
            ingested_items INTEGER NOT NULL,
            duplicate_items INTEGER NOT NULL,
            skipped_items INTEGER NOT NULL,
            parent_event_id TEXT NOT NULL,
            hardening_run_id TEXT NOT NULL,
            provenance_run_id TEXT NOT NULL,
            execution_mode TEXT NOT NULL,
            external_network INTEGER NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_news443_case
            ON news_acquisition_run_443(case_id,created_at);

            CREATE TABLE IF NOT EXISTS news_acquisition_item_443(
            item_run_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            news_item_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            content_id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            canonical_url TEXT NOT NULL,
            published_at TEXT NOT NULL,
            state TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_news443_item_run
            ON news_acquisition_item_443(run_id,created_at);
            """
        )
        self.db.conn.commit()

    def _rh(self, row):
        return _sha({k: row[k] for k in row if k != "record_hash"})

    def _identity(self, identity):
        return self.hardening442.surface441._identity(identity)

    def _authorize(self, identity, case_id, source_id):
        ident = self._identity(identity)
        self.governance.authorize(
            ident,
            case_id=str(case_id),
            capability="crawler.run",
            object_type="news_acquisition_443",
            object_id=str(source_id),
        )
        return ident

    def _source(self, source_id):
        src = self.registry421.get(source_id)
        if int(src.get("enabled", 0)) != 1:
            raise PermissionError("news source is disabled")
        if src.get("source_type") not in ALLOWED_SOURCE_TYPES:
            raise PermissionError("Build 443 requires source_type rss, news, or api")
        if src.get("access_mode") not in ALLOWED_ACCESS_MODES:
            raise PermissionError("Build 443 supports unauthenticated public news sources only")
        if bool((src.get("coverage") or {}).get("fixture_only")):
            return src
        return src

    def _allowed_article_hosts(self, source):
        base_host = (urlsplit(str(source.get("base_url") or "")).hostname or "").casefold()
        hosts = {base_host} if base_host else set()
        for value in (source.get("coverage") or {}).get("allowed_article_hosts", []) or []:
            host = str(value or "").casefold().rstrip(".")
            if host:
                hosts.add(host)
        return hosts

    def create_feed_task(self, *, identity, case_id, source_id, feed_url=""):
        ident = self._authorize(identity, case_id, source_id)
        source = self._source(source_id)
        target = str(feed_url or source.get("base_url") or "").strip()
        if not target:
            raise ValueError("registered news source requires a feed URL")
        parsed = urlsplit(target)
        base = urlsplit(str(source.get("base_url") or ""))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("feed URL must be public http(s)")
        if not base.hostname or parsed.hostname.casefold() != base.hostname.casefold():
            raise PermissionError("feed URL must remain on the exact registered source host")
        return self.crawler425.create_task(
            identity=ident,
            case_id=str(case_id),
            source_id=source_id,
            target=target,
            objective="Build 443 public news feed acquisition",
            scope={
                "allowed_hosts": [parsed.hostname.casefold()],
                "news443": True,
                "feed_only": True,
            },
            budget={
                "max_pages": 1,
                "max_bytes": MAX_FEED_BYTES,
                "max_seconds": 20,
            },
        )

    def _feed_response(self, capture, surface_result, task):
        run = surface_result.get("run") or {}
        final_url = str(run.get("final_url") or task["target"])
        response = capture.latest_for(final_url)
        if response is None:
            raise RuntimeError("Build 443 could not access the in-memory feed response")
        body = bytes(getattr(response, "body", b"") or b"")
        if not body:
            raise ValueError("news feed response is empty")
        if len(body) > MAX_FEED_BYTES:
            raise ValueError("news feed exceeds Build-443 byte limit")
        media = str((getattr(response, "headers", {}) or {}).get("content-type", "")).split(";", 1)[0].strip().casefold()
        if media and media not in FEED_MEDIA:
            raise ValueError("unsupported news feed media type")
        return final_url, media, body

    def _xml_items(self, body):
        upper = body[:4096].upper()
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
            raise ValueError("DTD/entity declarations are forbidden in news feeds")
        root = ET.fromstring(body)
        root_kind = _local(root.tag)
        items = []
        if root_kind == "rss":
            channel = next((x for x in list(root) if _local(x.tag) == "channel"), root)
            nodes = [x for x in list(channel) if _local(x.tag) == "item"]
            kind = "rss"
            for node in nodes[:MAX_ITEMS_PER_RUN]:
                values = {}
                for child in list(node):
                    key = _local(child.tag)
                    text = "".join(child.itertext()).strip()
                    if key not in values and text:
                        values[key] = text
                link = values.get("link", "")
                guid = values.get("guid", "")
                items.append(
                    {
                        "title": _plain(values.get("title", "")),
                        "url": str(link or (guid if str(guid).startswith(("http://", "https://")) else "")).strip(),
                        "external_id": str(guid or link).strip(),
                        "published_at": _iso(
                            values.get("pubdate")
                            or values.get("published")
                            or values.get("date")
                        ),
                        "author": _plain(
                            values.get("creator")
                            or values.get("author")
                            or values.get("managingeditor")
                            or ""
                        )[:500],
                        "summary": _plain(
                            values.get("description")
                            or values.get("encoded")
                            or values.get("summary")
                            or ""
                        ),
                        "language": "",
                    }
                )
            return kind, items
        if root_kind == "feed":
            kind = "atom"
            nodes = [x for x in list(root) if _local(x.tag) == "entry"]
            for node in nodes[:MAX_ITEMS_PER_RUN]:
                title = ""
                external_id = ""
                published = ""
                author = ""
                summary = ""
                link = ""
                for child in list(node):
                    key = _local(child.tag)
                    text = "".join(child.itertext()).strip()
                    if key == "title" and not title:
                        title = text
                    elif key == "id" and not external_id:
                        external_id = text
                    elif key in {"published", "updated"} and not published:
                        published = text
                    elif key in {"summary", "content"} and not summary:
                        summary = text
                    elif key == "author" and not author:
                        author = text
                    elif key == "link":
                        rel = str(child.attrib.get("rel") or "alternate").casefold()
                        href = str(child.attrib.get("href") or "").strip()
                        if href and rel in {"alternate", ""} and not link:
                            link = href
                items.append(
                    {
                        "title": _plain(title),
                        "url": link,
                        "external_id": str(external_id or link).strip(),
                        "published_at": _iso(published),
                        "author": _plain(author)[:500],
                        "summary": _plain(summary),
                        "language": "",
                    }
                )
            return kind, items
        raise ValueError("unsupported XML news feed root")

    def _json_items(self, body):
        data = json.loads(body.decode("utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ValueError("unsupported JSON news feed")
        version = str(data.get("version") or "")
        if version and "jsonfeed.org/version" not in version:
            raise ValueError("unsupported JSON feed version")
        items = []
        for item in data["items"][:MAX_ITEMS_PER_RUN]:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or item.get("external_url") or "").strip()
            items.append(
                {
                    "title": _plain(item.get("title") or ""),
                    "url": url,
                    "external_id": str(item.get("id") or url).strip(),
                    "published_at": _iso(item.get("date_published") or item.get("date_modified")),
                    "author": _plain(
                        ((item.get("authors") or [{}])[0] or {}).get("name", "")
                        if isinstance(item.get("authors"), list)
                        else ""
                    )[:500],
                    "summary": _plain(
                        item.get("summary")
                        or item.get("content_text")
                        or item.get("content_html")
                        or ""
                    ),
                    "language": str(item.get("language") or data.get("language") or "").lower()[:32],
                }
            )
        return "jsonfeed", items

    def _parse_feed(self, media, body):
        stripped = body.lstrip()
        if media in {"application/json", "application/feed+json"} or stripped.startswith(b"{"):
            return self._json_items(body)
        return self._xml_items(body)

    def _normalize_item(self, source, item):
        title = _plain(item.get("title", ""))
        url = str(item.get("url") or "").strip()
        published = _iso(item.get("published_at"))
        if not title:
            return None, "missing_title"
        if not url:
            return None, "missing_canonical_url"
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None, "invalid_canonical_url"
        if parsed.hostname.casefold().endswith(".onion"):
            return None, "onion_canonical_url_forbidden"
        if parsed.username is not None or parsed.password is not None:
            return None, "credential_url_forbidden"
        if parsed.hostname.casefold() not in self._allowed_article_hosts(source):
            return None, "article_host_outside_source_allowlist"
        if not published:
            return None, "missing_or_invalid_publication_time"
        external_id = str(item.get("external_id") or "").strip()
        if not external_id:
            external_id = _sha(
                {
                    "url": url,
                    "title": title,
                    "published_at": published,
                }
            )[:40]
        return {
            "title": title,
            "canonical_url": url,
            "published_at": published,
            "external_id": external_id[:1000],
            "author": _plain(item.get("author", ""))[:500],
            "summary": _plain(item.get("summary", "")),
            "language": str(item.get("language", "") or "").lower()[:32],
        }, ""

    def _duplicate_external_id(self, source_id, external_id):
        return bool(
            self.db.one(
                "SELECT 1 FROM news_item_429 WHERE source_id=? AND external_id=? LIMIT 1",
                (str(source_id), str(external_id)),
            )
        )

    def _item_payload(self, source, item):
        return (
            f"TITLE: {item['title']}\n"
            f"URL: {item['canonical_url']}\n"
            f"PUBLISHED_AT: {item['published_at']}\n"
            f"PUBLISHER: {source['name']}\n"
            f"AUTHOR: {item['author']}\n"
            f"SUMMARY: {item['summary']}"
        ).encode("utf-8")

    def _record_item_row(
        self,
        *,
        run_id,
        news_item_id="",
        event_id="",
        content_id="",
        external_id="",
        canonical_url="",
        published_at="",
        state,
        reason="",
    ):
        row = {
            "item_run_id": "news443item_" + secrets.token_hex(8),
            "run_id": run_id,
            "news_item_id": str(news_item_id or ""),
            "event_id": str(event_id or ""),
            "content_id": str(content_id or ""),
            "external_id": str(external_id or ""),
            "canonical_url": str(canonical_url or ""),
            "published_at": str(published_at or ""),
            "state": str(state),
            "reason": str(reason or "")[:300],
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO news_acquisition_item_443 VALUES("
            + ",".join("?" for _ in row)
            + ")",
            tuple(row.values()),
        )
        return row

    def _persist_run(
        self,
        *,
        identity,
        case_id,
        source_id,
        task_id,
        feed_url,
        feed_kind,
        parsed_items,
        ingested_items,
        duplicate_items,
        skipped_items,
        parent_event_id,
        hardening_run_id,
        provenance_run_id,
        execution_mode,
        external_network,
        run_id,
    ):
        row = {
            "run_id": run_id,
            "case_id": str(case_id),
            "source_id": str(source_id),
            "task_id": str(task_id),
            "feed_url": str(feed_url),
            "feed_kind": str(feed_kind),
            "parsed_items": int(parsed_items),
            "ingested_items": int(ingested_items),
            "duplicate_items": int(duplicate_items),
            "skipped_items": int(skipped_items),
            "parent_event_id": str(parent_event_id),
            "hardening_run_id": str(hardening_run_id),
            "provenance_run_id": str(provenance_run_id),
            "execution_mode": str(execution_mode),
            "external_network": 1 if external_network else 0,
            "created_by": str(identity["username"]),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO news_acquisition_run_443 VALUES("
            + ",".join("?" for _ in row)
            + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "news_acquisition_run_443",
            "news_acquisition_run_443",
            run_id,
            str(case_id),
            {
                "source_id": source_id,
                "feed_kind": feed_kind,
                "ingested_items": ingested_items,
                "duplicates": duplicate_items,
                "skipped": skipped_items,
                "external_network": bool(external_network),
            },
        )
        return self.run(run_id)

    def _execute(
        self,
        *,
        identity,
        case_id,
        task_id,
        transport,
        resolver,
        execution_mode,
        authorization_mode,
        live,
        external_network,
    ):
        ident = self._identity(identity)
        task = self.hardening442._task(task_id)
        if task["case_id"] != str(case_id):
            raise PermissionError("news task does not belong to requested case")
        self._authorize(ident, case_id, task["source_id"])
        source = self._source(task["source_id"])
        if live and bool((source.get("coverage") or {}).get("fixture_only")):
            raise PermissionError("synthetic news fixture cannot use live acquisition")
        if task["state"] != "planned":
            raise ValueError("news acquisition task must be planned")
        if not bool((task.get("scope") or {}).get("news443")):
            raise PermissionError("task was not created as a Build-443 news feed task")

        capture = CapturingTransport443(transport)
        surface = self.hardening442._execute_hardened(
            identity=ident,
            task_id=task_id,
            transport=capture,
            resolver=resolver,
            execution_mode=execution_mode,
            authorization_mode=authorization_mode,
            live=live,
            external_validation=external_network,
        )
        if (surface.get("run") or {}).get("state") != "completed":
            raise RuntimeError("hardened feed retrieval did not complete")

        final_url, media, body = self._feed_response(capture, surface, task)
        feed_kind, parsed = self._parse_feed(media, body)
        run_id = "news443_" + secrets.token_hex(10)
        parent_event_id = str((surface.get("accepted") or {}).get("event_id") or "")
        hardening_run_id = str((surface.get("hardening") or {}).get("hardening_run_id") or "")
        ingested = 0
        duplicates = 0
        skipped = 0
        created = []

        for raw_item in parsed[:MAX_ITEMS_PER_RUN]:
            item, reason = self._normalize_item(source, raw_item)
            if item is None:
                skipped += 1
                self._record_item_row(
                    run_id=run_id,
                    external_id=str(raw_item.get("external_id") or ""),
                    canonical_url=str(raw_item.get("url") or ""),
                    published_at=str(raw_item.get("published_at") or ""),
                    state="skipped",
                    reason=reason,
                )
                continue
            if self._duplicate_external_id(source["source_id"], item["external_id"]):
                duplicates += 1
                self._record_item_row(
                    run_id=run_id,
                    external_id=item["external_id"],
                    canonical_url=item["canonical_url"],
                    published_at=item["published_at"],
                    state="duplicate",
                    reason="source_external_id_already_ingested",
                )
                continue

            payload = self._item_payload(source, item)
            digest = hashlib.sha256(payload).hexdigest()
            method = "rss" if feed_kind in {"rss", "atom"} else "api"
            event = self.events422.record(
                identity=ident,
                case_id=str(case_id),
                source_id=source["source_id"],
                target=item["canonical_url"],
                method=method,
                status="retrieved",
                content_sha256=digest,
                media_type="text/plain",
                bytes_count=len(payload),
                parent_event_id=parent_event_id,
                provenance={
                    "build": BUILD,
                    "feed_url": final_url,
                    "feed_kind": feed_kind,
                    "parent_feed_event_id": parent_event_id,
                    "normalized_feed_item": True,
                    "raw_feed_persisted": False,
                },
                usage={
                    "public_feed_only": True,
                    "article_body_fetched": False,
                    "authentication": False,
                    "paywall_bypass": False,
                    "javascript": False,
                },
            )
            content = self.content423.ingest(
                identity=ident,
                event_id=event["event_id"],
                content=payload,
                media_type="text/plain",
                metadata={
                    "build": BUILD,
                    "feed_kind": feed_kind,
                    "normalized_news_item": True,
                },
            )
            news = self.news429.ingest_item(
                identity=ident,
                case_id=str(case_id),
                source_id=source["source_id"],
                event_id=event["event_id"],
                content_id=content["content_id"],
                canonical_url=item["canonical_url"],
                title=item["title"],
                publisher=source["name"],
                author=item["author"],
                published_at=item["published_at"],
                language=item["language"],
                external_id=item["external_id"],
                connector_kind="rss" if feed_kind == "rss" else ("atom" if feed_kind == "atom" else "api"),
                metadata={
                    "build": BUILD,
                    "feed_url": final_url,
                    "feed_kind": feed_kind,
                    "summary_from_feed": bool(item["summary"]),
                    "article_body_fetched": False,
                    "semantic_extraction_performed": False,
                },
            )
            ingested += 1
            created.append(news["news_item_id"])
            self._record_item_row(
                run_id=run_id,
                news_item_id=news["news_item_id"],
                event_id=event["event_id"],
                content_id=content["content_id"],
                external_id=item["external_id"],
                canonical_url=item["canonical_url"],
                published_at=item["published_at"],
                state="ingested",
            )

        provenance = self.provenance431.analyze(identity=ident, case_id=str(case_id))
        run = self._persist_run(
            identity=ident,
            case_id=case_id,
            source_id=source["source_id"],
            task_id=task_id,
            feed_url=final_url,
            feed_kind=feed_kind,
            parsed_items=len(parsed),
            ingested_items=ingested,
            duplicate_items=duplicates,
            skipped_items=skipped,
            parent_event_id=parent_event_id,
            hardening_run_id=hardening_run_id,
            provenance_run_id=provenance["run_id"],
            execution_mode=execution_mode,
            external_network=external_network,
            run_id=run_id,
        )
        return {
            "run": run,
            "created_news_item_ids": created,
            "provenance": provenance,
            "surface": surface.get("run"),
            "hardening": surface.get("hardening"),
            "raw_feed_persisted": False,
            "automatic_semantic_extraction": False,
        }

    def execute_replay(self, *, identity, case_id, task_id, transport, resolver):
        return self._execute(
            identity=identity,
            case_id=case_id,
            task_id=task_id,
            transport=transport,
            resolver=resolver,
            execution_mode="deterministic_news_replay",
            authorization_mode="test_replay",
            live=False,
            external_network=False,
        )

    def execute_live(self, *, identity, case_id, task_id, confirmation):
        if str(confirmation or "").strip().upper() != LIVE_CONFIRM:
            raise PermissionError(f"explicit {LIVE_CONFIRM} confirmation required")
        return self._execute(
            identity=identity,
            case_id=case_id,
            task_id=task_id,
            transport=ProcessSurfaceTransport451(),
            resolver=self.hardening442._default_resolver,
            execution_mode="live_hardened_news_feed",
            authorization_mode="explicit_news_confirmation",
            live=True,
            external_network=True,
        )

    def run_case_selftest(self, *, identity, case_id):
        from eagleeye.crawler.engine import FetchResponse, StaticTransport

        ident = self._identity(identity)
        token = secrets.token_hex(5)
        base = f"https://news443-{token}.example.org/"
        source = self.registry421.register(
            identity=ident,
            name="Build 443 Synthetic News " + token,
            source_type="rss",
            access_mode="public",
            base_url=base + "feed.xml",
            capabilities=["news_feed", "rss", "public_articles"],
            coverage={
                "fixture_only": True,
                "live_execution_forbidden": True,
                "allowed_article_hosts": [f"news443-{token}.example.org"],
            },
            license_note="Synthetic Build 443 deterministic feed fixture.",
        )
        task = self.create_feed_task(
            identity=ident,
            case_id=str(case_id),
            source_id=source["source_id"],
        )
        host = f"news443-{token}.example.org"
        robots_url = f"https://{host}/robots.txt"
        article_one = f"https://{host}/article-1"
        article_two = f"https://{host}/article-2"
        feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Fixture</title>
<item><title>First public report</title><link>{article_one}</link><guid>fixture-1-{token}</guid><pubDate>Sat, 26 Sep 2026 10:00:00 GMT</pubDate><description>First summary.</description></item>
<item><title>Second public report</title><link>{article_two}</link><guid>fixture-2-{token}</guid><pubDate>Sat, 26 Sep 2026 11:00:00 GMT</pubDate><description>Second summary.</description></item>
</channel></rss>""".encode("utf-8")
        transport = StaticTransport(
            {
                robots_url: FetchResponse(
                    robots_url,
                    200,
                    {"content-type": "text/plain"},
                    b"User-agent: *\nAllow: /\n",
                    1,
                ),
                task["target"]: FetchResponse(
                    task["target"],
                    200,
                    {"content-type": "application/rss+xml; charset=utf-8"},
                    feed,
                    2,
                ),
            }
        )
        old_sleep = self.hardening442.sleep
        self.hardening442.sleep = lambda _seconds: None
        try:
            result = self.execute_replay(
                identity=ident,
                case_id=str(case_id),
                task_id=task["task_id"],
                transport=transport,
                resolver=lambda _host: ["93.184.216.34"],
            )
        finally:
            self.hardening442.sleep = old_sleep
        items = self.news429.case_items(str(case_id))
        checks = {
            "feed_retrieved": (result.get("surface") or {}).get("state") == "completed",
            "hardening_passed": (result.get("hardening") or {}).get("state") == "completed",
            "rss_detected": result["run"]["feed_kind"] == "rss",
            "two_items_ingested": result["run"]["ingested_items"] == 2,
            "no_duplicates": result["run"]["duplicate_items"] == 0,
            "two_news_items_visible": len(items) >= 2,
            "provenance_analysis_created": bool(result["run"]["provenance_run_id"]),
            "raw_feed_not_persisted": result["raw_feed_persisted"] is False,
            "semantic_extraction_not_faked": result["automatic_semantic_extraction"] is False,
            "no_external_network": result["run"]["external_network"] is False,
            "integrity_valid": self.verify_integrity()["valid"],
        }
        return {
            "build": BUILD,
            "case_id": str(case_id),
            "result": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "run": result["run"],
            "news_item_ids": result["created_news_item_ids"],
            "note": "Deterministic RSS replay; no external sockets and no automatic semantic claims.",
        }

    def run(self, run_id):
        row = self.db.one("SELECT * FROM news_acquisition_run_443 WHERE run_id=?", (str(run_id),))
        if not row:
            raise KeyError("Build-443 news acquisition run not found")
        out = dict(row)
        out["external_network"] = bool(out["external_network"])
        out["items"] = [
            dict(r)
            for r in self.db.all(
                "SELECT * FROM news_acquisition_item_443 WHERE run_id=? ORDER BY created_at,item_run_id",
                (str(run_id),),
            )
        ]
        return out

    def case_runs(self, case_id):
        return [
            self.run(r["run_id"])
            for r in self.db.all(
                "SELECT run_id FROM news_acquisition_run_443 WHERE case_id=? ORDER BY created_at,run_id",
                (str(case_id),),
            )
        ]

    def verify_integrity(self):
        bad = []
        for table, key in (
            ("news_acquisition_run_443", "run_id"),
            ("news_acquisition_item_443", "item_run_id"),
        ):
            for row in self.db.all(f"SELECT * FROM {table}"):
                item = dict(row)
                if self._rh(item) != item.get("record_hash"):
                    bad.append({"table": table, "id": item.get(key), "reason": "record_hash_mismatch"})
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        runs = int(self.db.one("SELECT COUNT(*) n FROM news_acquisition_run_443")["n"])
        external = int(
            self.db.one(
                "SELECT COUNT(*) n FROM news_acquisition_run_443 WHERE external_network=1"
            )["n"]
        )
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "runs": runs,
            "live_runs": external,
            "integrity_valid": self.verify_integrity()["valid"],
            "live_news_acquisition": True,
            "supported_feed_kinds": ["rss", "atom", "jsonfeed"],
            "public_sources_only": True,
            "authenticated_news_sources_supported": False,
            "feed_network_path": "Build 442 hardened public retrieval",
            "robots_fail_closed": True,
            "dns_rebinding_defense": True,
            "bounded_retry_and_rate_limit": True,
            "raw_feed_persisted": False,
            "normalized_news_items_persisted": True,
            "build429_integration": True,
            "build431_provenance_integration": True,
            "automatic_semantic_extraction_430": False,
            "article_body_fetch": False,
            "paywall_bypass": False,
            "javascript_execution": False,
            "automatic_live_execution": False,
            "live_confirmation": LIVE_CONFIRM,
            "autonomous_scope_expansion": False,
            "truth_determined": False,
            "production_release_ready": False,
        }
