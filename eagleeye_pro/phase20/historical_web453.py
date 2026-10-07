from __future__ import annotations

from datetime import datetime, timezone
import difflib
import hashlib
import ipaddress
import json
import re
import secrets
from urllib.parse import quote, urlencode, urlsplit

BUILD = "453.0"
POLICY_ID = "phase20.historical-web-intelligence.v453"
PROVIDERS = ("internet_archive", "common_crawl")
MAX_IMPORTED_RECORDS = 1000
MAX_COMPARE_LINES = 120


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value):
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _public_url(value):
    text = str(value or "").strip()
    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("historical target must be an absolute public http(s) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("credentials are forbidden in historical target URLs")
    host = parsed.hostname.casefold()
    if host.endswith(".onion"):
        raise ValueError("onion history requires the isolated Tor path")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("local/private historical targets are forbidden")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise ValueError("local/private historical targets are forbidden")
    return text


def _timestamp(value):
    raw = str(value or "").strip()
    if re.fullmatch(r"\d{14}", raw):
        dt = datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        return dt.isoformat(timespec="seconds")
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("capture timestamp must be Wayback YYYYmmddHHMMSS or ISO-8601") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _wayback_timestamp(iso_timestamp):
    dt = datetime.fromisoformat(str(iso_timestamp).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")


def _norm_lines(text):
    out = []
    for line in str(text or "").splitlines():
        clean = re.sub(r"\s+", " ", line).strip()
        if len(clean) >= 3:
            out.append(clean[:1000])
    return out


class HistoricalWebIntelligence453:
    def __init__(self, db, audit, *, events422, content423, archive428, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.events422 = events422
        self.content423 = content423
        self.archive428 = archive428
        self.actor = actor
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS historical_query_453(
          query_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          original_url TEXT NOT NULL,
          from_time TEXT NOT NULL,
          to_time TEXT NOT NULL,
          providers_json TEXT NOT NULL,
          provider_options_json TEXT NOT NULL,
          max_captures INTEGER NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          record_hash TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_hq453_case_url
          ON historical_query_453(case_id, original_url, created_at);

        CREATE TABLE IF NOT EXISTS historical_candidate_453(
          candidate_id TEXT PRIMARY KEY,
          query_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          provider TEXT NOT NULL,
          captured_at TEXT NOT NULL,
          original_url TEXT NOT NULL,
          archive_url TEXT NOT NULL,
          status_code INTEGER NOT NULL,
          media_type TEXT NOT NULL,
          provider_digest TEXT NOT NULL,
          index_event_id TEXT NOT NULL,
          index_content_id TEXT NOT NULL,
          source_ref TEXT NOT NULL,
          provider_metadata_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          record_hash TEXT NOT NULL,
          UNIQUE(query_id, provider, captured_at, archive_url, provider_digest)
        );
        CREATE INDEX IF NOT EXISTS idx_hc453_case_url_time
          ON historical_candidate_453(case_id, original_url, captured_at);

        CREATE TABLE IF NOT EXISTS historical_capture_link_453(
          link_id TEXT PRIMARY KEY,
          candidate_id TEXT NOT NULL UNIQUE,
          archive_capture_id TEXT NOT NULL UNIQUE,
          retrieved_event_id TEXT NOT NULL,
          content_id TEXT NOT NULL,
          linked_by TEXT NOT NULL,
          linked_at TEXT NOT NULL,
          record_hash TEXT NOT NULL
        );
        """)
        self.db.conn.commit()

    def _identity(self, identity):
        if not isinstance(identity, dict):
            raise PermissionError("active identity required")
        actor = str(identity.get("username") or identity.get("user_id") or "").strip()
        if not actor:
            raise PermissionError("active identity required")
        return actor

    def _record_hash(self, record):
        return _sha({k: record[k] for k in record if k != "record_hash"})

    def create_query(self, *, identity, case_id, original_url, providers=PROVIDERS,
                     from_time="", to_time="", max_captures=200, common_crawl_index=""):
        actor = self._identity(identity)
        case_id = str(case_id or "").strip()
        if not case_id:
            raise ValueError("case_id required")
        url = _public_url(original_url)
        if isinstance(providers, str):
            providers = [providers]
        selected = tuple(dict.fromkeys(str(p).strip().lower() for p in providers if str(p).strip()))
        if not selected or any(p not in PROVIDERS for p in selected):
            raise ValueError("unsupported historical provider")
        now = datetime.now(timezone.utc)
        start = _timestamp(from_time) if from_time else datetime(1990, 1, 1, tzinfo=timezone.utc).isoformat(timespec="seconds")
        end = _timestamp(to_time) if to_time else now.isoformat(timespec="seconds")
        if start > end:
            raise ValueError("historical query from_time must not be after to_time")
        limit = max(1, min(int(max_captures), 1000))
        cc_index = str(common_crawl_index or "").strip()
        if "common_crawl" in selected and cc_index and not re.fullmatch(r"CC-MAIN-\d{4}-\d{2}", cc_index):
            raise ValueError("invalid Common Crawl index name")
        options = {"common_crawl_index": cc_index}
        query_id = "histq453_" + secrets.token_hex(10)
        record = {
            "query_id": query_id,
            "case_id": case_id,
            "original_url": url,
            "from_time": start,
            "to_time": end,
            "providers_json": _canon(list(selected)),
            "provider_options_json": _canon(options),
            "max_captures": limit,
            "created_by": actor,
            "created_at": _now(),
        }
        record["record_hash"] = self._record_hash(record)
        self.db.execute(
            "INSERT INTO historical_query_453 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            tuple(record.values()),
        )
        self.audit.log(
            "historical_query_created_453", "historical_query_453", query_id, case_id,
            {"original_url": url, "providers": list(selected), "max_captures": limit},
        )
        return {**record, "providers": list(selected), "provider_options": options,
                "requests": self.provider_requests(query_id)}

    def get_query(self, query_id):
        row = self.db.one("SELECT * FROM historical_query_453 WHERE query_id=?", (query_id,))
        if not row:
            raise KeyError("historical query not found")
        out = dict(row)
        out["providers"] = json.loads(out.pop("providers_json"))
        out["provider_options"] = json.loads(out.pop("provider_options_json"))
        return out

    def provider_requests(self, query_id):
        query = self.get_query(query_id)
        dt_from = datetime.fromisoformat(query["from_time"].replace("Z", "+00:00"))
        dt_to = datetime.fromisoformat(query["to_time"].replace("Z", "+00:00"))
        requests = []
        if "internet_archive" in query["providers"]:
            params = {
                "url": query["original_url"],
                "output": "json",
                "fl": "timestamp,original,statuscode,mimetype,digest",
                "filter": "statuscode:200",
                "collapse": "digest",
                "from": dt_from.strftime("%Y"),
                "to": dt_to.strftime("%Y"),
                "limit": str(query["max_captures"]),
            }
            requests.append({
                "provider": "internet_archive",
                "url": "https://web.archive.org/cdx/search/cdx?" + urlencode(params),
                "method": "GET",
                "expected_format": "wayback_cdx_json",
                "public_only": True,
            })
        if "common_crawl" in query["providers"]:
            index = query["provider_options"].get("common_crawl_index") or ""
            if index:
                params = {
                    "url": query["original_url"],
                    "output": "json",
                    "filter": "status:200",
                }
                requests.append({
                    "provider": "common_crawl",
                    "url": f"https://index.commoncrawl.org/{quote(index, safe='-')}-index?" + urlencode(params),
                    "method": "GET",
                    "expected_format": "common_crawl_cdxj",
                    "public_only": True,
                    "index": index,
                })
            else:
                requests.append({
                    "provider": "common_crawl",
                    "url": "",
                    "method": "GET",
                    "expected_format": "common_crawl_cdxj",
                    "public_only": True,
                    "requires_index_selection": True,
                    "note": "Select a current CC-MAIN index before live execution.",
                })
        return requests

    def _payload_text(self, payload):
        if isinstance(payload, bytes):
            raw = bytes(payload)
            text = raw.decode("utf-8", errors="strict")
        elif isinstance(payload, str):
            text = payload
            raw = text.encode("utf-8")
        else:
            raise ValueError("historical index payload must be UTF-8 text")
        if len(raw) > 4_000_000:
            raise ValueError("historical index payload exceeds bounded import size")
        return text, raw

    def _verify_index_provenance(self, *, query, provider, event_id, content_id, payload_bytes):
        event = self.events422.get(event_id)
        if event["case_id"] != query["case_id"]:
            raise ValueError("index event belongs to another case")
        observation = self.db.one(
            "SELECT 1 ok FROM content_observation_423 WHERE event_id=? AND content_id=?",
            (event_id, content_id),
        )
        if not observation:
            raise ValueError("index content is not linked to the acquisition event")
        content = self.db.one(
            "SELECT sha256 FROM content_object_423 WHERE content_id=?", (content_id,)
        )
        if not content or content["sha256"] != hashlib.sha256(payload_bytes).hexdigest():
            raise ValueError("supplied index payload does not match referenced content hash")
        host = (urlsplit(event["target"]).hostname or "").casefold()
        expected = {
            "internet_archive": {"web.archive.org"},
            "common_crawl": {"index.commoncrawl.org"},
        }[provider]
        if host not in expected:
            raise ValueError("index event target does not match historical provider")
        return event

    def _parse_wayback(self, payload):
        data = json.loads(str(payload))
        if not isinstance(data, list) or not data:
            return []
        if isinstance(data[0], list):
            header = [str(x).strip().lower() for x in data[0]]
            rows = [dict(zip(header, row)) for row in data[1:] if isinstance(row, list)]
        else:
            rows = [dict(x) for x in data if isinstance(x, dict)]
        return rows[:MAX_IMPORTED_RECORDS]

    def _parse_common_crawl(self, payload):
        rows = []
        for line in str(payload).splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
            if len(rows) >= MAX_IMPORTED_RECORDS:
                break
        return rows

    def import_index_payload(self, *, identity, query_id, provider, payload,
                             index_event_id, index_content_id, source_ref=""):
        self._identity(identity)
        query = self.get_query(query_id)
        provider = str(provider or "").strip().lower()
        if provider not in query["providers"]:
            raise ValueError("provider was not authorized by the historical query")
        payload_text, payload_bytes = self._payload_text(payload)
        self._verify_index_provenance(
            query=query, provider=provider, event_id=index_event_id,
            content_id=index_content_id, payload_bytes=payload_bytes
        )
        rows = self._parse_wayback(payload_text) if provider == "internet_archive" else self._parse_common_crawl(payload_text)
        created, skipped = [], 0
        lower, upper = query["from_time"], query["to_time"]
        for raw in rows:
            try:
                if provider == "internet_archive":
                    captured = _timestamp(raw.get("timestamp"))
                    original = _public_url(raw.get("original") or query["original_url"])
                    status = int(raw.get("statuscode") or 0)
                    media = str(raw.get("mimetype") or "")
                    digest = str(raw.get("digest") or "")
                    archive_url = f"https://web.archive.org/web/{_wayback_timestamp(captured)}id_/{original}"
                    meta = {}
                else:
                    captured = _timestamp(raw.get("timestamp"))
                    original = _public_url(raw.get("url") or query["original_url"])
                    status = int(raw.get("status") or 0)
                    media = str(raw.get("mime") or raw.get("mime-detected") or "")
                    digest = str(raw.get("digest") or "")
                    filename = str(raw.get("filename") or "")
                    offset = str(raw.get("offset") or "")
                    length = str(raw.get("length") or "")
                    archive_url = ("https://data.commoncrawl.org/" + filename) if filename else ""
                    meta = {"filename": filename, "offset": offset, "length": length,
                            "warc_range_required": bool(filename and offset and length)}
                if not (lower <= captured <= upper):
                    skipped += 1
                    continue
                if status and not 100 <= status <= 599:
                    skipped += 1
                    continue
                candidate_id = "histc453_" + secrets.token_hex(10)
                record = {
                    "candidate_id": candidate_id,
                    "query_id": query_id,
                    "case_id": query["case_id"],
                    "provider": provider,
                    "captured_at": captured,
                    "original_url": original,
                    "archive_url": archive_url,
                    "status_code": status,
                    "media_type": media,
                    "provider_digest": digest,
                    "index_event_id": index_event_id,
                    "index_content_id": index_content_id,
                    "source_ref": str(source_ref or ""),
                    "provider_metadata_json": _canon(meta),
                    "created_at": _now(),
                }
                record["record_hash"] = self._record_hash(record)
                try:
                    self.db.execute(
                        "INSERT INTO historical_candidate_453 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        tuple(record.values()),
                    )
                except Exception as exc:
                    if "UNIQUE constraint failed" in str(exc):
                        skipped += 1
                        continue
                    raise
                created.append(candidate_id)
            except (TypeError, ValueError):
                skipped += 1
                continue
            if len(created) >= query["max_captures"]:
                break
        self.audit.log(
            "historical_index_imported_453", "historical_query_453", query_id, query["case_id"],
            {"provider": provider, "created": len(created), "skipped": skipped,
             "index_event_id": index_event_id, "index_content_id": index_content_id},
        )
        return {"build": BUILD, "query_id": query_id, "provider": provider,
                "created": len(created), "skipped": skipped,
                "candidate_ids": created, "truth_determined": False}

    def candidates(self, query_id):
        rows = self.db.all(
            "SELECT * FROM historical_candidate_453 WHERE query_id=? "
            "ORDER BY julianday(captured_at), provider, candidate_id",
            (query_id,),
        )
        out = []
        previous_digest = None
        for idx, row in enumerate(rows):
            item = dict(row)
            item["provider_metadata"] = json.loads(item.pop("provider_metadata_json"))
            digest = item["provider_digest"]
            item["first_seen"] = idx == 0
            item["last_seen"] = idx == len(rows) - 1
            item["content_digest_changed"] = bool(previous_digest and digest and previous_digest != digest)
            previous_digest = digest or previous_digest
            item["retrieval_ready"] = bool(item["archive_url"]) and not item["provider_metadata"].get("warc_range_required", False)
            out.append(item)
        return out

    def ranked_candidates(self, query_id, limit=30):
        items = self.candidates(query_id)
        if not items:
            return []
        selected = []
        seen_digests = set()
        for item in items:
            score = 0
            if item["first_seen"] or item["last_seen"]:
                score += 40
            if item["content_digest_changed"]:
                score += 30
            if item["provider_digest"] and item["provider_digest"] not in seen_digests:
                score += 20
                seen_digests.add(item["provider_digest"])
            if item["status_code"] == 200:
                score += 5
            if "html" in item["media_type"].casefold():
                score += 5
            if item["retrieval_ready"]:
                score += 5
            selected.append({**item, "investigative_priority": score})
        selected.sort(key=lambda x: (-x["investigative_priority"], x["captured_at"], x["candidate_id"]))
        return selected[:max(1, min(int(limit), 100))]

    def link_retrieved_capture(self, *, identity, candidate_id, archive_source_id,
                               retrieved_event_id, content_id):
        actor = self._identity(identity)
        candidate = self.db.one(
            "SELECT * FROM historical_candidate_453 WHERE candidate_id=?", (candidate_id,)
        )
        if not candidate:
            raise KeyError("historical candidate not found")
        event = self.events422.get(retrieved_event_id)
        if event["case_id"] != candidate["case_id"] or event["source_id"] != archive_source_id:
            raise ValueError("retrieved archive event does not match candidate case/source")
        observation = self.db.one(
            "SELECT 1 ok FROM content_observation_423 WHERE event_id=? AND content_id=?",
            (retrieved_event_id, content_id),
        )
        if not observation:
            raise ValueError("retrieved archive content is not linked to event")
        target = str(event["target"])
        if candidate["archive_url"] and target.rstrip("/") != candidate["archive_url"].rstrip("/"):
            raise ValueError("retrieved event target does not match candidate archive URL")
        archive = self.archive428.register_capture(
            identity=identity,
            case_id=candidate["case_id"],
            source_id=archive_source_id,
            original_url=candidate["original_url"],
            archive_url=candidate["archive_url"],
            captured_at=candidate["captured_at"],
            retrieved_event_id=retrieved_event_id,
            content_id=content_id,
            archive_provider=candidate["provider"],
            metadata={"build": BUILD, "historical_candidate_id": candidate_id,
                      "index_event_id": candidate["index_event_id"],
                      "index_content_id": candidate["index_content_id"]},
        )
        link = {
            "link_id": "histl453_" + secrets.token_hex(10),
            "candidate_id": candidate_id,
            "archive_capture_id": archive["archive_capture_id"],
            "retrieved_event_id": retrieved_event_id,
            "content_id": content_id,
            "linked_by": actor,
            "linked_at": _now(),
        }
        link["record_hash"] = self._record_hash(link)
        self.db.execute(
            "INSERT INTO historical_capture_link_453 VALUES(?,?,?,?,?,?,?,?)",
            tuple(link.values()),
        )
        self.audit.log(
            "historical_capture_linked_453", "historical_capture_link_453",
            link["link_id"], candidate["case_id"],
            {"candidate_id": candidate_id, "archive_capture_id": archive["archive_capture_id"]},
        )
        return {**link, "archive_capture": archive}

    def compare_texts(self, *, older_text, newer_text):
        older = _norm_lines(older_text)
        newer = _norm_lines(newer_text)
        matcher = difflib.SequenceMatcher(None, older, newer)
        added, removed = [], []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in {"insert", "replace"}:
                added.extend(newer[j1:j2])
            if tag in {"delete", "replace"}:
                removed.extend(older[i1:i2])
        return {
            "build": BUILD,
            "older_sha256": hashlib.sha256(str(older_text or "").encode()).hexdigest(),
            "newer_sha256": hashlib.sha256(str(newer_text or "").encode()).hexdigest(),
            "similarity": round(matcher.ratio(), 6),
            "added_lines": added[:MAX_COMPARE_LINES],
            "removed_lines": removed[:MAX_COMPARE_LINES],
            "added_count": len(added),
            "removed_count": len(removed),
            "possible_disappearances": removed[:MAX_COMPARE_LINES],
            "change_signal_not_truth": True,
        }

    def case_timeline(self, case_id, original_url=""):
        sql = "SELECT * FROM historical_candidate_453 WHERE case_id=?"
        args = [case_id]
        if original_url:
            sql += " AND original_url=?"
            args.append(_public_url(original_url))
        sql += " ORDER BY julianday(captured_at), provider, candidate_id"
        return [dict(x) for x in self.db.all(sql, args)]

    def verify_integrity(self):
        bad = []
        for table, key in (
            ("historical_query_453", "query_id"),
            ("historical_candidate_453", "candidate_id"),
            ("historical_capture_link_453", "link_id"),
        ):
            for row in self.db.all("SELECT * FROM " + table):
                item = dict(row)
                if self._record_hash(item) != item["record_hash"]:
                    bad.append({key: item[key], "table": table, "reason": "record_hash_mismatch"})
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        q = self.db.one("SELECT COUNT(*) n FROM historical_query_453")["n"]
        c = self.db.one("SELECT COUNT(*) n FROM historical_candidate_453")["n"]
        l = self.db.one("SELECT COUNT(*) n FROM historical_capture_link_453")["n"]
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "queries": int(q),
            "candidates": int(c),
            "retrieved_capture_links": int(l),
            "providers": list(PROVIDERS),
            "internet_archive_cdx": True,
            "common_crawl_index": True,
            "cross_provider_deduplication_signal": True,
            "historical_change_comparison": True,
            "direct_network_authority": False,
            "uses_existing_governed_acquisition": True,
            "historical_capture_is_observation_not_truth": True,
            "integrity_valid": self.verify_integrity()["valid"],
            "production_release_ready": False,
        }
