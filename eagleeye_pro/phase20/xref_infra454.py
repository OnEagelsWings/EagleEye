from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import re
import secrets
from urllib.parse import quote, urlencode, urlsplit

from eagleeye_pro.security.url_policy import URLPolicy

BUILD = "454.0"
INFRA_POLICY = "phase20.public-domain-infrastructure.v454"
XREF_POLICY = "phase20.cross-reference-engine.v454"
DNS_TYPES = ("A", "AAAA", "MX", "NS")
PROVIDERS = ("rdap_domain", "dns_google", "ct_crtsh", "rdap_ip", "ripestat_network")
MAX_PAYLOAD_BYTES = 4_000_000
MAX_FACTS_PER_IMPORT = 3000


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value):
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, float(value)))


def _domain(value):
    raw = str(value or "").strip().lower().rstrip(".")
    if "://" in raw:
        raw = urlsplit(raw).hostname or ""
    raw = raw.split("/", 1)[0].strip().rstrip(".")
    if raw.startswith("www."):
        raw = raw[4:]
    try:
        ascii_domain = raw.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("invalid domain") from exc
    if (
        not ascii_domain
        or len(ascii_domain) > 253
        or any(not part or len(part) > 63 or part.startswith("-") or part.endswith("-")
               or not re.fullmatch(r"[a-z0-9-]+", part) for part in ascii_domain.split("."))
        or "." not in ascii_domain
        or URLPolicy.is_private_or_local_host(ascii_domain)
    ):
        raise ValueError("invalid or private domain")
    return ascii_domain


def _ip(value):
    try:
        obj = ipaddress.ip_address(str(value or "").strip())
    except ValueError as exc:
        raise ValueError("invalid IP address") from exc
    if not obj.is_global:
        raise ValueError("private or non-global IP address")
    return obj.compressed


def _host(value):
    try:
        return (urlsplit(str(value or "")).hostname or "").casefold().rstrip(".")
    except ValueError:
        return ""


def _payload_text(payload):
    if isinstance(payload, bytes):
        raw = bytes(payload)
        text = raw.decode("utf-8", errors="strict")
    elif isinstance(payload, str):
        text = payload
        raw = text.encode("utf-8")
    else:
        raise ValueError("infrastructure payload must be UTF-8 text")
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise ValueError("infrastructure payload exceeds bounded import size")
    return text, raw


def _json_payload(payload):
    text, raw = _payload_text(payload)
    try:
        return json.loads(text), raw
    except json.JSONDecodeError as exc:
        raise ValueError("infrastructure payload must contain valid JSON") from exc


def _norm_fact(kind, value):
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if kind in {"domain", "nameserver", "mx", "certificate_name", "cname"}:
        return text.casefold().rstrip(".")
    if kind in {"ip", "network_start", "network_end"}:
        try:
            return ipaddress.ip_address(text).compressed
        except ValueError:
            return text.casefold()
    if kind == "asn":
        text = text.upper().replace(" ", "")
        return text if text.startswith("AS") else "AS" + text
    return text.casefold()


class InfrastructureIntel454:
    """Public domain/network intelligence with strict acquisition provenance.

    This service only plans public lookups and imports already-acquired payloads.
    It has no socket/network authority, performs no port scanning and makes no
    ownership/control determination.
    """

    def __init__(self, db, audit, *, registry421, events422, content423, governance, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.registry421 = registry421
        self.events422 = events422
        self.content423 = content423
        self.governance = governance
        self.actor = actor
        self._schema()

    def _schema(self):
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS infra_lookup_454(
          lookup_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          resource_kind TEXT NOT NULL,
          resource TEXT NOT NULL,
          provider TEXT NOT NULL,
          request_url TEXT NOT NULL,
          expected_format TEXT NOT NULL,
          purpose TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          record_hash TEXT NOT NULL,
          UNIQUE(case_id, provider, resource_kind, resource, request_url)
        );
        CREATE INDEX IF NOT EXISTS idx_il454_case_resource
          ON infra_lookup_454(case_id, resource_kind, resource);

        CREATE TABLE IF NOT EXISTS infra_fact_454(
          fact_id TEXT PRIMARY KEY,
          lookup_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          provider TEXT NOT NULL,
          resource_kind TEXT NOT NULL,
          resource TEXT NOT NULL,
          fact_type TEXT NOT NULL,
          fact_value TEXT NOT NULL,
          normalized_value TEXT NOT NULL,
          reliability REAL NOT NULL,
          source_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          content_id TEXT NOT NULL,
          source_ref TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          record_hash TEXT NOT NULL,
          UNIQUE(case_id, resource_kind, resource, fact_type, normalized_value, event_id)
        );
        CREATE INDEX IF NOT EXISTS idx_if454_case_value
          ON infra_fact_454(case_id, fact_type, normalized_value);
        CREATE INDEX IF NOT EXISTS idx_if454_resource
          ON infra_fact_454(case_id, resource_kind, resource);

        CREATE TABLE IF NOT EXISTS infra_import_454(
          import_id TEXT PRIMARY KEY,
          lookup_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          provider TEXT NOT NULL,
          event_id TEXT NOT NULL,
          content_id TEXT NOT NULL,
          payload_sha256 TEXT NOT NULL,
          fact_count INTEGER NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          record_hash TEXT NOT NULL,
          UNIQUE(lookup_id, event_id, content_id)
        );
        """)
        self.db.conn.commit()

    def _rh(self, row):
        return _sha({k: row[k] for k in row if k != "record_hash"})

    def _identity(self, identity):
        if not isinstance(identity, dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("canonical active identity required")
        try:
            user = self.governance.identity.public_user(str(identity["username"]))
        except (KeyError, ValueError):
            raise PermissionError("canonical active identity required") from None
        if not user.get("active") or str(user.get("user_id")) != str(identity.get("user_id")):
            raise PermissionError("canonical active identity required")
        return {**user, "session_id": str(identity.get("session_id") or "infra454")}

    def _authorize(self, identity, case_id):
        ident = self._identity(identity)
        self.governance.authorize(
            ident, case_id=str(case_id), capability="research.run",
            object_type="public_domain_infrastructure_454", object_id=str(case_id),
        )
        return ident

    def _insert_lookup(self, *, ident, case_id, resource_kind, resource, provider, request_url,
                       expected_format="json", purpose="public_infrastructure_correlation"):
        existing = self.db.one(
            "SELECT * FROM infra_lookup_454 WHERE case_id=? AND provider=? AND resource_kind=? AND resource=? AND request_url=?",
            (case_id, provider, resource_kind, resource, request_url),
        )
        if existing:
            return dict(existing)
        row = {
            "lookup_id": "infra454_" + secrets.token_hex(10),
            "case_id": str(case_id),
            "resource_kind": resource_kind,
            "resource": resource,
            "provider": provider,
            "request_url": request_url,
            "expected_format": expected_format,
            "purpose": purpose,
            "created_by": str(ident["username"]),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO infra_lookup_454 VALUES(?,?,?,?,?,?,?,?,?,?,?)", tuple(row.values())
        )
        return row

    def plan_domain(self, *, identity, case_id, domain):
        ident = self._authorize(identity, case_id)
        d = _domain(domain)
        requests = []
        requests.append(self._insert_lookup(
            ident=ident, case_id=case_id, resource_kind="domain", resource=d,
            provider="rdap_domain", request_url="https://rdap.org/domain/" + quote(d, safe=".-"),
            purpose="registration_metadata_candidate",
        ))
        for record_type in DNS_TYPES:
            url = "https://dns.google/resolve?" + urlencode({"name": d, "type": record_type})
            requests.append(self._insert_lookup(
                ident=ident, case_id=case_id, resource_kind="domain", resource=d,
                provider="dns_google", request_url=url,
                purpose="dns_" + record_type.lower() + "_observation",
            ))
        requests.append(self._insert_lookup(
            ident=ident, case_id=case_id, resource_kind="domain", resource=d,
            provider="ct_crtsh",
            request_url="https://crt.sh/?" + urlencode({"q": "%." + d, "output": "json"}),
            purpose="certificate_transparency_name_observation",
        ))
        self.audit.log(
            "domain_infrastructure_plan_created_454", "infra_lookup_454", d, str(case_id),
            {"domain": d, "lookups": len(requests), "providers": sorted({x["provider"] for x in requests})},
        )
        return {
            "build": BUILD, "case_id": str(case_id), "domain": d, "lookups": requests,
            "network_used": False, "public_sources_only": True,
            "ownership_or_control_determined": False,
        }

    def plan_ip_pivots(self, *, identity, case_id, domain):
        ident = self._authorize(identity, case_id)
        d = _domain(domain)
        rows = self.db.all(
            "SELECT DISTINCT normalized_value FROM infra_fact_454 "
            "WHERE case_id=? AND resource_kind='domain' AND resource=? AND fact_type IN ('ip','ipv6') "
            "ORDER BY normalized_value",
            (case_id, d),
        )
        requests = []
        for row in rows[:100]:
            ip = _ip(row["normalized_value"])
            requests.append(self._insert_lookup(
                ident=ident, case_id=case_id, resource_kind="ip", resource=ip,
                provider="rdap_ip", request_url="https://rdap.org/ip/" + quote(ip, safe=":."),
                purpose="public_ip_registration_metadata",
            ))
            requests.append(self._insert_lookup(
                ident=ident, case_id=case_id, resource_kind="ip", resource=ip,
                provider="ripestat_network",
                request_url="https://stat.ripe.net/data/network-info/data.json?" + urlencode({"resource": ip}),
                purpose="public_prefix_asn_observation",
            ))
        return {
            "build": BUILD, "case_id": str(case_id), "domain": d, "ip_count": len(rows),
            "lookups": requests, "network_used": False,
            "active_scanning": False, "port_scanning": False,
        }

    def get_lookup(self, lookup_id):
        row = self.db.one("SELECT * FROM infra_lookup_454 WHERE lookup_id=?", (str(lookup_id),))
        if not row:
            raise KeyError("infrastructure lookup not found")
        return dict(row)

    def list_lookups(self, case_id, resource=""):
        sql = "SELECT * FROM infra_lookup_454 WHERE case_id=?"
        args = [case_id]
        if resource:
            sql += " AND resource=?"
            args.append(str(resource))
        sql += " ORDER BY created_at, lookup_id"
        return [dict(r) for r in self.db.all(sql, args)]

    def _verify_provenance(self, *, lookup, event_id, content_id, payload_bytes):
        event = self.events422.get(event_id)
        if event["case_id"] != lookup["case_id"]:
            raise ValueError("infrastructure event belongs to another case")
        observation = self.db.one(
            "SELECT * FROM content_observation_423 WHERE event_id=? AND content_id=? AND case_id=?",
            (event_id, content_id, lookup["case_id"]),
        )
        if not observation:
            raise ValueError("infrastructure content is not linked to the acquisition event")
        content = self.db.one("SELECT * FROM content_object_423 WHERE content_id=?", (content_id,))
        if not content or content["sha256"] != hashlib.sha256(payload_bytes).hexdigest():
            raise ValueError("supplied infrastructure payload does not match referenced content hash")
        expected_host = _host(lookup["request_url"])
        event_host = _host(event["target"])
        if event_host != expected_host:
            raise ValueError("acquisition target host does not match infrastructure provider")
        allowed = {
            "rdap_domain": "rdap.org",
            "dns_google": "dns.google",
            "ct_crtsh": "crt.sh",
            "rdap_ip": "rdap.org",
            "ripestat_network": "stat.ripe.net",
        }
        if expected_host != allowed[lookup["provider"]]:
            raise ValueError("lookup provider host contract mismatch")
        return event, content, observation

    def _fact(self, *, lookup, fact_type, value, reliability, source_id, event_id, content_id,
              source_ref, evidence=None):
        raw = str(value or "").strip()
        if not raw:
            return None
        normalized = _norm_fact(fact_type, raw)
        if not normalized or len(normalized) > 2000:
            return None
        existing = self.db.one(
            "SELECT * FROM infra_fact_454 WHERE case_id=? AND resource_kind=? AND resource=? "
            "AND fact_type=? AND normalized_value=? AND event_id=?",
            (lookup["case_id"], lookup["resource_kind"], lookup["resource"], fact_type, normalized, event_id),
        )
        if existing:
            return dict(existing)
        row = {
            "fact_id": "infrafact454_" + secrets.token_hex(10),
            "lookup_id": lookup["lookup_id"],
            "case_id": lookup["case_id"],
            "provider": lookup["provider"],
            "resource_kind": lookup["resource_kind"],
            "resource": lookup["resource"],
            "fact_type": fact_type,
            "fact_value": raw[:2000],
            "normalized_value": normalized,
            "reliability": _clamp(reliability),
            "source_id": source_id,
            "event_id": event_id,
            "content_id": content_id,
            "source_ref": str(source_ref or lookup["request_url"])[:4096],
            "evidence_json": _canon(evidence or {}),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO infra_fact_454 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            tuple(row.values()),
        )
        return row

    @staticmethod
    def _walk_entities(entities):
        out = []
        for entity in entities or []:
            if not isinstance(entity, dict):
                continue
            roles = [str(x).casefold() for x in entity.get("roles") or []]
            handle = entity.get("handle")
            if handle:
                if "registrar" in roles:
                    out.append(("registrar_handle", handle, .75, {"roles": roles}))
                elif "registrant" in roles:
                    out.append(("registrant_handle", handle, .6, {"roles": roles}))
                else:
                    out.append(("rdap_entity_handle", handle, .45, {"roles": roles}))
            out.extend(InfrastructureIntel454._walk_entities(entity.get("entities") or []))
        return out

    def _parse_rdap_domain(self, data):
        facts = []
        if data.get("ldhName"):
            facts.append(("domain", data["ldhName"], .98, {}))
        if data.get("unicodeName"):
            facts.append(("unicode_domain", data["unicodeName"], .95, {}))
        if data.get("handle"):
            facts.append(("rdap_handle", data["handle"], .9, {}))
        for status in data.get("status") or []:
            facts.append(("domain_status", status, .9, {}))
        for ns in data.get("nameservers") or []:
            if isinstance(ns, dict) and (ns.get("ldhName") or ns.get("unicodeName")):
                facts.append(("nameserver", ns.get("ldhName") or ns.get("unicodeName"), .95, {}))
        for ev in data.get("events") or []:
            if isinstance(ev, dict) and ev.get("eventAction") and ev.get("eventDate"):
                facts.append(("rdap_event", f"{ev['eventAction']}|{ev['eventDate']}", .9, dict(ev)))
        facts.extend(self._walk_entities(data.get("entities") or []))
        secure = data.get("secureDNS") or {}
        if isinstance(secure, dict) and "delegationSigned" in secure:
            facts.append(("dnssec_delegation_signed", str(bool(secure["delegationSigned"])).lower(), .95, {}))
        return facts

    def _parse_rdap_ip(self, data):
        facts = []
        for key, kind, rel in (
            ("handle", "network_handle", .9),
            ("name", "network_name", .8),
            ("country", "network_country", .75),
            ("startAddress", "network_start", .95),
            ("endAddress", "network_end", .95),
            ("type", "network_type", .7),
        ):
            if data.get(key):
                facts.append((kind, data[key], rel, {}))
        facts.extend(self._walk_entities(data.get("entities") or []))
        return facts

    def _parse_dns(self, data):
        facts = []
        type_map = {1: "ip", 28: "ipv6", 15: "mx", 2: "nameserver", 5: "cname", 16: "txt"}
        for answer in data.get("Answer") or []:
            if not isinstance(answer, dict):
                continue
            kind = type_map.get(int(answer.get("type") or 0))
            value = str(answer.get("data") or "").strip()
            if not kind or not value:
                continue
            if kind == "mx":
                parts = value.split()
                value = parts[-1] if parts else value
            elif kind in {"nameserver", "cname"}:
                value = value.rstrip(".")
            facts.append((kind, value, .92, {"ttl": answer.get("TTL"), "dns_type": answer.get("type")}))
        if "Status" in data:
            facts.append(("dns_response_status", data["Status"], .95, {}))
        return facts

    def _parse_crtsh(self, data):
        if not isinstance(data, list):
            raise ValueError("crt.sh payload must be a JSON array")
        facts = []
        for item in data[:1500]:
            if not isinstance(item, dict):
                continue
            names = []
            if item.get("common_name"):
                names.append(item["common_name"])
            if item.get("name_value"):
                names.extend(str(item["name_value"]).splitlines())
            for name in names:
                clean = str(name).strip().casefold().lstrip("*.").rstrip(".")
                if clean and "." in clean:
                    facts.append(("certificate_name", clean, .82, {"certificate_id": item.get("id")}))
            if item.get("issuer_name"):
                facts.append(("certificate_issuer", item["issuer_name"], .55, {"certificate_id": item.get("id")}))
            if item.get("id"):
                facts.append(("certificate_id", item["id"], .95, {}))
            if item.get("serial_number"):
                facts.append(("certificate_serial", item["serial_number"], .9, {"certificate_id": item.get("id")}))
        return facts

    def _parse_ripestat(self, data):
        section = data.get("data") if isinstance(data, dict) else None
        if not isinstance(section, dict):
            raise ValueError("RIPEstat payload has no data object")
        facts = []
        if section.get("prefix"):
            facts.append(("prefix", section["prefix"], .94, {}))
        for asn in section.get("asns") or []:
            facts.append(("asn", asn, .94, {"method": "RIPE RIS network-info"}))
        return facts

    def import_payload(self, *, identity, lookup_id, payload, event_id, content_id, source_ref=""):
        lookup = self.get_lookup(lookup_id)
        ident = self._authorize(identity, lookup["case_id"])
        data, raw = _json_payload(payload)
        event, _, _ = self._verify_provenance(
            lookup=lookup, event_id=event_id, content_id=content_id, payload_bytes=raw
        )
        parser = {
            "rdap_domain": self._parse_rdap_domain,
            "dns_google": self._parse_dns,
            "ct_crtsh": self._parse_crtsh,
            "rdap_ip": self._parse_rdap_ip,
            "ripestat_network": self._parse_ripestat,
        }[lookup["provider"]]
        parsed = parser(data)
        facts = []
        for kind, value, reliability, evidence in parsed[:MAX_FACTS_PER_IMPORT]:
            fact = self._fact(
                lookup=lookup, fact_type=kind, value=value, reliability=reliability,
                source_id=event["source_id"], event_id=event_id, content_id=content_id,
                source_ref=source_ref or event["target"], evidence=evidence,
            )
            if fact:
                facts.append(fact)
        import_row = {
            "import_id": "infraimp454_" + secrets.token_hex(10),
            "lookup_id": lookup_id,
            "case_id": lookup["case_id"],
            "provider": lookup["provider"],
            "event_id": event_id,
            "content_id": content_id,
            "payload_sha256": hashlib.sha256(raw).hexdigest(),
            "fact_count": len(facts),
            "created_by": str(ident["username"]),
            "created_at": _now(),
        }
        import_row["record_hash"] = self._rh(import_row)
        try:
            self.db.execute(
                "INSERT INTO infra_import_454 VALUES(?,?,?,?,?,?,?,?,?,?,?)", tuple(import_row.values())
            )
        except Exception as exc:
            if "UNIQUE constraint failed" not in str(exc):
                raise
        self.audit.log(
            "infrastructure_payload_imported_454", "infra_import_454", import_row["import_id"],
            lookup["case_id"], {"provider": lookup["provider"], "resource": lookup["resource"],
                                "fact_count": len(facts), "event_id": event_id},
        )
        return {
            "build": BUILD, "lookup": lookup, "fact_count": len(facts), "facts": facts,
            "payload_sha256": import_row["payload_sha256"],
            "public_observations_not_control_claims": True,
        }

    def facts(self, case_id, resource="", fact_type=""):
        sql = "SELECT * FROM infra_fact_454 WHERE case_id=?"
        args = [case_id]
        if resource:
            sql += " AND resource=?"
            args.append(str(resource))
        if fact_type:
            sql += " AND fact_type=?"
            args.append(str(fact_type))
        sql += " ORDER BY created_at, fact_id"
        out = []
        for row in self.db.all(sql, args):
            item = dict(row)
            item["evidence"] = json.loads(item.pop("evidence_json"))
            out.append(item)
        return out

    def verify_integrity(self):
        bad = []
        for table, key in (
            ("infra_lookup_454", "lookup_id"),
            ("infra_fact_454", "fact_id"),
            ("infra_import_454", "import_id"),
        ):
            for row in self.db.all("SELECT * FROM " + table):
                item = dict(row)
                if self._rh(item) != item["record_hash"]:
                    bad.append({key: item[key], "table": table, "reason": "record_hash_mismatch"})
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        lookups = int(self.db.one("SELECT COUNT(*) n FROM infra_lookup_454")["n"])
        facts = int(self.db.one("SELECT COUNT(*) n FROM infra_fact_454")["n"])
        return {
            "build": BUILD, "policy": INFRA_POLICY, "lookups": lookups, "facts": facts,
            "providers": list(PROVIDERS), "dns_types": list(DNS_TYPES),
            "rdap": True, "dns_over_https": True, "certificate_transparency": True,
            "ripestat_ip_to_prefix_asn": True, "direct_network_authority": False,
            "active_scanning": False, "port_scanning": False,
            "ownership_or_control_determination": False,
            "integrity_valid": self.verify_integrity()["valid"],
            "production_release_ready": False,
        }


class CrossReferenceEngine454:
    """Explainable candidate relationships across entities, domains and history."""

    ANCHOR_WEIGHTS = {
        "external_id": .90, "email": .85, "phone": .82, "url": .68,
        "domain": .60, "username": .48, "organisation": .36,
        "location": .22, "birth_year": .18,
    }
    INFRA_WEIGHTS = {
        "ip": .48, "ipv6": .48, "mx": .28, "cname": .30,
        "nameserver": .14, "registrar_handle": .10, "asn": .10,
        "network_name": .08,
    }

    def __init__(self, db, audit, *, infra454, historical453, entity437, base115, governance, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.infra454 = infra454
        self.historical453 = historical453
        self.entity437 = entity437
        self.base115 = base115
        self.governance = governance
        self.actor = actor
        self._schema()

    def _schema(self):
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS xref_candidate_454(
          candidate_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          left_kind TEXT NOT NULL,
          left_ref TEXT NOT NULL,
          right_kind TEXT NOT NULL,
          right_ref TEXT NOT NULL,
          relation_type TEXT NOT NULL,
          score REAL NOT NULL,
          signals_json TEXT NOT NULL,
          contradictions_json TEXT NOT NULL,
          source_refs_json TEXT NOT NULL,
          status TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          record_hash TEXT NOT NULL,
          UNIQUE(case_id,left_kind,left_ref,right_kind,right_ref,relation_type)
        );
        CREATE INDEX IF NOT EXISTS idx_xc454_case_score
          ON xref_candidate_454(case_id, score DESC);

        CREATE TABLE IF NOT EXISTS xref_run_454(
          run_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_count INTEGER NOT NULL,
          domain_count INTEGER NOT NULL,
          candidate_count INTEGER NOT NULL,
          result_json TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          record_hash TEXT NOT NULL
        );
        """)
        self.db.conn.commit()

    def _rh(self, row):
        return _sha({k: row[k] for k in row if k != "record_hash"})

    def _identity(self, identity):
        if not isinstance(identity, dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("canonical active identity required")
        try:
            user = self.governance.identity.public_user(str(identity["username"]))
        except (KeyError, ValueError):
            raise PermissionError("canonical active identity required") from None
        if not user.get("active") or str(user.get("user_id")) != str(identity.get("user_id")):
            raise PermissionError("canonical active identity required")
        return {**user, "session_id": str(identity.get("session_id") or "xref454")}

    def _authorize(self, identity, case_id):
        ident = self._identity(identity)
        self.governance.authorize(
            ident, case_id=str(case_id), capability="research.run",
            object_type="cross_reference_engine_454", object_id=str(case_id),
        )
        return ident

    def _entity_nodes(self, case_id):
        rows = self.db.all(
            "SELECT * FROM resolution_entities_115 WHERE case_id=? ORDER BY resolution_entity_id",
            (case_id,),
        )
        nodes = {}
        for row in rows:
            eid = row["resolution_entity_id"]
            aliases = self.db.all(
                "SELECT normalized_alias,source_ref FROM resolution_aliases_115 "
                "WHERE resolution_entity_id=? ORDER BY alias_id", (eid,)
            )
            anchors = self.db.all(
                "SELECT anchor_type,anchor_value,normalized_value,reliability,source_ref "
                "FROM resolution_anchors_115 WHERE resolution_entity_id=? ORDER BY anchor_id", (eid,)
            )
            nodes[eid] = {**dict(row), "aliases": aliases, "anchors": anchors}
        return nodes

    def _domain_resources(self, case_id):
        rows = self.db.all(
            "SELECT DISTINCT resource FROM infra_lookup_454 "
            "WHERE case_id=? AND resource_kind='domain' ORDER BY resource", (case_id,)
        )
        return [r["resource"] for r in rows]

    @staticmethod
    def _ordered(left_kind, left_ref, right_kind, right_ref):
        a = (left_kind, left_ref)
        b = (right_kind, right_ref)
        return (a, b) if a <= b else (b, a)

    def _save(self, *, ident, case_id, left_kind, left_ref, right_kind, right_ref,
              relation_type, score, signals, contradictions=None, source_refs=None):
        left, right = self._ordered(left_kind, left_ref, right_kind, right_ref)
        left_kind, left_ref = left
        right_kind, right_ref = right
        score = round(_clamp(score), 6)
        if score < .20 or (left_kind, left_ref) == (right_kind, right_ref):
            return None
        status = "high_review_candidate" if score >= .78 else "medium_review_candidate" if score >= .52 else "low_review_candidate"
        existing = self.db.one(
            "SELECT * FROM xref_candidate_454 WHERE case_id=? AND left_kind=? AND left_ref=? "
            "AND right_kind=? AND right_ref=? AND relation_type=?",
            (case_id, left_kind, left_ref, right_kind, right_ref, relation_type),
        )
        payload_signals = list(signals or [])
        payload_contradictions = list(contradictions or [])
        payload_sources = sorted({str(x) for x in (source_refs or []) if str(x)})
        if existing:
            row = dict(existing)
            merged_signals = list(json.loads(row["signals_json"]))
            seen = {_canon(x) for x in merged_signals}
            for signal in payload_signals:
                if _canon(signal) not in seen:
                    merged_signals.append(signal)
                    seen.add(_canon(signal))
            row["signals_json"] = _canon(merged_signals)
            row["contradictions_json"] = _canon(payload_contradictions or json.loads(row["contradictions_json"]))
            row["source_refs_json"] = _canon(sorted(set(payload_sources) | set(json.loads(row["source_refs_json"]))))
            row["score"] = max(float(row["score"]), score)
            row["status"] = "high_review_candidate" if row["score"] >= .78 else "medium_review_candidate" if row["score"] >= .52 else "low_review_candidate"
            row["created_by"] = str(ident["username"])
            row["created_at"] = _now()
            row["record_hash"] = self._rh(row)
            self.db.execute(
                "UPDATE xref_candidate_454 SET score=?,signals_json=?,contradictions_json=?,"
                "source_refs_json=?,status=?,created_by=?,created_at=?,record_hash=? WHERE candidate_id=?",
                (row["score"], row["signals_json"], row["contradictions_json"], row["source_refs_json"],
                 row["status"], row["created_by"], row["created_at"], row["record_hash"], row["candidate_id"]),
            )
            return row
        row = {
            "candidate_id": "xref454_" + secrets.token_hex(10),
            "case_id": case_id,
            "left_kind": left_kind, "left_ref": left_ref,
            "right_kind": right_kind, "right_ref": right_ref,
            "relation_type": relation_type, "score": score,
            "signals_json": _canon(payload_signals),
            "contradictions_json": _canon(payload_contradictions),
            "source_refs_json": _canon(payload_sources),
            "status": status, "created_by": str(ident["username"]), "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO xref_candidate_454 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            tuple(row.values()),
        )
        return row

    def _entity_domain_edges(self, *, ident, case_id, entities, domains):
        count = 0
        domain_set = set(domains)
        for eid, entity in entities.items():
            for anchor in entity["anchors"]:
                target = ""
                if anchor["anchor_type"] == "domain":
                    try:
                        target = _domain(anchor["anchor_value"])
                    except ValueError:
                        continue
                elif anchor["anchor_type"] == "url":
                    h = _host(anchor["anchor_value"])
                    try:
                        target = _domain(h) if h else ""
                    except ValueError:
                        continue
                if target and target in domain_set:
                    score = .92 if anchor["anchor_type"] == "domain" else .80
                    score *= max(.45, float(anchor.get("reliability") or .5))
                    result = self._save(
                        ident=ident, case_id=case_id, left_kind="entity", left_ref=eid,
                        right_kind="domain", right_ref=target, relation_type="entity_domain_anchor_candidate",
                        score=score,
                        signals=[{"type": "matching_" + anchor["anchor_type"], "value": target,
                                  "anchor_reliability": anchor.get("reliability")}],
                        source_refs=[anchor.get("source_ref") or ""],
                    )
                    count += int(result is not None)
        return count

    def _shared_entity_anchors(self, *, ident, case_id, entities):
        index = defaultdict(list)
        for eid, entity in entities.items():
            for anchor in entity["anchors"]:
                kind = anchor["anchor_type"]
                value = anchor["normalized_value"]
                if kind in self.ANCHOR_WEIGHTS and value:
                    index[(kind, value)].append((eid, anchor))
        count = 0
        for (kind, value), members in index.items():
            unique = {}
            for eid, anchor in members:
                unique.setdefault(eid, anchor)
            ids = sorted(unique)
            if len(ids) < 2 or len(ids) > 25:
                continue
            for i, left in enumerate(ids):
                for right in ids[i + 1:]:
                    a, b = unique[left], unique[right]
                    weight = self.ANCHOR_WEIGHTS[kind] * min(float(a["reliability"]), float(b["reliability"]))
                    result = self._save(
                        ident=ident, case_id=case_id, left_kind="entity", left_ref=left,
                        right_kind="entity", right_ref=right, relation_type="shared_anchor_candidate",
                        score=weight,
                        signals=[{"type": "shared_anchor", "anchor_type": kind, "normalized_value": value,
                                  "note": "Shared anchor is a relationship lead, not identity proof."}],
                        source_refs=[a.get("source_ref") or "", b.get("source_ref") or ""],
                    )
                    count += int(result is not None)
        return count

    def _domain_infrastructure_edges(self, *, ident, case_id, domains):
        facts = self.infra454.facts(case_id)
        index = defaultdict(lambda: defaultdict(list))
        for fact in facts:
            if fact["resource_kind"] != "domain" or fact["resource"] not in domains:
                continue
            kind = fact["fact_type"]
            if kind not in self.INFRA_WEIGHTS:
                continue
            index[(kind, fact["normalized_value"])][fact["resource"]].append(fact)
        pair_signals = defaultdict(list)
        pair_sources = defaultdict(set)
        pair_scores = defaultdict(float)
        for (kind, value), by_domain in index.items():
            members = sorted(by_domain)
            # Very common infrastructure is weak and can be misleading (CDNs, shared DNS).
            prevalence = len(members)
            if prevalence < 2 or prevalence > 50:
                continue
            attenuation = 1.0 if prevalence <= 4 else .65 if prevalence <= 10 else .35
            for i, left in enumerate(members):
                for right in members[i + 1:]:
                    pair = (left, right)
                    contribution = self.INFRA_WEIGHTS[kind] * attenuation
                    pair_scores[pair] += contribution
                    pair_signals[pair].append({
                        "type": "shared_infrastructure", "fact_type": kind,
                        "normalized_value": value, "prevalence_in_case": prevalence,
                        "contribution": round(contribution, 4),
                    })
                    for fact in by_domain[left] + by_domain[right]:
                        pair_sources[pair].add(fact["source_ref"])
        count = 0
        for pair, raw_score in pair_scores.items():
            diverse = len({s["fact_type"] for s in pair_signals[pair]})
            score = min(.82, raw_score + min(.12, .04 * max(0, diverse - 1)))
            result = self._save(
                ident=ident, case_id=case_id, left_kind="domain", left_ref=pair[0],
                right_kind="domain", right_ref=pair[1],
                relation_type="shared_public_infrastructure_candidate", score=score,
                signals=pair_signals[pair],
                contradictions=[{"type": "interpretation_guardrail",
                                 "note": "Shared hosting, CDN, registrar, mail or DNS infrastructure does not prove common ownership/control."}],
                source_refs=pair_sources[pair],
            )
            count += int(result is not None)
        return count

    def _history_edges(self, *, ident, case_id, entities, domains):
        count = 0
        rows = self.db.all(
            "SELECT candidate_id,original_url,archive_url,captured_at,index_event_id,index_content_id "
            "FROM historical_candidate_453 WHERE case_id=? ORDER BY captured_at,candidate_id",
            (case_id,),
        )
        for row in rows:
            host = _host(row["original_url"])
            try:
                d = _domain(host) if host else ""
            except ValueError:
                continue
            if d in domains:
                result = self._save(
                    ident=ident, case_id=case_id, left_kind="domain", left_ref=d,
                    right_kind="historical_capture", right_ref=row["candidate_id"],
                    relation_type="historical_observation_of_domain", score=.96,
                    signals=[{"type": "historical_url_host_match", "captured_at": row["captured_at"],
                              "original_url": row["original_url"]}],
                    source_refs=[row["archive_url"], row["index_event_id"], row["index_content_id"]],
                )
                count += int(result is not None)
            for eid, entity in entities.items():
                matched = False
                refs = []
                for anchor in entity["anchors"]:
                    target = ""
                    if anchor["anchor_type"] == "domain":
                        try:
                            target = _domain(anchor["anchor_value"])
                        except ValueError:
                            continue
                    elif anchor["anchor_type"] == "url":
                        ah = _host(anchor["anchor_value"])
                        try:
                            target = _domain(ah) if ah else ""
                        except ValueError:
                            continue
                    if target == d:
                        matched = True
                        refs.append(anchor.get("source_ref") or "")
                if matched:
                    result = self._save(
                        ident=ident, case_id=case_id, left_kind="entity", left_ref=eid,
                        right_kind="historical_capture", right_ref=row["candidate_id"],
                        relation_type="entity_historical_domain_candidate", score=.72,
                        signals=[{"type": "entity_anchor_matches_historical_host", "domain": d,
                                  "captured_at": row["captured_at"]}],
                        source_refs=refs + [row["archive_url"]],
                    )
                    count += int(result is not None)
        return count

    def run_case(self, *, identity, case_id):
        ident = self._authorize(identity, case_id)
        preflight = {
            "infrastructure": self.infra454.verify_integrity()["valid"],
            "historical_web": self.historical453.verify_integrity()["valid"],
        }
        if not all(preflight.values()):
            raise RuntimeError("Build-454 provenance preflight failed")
        entities = self._entity_nodes(case_id)
        domains = self._domain_resources(case_id)
        counts = {
            "entity_domain": self._entity_domain_edges(
                ident=ident, case_id=case_id, entities=entities, domains=domains
            ),
            "shared_entity_anchor": self._shared_entity_anchors(
                ident=ident, case_id=case_id, entities=entities
            ),
            "shared_infrastructure": self._domain_infrastructure_edges(
                ident=ident, case_id=case_id, domains=domains
            ),
            "historical": self._history_edges(
                ident=ident, case_id=case_id, entities=entities, domains=domains
            ),
        }
        candidate_count = int(self.db.one(
            "SELECT COUNT(*) n FROM xref_candidate_454 WHERE case_id=?", (case_id,)
        )["n"])
        result = {
            "build": BUILD, "preflight": preflight, "generated_by_type": counts,
            "candidate_count": candidate_count,
            "identity_automatically_merged": False,
            "ownership_or_control_determined": False,
            "human_review_required": True,
        }
        row = {
            "run_id": "xrefrun454_" + secrets.token_hex(10), "case_id": str(case_id),
            "entity_count": len(entities), "domain_count": len(domains),
            "candidate_count": candidate_count, "result_json": _canon(result),
            "created_by": str(ident["username"]), "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute("INSERT INTO xref_run_454 VALUES(?,?,?,?,?,?,?,?,?)", tuple(row.values()))
        self.audit.log(
            "cross_reference_run_454", "xref_run_454", row["run_id"], str(case_id),
            {"entities": len(entities), "domains": len(domains), "candidates": candidate_count},
        )
        return {**result, "run_id": row["run_id"]}

    def candidates(self, case_id, min_score=0.0, limit=250):
        rows = self.db.all(
            "SELECT * FROM xref_candidate_454 WHERE case_id=? AND score>=? "
            "ORDER BY score DESC,relation_type,candidate_id LIMIT ?",
            (case_id, float(min_score), max(1, min(int(limit), 1000))),
        )
        out = []
        for row in rows:
            item = dict(row)
            item["signals"] = json.loads(item.pop("signals_json"))
            item["contradictions"] = json.loads(item.pop("contradictions_json"))
            item["source_refs"] = json.loads(item.pop("source_refs_json"))
            out.append(item)
        return out

    def shortest_candidate_path(self, *, case_id, start_kind, start_ref, end_kind, end_ref,
                                min_score=.35, max_depth=6):
        start = (str(start_kind), str(start_ref))
        end = (str(end_kind), str(end_ref))
        if start == end:
            return {"found": True, "nodes": [{"kind": start[0], "ref": start[1]}], "edges": []}
        edges = self.candidates(case_id, min_score=min_score, limit=1000)
        adjacency = defaultdict(list)
        for edge in edges:
            a = (edge["left_kind"], edge["left_ref"])
            b = (edge["right_kind"], edge["right_ref"])
            adjacency[a].append((b, edge))
            adjacency[b].append((a, edge))
        queue = deque([(start, [start], [])])
        seen = {start}
        while queue:
            node, nodes, used_edges = queue.popleft()
            if len(used_edges) >= int(max_depth):
                continue
            for nxt, edge in sorted(adjacency.get(node, []), key=lambda x: -float(x[1]["score"])):
                if nxt in seen:
                    continue
                next_nodes = nodes + [nxt]
                next_edges = used_edges + [edge]
                if nxt == end:
                    return {
                        "found": True,
                        "nodes": [{"kind": k, "ref": r} for k, r in next_nodes],
                        "edges": next_edges,
                        "candidate_path_not_proof": True,
                    }
                seen.add(nxt)
                queue.append((nxt, next_nodes, next_edges))
        return {"found": False, "nodes": [], "edges": [], "candidate_path_not_proof": True}

    def pivot_recommendations(self, case_id):
        domains = self._domain_resources(case_id)
        recommendations = []
        for d in domains:
            providers = {r["provider"] for r in self.db.all(
                "SELECT provider FROM infra_lookup_454 WHERE case_id=? AND resource_kind='domain' AND resource=?",
                (case_id, d),
            )}
            imported = {r["provider"] for r in self.db.all(
                "SELECT DISTINCT provider FROM infra_fact_454 WHERE case_id=? AND resource_kind='domain' AND resource=?",
                (case_id, d),
            )}
            missing = sorted(providers - imported)
            if missing:
                recommendations.append({
                    "domain": d, "priority": "high", "action": "complete_planned_public_lookups",
                    "missing_providers": missing,
                })
            has_ips = bool(self.db.one(
                "SELECT 1 ok FROM infra_fact_454 WHERE case_id=? AND resource_kind='domain' "
                "AND resource=? AND fact_type IN ('ip','ipv6') LIMIT 1", (case_id, d)
            ))
            has_ip_plans = bool(self.db.one(
                "SELECT 1 ok FROM infra_lookup_454 WHERE case_id=? AND resource_kind='ip' LIMIT 1",
                (case_id,),
            ))
            if has_ips and not has_ip_plans:
                recommendations.append({
                    "domain": d, "priority": "medium", "action": "plan_ip_rdap_and_ripestat_pivots"
                })
        return {
            "build": BUILD, "case_id": str(case_id), "recommendations": recommendations,
            "autonomous_execution": False, "human_dispatch_required": True,
        }

    def verify_integrity(self):
        bad = []
        for table, key in (("xref_candidate_454", "candidate_id"), ("xref_run_454", "run_id")):
            for row in self.db.all("SELECT * FROM " + table):
                item = dict(row)
                if self._rh(item) != item["record_hash"]:
                    bad.append({key: item[key], "table": table, "reason": "record_hash_mismatch"})
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        candidates = int(self.db.one("SELECT COUNT(*) n FROM xref_candidate_454")["n"])
        runs = int(self.db.one("SELECT COUNT(*) n FROM xref_run_454")["n"])
        return {
            "build": BUILD, "policy": XREF_POLICY, "runs": runs, "candidates": candidates,
            "entity_domain_correlation": True, "shared_anchor_correlation": True,
            "shared_infrastructure_correlation": True, "historical_web_correlation": True,
            "explainable_candidate_paths": True, "pivot_recommendations": True,
            "automatic_identity_merge": False, "automatic_ownership_determination": False,
            "human_review_required": True, "integrity_valid": self.verify_integrity()["valid"],
            "production_release_ready": False,
        }
