from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlsplit

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

POLICY_VERSION = "phase15.search-capsule.v1"
VALID_ONION = re.compile(r"^[a-z2-7]{56}\.onion$")
HOST_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.I)
SECRET_NAME = re.compile(r"(^|_)(password|passwd|token|cookie|authorization|secret|api[-_]?key|private[-_]?key|bearer|session)($|_)", re.I)
FORBIDDEN_HEADERS = {"authorization", "cookie", "proxy-authorization", "referer", "x-api-key"}
ALLOWED_METHODS = {"GET", "HEAD"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _safe_chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        pass


def _normalize_host(raw: str) -> str:
    host = str(raw or "").strip().lower().rstrip(".")
    if not host or "*" in host or "/" in host or "://" in host or "@" in host:
        raise ValueError("Egress allowlist entries must be exact host names")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Literal IP addresses are not accepted in Build 345 egress allowlists")
    if VALID_ONION.fullmatch(host):
        return host
    if not HOST_RE.fullmatch(host):
        raise ValueError(f"Invalid host: {host}")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Local host names are forbidden in external egress allowlists")
    return host


def _redact(value: Any, summary: dict[str, int], key_name: str = "") -> Any:
    if SECRET_NAME.search(key_name):
        summary["secret_fields_redacted"] = summary.get("secret_fields_redacted", 0) + 1
        return "<redacted>"
    if isinstance(value, Mapping):
        return {str(k): _redact(v, summary, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v, summary, key_name) for v in value]
    if isinstance(value, tuple):
        return [_redact(v, summary, key_name) for v in value]
    return value


class SearchSessionCapsuleManager:
    """Search-by-search local isolation and fail-closed request preflight.

    Build 345 deliberately does not open sockets, alter proxy/Tor configuration, or
    execute browser/network requests. It creates isolated state and produces a
    persisted OPSEC decision that later gateways must present before egress.
    """

    def __init__(self, db: Any, base_dir: str | Path, actor: str = "local-analyst") -> None:
        self.db = db
        self.base_dir = Path(base_dir).resolve()
        self.actor = actor
        self.root = self.base_dir / "data" / "search_capsules"
        self.root.mkdir(parents=True, exist_ok=True)
        _safe_chmod(self.root, 0o700)
        self.ensure_builtin_profiles()

    def ensure_builtin_profiles(self) -> None:
        profiles = [
            {
                "profile_id": "direct_https_v1", "profile_kind": "direct_https",
                "display_name": "Direct HTTPS read-only policy profile", "allowed_schemes": ["https"],
                "dns_mode": "system_resolver_allowed_after_preflight", "webrtc_mode": "disabled_required_for_browser_gateway",
                "system_mutation_allowed": 0, "runtime_execution_enabled": 0, "review_status": "approved_policy",
                "config_ref": "builtin:direct_https_v1",
            },
            {
                "profile_id": "tor_read_only_v1", "profile_kind": "approved_tor",
                "display_name": "Approved Tor read-only policy profile", "allowed_schemes": ["http", "https"],
                "dns_mode": "proxy_resolution_required_no_local_onion_dns", "webrtc_mode": "disabled_required_for_browser_gateway",
                "system_mutation_allowed": 0, "runtime_execution_enabled": 0, "review_status": "approved_policy",
                "config_ref": "external-config-ref:tor_read_only_v1",
            },
        ]
        for p in profiles:
            body = {**p, "created_at": "policy-static"}
            self.db.execute(
                "INSERT OR IGNORE INTO phase15_network_profiles(profile_id,profile_kind,display_name,allowed_schemes_json,dns_mode,webrtc_mode,system_mutation_allowed,runtime_execution_enabled,review_status,config_ref,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (p["profile_id"], p["profile_kind"], p["display_name"], _canon(p["allowed_schemes"]), p["dns_mode"], p["webrtc_mode"], p["system_mutation_allowed"], p["runtime_execution_enabled"], p["review_status"], p["config_ref"], "policy-static", _sha(body)),
            )

    def _profile(self, profile_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase15_network_profiles WHERE profile_id=?", (profile_id,))
        if not row:
            raise KeyError(f"network profile not found: {profile_id}")
        if row["review_status"] != "approved_policy" or int(row["system_mutation_allowed"]) != 0:
            raise PermissionError("network profile is not approved for fail-closed capsule use")
        row["allowed_schemes"] = json.loads(row["allowed_schemes_json"])
        return row

    def _workspace(self, search_run_id: str) -> Path:
        return self.root / search_run_id

    def _capsule(self, search_run_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase15_search_capsules WHERE search_run_id=?", (search_run_id,))
        if not row:
            raise KeyError(search_run_id)
        row["egress_allowlist"] = json.loads(row["egress_allowlist_json"])
        row["resource_limits"] = json.loads(row["resource_limits_json"])
        row["isolation"] = json.loads(row["isolation_json"])
        return row

    def create_capsule(
        self,
        *,
        case_id: str,
        search_kind: str,
        egress_allowlist: list[str],
        network_profile_ref: str,
        task_id: str | None = None,
        max_requests: int = 25,
        max_response_bytes: int = 10 * 1024 * 1024,
        ttl_minutes: int = 120,
        actor: str | None = None,
    ) -> dict[str, Any]:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(f"case not found: {case_id}")
        kind = str(search_kind or "").strip().lower()
        if kind not in {"clearnet", "darknet"}:
            raise ValueError("search_kind must be clearnet or darknet")
        profile = self._profile(network_profile_ref)
        hosts = list(dict.fromkeys(_normalize_host(v) for v in egress_allowlist))
        if not hosts or len(hosts) > 100:
            raise ValueError("1..100 exact egress hosts are required")
        if kind == "darknet":
            if profile["profile_kind"] != "approved_tor" or any(not VALID_ONION.fullmatch(h) for h in hosts):
                raise PermissionError("Darknet capsules require the approved Tor profile and exact v3 onion hosts")
        else:
            if profile["profile_kind"] != "direct_https" or any(VALID_ONION.fullmatch(h) for h in hosts):
                raise PermissionError("Clearnet capsules require the direct HTTPS profile and non-onion hosts")
        max_requests = max(1, min(int(max_requests), 500))
        max_response_bytes = max(1024, min(int(max_response_bytes), 100 * 1024 * 1024))
        ttl_minutes = max(5, min(int(ttl_minutes), 8 * 60))
        search_run_id = "sr345_" + uuid.uuid4().hex[:20]
        ws = self._workspace(search_run_id)
        for rel in ("http/cookies", "http/cache", "browser/profile", "temp", "secrets/refs", "logs"):
            d = ws / rel
            d.mkdir(parents=True, exist_ok=False)
            _safe_chmod(d, 0o700)
        key = os.urandom(32)
        key_path = ws / ".capsule_key"
        key_path.write_bytes(key)
        _safe_chmod(key_path, 0o600)
        isolation = {
            "workspace_unique": True,
            "http_cookie_state": f"{search_run_id}/http/cookies",
            "http_cache_state": f"{search_run_id}/http/cache",
            "browser_profile_state": f"{search_run_id}/browser/profile",
            "temporary_files": f"{search_run_id}/temp",
            "secret_refs_only": f"{search_run_id}/secrets/refs",
            "shared_state_allowed": False,
        }
        limits = {"max_requests": max_requests, "max_response_bytes": max_response_bytes, "max_redirects": 5}
        now = datetime.now(timezone.utc)
        created = now.isoformat(timespec="seconds")
        expires = (now + timedelta(minutes=ttl_minutes)).isoformat(timespec="seconds")
        workspace_ref = str(ws.relative_to(self.base_dir).as_posix())
        manifest = {
            "search_run_id": search_run_id, "case_id": case_id, "search_kind": kind,
            "network_profile_ref": network_profile_ref, "egress_allowlist": hosts,
            "resource_limits": limits, "isolation": isolation, "key_fingerprint": _sha(key),
            "runtime_network_execution_enabled": False, "policy_version": POLICY_VERSION,
        }
        mp = ws / "capsule_manifest.json"
        mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _safe_chmod(mp, 0o600)
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO phase15_search_runs(search_run_id,case_id,task_id,search_kind,state,opsec_state,network_profile_ref,workspace_ref,policy_version,created_by,created_at,completed_at,summary_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (search_run_id, case_id, task_id, kind, "active", "preflight_required", network_profile_ref, workspace_ref, POLICY_VERSION, actor or self.actor, created, None, _canon({"network_execution": False, "egress_hosts": len(hosts)})),
            )
            self.db.execute(
                "INSERT INTO phase15_search_capsules(search_run_id,case_id,task_id,search_kind,capsule_state,network_profile_ref,workspace_ref,key_fingerprint,egress_allowlist_json,resource_limits_json,isolation_json,created_by,created_at,expires_at,closed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (search_run_id, case_id, task_id, kind, "active", network_profile_ref, workspace_ref, _sha(key), _canon(hosts), _canon(limits), _canon(isolation), actor or self.actor, created, expires, None),
            )
        self.append_encrypted_log(search_run_id, event_type="capsule_created", severity="info", payload={"manifest": manifest})
        return {**manifest, "workspace_ref": workspace_ref, "created_at": created, "expires_at": expires, "capsule_state": "active"}

    def create_darknet_capsule(self, *, case_id: str, source_ids: list[str], task_id: str | None = None, actor: str | None = None, max_requests: int = 25) -> dict[str, Any]:
        ids = list(dict.fromkeys(str(v).strip() for v in source_ids if str(v).strip()))
        if not ids:
            raise ValueError("source_ids required")
        ph = ",".join("?" for _ in ids)
        rows = self.db.all(f"SELECT source_id,locator,review_status,allowed_use FROM phase15_sources WHERE source_id IN ({ph}) AND source_kind='darknet_onion'", ids)
        if len(rows) != len(ids) or any(r["review_status"] != "approved_read_only" or r["allowed_use"] != "public_or_authorized_read_only" for r in rows):
            raise PermissionError("Every darknet source must be human-reviewed and approved read-only")
        return self.create_capsule(case_id=case_id, search_kind="darknet", egress_allowlist=[r["locator"] for r in rows], network_profile_ref="tor_read_only_v1", task_id=task_id, actor=actor, max_requests=max_requests)

    def _source_ok(self, source_id: str | None, host: str) -> bool:
        if not source_id:
            return False
        row = self.db.one("SELECT locator,review_status,allowed_use FROM phase15_sources WHERE source_id=? AND source_kind='darknet_onion'", (source_id,))
        return bool(row and row["locator"] == host and row["review_status"] == "approved_read_only" and row["allowed_use"] == "public_or_authorized_read_only")

    def _url_checks(self, url: str, capsule: dict[str, Any], profile: dict[str, Any], source_id: str | None) -> tuple[dict[str, Any], str, str]:
        try:
            parsed = urlsplit(str(url))
        except ValueError:
            return {"url_parse": False}, "", ""
        host = (parsed.hostname or "").lower().rstrip(".")
        try:
            port = parsed.port
            port_valid = True
        except ValueError:
            port = None
            port_valid = False
        checks: dict[str, Any] = {
            "url_parse": bool(host and parsed.scheme),
            "scheme_allowed": parsed.scheme.lower() in set(profile["allowed_schemes"]),
            "userinfo_absent": parsed.username is None and parsed.password is None,
            "host_exact_allowlist": host in set(capsule["egress_allowlist"]),
            "port_allowed": port_valid and port in (None, 80, 443),
        }
        secret_query = [k for k, _ in parse_qsl(parsed.query, keep_blank_values=True) if SECRET_NAME.search(k)]
        checks["query_secret_keys_absent"] = not secret_query
        if capsule["search_kind"] == "darknet":
            checks["v3_onion_host"] = bool(VALID_ONION.fullmatch(host))
            checks["reviewed_source_match"] = self._source_ok(source_id, host)
        else:
            checks["non_onion_host"] = not bool(VALID_ONION.fullmatch(host))
        return checks, parsed.scheme.lower(), host

    def preflight_request(
        self,
        search_run_id: str,
        *,
        url: str,
        method: str = "GET",
        headers: Mapping[str, Any] | None = None,
        redirect_chain: list[str] | None = None,
        source_id: str | None = None,
        expected_response_bytes: int = 0,
    ) -> dict[str, Any]:
        capsule = self._capsule(search_run_id)
        profile = self._profile(capsule["network_profile_ref"])
        ws = self.base_dir / capsule["workspace_ref"]
        key_path = ws / ".capsule_key"
        method_u = str(method or "").upper()
        headers_l = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        checks, scheme, host = self._url_checks(url, capsule, profile, source_id)
        previous = int(self.db.one("SELECT COUNT(*) c FROM phase15_opsec_decisions WHERE search_run_id=?", (search_run_id,))["c"])
        seq = previous + 1
        try:
            profile_cfg = json.loads(str(profile.get("config_ref") or "{}"))
        except Exception:
            profile_cfg = {}
        controlled_tor_v370 = bool(
            capsule.get("search_kind") == "darknet"
            and capsule.get("network_profile_ref") == "tor_read_only_v1"
            and profile.get("profile_kind") == "approved_tor"
            and int(profile.get("runtime_execution_enabled") or 0) == 1
            and isinstance(profile_cfg, dict)
            and profile_cfg.get("policy") == "phase16.controlled-tor-gateway.v370"
            and profile_cfg.get("enabled") is True
        )
        checks.update({
            "capsule_active": capsule["capsule_state"] == "active",
            "workspace_present": ws.is_dir(),
            "per_capsule_key_present": key_path.is_file() and _sha(key_path.read_bytes()) == capsule["key_fingerprint"],
            "method_read_only": method_u in ALLOWED_METHODS,
            "forbidden_headers_absent": not any(k in FORBIDDEN_HEADERS or SECRET_NAME.search(k) for k in headers_l),
            "request_budget_available": seq <= int(capsule["resource_limits"]["max_requests"]),
            "response_budget_valid": 0 <= int(expected_response_bytes or 0) <= int(capsule["resource_limits"]["max_response_bytes"]),
            "profile_system_mutation_forbidden": int(profile["system_mutation_allowed"]) == 0,
            "runtime_gateway_disabled_in_345": int(profile["runtime_execution_enabled"]) == 0 or controlled_tor_v370,
            "runtime_gateway_enabled_only_by_controlled_tor_v370": int(profile["runtime_execution_enabled"]) == 0 or controlled_tor_v370,
            "dns_policy_present": bool(profile["dns_mode"]),
            "webrtc_disable_required": "disabled_required" in profile["webrtc_mode"],
            "third_party_subrequests_forbidden": True,
        })
        redirects = list(redirect_chain or [])
        checks["redirect_count_within_limit"] = len(redirects) <= int(capsule["resource_limits"]["max_redirects"])
        redirect_ok = True
        for item in redirects:
            rc, _, _ = self._url_checks(item, capsule, profile, source_id)
            if not all(bool(v) for v in rc.values()):
                redirect_ok = False
                break
        checks["redirect_targets_allowlisted"] = redirect_ok
        failed = sorted(k for k, v in checks.items() if v is not True)
        disposition = "allow_for_gateway" if not failed else "block"
        decision_id = "opsec345_" + uuid.uuid4().hex[:20]
        created = _now()
        body = {
            "decision_id": decision_id, "search_run_id": search_run_id, "request_seq": seq,
            "target_scheme": scheme, "target_host": host, "source_id": source_id,
            "disposition": disposition, "reason_codes": failed, "checks": checks,
            "policy_version": POLICY_VERSION, "created_at": created,
        }
        self.db.execute(
            "INSERT INTO phase15_opsec_decisions(decision_id,search_run_id,request_seq,target_scheme,target_host,source_id,disposition,reason_codes_json,checks_json,policy_version,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (decision_id, search_run_id, seq, scheme, host, source_id, disposition, _canon(failed), _canon(checks), POLICY_VERSION, created, _sha(body)),
        )
        self.db.execute("UPDATE phase15_search_runs SET opsec_state=? WHERE search_run_id=?", ("preflight_passed" if disposition == "allow_for_gateway" else "blocked", search_run_id))
        self.append_encrypted_log(search_run_id, event_type="request_preflight", severity="warning" if failed else "info", payload={"url": url, "method": method_u, "headers": dict(headers or {}), "decision": body})
        return {**body, "network_execution": False, "gateway_token_issued": disposition == "allow_for_gateway"}

    def append_encrypted_log(self, search_run_id: str, *, event_type: str, severity: str, payload: Any) -> dict[str, Any]:
        capsule = self._capsule(search_run_id)
        ws = self.base_dir / capsule["workspace_ref"]
        key = (ws / ".capsule_key").read_bytes()
        if len(key) != 32:
            raise RuntimeError("invalid capsule key")
        summary: dict[str, int] = {}
        redacted = _redact(payload, summary)
        body = {"search_run_id": search_run_id, "event_type": str(event_type), "severity": str(severity), "created_at": _now(), "payload": redacted}
        raw = _canon(body).encode("utf-8")
        nonce = os.urandom(12)
        encrypted = b"EE345\0" + nonce + AESGCM(key).encrypt(nonce, raw, search_run_id.encode("utf-8"))
        log_id = "clog345_" + uuid.uuid4().hex[:20]
        path = ws / "logs" / f"{log_id}.aesgcm"
        path.write_bytes(encrypted)
        _safe_chmod(path, 0o600)
        ref = str(path.relative_to(self.base_dir).as_posix())
        digest = _sha(encrypted)
        self.db.execute(
            "INSERT INTO phase15_capsule_logs(log_id,search_run_id,event_type,severity,encrypted_ref,digest_sha256,redaction_summary_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (log_id, search_run_id, str(event_type), str(severity), ref, digest, _canon(summary), body["created_at"]),
        )
        return {"log_id": log_id, "encrypted_ref": ref, "digest_sha256": digest, "redaction_summary": summary}

    def decrypt_log(self, log_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase15_capsule_logs WHERE log_id=?", (log_id,))
        if not row:
            raise KeyError(log_id)
        capsule = self._capsule(row["search_run_id"])
        ws = self.base_dir / capsule["workspace_ref"]
        key = (ws / ".capsule_key").read_bytes()
        encrypted = (self.base_dir / row["encrypted_ref"]).read_bytes()
        if not encrypted.startswith(b"EE345\0") or _sha(encrypted) != row["digest_sha256"]:
            raise RuntimeError("encrypted log integrity failure")
        nonce, ciphertext = encrypted[6:18], encrypted[18:]
        raw = AESGCM(key).decrypt(nonce, ciphertext, row["search_run_id"].encode("utf-8"))
        return json.loads(raw)

    def close_capsule(self, search_run_id: str, *, actor: str | None = None) -> dict[str, Any]:
        capsule = self._capsule(search_run_id)
        ws = self.base_dir / capsule["workspace_ref"]
        now = _now()
        for rel in ("http", "browser", "temp"):
            shutil.rmtree(ws / rel, ignore_errors=True)
        with self.db.transaction(immediate=True):
            self.db.execute("UPDATE phase15_search_capsules SET capsule_state='closed',closed_at=? WHERE search_run_id=?", (now, search_run_id))
            self.db.execute("UPDATE phase15_search_runs SET state='closed',completed_at=?,summary_json=? WHERE search_run_id=?", (now, _canon({"closed_by": actor or self.actor, "transient_state_purged": True, "network_execution": False}), search_run_id))
        self.append_encrypted_log(search_run_id, event_type="capsule_closed", severity="info", payload={"actor": actor or self.actor, "transient_state_purged": True})
        return {"search_run_id": search_run_id, "capsule_state": "closed", "transient_state_purged": True, "closed_at": now}

    def list_capsules(self, *, case_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        sql = "SELECT search_run_id,case_id,task_id,search_kind,capsule_state,network_profile_ref,workspace_ref,key_fingerprint,egress_allowlist_json,resource_limits_json,created_by,created_at,expires_at,closed_at FROM phase15_search_capsules"
        rows = self.db.all(sql + " WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, limit)) if case_id else self.db.all(sql + " ORDER BY created_at DESC LIMIT ?", (limit,))
        for row in rows:
            row["egress_allowlist"] = json.loads(row.pop("egress_allowlist_json"))
            row["resource_limits"] = json.loads(row.pop("resource_limits_json"))
        return rows

    def decisions(self, search_run_id: str) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT decision_id,request_seq,target_scheme,target_host,source_id,disposition,reason_codes_json,checks_json,policy_version,created_at,record_hash FROM phase15_opsec_decisions WHERE search_run_id=? ORDER BY request_seq", (search_run_id,))
        for row in rows:
            row["reason_codes"] = json.loads(row.pop("reason_codes_json"))
            row["checks"] = json.loads(row.pop("checks_json"))
        return rows
