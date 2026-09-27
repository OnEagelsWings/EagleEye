from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit
import hashlib
import ipaddress
import json
import secrets

from eagleeye_pro.phase19.surface_retrieval441 import PinnedSurfaceTransport441

BUILD = "444.0"
POLICY_ID = "phase20.controlled-public-social.v444"
LIVE_CONFIRM = "SOCIAL444_LIVE"
MAX_RESPONSE_BYTES = 1_000_000
MAX_OBJECTS_PER_RUN = 50
MAX_TEXT_CHARS = 12_000
ADAPTERS = {"mastodon_public", "bluesky_public", "generic_public"}
PUBLIC_VISIBILITY = {"public", "unlisted"}
JSON_MEDIA = {"application/json", "application/activity+json", "application/ld+json"}
_SENSITIVE_KEYS = (
    "password",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "session",
    "credential",
    "api_key",
    "apikey",
    "client_secret",
)


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
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="seconds")


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


def _public_host(url):
    parsed = urlsplit(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("public http(s) URL required")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("credential-bearing URLs are forbidden")
    host = parsed.hostname.casefold().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".onion"):
        raise ValueError("public non-onion host required")
    try:
        address = ipaddress.ip_address(host)
        if not address.is_global:
            raise ValueError("literal IP must be globally routable")
    except ValueError as exc:
        if "globally routable" in str(exc):
            raise
    return host


def _contains_sensitive_key(value):
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).casefold()
            if any(token in lowered for token in _SENSITIVE_KEYS):
                return True
            if _contains_sensitive_key(item):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value[:200])
    return False


class CapturingTransport444:
    transport_kind = "social444_memory_capture"

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


class ControlledPublicSocial444:
    """Single-endpoint public-social acquisition through Build 442 hardening.

    Build 444 deliberately does not paginate, enumerate social graphs, authenticate,
    message users, execute JavaScript, or discover hidden/private endpoints.
    """

    def __init__(
        self,
        db,
        audit,
        *,
        registry421,
        crawler425,
        events422,
        content423,
        social432,
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
        self.social432 = social432
        self.hardening442 = hardening442
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS social_acquisition_run_444(
            run_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            adapter TEXT NOT NULL,
            endpoint_url TEXT NOT NULL,
            parsed_objects INTEGER NOT NULL,
            ingested_objects INTEGER NOT NULL,
            duplicate_objects INTEGER NOT NULL,
            skipped_objects INTEGER NOT NULL,
            parent_event_id TEXT NOT NULL,
            hardening_run_id TEXT NOT NULL,
            execution_mode TEXT NOT NULL,
            external_network INTEGER NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_social444_case
            ON social_acquisition_run_444(case_id,created_at);

            CREATE TABLE IF NOT EXISTS social_acquisition_item_444(
            item_run_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            observation_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            content_id TEXT NOT NULL,
            external_object_id TEXT NOT NULL,
            canonical_url TEXT NOT NULL,
            object_type TEXT NOT NULL,
            state TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_social444_item_run
            ON social_acquisition_item_444(run_id,created_at);
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
            object_type="social_acquisition_444",
            object_id=str(source_id),
        )
        return ident

    def _source(self, source_id):
        source = self.registry421.get(source_id)
        if int(source.get("enabled", 0)) != 1:
            raise PermissionError("social source is disabled")
        if source.get("source_type") != "social":
            raise PermissionError("Build 444 requires source_type=social")
        if source.get("access_mode") != "public":
            raise PermissionError("Build 444 supports unauthenticated public sources only")
        adapter = str((source.get("coverage") or {}).get("social_adapter") or "").strip().lower()
        if adapter not in ADAPTERS:
            raise PermissionError("social source coverage.social_adapter must be explicitly reviewed")
        if adapter == "generic_public":
            schema = str((source.get("coverage") or {}).get("generic_schema") or "").strip()
            if schema != "eagleeye_public_social_v1":
                raise PermissionError("generic public social requires eagleeye_public_social_v1 schema")
        return source, adapter

    def _allowed_object_hosts(self, source):
        base_host = _public_host(source.get("base_url"))
        hosts = {base_host}
        for raw in (source.get("coverage") or {}).get("allowed_object_hosts", []) or []:
            host = str(raw or "").casefold().rstrip(".")
            if host:
                hosts.add(host)
        return hosts

    def create_task(self, *, identity, case_id, source_id, endpoint_url=""):
        ident = self._authorize(identity, case_id, source_id)
        source, adapter = self._source(source_id)
        target = str(endpoint_url or source.get("base_url") or "").strip()
        target_host = _public_host(target)
        base_host = _public_host(source.get("base_url"))
        if target_host != base_host:
            raise PermissionError("social endpoint must remain on exact registered source host")
        return self.crawler425.create_task(
            identity=ident,
            case_id=str(case_id),
            source_id=source_id,
            target=target,
            objective="Build 444 controlled public-social endpoint acquisition",
            scope={
                "allowed_hosts": [target_host],
                "social444": True,
                "social_adapter": adapter,
                "single_endpoint_only": True,
                "automatic_pagination": False,
                "social_graph_enumeration": False,
            },
            budget={
                "max_pages": 1,
                "max_bytes": MAX_RESPONSE_BYTES,
                "max_seconds": 20,
            },
        )

    def _response(self, capture, surface_result, task):
        run = surface_result.get("run") or {}
        final_url = str(run.get("final_url") or task["target"])
        response = capture.latest_for(final_url)
        if response is None:
            raise RuntimeError("Build 444 could not access in-memory social response")
        body = bytes(getattr(response, "body", b"") or b"")
        if not body:
            raise ValueError("public-social response is empty")
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("public-social response exceeds byte limit")
        media = str((getattr(response, "headers", {}) or {}).get("content-type", "")).split(";", 1)[0].strip().casefold()
        if media and media not in JSON_MEDIA:
            raise ValueError("Build 444 accepts JSON public-social responses only")
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception as exc:
            raise ValueError("public-social response is not valid UTF-8 JSON") from exc
        if _contains_sensitive_key(data):
            raise ValueError("credential/session-like fields detected in public-social response")
        return final_url, media, data

    def _canonical_bluesky_url(self, post):
        author = post.get("author") or {}
        handle = str(author.get("handle") or author.get("did") or "").strip()
        uri = str(post.get("uri") or "").strip()
        rkey = uri.rsplit("/", 1)[-1] if uri.startswith("at://") else ""
        if not handle or not rkey:
            return ""
        return "https://bsky.app/profile/" + quote(handle, safe=":@.-") + "/post/" + quote(rkey, safe="")

    def _normalize_mastodon_status(self, item):
        visibility = str(item.get("visibility") or "").casefold()
        if visibility not in PUBLIC_VISIBILITY:
            return None, "non_public_visibility"
        external_id = str(item.get("id") or "").strip()
        canonical = str(item.get("url") or item.get("uri") or "").strip()
        created = _iso(item.get("created_at"))
        account = item.get("account") or {}
        if not external_id:
            return None, "missing_external_object_id"
        if not canonical:
            return None, "missing_canonical_url"
        if not created:
            return None, "missing_or_invalid_publication_time"
        reshare = item.get("reblog") if isinstance(item.get("reblog"), dict) else None
        text_source = (reshare or item).get("content") or ""
        metrics = {
            "replies": int(item.get("replies_count") or 0),
            "reshares": int(item.get("reblogs_count") or 0),
            "likes": int(item.get("favourites_count") or 0),
        }
        return {
            "adapter": "mastodon_public",
            "platform": "mastodon",
            "object_type": "post",
            "external_object_id": external_id,
            "account_id": str(account.get("id") or "")[:300],
            "account_handle": str(account.get("acct") or account.get("username") or "")[:200],
            "canonical_url": canonical,
            "published_at": created,
            "visibility": visibility,
            "language": str(item.get("language") or "").lower()[:32],
            "reply_to_external_id": str(item.get("in_reply_to_id") or "")[:500],
            "reshare_of_external_id": str((reshare or {}).get("id") or "")[:500],
            "metrics": metrics,
            "text": _plain(text_source),
            "metadata": {
                "build": BUILD,
                "source_observation": True,
                "article_or_profile_expansion": False,
            },
        }, ""

    def _mastodon_objects(self, data):
        if isinstance(data, list):
            raw = data
        elif isinstance(data, dict) and "id" in data:
            raw = [data]
        else:
            raise ValueError("unsupported Mastodon public response shape")
        out = []
        for item in raw[:MAX_OBJECTS_PER_RUN]:
            if not isinstance(item, dict):
                continue
            out.append(self._normalize_mastodon_status(item))
        return out

    def _normalize_bluesky_post(self, post):
        if not isinstance(post, dict):
            return None, "invalid_post_object"
        uri = str(post.get("uri") or "").strip()
        record = post.get("record") or {}
        created = _iso(record.get("createdAt") or post.get("indexedAt"))
        canonical = self._canonical_bluesky_url(post)
        author = post.get("author") or {}
        if not uri:
            return None, "missing_external_object_id"
        if not canonical:
            return None, "missing_canonical_url"
        if not created:
            return None, "missing_or_invalid_publication_time"
        reply = record.get("reply") if isinstance(record.get("reply"), dict) else {}
        reply_parent = reply.get("parent") if isinstance(reply.get("parent"), dict) else {}
        return {
            "adapter": "bluesky_public",
            "platform": "bluesky",
            "object_type": "post",
            "external_object_id": uri,
            "account_id": str(author.get("did") or "")[:300],
            "account_handle": str(author.get("handle") or "")[:200],
            "canonical_url": canonical,
            "published_at": created,
            "visibility": "public",
            "language": str((record.get("langs") or [""])[0] if isinstance(record.get("langs"), list) else "")[:32].lower(),
            "reply_to_external_id": str(reply_parent.get("uri") or "")[:500],
            "reshare_of_external_id": "",
            "metrics": {
                "replies": int(post.get("replyCount") or 0),
                "reshares": int(post.get("repostCount") or 0),
                "likes": int(post.get("likeCount") or 0),
                "quotes": int(post.get("quoteCount") or 0),
            },
            "text": _plain(record.get("text") or ""),
            "metadata": {
                "build": BUILD,
                "source_observation": True,
                "indexed_at": str(post.get("indexedAt") or ""),
                "social_graph_enumerated": False,
            },
        }, ""

    def _bluesky_objects(self, data):
        posts = []
        if isinstance(data, dict) and isinstance(data.get("feed"), list):
            for item in data["feed"][:MAX_OBJECTS_PER_RUN]:
                if isinstance(item, dict) and isinstance(item.get("post"), dict):
                    posts.append(item["post"])
        elif isinstance(data, dict) and isinstance(data.get("posts"), list):
            posts = [x for x in data["posts"][:MAX_OBJECTS_PER_RUN] if isinstance(x, dict)]
        elif isinstance(data, dict) and isinstance((data.get("thread") or {}).get("post"), dict):
            posts = [data["thread"]["post"]]
        elif isinstance(data, dict) and "uri" in data and "record" in data:
            posts = [data]
        else:
            raise ValueError("unsupported Bluesky public AppView response shape")
        return [self._normalize_bluesky_post(post) for post in posts]

    def _generic_objects(self, data):
        raw = data.get("items") if isinstance(data, dict) else data
        if not isinstance(raw, list):
            raise ValueError("generic public social response must be an items array or list")
        out = []
        for item in raw[:MAX_OBJECTS_PER_RUN]:
            if not isinstance(item, dict):
                out.append((None, "invalid_item"))
                continue
            visibility = str(item.get("visibility") or "public").casefold()
            if visibility not in PUBLIC_VISIBILITY:
                out.append((None, "non_public_visibility"))
                continue
            external_id = str(item.get("external_object_id") or "").strip()
            canonical = str(item.get("canonical_url") or "").strip()
            published = _iso(item.get("published_at"))
            object_type = str(item.get("object_type") or "post").casefold()
            if object_type not in {"post", "profile", "thread", "account"}:
                out.append((None, "unsupported_object_type"))
                continue
            if not external_id:
                out.append((None, "missing_external_object_id"))
                continue
            if not canonical:
                out.append((None, "missing_canonical_url"))
                continue
            if object_type in {"post", "thread"} and not published:
                out.append((None, "missing_or_invalid_publication_time"))
                continue
            if object_type in {"profile", "account"} and not published:
                published = _now()
                timestamp_semantics = "observed_at_collection_time"
            else:
                timestamp_semantics = "source_published_at"
            metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
            cleaned_metrics = {}
            for key, value in metrics.items():
                try:
                    number = int(value)
                except Exception:
                    continue
                if number >= 0:
                    cleaned_metrics[str(key).lower()[:64]] = number
            out.append(
                (
                    {
                        "adapter": "generic_public",
                        "platform": str(item.get("platform") or "generic").lower()[:80],
                        "object_type": object_type,
                        "external_object_id": external_id[:500],
                        "account_id": str(item.get("account_id") or "")[:300],
                        "account_handle": str(item.get("account_handle") or "")[:200],
                        "canonical_url": canonical,
                        "published_at": published,
                        "visibility": visibility,
                        "language": str(item.get("language") or "").lower()[:32],
                        "reply_to_external_id": str(item.get("reply_to_external_id") or "")[:500],
                        "reshare_of_external_id": str(item.get("reshare_of_external_id") or "")[:500],
                        "metrics": cleaned_metrics,
                        "text": _plain(item.get("text") or ""),
                        "metadata": {
                            "build": BUILD,
                            "source_observation": True,
                            "timestamp_semantics": timestamp_semantics,
                            "generic_schema": "eagleeye_public_social_v1",
                        },
                    },
                    "",
                )
            )
        return out

    def _parse(self, adapter, data):
        if adapter == "mastodon_public":
            return self._mastodon_objects(data)
        if adapter == "bluesky_public":
            return self._bluesky_objects(data)
        if adapter == "generic_public":
            return self._generic_objects(data)
        raise ValueError("unsupported social adapter")

    def _normalize_object(self, source, expected_adapter, parsed):
        item, reason = parsed
        if item is None:
            return None, reason
        if item["adapter"] != expected_adapter:
            return None, "adapter_mismatch"
        try:
            host = _public_host(item["canonical_url"])
        except ValueError:
            return None, "invalid_canonical_url"
        if host not in self._allowed_object_hosts(source):
            return None, "object_host_outside_source_allowlist"
        if item["visibility"] not in PUBLIC_VISIBILITY:
            return None, "non_public_visibility"
        if not item["text"] and item["object_type"] in {"post", "thread"}:
            return None, "empty_public_text"
        return item, ""

    def _duplicate(self, source_id, adapter, object_type, external_id):
        return bool(
            self.db.one(
                "SELECT 1 FROM social_observation_432 "
                "WHERE source_id=? AND adapter=? AND object_type=? AND external_object_id=? LIMIT 1",
                (str(source_id), str(adapter), str(object_type), str(external_id)),
            )
        )

    def _payload(self, item):
        return (
            f"PLATFORM: {item['platform']}\n"
            f"OBJECT_TYPE: {item['object_type']}\n"
            f"ACCOUNT: {item['account_handle']}\n"
            f"CANONICAL_URL: {item['canonical_url']}\n"
            f"PUBLISHED_AT: {item['published_at']}\n"
            f"VISIBILITY: {item['visibility']}\n"
            f"TEXT: {item['text']}"
        ).encode("utf-8")

    def _record_item(
        self,
        *,
        run_id,
        observation_id="",
        event_id="",
        content_id="",
        external_object_id="",
        canonical_url="",
        object_type="",
        state,
        reason="",
    ):
        row = {
            "item_run_id": "social444item_" + secrets.token_hex(8),
            "run_id": str(run_id),
            "observation_id": str(observation_id or ""),
            "event_id": str(event_id or ""),
            "content_id": str(content_id or ""),
            "external_object_id": str(external_object_id or ""),
            "canonical_url": str(canonical_url or ""),
            "object_type": str(object_type or ""),
            "state": str(state),
            "reason": str(reason or "")[:300],
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO social_acquisition_item_444 VALUES("
            + ",".join("?" for _ in row)
            + ")",
            tuple(row.values()),
        )
        return row

    def _record_run(
        self,
        *,
        identity,
        case_id,
        source_id,
        task_id,
        adapter,
        endpoint_url,
        parsed_objects,
        ingested_objects,
        duplicate_objects,
        skipped_objects,
        parent_event_id,
        hardening_run_id,
        execution_mode,
        external_network,
        run_id,
    ):
        row = {
            "run_id": str(run_id),
            "case_id": str(case_id),
            "source_id": str(source_id),
            "task_id": str(task_id),
            "adapter": str(adapter),
            "endpoint_url": str(endpoint_url),
            "parsed_objects": int(parsed_objects),
            "ingested_objects": int(ingested_objects),
            "duplicate_objects": int(duplicate_objects),
            "skipped_objects": int(skipped_objects),
            "parent_event_id": str(parent_event_id),
            "hardening_run_id": str(hardening_run_id),
            "execution_mode": str(execution_mode),
            "external_network": 1 if external_network else 0,
            "created_by": str(identity["username"]),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO social_acquisition_run_444 VALUES("
            + ",".join("?" for _ in row)
            + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "social_acquisition_run_444",
            "social_acquisition_run_444",
            run_id,
            str(case_id),
            {
                "source_id": source_id,
                "adapter": adapter,
                "ingested_objects": ingested_objects,
                "duplicates": duplicate_objects,
                "skipped": skipped_objects,
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
            raise PermissionError("social task does not belong to requested case")
        self._authorize(ident, case_id, task["source_id"])
        source, adapter = self._source(task["source_id"])
        if live and bool((source.get("coverage") or {}).get("fixture_only")):
            raise PermissionError("synthetic social fixture cannot use live acquisition")
        if task["state"] != "planned":
            raise ValueError("social acquisition task must be planned")
        scope = task.get("scope") or {}
        if not bool(scope.get("social444")) or str(scope.get("social_adapter") or "") != adapter:
            raise PermissionError("task was not created as a Build-444 social task")

        capture = CapturingTransport444(transport)
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
            raise RuntimeError("hardened public-social retrieval did not complete")
        final_url, _media, data = self._response(capture, surface, task)
        parsed = self._parse(adapter, data)

        run_id = "social444_" + secrets.token_hex(10)
        parent_event_id = str((surface.get("accepted") or {}).get("event_id") or "")
        hardening_run_id = str((surface.get("hardening") or {}).get("hardening_run_id") or "")
        ingested = 0
        duplicates = 0
        skipped = 0
        created = []

        for raw in parsed[:MAX_OBJECTS_PER_RUN]:
            item, reason = self._normalize_object(source, adapter, raw)
            if item is None:
                skipped += 1
                self._record_item(
                    run_id=run_id,
                    state="skipped",
                    reason=reason,
                )
                continue
            if self._duplicate(
                source["source_id"],
                adapter,
                item["object_type"],
                item["external_object_id"],
            ):
                duplicates += 1
                self._record_item(
                    run_id=run_id,
                    external_object_id=item["external_object_id"],
                    canonical_url=item["canonical_url"],
                    object_type=item["object_type"],
                    state="duplicate",
                    reason="source_adapter_object_external_id_already_ingested",
                )
                continue

            payload = self._payload(item)
            digest = hashlib.sha256(payload).hexdigest()
            event = self.events422.record(
                identity=ident,
                case_id=str(case_id),
                source_id=source["source_id"],
                target=item["canonical_url"],
                method="social_api",
                status="retrieved",
                content_sha256=digest,
                media_type="text/plain",
                bytes_count=len(payload),
                parent_event_id=parent_event_id,
                provenance={
                    "build": BUILD,
                    "adapter": adapter,
                    "endpoint_url": final_url,
                    "parent_endpoint_event_id": parent_event_id,
                    "normalized_public_social_object": True,
                    "raw_endpoint_response_persisted": False,
                },
                usage={
                    "public_only": True,
                    "authenticated": False,
                    "private_or_direct_content": False,
                    "social_graph_enumeration": False,
                    "automatic_pagination": False,
                    "messaging": False,
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
                    "adapter": adapter,
                    "normalized_public_social_object": True,
                },
            )
            observation = self.social432.record(
                identity=ident,
                case_id=str(case_id),
                source_id=source["source_id"],
                event_id=event["event_id"],
                content_id=content["content_id"],
                adapter=adapter,
                canonical_url=item["canonical_url"],
                external_object_id=item["external_object_id"],
                platform=item["platform"],
                object_type=item["object_type"],
                account_id=item["account_id"],
                account_handle=item["account_handle"],
                published_at=item["published_at"],
                visibility=item["visibility"],
                language=item["language"],
                reply_to_external_id=item["reply_to_external_id"],
                reshare_of_external_id=item["reshare_of_external_id"],
                metrics=item["metrics"],
                metadata={
                    **item["metadata"],
                    "endpoint_url": final_url,
                    "raw_endpoint_response_persisted": False,
                },
                test_fixture=False,
            )
            ingested += 1
            created.append(observation["observation_id"])
            self._record_item(
                run_id=run_id,
                observation_id=observation["observation_id"],
                event_id=event["event_id"],
                content_id=content["content_id"],
                external_object_id=item["external_object_id"],
                canonical_url=item["canonical_url"],
                object_type=item["object_type"],
                state="ingested",
            )

        run = self._record_run(
            identity=ident,
            case_id=case_id,
            source_id=source["source_id"],
            task_id=task_id,
            adapter=adapter,
            endpoint_url=final_url,
            parsed_objects=len(parsed),
            ingested_objects=ingested,
            duplicate_objects=duplicates,
            skipped_objects=skipped,
            parent_event_id=parent_event_id,
            hardening_run_id=hardening_run_id,
            execution_mode=execution_mode,
            external_network=external_network,
            run_id=run_id,
        )
        return {
            "run": run,
            "created_observation_ids": created,
            "surface": surface.get("run"),
            "hardening": surface.get("hardening"),
            "raw_endpoint_response_persisted": False,
            "automatic_pagination": False,
            "social_graph_enumeration": False,
        }

    def execute_replay(self, *, identity, case_id, task_id, transport, resolver):
        return self._execute(
            identity=identity,
            case_id=case_id,
            task_id=task_id,
            transport=transport,
            resolver=resolver,
            execution_mode="deterministic_social_replay",
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
            transport=PinnedSurfaceTransport441(),
            resolver=self.hardening442._default_resolver,
            execution_mode="live_hardened_public_social_get",
            authorization_mode="explicit_social_confirmation",
            live=True,
            external_network=True,
        )

    def run_case_selftest(self, *, identity, case_id):
        from eagleeye.crawler.engine import FetchResponse, StaticTransport

        ident = self._identity(identity)
        token = secrets.token_hex(5)
        host = f"social444-{token}.example.org"
        endpoint = f"https://{host}/public.json"
        source = self.registry421.register(
            identity=ident,
            name="Build 444 Synthetic Public Social " + token,
            source_type="social",
            access_mode="public",
            base_url=endpoint,
            capabilities=["public_posts", "public_json", "case_fixture"],
            coverage={
                "fixture_only": True,
                "live_execution_forbidden": True,
                "social_adapter": "generic_public",
                "generic_schema": "eagleeye_public_social_v1",
                "allowed_object_hosts": [host],
            },
            license_note="Synthetic Build 444 deterministic public-social fixture.",
        )
        task = self.create_task(
            identity=ident,
            case_id=str(case_id),
            source_id=source["source_id"],
        )
        robots = f"https://{host}/robots.txt"
        object_url = f"https://{host}/posts/{token}"
        response = {
            "items": [
                {
                    "external_object_id": "social-" + token,
                    "canonical_url": object_url,
                    "published_at": "2026-09-26T16:00:00Z",
                    "text": "Synthetic public social observation " + token,
                    "platform": "generic",
                    "object_type": "post",
                    "visibility": "public",
                    "account_id": "acct-" + token,
                    "account_handle": "@fixture",
                    "language": "en",
                    "metrics": {"likes": 2, "replies": 1},
                }
            ]
        }
        transport = StaticTransport(
            {
                robots: FetchResponse(
                    robots,
                    200,
                    {"content-type": "text/plain"},
                    b"User-agent: *\nAllow: /\n",
                    1,
                ),
                endpoint: FetchResponse(
                    endpoint,
                    200,
                    {"content-type": "application/json"},
                    json.dumps(response).encode("utf-8"),
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
        observations = self.social432.case_items(str(case_id), include_fixtures=False)
        checks = {
            "endpoint_retrieved": (result.get("surface") or {}).get("state") == "completed",
            "hardening_passed": (result.get("hardening") or {}).get("state") == "completed",
            "one_object_ingested": result["run"]["ingested_objects"] == 1,
            "observation_visible": any(
                x["observation_id"] in result["created_observation_ids"] for x in observations
            ),
            "build432_live_observation_not_fixture": all(
                not x["test_fixture"] for x in observations if x["observation_id"] in result["created_observation_ids"]
            ),
            "no_external_network": result["run"]["external_network"] is False,
            "no_pagination": result["automatic_pagination"] is False,
            "no_social_graph_enumeration": result["social_graph_enumeration"] is False,
            "integrity_valid": self.verify_integrity()["valid"],
        }
        return {
            "build": BUILD,
            "case_id": str(case_id),
            "result": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "run": result["run"],
            "observation_ids": result["created_observation_ids"],
            "note": "Deterministic generic-public social replay; no external sockets, login, pagination or graph enumeration.",
        }

    def run(self, run_id):
        row = self.db.one("SELECT * FROM social_acquisition_run_444 WHERE run_id=?", (str(run_id),))
        if not row:
            raise KeyError("Build-444 social acquisition run not found")
        out = dict(row)
        out["external_network"] = bool(out["external_network"])
        out["items"] = [
            dict(r)
            for r in self.db.all(
                "SELECT * FROM social_acquisition_item_444 WHERE run_id=? ORDER BY created_at,item_run_id",
                (str(run_id),),
            )
        ]
        return out

    def case_runs(self, case_id):
        return [
            self.run(r["run_id"])
            for r in self.db.all(
                "SELECT run_id FROM social_acquisition_run_444 WHERE case_id=? ORDER BY created_at,run_id",
                (str(case_id),),
            )
        ]

    def verify_integrity(self):
        bad = []
        for table, key in (
            ("social_acquisition_run_444", "run_id"),
            ("social_acquisition_item_444", "item_run_id"),
        ):
            for row in self.db.all(f"SELECT * FROM {table}"):
                item = dict(row)
                if self._rh(item) != item.get("record_hash"):
                    bad.append({"table": table, "id": item.get(key), "reason": "record_hash_mismatch"})
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        runs = int(self.db.one("SELECT COUNT(*) n FROM social_acquisition_run_444")["n"])
        live = int(
            self.db.one(
                "SELECT COUNT(*) n FROM social_acquisition_run_444 WHERE external_network=1"
            )["n"]
        )
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "runs": runs,
            "live_runs": live,
            "integrity_valid": self.verify_integrity()["valid"],
            "controlled_public_social_acquisition": True,
            "supported_adapters": sorted(ADAPTERS),
            "mastodon_public_json": True,
            "bluesky_public_appview_json": True,
            "generic_public_schema": "eagleeye_public_social_v1",
            "public_sources_only": True,
            "authenticated_social_supported": False,
            "private_or_direct_content_supported": False,
            "messaging_supported": False,
            "automatic_pagination": False,
            "follower_following_enumeration": False,
            "social_graph_enumeration": False,
            "javascript_execution": False,
            "raw_endpoint_response_persisted": False,
            "build432_integration": True,
            "build442_hardened_network_path": True,
            "robots_fail_closed": True,
            "dns_rebinding_defense": True,
            "bounded_retry_and_rate_limit": True,
            "automatic_live_execution": False,
            "live_confirmation": LIVE_CONFIRM,
            "autonomous_scope_expansion": False,
            "truth_determined": False,
            "production_release_ready": False,
        }
