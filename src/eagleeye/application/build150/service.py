from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import re
import secrets
import threading
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

POLICY_CONFIRMATION = "CAPTURE-POLICY 150 FREIGEBEN"
SESSION_CONFIRMATION = "CAPTURE-SESSION 150 STARTEN"
STOP_CONFIRMATION = "CAPTURE-SESSION 150 BEENDEN"
VERIFY_CONFIRMATION = "CAPTURE 150 INTEGRITÄT PRÜFEN"

POLICY_MODES = {"manual", "approved_hosts"}
POLICY_STATUSES = {"draft", "approved", "revoked"}
SESSION_STATUSES = {"planned", "active", "paused", "stopped", "expired", "completed"}
TRACKING_KEYS = {"fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid"}
SECRET_KEYS = {"access_token", "token", "api_key", "apikey", "signature", "sig", "auth", "authorization", "password", "secret", "key"}


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha(value: Any) -> str:
    return _sha_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))


def _safe(value: Any, limit: int = 4000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _host(value: str) -> str:
    try:
        return (urlsplit(value).hostname or "").casefold().rstrip(".")
    except ValueError:
        return ""


def _canonical_public_url(value: Any, *, allow_query: bool = True) -> str:
    raw = str(value or "").strip()
    if not raw or len(raw) > 8192:
        raise ValueError("Ungültige oder zu lange URL")
    try:
        parts = urlsplit(raw)
    except ValueError as exc:
        raise ValueError("URL konnte nicht sicher verarbeitet werden") from exc
    if parts.scheme.casefold() != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Capture akzeptiert ausschließlich öffentliche HTTPS-URLs ohne eingebettete Zugangsdaten")
    host = parts.hostname.casefold().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Lokale Hosts sind gesperrt")
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Private, Loopback- oder reservierte IP-Ziele sind gesperrt")
    query: list[tuple[str, str]] = []
    if allow_query:
        for key, item in parse_qsl(parts.query, keep_blank_values=True, max_num_fields=100):
            normalized = key.casefold().strip()
            if normalized in SECRET_KEYS or normalized.endswith("_token") or normalized.endswith("_secret") or normalized.endswith("_signature"):
                raise ValueError("URL enthält möglicherweise Geheimnis- oder Signaturparameter")
            if normalized.startswith("utm_") or normalized in TRACKING_KEYS:
                continue
            query.append((key[:200], item[:2000]))
    port = parts.port
    netloc = host if port in {None, 443} else f"{host}:{port}"
    return urlunsplit(("https", netloc, parts.path or "/", urlencode(query, doseq=True), ""))


def _normalize_hosts(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip().casefold().rstrip(".")
        if not text:
            continue
        if "://" in text:
            text = _host(_canonical_public_url(text, allow_query=False))
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", text) or ".." in text or "." not in text:
            raise ValueError(f"Ungültiger öffentlicher Host: {text}")
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out[:100]


def _loads(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    return loads(value, default)


class Build150EvidenceCaptureService:
    BUILD = "150.0"
    MAX_PAYLOAD_BYTES = 28 * 1024 * 1024
    MAX_RESOURCES = 750
    MAX_JSONLD = 40
    MAX_SESSION_MINUTES = 240
    MAX_POLICY_CAPTURES = 5000

    def __init__(self, db: Any, audit: Any, base_dir: str | Path, *, capture129: Any, build136: Any, build149: Any) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.capture129 = capture129
        self.build136 = build136
        self.build149 = build149
        self.package_root = self.base_dir / "data" / "browser_evidence_150"
        self._capture_lock = threading.RLock()
        self.package_root.mkdir(parents=True, exist_ok=True)
        try:
            self.package_root.chmod(0o700)
        except OSError:
            pass

    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not row:
            raise KeyError("Fall nicht gefunden")
        return row

    def _target(self, case_id: str, target_id: str) -> None:
        if target_id and not self.db.one("SELECT target_id FROM targets WHERE case_id=? AND target_id=?", (case_id, target_id)):
            raise ValueError("Zielperson gehört nicht zu diesem Fall")

    def _event(self, *, case_id: str | None, event_type: str, actor: str, session_id: str = "", record_id: str = "", payload: Mapping[str, Any] | None = None) -> str:
        last = self.db.one("SELECT event_hash FROM capture_events_150 WHERE case_id IS ? ORDER BY sequence DESC LIMIT 1", (case_id,))
        previous = str((last or {}).get("event_hash") or "")
        event_id = new_id("cap150evt")
        created = now_ts()
        safe_payload = dict(payload or {})
        event_hash = _sha({"event_id": event_id, "case_id": case_id or "", "session_id": session_id, "record_id": record_id, "event_type": event_type, "actor": actor, "payload": safe_payload, "previous_hash": previous, "created_at": created})
        self.db.execute(
            "INSERT INTO capture_events_150(event_id,case_id,session_id,record_id,actor,event_type,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (event_id, case_id, session_id, record_id, actor, event_type, dumps(safe_payload), previous, event_hash, created),
        )
        self.audit.log(event_type, "browser_capture_150", record_id or session_id or event_id, case_id, safe_payload)
        return event_id

    def create_policy(self, *, case_id: str, target_id: str = "", label: str, purpose: str, legal_basis: str, mode: str, allowed_hosts: Iterable[str], excluded_hosts: Iterable[str] = (), include_html: bool = True, include_visible_text: bool = True, include_screenshot: bool = True, include_resource_inventory: bool = True, include_jsonld: bool = True, capture_delay_ms: int = 1500, min_interval_seconds: int = 30, max_captures: int = 100, retention_days: int = 365, actor: str) -> dict[str, Any]:
        self._case(case_id); self._target(case_id, target_id)
        mode = str(mode or "manual")
        if mode not in POLICY_MODES:
            raise ValueError("Ungültiger Capture-Modus")
        label = _safe(label, 200); purpose = _safe(purpose, 2000); legal_basis = _safe(legal_basis, 1000)
        if len(label) < 3 or len(purpose) < 10 or len(legal_basis) < 8:
            raise ValueError("Bezeichnung, Zweck und Rechtsgrundlage müssen nachvollziehbar sein")
        allowed = _normalize_hosts(allowed_hosts)
        excluded = _normalize_hosts(excluded_hosts)
        if mode == "approved_hosts" and not allowed:
            raise ValueError("Automatische Captures benötigen eine explizite Host-Allowlist")
        if set(allowed) & set(excluded):
            raise ValueError("Ein Host kann nicht zugleich erlaubt und ausgeschlossen sein")
        delay = max(500, min(15000, int(capture_delay_ms)))
        interval = max(10, min(86400, int(min_interval_seconds)))
        max_count = max(1, min(self.MAX_POLICY_CAPTURES, int(max_captures)))
        retention = max(1, min(3650, int(retention_days)))
        policy_id = new_id("cappol150")
        ts = now_ts()
        self.db.execute(
            """INSERT INTO capture_policies_150(policy_id,case_id,target_id,label,purpose,legal_basis,mode,allowed_hosts_json,excluded_hosts_json,include_html,include_visible_text,include_screenshot,include_resource_inventory,include_jsonld,capture_delay_ms,min_interval_seconds,max_captures,retention_days,status,created_by,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'draft',?,?,?)""",
            (policy_id, case_id, target_id or None, label, purpose, legal_basis, mode, dumps(allowed), dumps(excluded), int(include_html), int(include_visible_text), int(include_screenshot), int(include_resource_inventory), int(include_jsonld), delay, interval, max_count, retention, actor, ts, ts),
        )
        self._event(case_id=case_id, event_type="capture_policy_created", actor=actor, payload={"policy_id": policy_id, "mode": mode, "allowed_hosts": allowed, "max_captures": max_count})
        return self.get_policy(case_id, policy_id)

    def approve_policy(self, *, case_id: str, policy_id: str, confirmation: str, actor: str) -> dict[str, Any]:
        if confirmation != POLICY_CONFIRMATION:
            raise ValueError("Bestätigungsphrase stimmt nicht")
        row = self.db.one("SELECT * FROM capture_policies_150 WHERE case_id=? AND policy_id=?", (case_id, policy_id))
        if not row:
            raise KeyError("Capture-Policy nicht gefunden")
        if row["status"] == "approved":
            return self.get_policy(case_id, policy_id)
        if row["status"] == "revoked":
            raise ValueError("Widerrufene Policies können nicht erneut freigegeben werden")
        if row["mode"] == "approved_hosts" and row["created_by"] == actor:
            raise PermissionError("Automatische Capture-Policies benötigen eine unabhängige zweite Person")
        self.db.execute("UPDATE capture_policies_150 SET status='approved',approved_by=?,approved_at=?,updated_at=? WHERE policy_id=?", (actor, now_ts(), now_ts(), policy_id))
        self._event(case_id=case_id, event_type="capture_policy_approved", actor=actor, payload={"policy_id": policy_id, "mode": row["mode"]})
        return self.get_policy(case_id, policy_id)

    def revoke_policy(self, *, case_id: str, policy_id: str, actor: str, reason: str) -> dict[str, Any]:
        reason = _safe(reason, 1000)
        if len(reason) < 8:
            raise ValueError("Widerrufsgrund ist erforderlich")
        row = self.db.one("SELECT * FROM capture_policies_150 WHERE case_id=? AND policy_id=?", (case_id, policy_id))
        if not row:
            raise KeyError("Capture-Policy nicht gefunden")
        with self.db.transaction(immediate=True):
            self.db.execute("UPDATE capture_policies_150 SET status='revoked',updated_at=? WHERE policy_id=?", (now_ts(), policy_id))
            self.db.execute("UPDATE capture_sessions_150 SET status='stopped',stopped_at=?,stop_reason=?,updated_at=? WHERE policy_id=? AND status IN ('planned','active','paused')", (now_ts(), reason, now_ts(), policy_id))
            self._event(case_id=case_id, event_type="capture_policy_revoked", actor=actor, payload={"policy_id": policy_id, "reason": reason})
        return self.get_policy(case_id, policy_id)

    def get_policy(self, case_id: str, policy_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM capture_policies_150 WHERE case_id=? AND policy_id=?", (case_id, policy_id))
        if not row:
            raise KeyError("Capture-Policy nicht gefunden")
        row["allowed_hosts"] = _loads(row.pop("allowed_hosts_json", "[]"), [])
        row["excluded_hosts"] = _loads(row.pop("excluded_hosts_json", "[]"), [])
        return row

    def start_session(self, *, case_id: str, policy_id: str, duration_minutes: int, confirmation: str, actor: str) -> dict[str, Any]:
        if confirmation != SESSION_CONFIRMATION:
            raise ValueError("Bestätigungsphrase stimmt nicht")
        policy = self.get_policy(case_id, policy_id)
        if policy["status"] != "approved":
            raise PermissionError("Capture-Policy ist nicht freigegeben")
        duration = max(10, min(self.MAX_SESSION_MINUTES, int(duration_minutes)))
        if policy["mode"] == "approved_hosts" and not self.build136.build135.companion_active(case_id):
            raise PermissionError("Automatische Captures benötigen einen aktiven fallgebundenen Firefox-Companion")
        active = self.db.one("SELECT session_id FROM capture_sessions_150 WHERE case_id=? AND status='active'", (case_id,))
        if active:
            raise ValueError("Für diesen Fall läuft bereits eine Capture-Session")
        session_id = new_id("capsess150")
        started = _now_dt(); expires = started + timedelta(minutes=duration)
        self.db.execute(
            """INSERT INTO capture_sessions_150(session_id,policy_id,case_id,target_id,companion_case_id,status,max_captures,started_by,started_at,expires_at,created_at,updated_at)
               VALUES(?,?,?,?,?,'active',?,?,?,?,?,?)""",
            (session_id, policy_id, case_id, policy.get("target_id") or None, case_id, int(policy["max_captures"]), actor, started.isoformat(timespec="seconds"), expires.isoformat(timespec="seconds"), started.isoformat(timespec="seconds"), started.isoformat(timespec="seconds")),
        )
        self._event(case_id=case_id, session_id=session_id, event_type="capture_session_started", actor=actor, payload={"policy_id": policy_id, "mode": policy["mode"], "expires_at": expires.isoformat(timespec="seconds"), "max_captures": policy["max_captures"]})
        return self.get_session(case_id, session_id)

    def stop_session(self, *, case_id: str, session_id: str, confirmation: str, actor: str, reason: str = "manual_stop") -> dict[str, Any]:
        if confirmation != STOP_CONFIRMATION:
            raise ValueError("Bestätigungsphrase stimmt nicht")
        row = self.db.one("SELECT * FROM capture_sessions_150 WHERE case_id=? AND session_id=?", (case_id, session_id))
        if not row:
            raise KeyError("Capture-Session nicht gefunden")
        if row["status"] not in {"stopped", "completed", "expired"}:
            self.db.execute("UPDATE capture_sessions_150 SET status='stopped',stopped_at=?,stop_reason=?,updated_at=? WHERE session_id=?", (now_ts(), _safe(reason, 500), now_ts(), session_id))
            self._event(case_id=case_id, session_id=session_id, event_type="capture_session_stopped", actor=actor, payload={"reason": _safe(reason, 500), "captured_count": row["captured_count"]})
        return self.get_session(case_id, session_id)

    def get_session(self, case_id: str, session_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM capture_sessions_150 WHERE case_id=? AND session_id=?", (case_id, session_id))
        if not row:
            raise KeyError("Capture-Session nicht gefunden")
        return row

    def _active_session(self, case_id: str) -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, None]:
        row = self.db.one("SELECT * FROM capture_sessions_150 WHERE case_id=? AND status='active' ORDER BY started_at DESC LIMIT 1", (case_id,))
        if not row:
            return None, None
        now = _now_dt().isoformat(timespec="seconds")
        if row["expires_at"] <= now:
            self.db.execute("UPDATE capture_sessions_150 SET status='expired',stopped_at=?,stop_reason='expired',updated_at=? WHERE session_id=?", (now_ts(), now_ts(), row["session_id"]))
            self._event(case_id=case_id, session_id=row["session_id"], event_type="capture_session_expired", actor="system", payload={})
            return None, None
        if int(row["captured_count"]) >= int(row["max_captures"]):
            self.db.execute("UPDATE capture_sessions_150 SET status='completed',stopped_at=?,stop_reason='capture_budget_exhausted',updated_at=? WHERE session_id=?", (now_ts(), now_ts(), row["session_id"]))
            self._event(case_id=case_id, session_id=row["session_id"], event_type="capture_session_completed", actor="system", payload={"reason": "capture_budget_exhausted"})
            return None, None
        return row, self.get_policy(case_id, row["policy_id"])

    def companion_config(self, *, case_id: str, token: str) -> dict[str, Any]:
        self.build136.build135._verify_companion(case_id, token)
        session, policy = self._active_session(case_id)
        if not session or not policy:
            return {"ok": True, "active": False, "case_id": case_id, "build": self.BUILD}
        return {
            "ok": True,
            "active": True,
            "build": self.BUILD,
            "case_id": case_id,
            "session_id": session["session_id"],
            "mode": policy["mode"],
            "auto_capture": policy["mode"] == "approved_hosts",
            "allowed_hosts": policy["allowed_hosts"],
            "excluded_hosts": policy["excluded_hosts"],
            "capture_delay_ms": int(policy["capture_delay_ms"]),
            "min_interval_seconds": int(policy["min_interval_seconds"]),
            "remaining_captures": max(0, int(session["max_captures"]) - int(session["captured_count"])),
            "expires_at": session["expires_at"],
            "include": {
                "html": bool(policy["include_html"]),
                "visible_text": bool(policy["include_visible_text"]),
                "screenshot": bool(policy["include_screenshot"]),
                "resources": bool(policy["include_resource_inventory"]),
                "jsonld": bool(policy["include_jsonld"]),
            },
        }

    @staticmethod
    def _filter_resources(items: Any, *, source_host: str) -> list[dict[str, str]]:
        if not isinstance(items, list):
            return []
        out: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in items[: Build150EvidenceCaptureService.MAX_RESOURCES * 2]:
            if not isinstance(item, dict):
                continue
            kind = _safe(item.get("type"), 40).casefold()
            if kind not in {"link", "image", "script", "stylesheet", "video", "audio", "document", "canonical"}:
                continue
            try:
                url = _canonical_public_url(item.get("url"))
            except Exception:
                continue
            key = (kind, url)
            if key in seen:
                continue
            seen.add(key)
            out.append({"type": kind, "url": url, "host": _host(url), "relation": _safe(item.get("relation"), 100), "same_host": str(_host(url) == source_host).lower()})
            if len(out) >= Build150EvidenceCaptureService.MAX_RESOURCES:
                break
        return out

    @staticmethod
    def _filtered_jsonld(value: Any) -> list[Any]:
        if not isinstance(value, list):
            return []
        output: list[Any] = []
        for item in value[: Build150EvidenceCaptureService.MAX_JSONLD]:
            raw = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
            if len(raw.encode("utf-8")) <= 128 * 1024:
                output.append(item)
        return output

    def submit_companion_capture(self, *, case_id: str, session_id: str, token: str, payload: dict[str, Any], trigger_mode: str, origin: str = "") -> dict[str, Any]:
        # Serialize capture finalization so interval and budget checks cannot race in the local app process.
        with self._capture_lock:
            return self._submit_companion_capture_locked(case_id=case_id, session_id=session_id, token=token, payload=payload, trigger_mode=trigger_mode, origin=origin)

    def _submit_companion_capture_locked(self, *, case_id: str, session_id: str, token: str, payload: dict[str, Any], trigger_mode: str, origin: str = "") -> dict[str, Any]:
        self.build136.build135._verify_companion(case_id, token)
        session, policy = self._active_session(case_id)
        if not session or not policy or session["session_id"] != session_id:
            raise PermissionError("Keine aktive passende Capture-Session")
        trigger = str(trigger_mode or "manual")
        if trigger not in {"manual", "auto_approved"}:
            raise ValueError("Ungültiger Capture-Trigger")
        if trigger == "auto_approved" and policy["mode"] != "approved_hosts":
            raise PermissionError("Automatische Aufnahme ist für diese Policy nicht freigegeben")
        canonical = _canonical_public_url(payload.get("url"))
        source_host = _host(canonical)
        allowed = set(policy["allowed_hosts"]); excluded = set(policy["excluded_hosts"])
        if source_host in excluded:
            raise PermissionError("Der Host ist durch die Capture-Policy ausgeschlossen")
        # The server enforces the allowlist for every trigger. This prevents an old or
        # modified Companion from bypassing a deliberately narrow manual policy.
        if allowed and source_host not in allowed:
            raise PermissionError("Der Host ist nicht durch die Capture-Policy freigegeben")
        if trigger == "auto_approved" and source_host not in allowed:
            raise PermissionError("Der Host ist nicht für automatische Captures freigegeben")
        last = self.db.one("SELECT captured_at FROM browser_capture_records_150 WHERE session_id=? AND canonical_url=? ORDER BY captured_at DESC LIMIT 1", (session_id, canonical))
        if last:
            try:
                age = (_now_dt() - datetime.fromisoformat(str(last["captured_at"]).replace("Z", "+00:00"))).total_seconds()
            except Exception:
                age = 0
            if age < int(policy["min_interval_seconds"]):
                raise ValueError("Mindestintervall für diese Seite ist noch nicht abgelaufen")

        resources = self._filter_resources(payload.get("resources"), source_host=source_host) if policy["include_resource_inventory"] else []
        page_meta = payload.get("page_metadata") if isinstance(payload.get("page_metadata"), dict) else {}
        if trigger == "auto_approved" and bool(page_meta.get("sensitive_form_present")):
            raise PermissionError("Automatische Aufnahme einer Seite mit sichtbarem Passwortfeld ist gesperrt")
        jsonld = self._filtered_jsonld(payload.get("jsonld")) if policy["include_jsonld"] else []
        capture_payload = {
            "url": canonical,
            "title": _safe(payload.get("title") or source_host, 500),
            "visible_text": str(payload.get("visible_text") or "") if policy["include_visible_text"] else "",
            "html": str(payload.get("html") or "") if policy["include_html"] else "",
            "screenshot_base64": payload.get("screenshot_base64") if policy["include_screenshot"] else "",
            "attachments": [],
        }
        if not capture_payload["visible_text"].strip() and not capture_payload["html"].strip():
            capture_payload["visible_text"] = f"Capture metadata only: {capture_payload['title']}"
        ticket = self.capture129.issue_capture_ticket(case_id=case_id, target_id=session.get("target_id") or "", purpose=f"Build 150 browser evidence: {policy['purpose']}", actor=session["started_by"], ttl_seconds=120)
        result = self.capture129.capture_from_companion(ticket=ticket["ticket"], payload=capture_payload, origin=origin)
        capture = self.capture129.get_capture(case_id, result["capture_id"])
        previous = self.db.one("SELECT * FROM browser_capture_records_150 WHERE case_id=? AND canonical_url=? ORDER BY captured_at DESC LIMIT 1", (case_id, canonical))
        record_id = new_id("caprec150")
        metadata = {
            "page_metadata": {str(k)[:100]: _safe(v, 1000) for k, v in list(page_meta.items())[:100]},
            "jsonld": jsonld,
            "resource_count": len(resources),
            "capture_trigger": trigger,
            "untrusted_content": True,
            "automatic_truth_promotion": False,
        }
        dom_hash = _sha_bytes(str(capture_payload["html"]).encode("utf-8", errors="replace")) if capture_payload["html"] else ""
        resource_hash = _sha(resources)
        metadata_hash = _sha(metadata)
        package_relpath, package_sha = self._create_wacz_package(record_id=record_id, case_id=case_id, capture=capture, metadata=metadata, resources=resources)
        with self.db.transaction(immediate=True):
            self.db.execute(
                """INSERT INTO browser_capture_records_150(record_id,session_id,policy_id,case_id,target_id,capture_id_129,trigger_mode,canonical_url,source_host,title,page_language,document_type,dom_sha256,resource_inventory_sha256,metadata_sha256,previous_record_id,change_state,integrity_state,package_relpath,package_sha256,candidate_only,captured_by,captured_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (record_id, session_id, policy["policy_id"], case_id, session.get("target_id") or None, capture["capture_id"], trigger, canonical, source_host, capture["title"], _safe(page_meta.get("language"), 40), _safe(page_meta.get("document_type") or "html", 40), dom_hash, resource_hash, metadata_hash, (previous or {}).get("record_id"), capture["change_state"], "verified", package_relpath, package_sha, 1, session["started_by"], capture["captured_at"]),
            )
            for item in resources:
                self.db.execute("INSERT OR IGNORE INTO capture_resource_inventory_150(resource_id,record_id,case_id,resource_type,canonical_url,source_host,url_sha256,relation,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (new_id("capres150"), record_id, case_id, item["type"], item["url"], item["host"], _sha_bytes(item["url"].encode("utf-8")), item["relation"], now_ts()))
            self._create_diff(case_id=case_id, previous=previous, current_record_id=record_id, current_capture=capture, current_resources=resources, canonical_url=canonical, current_metadata_sha256=metadata_hash)
            self.db.execute("UPDATE capture_sessions_150 SET captured_count=captured_count+1,last_capture_at=?,updated_at=? WHERE session_id=?", (now_ts(), now_ts(), session_id))
            self._event(case_id=case_id, session_id=session_id, record_id=record_id, event_type="browser_evidence_captured", actor=session["started_by"], payload={"capture_id_129": capture["capture_id"], "trigger": trigger, "host": source_host, "change_state": capture["change_state"], "resources": len(resources), "package_sha256": package_sha, "candidate_only": True})
        return self.get_record(case_id, record_id)

    def _create_diff(self, *, case_id: str, previous: dict[str, Any] | None, current_record_id: str, current_capture: dict[str, Any], current_resources: list[dict[str, str]], canonical_url: str, current_metadata_sha256: str) -> None:
        if not previous:
            return
        previous_capture = self.capture129.get_capture(case_id, previous["capture_id_129"])
        prev_urls = {row["canonical_url"] for row in self.db.all("SELECT canonical_url FROM capture_resource_inventory_150 WHERE record_id=?", (previous["record_id"],))}
        current_urls = {row["url"] for row in current_resources}
        summary = {
            "text_changed": previous_capture["visible_text_sha256"] != current_capture["visible_text_sha256"],
            "html_changed": previous_capture["html_sha256"] != current_capture["html_sha256"],
            "screenshot_changed": previous_capture["screenshot_sha256"] != current_capture["screenshot_sha256"],
            "metadata_changed": previous["metadata_sha256"] != current_metadata_sha256,
            "resources_added": sorted(current_urls - prev_urls)[:100],
            "resources_removed": sorted(prev_urls - current_urls)[:100],
        }
        self.db.execute("INSERT INTO capture_diffs_150(diff_id,case_id,previous_record_id,current_record_id,canonical_url,text_changed,html_changed,screenshot_changed,metadata_changed,resources_added,resources_removed,summary_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (new_id("capdiff150"), case_id, previous["record_id"], current_record_id, canonical_url, int(summary["text_changed"]), int(summary["html_changed"]), int(summary["screenshot_changed"]), int(summary["metadata_changed"]), len(summary["resources_added"]), len(summary["resources_removed"]), dumps(summary), now_ts()))

    @staticmethod
    def _warc_record(*, record_type: str, content_type: str, payload: bytes, target_uri: str = "", record_id: str | None = None, date: str | None = None) -> bytes:
        rid = record_id or f"<urn:uuid:{uuid.uuid4()}>"
        block_digest = base64.b32encode(hashlib.sha256(payload).digest()).decode("ascii").rstrip("=")
        headers = ["WARC/1.1", f"WARC-Type: {record_type}", f"WARC-Date: {date or _now_dt().isoformat(timespec='seconds')}", f"WARC-Record-ID: {rid}", f"WARC-Block-Digest: sha256:{block_digest}"]
        if target_uri:
            headers.append(f"WARC-Target-URI: {target_uri}")
        headers.extend([f"Content-Type: {content_type}", f"Content-Length: {len(payload)}", "", ""])
        return "\r\n".join(headers).encode("utf-8") + payload + b"\r\n\r\n"

    def _create_wacz_package(self, *, record_id: str, case_id: str, capture: dict[str, Any], metadata: dict[str, Any], resources: list[dict[str, str]]) -> tuple[str, str]:
        case_dir = self.package_root / re.sub(r"[^A-Za-z0-9_-]", "_", case_id)
        case_dir.mkdir(parents=True, exist_ok=True)
        try:
            case_dir.chmod(0o700)
        except OSError:
            pass
        final = case_dir / f"{record_id}.wacz"
        temp = case_dir / f".{record_id}.tmp"
        artifacts = capture.get("artifacts") or []
        warc = bytearray()
        warcinfo = json.dumps({"software": "EagleEye PersonOSINT Pro 150.0", "format": "WARC/1.1", "record_id": record_id, "case_id_sha256": _sha_bytes(case_id.encode()), "capture_id": capture["capture_id"], "notice": "Companion DOM snapshot and viewport capture; not a full network transaction archive."}, ensure_ascii=False, sort_keys=True).encode("utf-8")
        warc.extend(self._warc_record(record_type="warcinfo", content_type="application/json", payload=warcinfo))
        file_entries: list[dict[str, Any]] = []
        for artifact in artifacts:
            path = (self.base_dir / artifact["relpath"]).resolve()
            try:
                path.relative_to(self.base_dir)
            except ValueError:
                continue
            if not path.is_file():
                continue
            data = path.read_bytes()
            warc.extend(self._warc_record(record_type="resource", content_type=artifact["media_type"], payload=data, target_uri=capture["canonical_url"]))
            file_entries.append({"name": artifact["filename"], "sha256": artifact["sha256"], "size": artifact["byte_size"], "type": artifact["artifact_kind"]})
        metadata_payload = json.dumps({"capture": {k: capture.get(k) for k in ("capture_id", "canonical_url", "source_host", "title", "captured_at", "change_state", "manifest_sha256")}, "metadata": metadata, "resources": resources, "candidate_only": True}, ensure_ascii=False, sort_keys=True).encode("utf-8")
        warc.extend(self._warc_record(record_type="metadata", content_type="application/json", payload=metadata_payload, target_uri=capture["canonical_url"]))
        warc_bytes = bytes(warc)
        warc_sha = _sha_bytes(warc_bytes)
        pages = json.dumps({"id": record_id, "url": capture["canonical_url"], "title": capture["title"], "ts": capture["captured_at"]}, ensure_ascii=False) + "\n"
        cdxj = f"{capture['canonical_url']} {capture['captured_at']} " + json.dumps({"url": capture["canonical_url"], "mime": "text/html", "status": "200", "digest": f"sha256:{capture['html_sha256'] or capture['visible_text_sha256']}", "filename": "archive/data.warc"}, separators=(",", ":")) + "\n"
        datapackage = {
            "profile": "data-package",
            "wacz_version": "1.1.1",
            "title": f"EagleEye Capture {record_id}",
            "created": now_ts(),
            "software": "EagleEye PersonOSINT Pro 150.0",
            "resources": [{"name": "data.warc", "path": "archive/data.warc", "hash": f"sha256:{warc_sha}", "bytes": len(warc_bytes)}],
            "eagleeye": {"record_id": record_id, "capture_id": capture["capture_id"], "candidate_only": True, "full_network_capture": False, "artifacts": file_entries},
        }
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr("archive/data.warc", warc_bytes)
            archive.writestr("pages/pages.jsonl", pages.encode("utf-8"))
            archive.writestr("indexes/index.cdxj", cdxj.encode("utf-8"))
            archive.writestr("datapackage.json", json.dumps(datapackage, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
        try:
            temp.chmod(0o600)
        except OSError:
            pass
        os.replace(temp, final)
        try:
            final.chmod(0o600)
        except OSError:
            pass
        return final.relative_to(self.base_dir).as_posix(), _sha_bytes(final.read_bytes())

    def get_record(self, case_id: str, record_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM browser_capture_records_150 WHERE case_id=? AND record_id=?", (case_id, record_id))
        if not row:
            raise KeyError("Capture-Record nicht gefunden")
        row["resources"] = self.db.all("SELECT resource_type,canonical_url,source_host,relation,url_sha256 FROM capture_resource_inventory_150 WHERE record_id=? ORDER BY resource_type,canonical_url", (record_id,))
        row["diff"] = self.db.one("SELECT * FROM capture_diffs_150 WHERE current_record_id=?", (record_id,))
        return row

    def verify_record(self, *, case_id: str, record_id: str, confirmation: str, actor: str) -> dict[str, Any]:
        if confirmation != VERIFY_CONFIRMATION:
            raise ValueError("Bestätigungsphrase stimmt nicht")
        row = self.get_record(case_id, record_id)
        problems: list[str] = []
        capture_check = self.capture129.verify_capture(case_id, row["capture_id_129"])
        if not capture_check.get("valid"):
            problems.extend([f"capture129:{item}" for item in capture_check.get("problems", [])])
        path = (self.base_dir / row["package_relpath"]).resolve()
        try:
            path.relative_to(self.base_dir)
        except ValueError:
            problems.append("unsafe_package_path")
        if not path.is_file():
            problems.append("package_missing")
        else:
            if _sha_bytes(path.read_bytes()) != row["package_sha256"]:
                problems.append("package_hash_mismatch")
            try:
                with zipfile.ZipFile(path) as archive:
                    required = {"archive/data.warc", "pages/pages.jsonl", "indexes/index.cdxj", "datapackage.json"}
                    if not required.issubset(set(archive.namelist())):
                        problems.append("wacz_required_entries_missing")
                    bad_member = archive.testzip()
                    if bad_member:
                        problems.append(f"wacz_crc_error:{bad_member}")
                    package = json.loads(archive.read("datapackage.json").decode("utf-8"))
                    eagleeye = package.get("eagleeye", {}) if isinstance(package, dict) else {}
                    if eagleeye.get("record_id") != record_id:
                        problems.append("wacz_record_mismatch")
                    if eagleeye.get("capture_id") != row["capture_id_129"]:
                        problems.append("wacz_capture_mismatch")
                    if eagleeye.get("candidate_only") is not True:
                        problems.append("wacz_candidate_contract_mismatch")
                    if eagleeye.get("full_network_capture") is not False:
                        problems.append("wacz_network_capture_claim_mismatch")
                    warc_bytes = archive.read("archive/data.warc")
                    resources = package.get("resources", []) if isinstance(package, dict) else []
                    warc_entry = next((item for item in resources if isinstance(item, dict) and item.get("path") == "archive/data.warc"), None)
                    if not warc_entry or warc_entry.get("hash") != f"sha256:{_sha_bytes(warc_bytes)}":
                        problems.append("wacz_warc_hash_mismatch")
            except Exception:
                problems.append("wacz_invalid")
        state = "verified" if not problems else "failed"
        self.db.execute("UPDATE browser_capture_records_150 SET integrity_state=? WHERE record_id=?", (state, record_id))
        self._event(case_id=case_id, session_id=row["session_id"], record_id=record_id, event_type="browser_evidence_verified", actor=actor, payload={"valid": not problems, "problems": problems})
        return {"record_id": record_id, "valid": not problems, "problems": problems, "capture129": capture_check}

    def verify_chain(self, case_id: str) -> dict[str, Any]:
        rows = self.db.all("SELECT * FROM capture_events_150 WHERE case_id=? ORDER BY sequence", (case_id,))
        previous = ""; problems: list[str] = []
        for row in rows:
            payload = _loads(row["payload_json"], {})
            expected = _sha({"event_id": row["event_id"], "case_id": row.get("case_id") or "", "session_id": row["session_id"], "record_id": row["record_id"], "event_type": row["event_type"], "actor": row["actor"], "payload": payload, "previous_hash": previous, "created_at": row["created_at"]})
            if row["previous_hash"] != previous:
                problems.append(f"previous_hash:{row['event_id']}")
            if not secrets.compare_digest(expected, row["event_hash"]):
                problems.append(f"event_hash:{row['event_id']}")
            previous = row["event_hash"]
        return {"valid": not problems, "events": len(rows), "problems": problems, "head": previous}

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        if case_id:
            self._case(case_id)
        where = "WHERE case_id=?" if case_id else ""
        params = (case_id,) if case_id else ()
        policies = self.db.all(f"SELECT * FROM capture_policies_150 {where} ORDER BY updated_at DESC", params)
        for row in policies:
            row["allowed_hosts"] = _loads(row.pop("allowed_hosts_json", "[]"), [])
            row["excluded_hosts"] = _loads(row.pop("excluded_hosts_json", "[]"), [])
        sessions = self.db.all(f"SELECT * FROM capture_sessions_150 {where} ORDER BY updated_at DESC", params)
        records = self.db.all(f"SELECT * FROM browser_capture_records_150 {where} ORDER BY captured_at DESC LIMIT 200", params)
        diffs = self.db.all(f"SELECT * FROM capture_diffs_150 {where} ORDER BY created_at DESC LIMIT 100", params)
        chain = self.verify_chain(case_id) if case_id else {"valid": True, "events": 0, "problems": []}
        return {
            "build": self.BUILD,
            "case_id": case_id,
            "policies": policies,
            "sessions": sessions,
            "records": records,
            "diffs": diffs,
            "chain": chain,
            "active_session": next((row for row in sessions if row["status"] == "active"), None),
            "security_contract": {
                "automatic_capture_requires_explicit_policy": True,
                "automatic_capture_requires_exact_hosts": True,
                "private_or_local_urls_allowed": False,
                "automatic_truth_promotion": False,
                "automatic_identity_assertions": 0,
                "full_network_warc_claimed": False,
                "proxy_environment_inherited": False,
            },
        }
