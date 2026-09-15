from __future__ import annotations

import base64
import binascii
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_text(value: str) -> str:
    return _sha(str(value or "").encode("utf-8", errors="replace"))


def _safe_name(value: str, fallback: str = "artifact.bin") -> str:
    name = Path(str(value or "")).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")[:120]
    return name or fallback


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("ß", "ss")
    text = re.sub(r"[^\w@.+-]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _loads(value: Any, default: Any) -> Any:
    if not value:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


class CaptureIdentityError(ValueError):
    pass


class CaptureIdentityConflict(CaptureIdentityError):
    pass


class CaptureIdentity129Service:
    """Evidence Capture 2.0 and precision-first identity hypothesis layer.

    The service is deliberately review-first. Captures become candidate-only evidence,
    identity recommendations never merge records, and AI output remains suggestions_only.
    """

    BUILD = "129.0"
    MAX_TEXT_BYTES = 2 * 1024 * 1024
    MAX_HTML_BYTES = 6 * 1024 * 1024
    MAX_SCREENSHOT_BYTES = 10 * 1024 * 1024
    MAX_ATTACHMENT_BYTES = 12 * 1024 * 1024
    MAX_TOTAL_BYTES = 24 * 1024 * 1024
    TICKET_TTL_MIN = 60
    TICKET_TTL_MAX = 1800
    REVIEW_DECISIONS = {"same_person", "distinct_person", "needs_more_evidence", "deferred", "rejected"}

    INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("ignore_instructions", re.compile(r"\b(ignore|disregard|forget)\b.{0,50}\b(instruction|prompt|policy)", re.I | re.S)),
        ("secret_exfiltration", re.compile(r"\b(api[-_ ]?key|access token|system prompt|password|secret)\b", re.I)),
        ("tool_execution", re.compile(r"\b(run|execute|launch)\b.{0,40}\b(shell|powershell|cmd|tool|browser)\b", re.I | re.S)),
        ("security_bypass", re.compile(r"\b(bypass|disable|override)\b.{0,40}\b(security|review|approval|safety)\b", re.I | re.S)),
    )

    def __init__(
        self,
        db: Any,
        audit: Any,
        base_dir: str | Path,
        *,
        evidence: Any,
        entities: Any,
        research_strategy: Any,
        protection: Any,
    ) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir)
        self.bundle_root = self.base_dir / "data" / "evidence_capture_129"
        self.bundle_root.mkdir(parents=True, exist_ok=True)
        self.evidence = evidence
        self.entities = entities
        self.research_strategy = research_strategy
        self.protection = protection

    # ---------- common guards ----------
    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (str(case_id),))
        if not row:
            raise CaptureIdentityError("Fall nicht gefunden")
        return row

    def _target(self, case_id: str, target_id: str) -> dict[str, Any] | None:
        if not target_id:
            return None
        row = self.db.one("SELECT * FROM targets WHERE target_id=? AND case_id=?", (target_id, case_id))
        if not row:
            raise CaptureIdentityError("Zielperson gehört nicht zu diesem Fall")
        return row

    @staticmethod
    def _canonical_public_url(value: str) -> tuple[str, str]:
        raw = str(value or "").strip()
        if len(raw) > 4096:
            raise CaptureIdentityError("URL ist zu lang")
        parts = urlsplit(raw)
        if parts.scheme.casefold() != "https" or not parts.hostname:
            raise CaptureIdentityError("Evidence Capture akzeptiert ausschließlich öffentliche HTTPS-URLs")
        host = parts.hostname.casefold().rstrip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            raise CaptureIdentityError("Lokale Ziele sind für Evidence Capture gesperrt")
        try:
            address = ipaddress.ip_address(host.strip("[]"))
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise CaptureIdentityError("Private oder lokale IP-Ziele sind gesperrt")
        port = parts.port
        netloc = host if port in {None, 443} else f"{host}:{port}"
        path = parts.path or "/"
        canonical = urlunsplit(("https", netloc, path, parts.query, ""))
        return canonical, host

    def _opsec(
        self,
        *,
        case_id: str,
        target_id: str = "",
        action_type: str,
        object_type: str,
        object_id: str = "",
        public_host: str = "",
        fingerprint: str = "",
        minimization: dict[str, Any] | None = None,
        outcome: str,
        actor: str,
    ) -> None:
        self.db.execute(
            """INSERT INTO opsec_events_129(event_id,case_id,target_id,action_type,object_type,object_id,public_host,value_fingerprint,data_minimization_json,outcome,actor,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (_id("op129"), case_id, target_id, action_type, object_type, object_id, public_host,
             fingerprint, _json(minimization or {}), outcome, actor, _now()),
        )

    # ---------- browser companion pairing ----------
    def issue_capture_ticket(
        self,
        *,
        case_id: str,
        target_id: str = "",
        purpose: str,
        actor: str,
        ttl_seconds: int = 600,
    ) -> dict[str, Any]:
        self._case(case_id)
        self._target(case_id, target_id)
        purpose = str(purpose or "").strip()
        if len(purpose) < 8:
            raise CaptureIdentityError("Ein nachvollziehbarer Capture-Zweck ist erforderlich")
        ttl = max(self.TICKET_TTL_MIN, min(self.TICKET_TTL_MAX, int(ttl_seconds)))
        token = secrets.token_urlsafe(32)
        ticket_id = _id("ctkt129")
        issued = _now_dt()
        expires = issued + timedelta(seconds=ttl)
        with self.db.transaction(immediate=True):
            self.db.execute(
                """UPDATE capture_tickets_129 SET state='expired'
                   WHERE case_id=? AND state='issued' AND expires_at<?""",
                (case_id, issued.isoformat(timespec="seconds")),
            )
            self.db.execute(
                """INSERT INTO capture_tickets_129(ticket_id,ticket_hash,case_id,target_id,purpose,state,issued_by,issued_at,expires_at)
                   VALUES(?,?,?,?,?,'issued',?,?,?)""",
                (ticket_id, _sha_text(token), case_id, target_id, purpose[:1000], actor,
                 issued.isoformat(timespec="seconds"), expires.isoformat(timespec="seconds")),
            )
            self._opsec(
                case_id=case_id, target_id=target_id, action_type="issue_companion_ticket",
                object_type="capture_ticket", object_id=ticket_id, fingerprint=_sha_text(token),
                minimization={"one_time": True, "ttl_seconds": ttl, "raw_ticket_logged": False},
                outcome="issued", actor=actor,
            )
            self.audit.log("issue_capture_ticket", "capture_ticket_129", ticket_id, case_id, {"target_id": target_id, "ttl_seconds": ttl})
        return {"ticket_id": ticket_id, "ticket": token, "expires_at": expires.isoformat(timespec="seconds"), "one_time": True}

    def _reserve_ticket(self, token: str, origin: str) -> dict[str, Any]:
        digest = _sha_text(token)
        now = _now()
        with self.db.transaction(immediate=True):
            row = self.db.one("SELECT * FROM capture_tickets_129 WHERE ticket_hash=?", (digest,))
            if not row:
                raise CaptureIdentityError("Capture-Ticket ist ungültig")
            if row["state"] != "issued":
                raise CaptureIdentityConflict("Capture-Ticket wurde bereits verwendet oder widerrufen")
            if row["expires_at"] < now:
                self.db.execute("UPDATE capture_tickets_129 SET state='expired' WHERE ticket_id=?", (row["ticket_id"],))
                raise CaptureIdentityConflict("Capture-Ticket ist abgelaufen")
            cur = self.db.execute(
                """UPDATE capture_tickets_129 SET state='reserved',client_origin_hash=?
                   WHERE ticket_id=? AND state='issued'""",
                (_sha_text(origin) if origin else "", row["ticket_id"]),
            )
            if cur.rowcount != 1:
                raise CaptureIdentityConflict("Capture-Ticket konnte nicht atomar reserviert werden")
            return row

    def _finish_ticket(self, ticket_id: str, *, used: bool) -> None:
        self.db.execute(
            "UPDATE capture_tickets_129 SET state=?,used_at=? WHERE ticket_id=? AND state='reserved'",
            ("used" if used else "issued", _now() if used else "", ticket_id),
        )

    # ---------- artifact capture ----------
    @staticmethod
    def _decode_data(value: Any, *, max_bytes: int, label: str) -> bytes:
        if value in {None, ""}:
            return b""
        if isinstance(value, bytes):
            data = value
        else:
            raw = str(value)
            if raw.startswith("data:") and "," in raw:
                raw = raw.split(",", 1)[1]
            try:
                data = base64.b64decode(raw, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise CaptureIdentityError(f"{label} enthält kein gültiges Base64") from exc
        if len(data) > max_bytes:
            raise CaptureIdentityError(f"{label} überschreitet das Größenlimit")
        return data

    @classmethod
    def _scan_injection(cls, *texts: str) -> list[str]:
        sample = "\n".join(str(text or "")[:400000] for text in texts)
        return sorted({key for key, pattern in cls.INJECTION_PATTERNS if pattern.search(sample)})

    def _artifact_write(self, bundle: Path, filename: str, data: bytes) -> Path:
        path = bundle / _safe_name(filename)
        if path.parent != bundle:
            raise CaptureIdentityError("Ungültiger Artifact-Pfad")
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(data)
        os.replace(temp, path)
        return path

    def capture_from_companion(self, *, ticket: str, payload: dict[str, Any], origin: str = "") -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise CaptureIdentityError("Capture-Payload muss ein JSON-Objekt sein")
        ticket_row = self._reserve_ticket(str(ticket or ""), origin)
        case_id = ticket_row["case_id"]
        target_id = ticket_row.get("target_id") or ""
        actor = ticket_row["issued_by"]
        capture_id = _id("cap129")
        bundle = self.bundle_root / re.sub(r"[^A-Za-z0-9_-]", "_", case_id) / capture_id
        evidence_package: dict[str, Any] | None = None
        try:
            canonical_url, host = self._canonical_public_url(str(payload.get("url") or ""))
            title = str(payload.get("title") or host).strip()[:500]
            visible_text = str(payload.get("visible_text") or "")
            html_text = str(payload.get("html") or "")
            if not visible_text.strip() and not html_text.strip():
                raise CaptureIdentityError("Capture benötigt sichtbaren Text oder HTML")
            visible_bytes = visible_text.encode("utf-8", errors="replace")
            html_bytes = html_text.encode("utf-8", errors="replace")
            if len(visible_bytes) > self.MAX_TEXT_BYTES or len(html_bytes) > self.MAX_HTML_BYTES:
                raise CaptureIdentityError("Text oder HTML überschreitet das Capture-Limit")
            screenshot = self._decode_data(payload.get("screenshot_base64"), max_bytes=self.MAX_SCREENSHOT_BYTES, label="Screenshot")
            raw_attachments = payload.get("attachments") or []
            if not isinstance(raw_attachments, list) or len(raw_attachments) > 20:
                raise CaptureIdentityError("Zu viele Anhänge")
            attachments: list[tuple[str, str, bytes]] = []
            attachment_total = 0
            for item in raw_attachments:
                if not isinstance(item, dict):
                    raise CaptureIdentityError("Ungültiger Anhang")
                data = self._decode_data(item.get("data_base64"), max_bytes=self.MAX_ATTACHMENT_BYTES, label="Anhang")
                attachment_total += len(data)
                if attachment_total > self.MAX_ATTACHMENT_BYTES:
                    raise CaptureIdentityError("Gesamtgröße der Anhänge überschreitet das Limit")
                if data:
                    attachments.append((_safe_name(item.get("filename"), "attachment.bin"), str(item.get("media_type") or "application/octet-stream")[:120], data))
            total_size = len(visible_bytes) + len(html_bytes) + len(screenshot) + attachment_total
            if total_size <= 0 or total_size > self.MAX_TOTAL_BYTES:
                raise CaptureIdentityError("Gesamtgröße des Captures ist unzulässig")

            injection_flags = self._scan_injection(visible_text, html_text)
            previous = self.db.one(
                "SELECT * FROM browser_captures_129 WHERE case_id=? AND canonical_url=? ORDER BY captured_at DESC LIMIT 1",
                (case_id, canonical_url),
            )
            visible_hash = _sha(visible_bytes)
            html_hash = _sha(html_bytes) if html_bytes else ""
            screenshot_hash = _sha(screenshot) if screenshot else ""
            previous_id = previous["capture_id"] if previous else ""
            changed_artifacts: list[str] = []
            if not previous:
                change_state = "first_capture"
            else:
                for field, kind, value in (
                    ("visible_text_sha256", "visible_text", visible_hash),
                    ("html_sha256", "html", html_hash),
                    ("screenshot_sha256", "screenshot", screenshot_hash),
                ):
                    if str(previous.get(field) or "") != value:
                        changed_artifacts.append(kind)
                change_state = "changed" if changed_artifacts else "unchanged"

            bundle.mkdir(parents=True, exist_ok=False)
            artifact_records: list[dict[str, Any]] = []

            def add_artifact(kind: str, filename: str, media_type: str, data: bytes) -> None:
                if not data:
                    return
                path = self._artifact_write(bundle, filename, data)
                artifact_records.append({
                    "artifact_id": _id("art129"), "kind": kind, "filename": path.name,
                    "media_type": media_type, "relpath": str(path.relative_to(self.base_dir)).replace("\\", "/"),
                    "sha256": _sha(data), "byte_size": len(data),
                })

            add_artifact("visible_text", "visible_text.txt", "text/plain; charset=utf-8", visible_bytes)
            add_artifact("html", "page.html", "text/html; charset=utf-8", html_bytes)
            add_artifact("screenshot", "screenshot.png", "image/png", screenshot)
            for index, (name, media_type, data) in enumerate(attachments, 1):
                add_artifact("attachment", f"{index:02d}_{name}", media_type, data)

            manifest = {
                "schema": "eagleeye.capture.129.0",
                "capture_id": capture_id,
                "case_id": case_id,
                "target_id": target_id,
                "source_url": canonical_url,
                "title": title,
                "captured_at": _now(),
                "captured_by": actor,
                "capture_mode": "firefox_companion_136",
                "artifacts": artifact_records,
                "change": {"state": change_state, "previous_capture_id": previous_id, "changed_artifacts": changed_artifacts},
                "security": {"untrusted_content": True, "injection_flags": injection_flags, "automatic_truth_promotion": False},
            }
            manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
            manifest_path = self._artifact_write(bundle, "manifest.json", manifest_bytes)
            manifest_hash = _sha(manifest_bytes)
            bundle_relpath = str(bundle.relative_to(self.base_dir)).replace("\\", "/")

            metadata = {
                "capture_id": capture_id,
                "target_id": target_id,
                "source_host": host,
                "artifact_hashes": {item["kind"] + ":" + item["filename"]: item["sha256"] for item in artifact_records},
                "manifest_sha256": manifest_hash,
                "change_state": change_state,
                "previous_capture_id": previous_id,
                "injection_flags": injection_flags,
                "untrusted_content": True,
                "automatic_truth_promotion": False,
            }

            with self.db.transaction(immediate=True):
                evidence_package = self.evidence.preserve_bytes(
                    case_id=case_id,
                    title=f"Browser Capture: {title}",
                    data=manifest_bytes,
                    media_type="application/json",
                    captured_by=actor,
                    source_url=canonical_url,
                    source_kind="browser_capture_129",
                    source_ref=capture_id,
                    metadata=metadata,
                    notes="Candidate-only browser capture. Artifact bundle is referenced by the manifest.",
                )
                self.db.execute(
                    """INSERT INTO browser_captures_129(capture_id,case_id,target_id,ticket_id,source_url,canonical_url,source_host,title,capture_mode,status,visible_text_sha256,html_sha256,screenshot_sha256,manifest_sha256,bundle_relpath,evidence_package_id,previous_capture_id,change_state,injection_flags_json,artifact_count,byte_size,captured_by,captured_at,metadata_json)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (capture_id, case_id, target_id, ticket_row["ticket_id"], str(payload.get("url") or "")[:4096], canonical_url,
                     host, title, "firefox_companion_136", "quarantined_untrusted" if injection_flags else "candidate_captured",
                     visible_hash, html_hash, screenshot_hash, manifest_hash, bundle_relpath,
                     evidence_package["package_id"], previous_id, change_state, _json(injection_flags),
                     len(artifact_records) + 1, total_size + len(manifest_bytes), actor, manifest["captured_at"], _json(metadata)),
                )
                for item in artifact_records:
                    self.db.execute(
                        """INSERT INTO capture_artifacts_129(artifact_id,capture_id,case_id,artifact_kind,filename,media_type,relpath,sha256,byte_size,created_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (item["artifact_id"], capture_id, case_id, item["kind"], item["filename"], item["media_type"],
                         item["relpath"], item["sha256"], item["byte_size"], manifest["captured_at"]),
                    )
                self.db.execute(
                    """INSERT INTO capture_artifacts_129(artifact_id,capture_id,case_id,artifact_kind,filename,media_type,relpath,sha256,byte_size,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (_id("art129"), capture_id, case_id, "manifest", manifest_path.name, "application/json",
                     str(manifest_path.relative_to(self.base_dir)).replace("\\", "/"), manifest_hash, len(manifest_bytes), manifest["captured_at"]),
                )
                if previous:
                    self.db.execute(
                        """INSERT INTO capture_changes_129(change_id,case_id,target_id,canonical_url,previous_capture_id,current_capture_id,change_state,changed_artifacts_json,summary_json,review_status,created_at)
                           VALUES(?,?,?,?,?,?,?,?,?,'pending',?)""",
                        (_id("chg129"), case_id, target_id, canonical_url, previous_id, capture_id, change_state,
                         _json(changed_artifacts), _json({"changed_count": len(changed_artifacts), "content_changed": bool(changed_artifacts)}), manifest["captured_at"]),
                    )
                brief_id = self._capture_ai_brief(
                    case_id=case_id, target_id=target_id, capture_id=capture_id,
                    injection_flags=injection_flags, change_state=change_state,
                    changed_artifacts=changed_artifacts, actor=actor,
                )
                self._opsec(
                    case_id=case_id, target_id=target_id, action_type="capture_companion_submit",
                    object_type="browser_capture", object_id=capture_id, public_host=host,
                    fingerprint=_sha_text(canonical_url),
                    minimization={"ticket_one_time": True, "url_in_audit": False, "content_in_audit": False, "artifact_count": len(artifact_records) + 1},
                    outcome="quarantined" if injection_flags else "candidate_captured", actor=actor,
                )
                self.audit.log("browser_capture", "browser_capture_129", capture_id, case_id, {
                    "target_id": target_id, "host": host, "url_fingerprint": _sha_text(canonical_url),
                    "change_state": change_state, "artifact_count": len(artifact_records) + 1,
                    "injection_flag_count": len(injection_flags), "ai_brief_id": brief_id,
                    "candidate_only": True,
                })
                self._finish_ticket(ticket_row["ticket_id"], used=True)
            return self.get_capture(case_id, capture_id)
        except BaseException:
            try:
                self._finish_ticket(ticket_row["ticket_id"], used=False)
            except Exception:
                pass
            if bundle.exists():
                shutil.rmtree(bundle, ignore_errors=True)
            if evidence_package:
                try:
                    self.evidence.discard_uncommitted_package(evidence_package)
                except Exception:
                    pass
            raise

    def _capture_ai_brief(
        self,
        *,
        case_id: str,
        target_id: str,
        capture_id: str,
        injection_flags: list[str],
        change_state: str,
        changed_artifacts: list[str],
        actor: str,
    ) -> str:
        suggestion_id = _id("ais129")
        warnings = []
        if injection_flags:
            warnings.append("External content contains instruction-like or secret-seeking patterns and remains quarantined.")
        if change_state == "changed":
            warnings.append("The page differs from the previous capture; review the changed artifacts before relying on it.")
        if change_state == "first_capture":
            warnings.append("No previous capture is available for change comparison.")
        content = {
            "summary": "Browser capture preserved as candidate-only evidence.",
            "change_state": change_state,
            "changed_artifacts": changed_artifacts,
            "injection_flags": injection_flags,
            "warnings": warnings,
            "next_checks": [
                "Verify author, publication date and original source.",
                "Seek an independent source before confirming the claim.",
                "Review identity anchors separately from page assertions.",
            ],
            "automatic_promotion": False,
        }
        self.db.execute(
            """INSERT INTO identity_ai_suggestions_129(suggestion_id,capture_id,case_id,target_id,suggestion_type,content_json,source_refs_json,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (suggestion_id, capture_id, case_id, target_id, "capture_triage", _json(content),
             _json([{"object_type": "browser_capture_129", "object_id": capture_id}]), _now()),
        )
        return suggestion_id

    def get_capture(self, case_id: str, capture_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM browser_captures_129 WHERE case_id=? AND capture_id=?", (case_id, capture_id))
        if not row:
            raise CaptureIdentityError("Capture nicht gefunden")
        row["injection_flags"] = _loads(row.pop("injection_flags_json", "[]"), [])
        row["metadata"] = _loads(row.pop("metadata_json", "{}"), {})
        row["artifacts"] = self.db.all("SELECT * FROM capture_artifacts_129 WHERE capture_id=? ORDER BY artifact_kind,filename", (capture_id,))
        row["changes"] = self.db.all("SELECT * FROM capture_changes_129 WHERE current_capture_id=? ORDER BY created_at DESC", (capture_id,))
        return row

    def list_captures(self, case_id: str, target_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        self._case(case_id)
        limit = max(1, min(500, int(limit)))
        if target_id:
            self._target(case_id, target_id)
            return self.db.all("SELECT * FROM browser_captures_129 WHERE case_id=? AND target_id=? ORDER BY captured_at DESC LIMIT ?", (case_id, target_id, limit))
        return self.db.all("SELECT * FROM browser_captures_129 WHERE case_id=? ORDER BY captured_at DESC LIMIT ?", (case_id, limit))

    def verify_capture(self, case_id: str, capture_id: str) -> dict[str, Any]:
        capture = self.get_capture(case_id, capture_id)
        problems: list[str] = []
        for artifact in capture["artifacts"]:
            path = (self.base_dir / artifact["relpath"]).resolve()
            try:
                path.relative_to(self.base_dir.resolve())
            except ValueError:
                problems.append(f"unsafe_path:{artifact['artifact_id']}")
                continue
            if not path.is_file():
                problems.append(f"missing:{artifact['artifact_kind']}")
                continue
            if _sha(path.read_bytes()) != artifact["sha256"]:
                problems.append(f"hash_mismatch:{artifact['artifact_kind']}")
        evidence_check = self.evidence.verify_package(capture["evidence_package_id"])
        if not evidence_check.get("ok", evidence_check.get("valid", False)):
            problems.append("evidence_package_invalid")
        return {"capture_id": capture_id, "valid": not problems, "problems": problems, "evidence": evidence_check}

    # ---------- identity resolution pro ----------
    def _entity(self, case_id: str, entity_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM resolution_entities_115 WHERE case_id=? AND resolution_entity_id=?", (case_id, entity_id))
        if not row:
            raise CaptureIdentityError("Resolution-Entität nicht gefunden oder fallfremd")
        row["attributes"] = _loads(row.get("attributes_json"), {})
        return row

    def _aliases(self, entity_id: str) -> list[str]:
        rows = self.db.all("SELECT normalized_alias FROM resolution_aliases_115 WHERE resolution_entity_id=?", (entity_id,))
        return [str(row["normalized_alias"]) for row in rows]

    def _anchors(self, entity_id: str) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM resolution_anchors_115 WHERE resolution_entity_id=?", (entity_id,))

    @staticmethod
    def _set_values(anchors: Iterable[dict[str, Any]], kind: str) -> set[str]:
        return {str(row.get("normalized_value") or "") for row in anchors if row.get("anchor_type") == kind and row.get("normalized_value")}

    def _source_independence(self, case_id: str, entity: dict[str, Any]) -> tuple[int, list[str]]:
        target_id = str(entity.get("source_entity_id") or "")
        if not target_id:
            return 0, []
        rows = self.db.all(
            "SELECT DISTINCT source_host FROM source_records_128 WHERE case_id=? AND target_id=? AND source_host<>''",
            (case_id, target_id),
        )
        hosts = sorted({str(row["source_host"]) for row in rows})
        return len(hosts), hosts[:20]

    @staticmethod
    def _similarity(left: Iterable[str], right: Iterable[str]) -> float:
        values = [SequenceMatcher(None, a, b).ratio() for a in left for b in right if a and b]
        return max(values, default=0.0)

    def create_identity_hypothesis(
        self,
        *,
        case_id: str,
        left_entity_id: str,
        right_entity_id: str,
        actor: str,
    ) -> dict[str, Any]:
        if left_entity_id == right_entity_id:
            raise CaptureIdentityError("Eine Entität kann nicht mit sich selbst verglichen werden")
        left = self._entity(case_id, left_entity_id)
        right = self._entity(case_id, right_entity_id)
        if left["entity_type"] != right["entity_type"]:
            raise CaptureIdentityError("Nur gleiche Entitätstypen können als Identitätshypothese verglichen werden")
        a_id, b_id = sorted((left_entity_id, right_entity_id))
        left, right = self._entity(case_id, a_id), self._entity(case_id, b_id)
        base = self.entities.compare(a_id, b_id, actor)
        la, ra = self._anchors(a_id), self._anchors(b_id)
        left_aliases, right_aliases = self._aliases(a_id), self._aliases(b_id)

        components: list[dict[str, Any]] = []

        def component(kind: str, direction: str, weight: float, value: float, rationale: str, refs: list[dict[str, str]] | None = None) -> None:
            components.append({"type": kind, "direction": direction, "weight": weight, "value": max(0.0, min(1.0, value)), "rationale": rationale, "refs": refs or []})

        name_similarity = SequenceMatcher(None, str(left["normalized_name"]), str(right["normalized_name"])).ratio()
        component("name_similarity", "support" if name_similarity >= .75 else "neutral", .20, name_similarity, "Normalized names are compared; name similarity alone is never identity proof.")
        alias_similarity = self._similarity(left_aliases, right_aliases)
        component("alias_similarity", "support" if alias_similarity >= .80 else "neutral", .12, alias_similarity, "Best overlap across registered aliases.")

        strong_match = 0
        strong_conflict = 0
        for kind in ("email", "phone", "external_id"):
            lset, rset = self._set_values(la, kind), self._set_values(ra, kind)
            overlap = lset & rset
            if overlap:
                strong_match += 1
                component(f"{kind}_match", "support", .35, 1.0, f"Matching reviewed {kind} anchor.")
            elif lset and rset:
                strong_conflict += 1
                component(f"{kind}_conflict", "conflict", .55, 1.0, f"Conflicting reviewed {kind} anchors.")

        for kind, weight in (("birth_year", .45), ("location", .16), ("organisation", .18), ("domain", .22), ("username", .22)):
            lset, rset = self._set_values(la, kind), self._set_values(ra, kind)
            overlap = lset & rset
            if overlap:
                component(f"{kind}_overlap", "support", weight, 1.0, f"Shared reviewed {kind} anchor.")
            elif lset and rset and kind == "birth_year":
                strong_conflict += 1
                component("birth_year_conflict", "conflict", weight, 1.0, "Conflicting birth-year anchors require distinction review.")
            elif lset and rset:
                component(f"{kind}_difference", "neutral", weight / 2, .5, f"Different {kind} anchors may reflect change over time; review required.")

        left_sources, left_hosts = self._source_independence(case_id, left)
        right_sources, right_hosts = self._source_independence(case_id, right)
        independent_hosts = sorted(set(left_hosts) | set(right_hosts))
        independent_count = len(independent_hosts)
        component("source_independence", "support" if independent_count >= 2 else "neutral", .12, min(1.0, independent_count / 3), "Distinct source hosts supporting the compared records.", [{"host": host} for host in independent_hosts])

        old_conflicts = list(base.get("conflicts") or [])
        conflict_count = strong_conflict + len(old_conflicts)
        support_count = sum(1 for row in components if row["direction"] == "support" and row["value"] >= .75)
        if conflict_count:
            recommendation = "likely_distinct_candidate"
        elif strong_match >= 1 and name_similarity >= .80 and independent_count >= 2:
            recommendation = "strong_same_person_candidate"
        elif (strong_match >= 1 or support_count >= 3) and name_similarity >= .65:
            recommendation = "possible_same_person_review"
        else:
            recommendation = "insufficient_evidence"

        explanation = {
            "recommendation": recommendation,
            "precision_policy": "false_merge_averse",
            "automatic_merge": False,
            "name_similarity": round(name_similarity, 4),
            "alias_similarity": round(alias_similarity, 4),
            "strong_anchor_matches": strong_match,
            "conflicts": conflict_count,
            "independent_source_count": independent_count,
            "warning": "This is a review recommendation, not an identity confirmation.",
        }
        hypothesis_id = _id("hyp129")
        existing = self.db.one(
            "SELECT hypothesis_id FROM identity_hypotheses_129 WHERE case_id=? AND left_entity_id=? AND right_entity_id=?",
            (case_id, a_id, b_id),
        )
        if existing:
            hypothesis_id = existing["hypothesis_id"]
        with self.db.transaction(immediate=True):
            if existing:
                self.db.execute("DELETE FROM identity_components_129 WHERE hypothesis_id=?", (hypothesis_id,))
                self.db.execute(
                    """UPDATE identity_hypotheses_129 SET base_comparison_id=?,state='candidate',recommendation=?,positive_component_count=?,conflict_component_count=?,independent_source_count=?,explanation_json=?,ai_brief_id='',created_by=?,created_at=?,reviewed_by='',reviewed_at='',review_decision='',review_reason=''
                       WHERE hypothesis_id=?""",
                    (base["comparison_id"], recommendation, support_count, conflict_count, independent_count, _json(explanation), actor, _now(), hypothesis_id),
                )
            else:
                self.db.execute(
                    """INSERT INTO identity_hypotheses_129(hypothesis_id,case_id,left_entity_id,right_entity_id,base_comparison_id,state,recommendation,positive_component_count,conflict_component_count,independent_source_count,explanation_json,created_by,created_at)
                       VALUES(?,?,?,?,?,'candidate',?,?,?,?,?,?,?)""",
                    (hypothesis_id, case_id, a_id, b_id, base["comparison_id"], recommendation, support_count, conflict_count, independent_count, _json(explanation), actor, _now()),
                )
            for row in components:
                self.db.execute(
                    """INSERT INTO identity_components_129(component_id,hypothesis_id,case_id,component_type,direction,weight,value,rationale,source_refs_json,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (_id("cmp129"), hypothesis_id, case_id, row["type"], row["direction"], row["weight"], row["value"], row["rationale"], _json(row["refs"]), _now()),
                )
            brief_id = self._identity_ai_brief(case_id, hypothesis_id, recommendation, components, actor)
            self.db.execute("UPDATE identity_hypotheses_129 SET ai_brief_id=? WHERE hypothesis_id=?", (brief_id, hypothesis_id))
            self.audit.log("create_identity_hypothesis", "identity_hypothesis_129", hypothesis_id, case_id, {
                "recommendation": recommendation, "support_components": support_count,
                "conflict_components": conflict_count, "independent_sources": independent_count,
                "automatic_merge": False,
            })
        return self.get_identity_hypothesis(case_id, hypothesis_id)

    def _identity_ai_brief(self, case_id: str, hypothesis_id: str, recommendation: str, components: list[dict[str, Any]], actor: str) -> str:
        conflicts = [row["type"] for row in components if row["direction"] == "conflict"]
        supports = [row["type"] for row in components if row["direction"] == "support"]
        suggestion_id = _id("ais129")
        content = {
            "recommendation": recommendation,
            "supporting_components": supports,
            "conflicting_components": conflicts,
            "required_counter_checks": [
                "Search for a conflicting birth date, location or employment timeline.",
                "Confirm whether matching sources are independent or copied.",
                "Prefer a reviewed strong anchor over name similarity.",
                "Do not merge records automatically.",
            ],
            "human_decision_required": True,
            "automatic_merge": False,
        }
        self.db.execute(
            """INSERT INTO identity_ai_suggestions_129(suggestion_id,hypothesis_id,case_id,suggestion_type,content_json,source_refs_json,created_at)
               VALUES(?,?,?,'identity_verification_brief',?,?,?)""",
            (suggestion_id, hypothesis_id, case_id, _json(content), _json([{"object_type": "identity_hypothesis_129", "object_id": hypothesis_id}]), _now()),
        )
        return suggestion_id

    def get_identity_hypothesis(self, case_id: str, hypothesis_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM identity_hypotheses_129 WHERE case_id=? AND hypothesis_id=?", (case_id, hypothesis_id))
        if not row:
            raise CaptureIdentityError("Identitätshypothese nicht gefunden")
        row["explanation"] = _loads(row.pop("explanation_json"), {})
        components = self.db.all("SELECT * FROM identity_components_129 WHERE hypothesis_id=? ORDER BY direction,weight DESC", (hypothesis_id,))
        for item in components:
            item["source_refs"] = _loads(item.pop("source_refs_json"), [])
        row["components"] = components
        row["ai_suggestions"] = self.db.all("SELECT * FROM identity_ai_suggestions_129 WHERE hypothesis_id=? ORDER BY created_at DESC", (hypothesis_id,))
        return row

    def list_identity_hypotheses(self, case_id: str, limit: int = 100) -> list[dict[str, Any]]:
        self._case(case_id)
        return self.db.all("SELECT * FROM identity_hypotheses_129 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, max(1, min(500, int(limit)))))

    def review_identity_hypothesis(
        self,
        *,
        case_id: str,
        hypothesis_id: str,
        decision: str,
        reason: str,
        actor: str,
    ) -> dict[str, Any]:
        if decision not in self.REVIEW_DECISIONS:
            raise CaptureIdentityError("Ungültige Identitätsentscheidung")
        if len(str(reason or "").strip()) < 12:
            raise CaptureIdentityError("Eine substanzielle Reviewbegründung ist erforderlich")
        with self.db.transaction(immediate=True):
            row = self.db.one("SELECT * FROM identity_hypotheses_129 WHERE case_id=? AND hypothesis_id=?", (case_id, hypothesis_id))
            if not row:
                raise CaptureIdentityError("Identitätshypothese nicht gefunden")
            if row["state"] != "candidate":
                raise CaptureIdentityConflict("Identitätshypothese wurde bereits terminal geprüft")
            cur = self.db.execute(
                """UPDATE identity_hypotheses_129 SET state='reviewed',reviewed_by=?,reviewed_at=?,review_decision=?,review_reason=?
                   WHERE hypothesis_id=? AND case_id=? AND state='candidate'""",
                (actor, _now(), decision, reason.strip()[:4000], hypothesis_id, case_id),
            )
            if cur.rowcount != 1:
                raise CaptureIdentityConflict("Parallele Reviewentscheidung wurde blockiert")
            self.audit.log("review_identity_hypothesis", "identity_hypothesis_129", hypothesis_id, case_id, {
                "decision": decision, "reason_length": len(reason.strip()), "destructive_merge": False,
            })
        return self.get_identity_hypothesis(case_id, hypothesis_id)

    # ---------- synthetic precision benchmark ----------
    @staticmethod
    def _benchmark_predict(case: dict[str, Any]) -> bool:
        if case["strong_conflicts"]:
            return False
        return bool(case["strong_matches"] >= 1 and case["name_similarity"] >= .80 and case["independent_sources"] >= 2)

    def run_identity_benchmark(self, *, actor: str) -> dict[str, Any]:
        # Synthetic, non-personal Golden Cases. False merges are deliberately weighted as the critical error.
        suite: list[dict[str, Any]] = []
        for index in range(40):
            same = index < 20
            suite.append({
                "id": f"golden129_{index:03d}",
                "expected_same": same,
                "name_similarity": .92 - (index % 4) * .025 if same else .88 - (index % 5) * .07,
                "strong_matches": 1 if same and index not in {6, 13} else 0,
                "strong_conflicts": 1 if (not same and index % 3 == 0) else 0,
                "independent_sources": 2 if same and index not in {6, 13} else (1 if same else index % 3),
            })
        tp = fp = tn = fn = 0
        details = []
        for item in suite:
            predicted = self._benchmark_predict(item)
            expected = bool(item["expected_same"])
            if predicted and expected:
                tp += 1
            elif predicted and not expected:
                fp += 1
            elif not predicted and not expected:
                tn += 1
            else:
                fn += 1
            details.append({"id": item["id"], "expected_same": expected, "predicted_same": predicted})
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        false_merge_rate = fp / max(1, fp + tn)
        benchmark_id = _id("bench129")
        result = {
            "benchmark_id": benchmark_id,
            "suite_version": "129.0-synthetic-1",
            "case_count": len(suite),
            "true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn,
            "precision": precision, "recall": recall, "false_merge_rate": false_merge_rate,
            "automatic_merge": False,
            "details": details,
        }
        self.db.execute(
            """INSERT INTO identity_benchmark_runs_129(benchmark_id,suite_version,case_count,true_positive,false_positive,true_negative,false_negative,precision,recall,false_merge_rate,result_json,created_by,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (benchmark_id, result["suite_version"], len(suite), tp, fp, tn, fn, precision, recall, false_merge_rate, _json(result), actor, _now()),
        )
        self.audit.log("run_identity_benchmark", "identity_benchmark_129", benchmark_id, None, {
            "case_count": len(suite), "precision": round(precision, 6), "recall": round(recall, 6), "false_merge_rate": round(false_merge_rate, 6),
        })
        return result

    def dashboard(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        captures = self.list_captures(case_id, limit=100)
        hypotheses = self.list_identity_hypotheses(case_id, limit=100)
        changes = self.db.all("SELECT * FROM capture_changes_129 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,))
        suggestions = self.db.all("SELECT * FROM identity_ai_suggestions_129 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,))
        entities = self.db.all("SELECT resolution_entity_id,entity_type,display_name,candidate_only,created_at FROM resolution_entities_115 WHERE case_id=? ORDER BY created_at DESC", (case_id,))
        latest_benchmark = self.db.one("SELECT * FROM identity_benchmark_runs_129 ORDER BY created_at DESC LIMIT 1")
        return {
            "status": {
                "build": self.BUILD,
                "capture_mode": "candidate_only",
                "identity_policy": "false_merge_averse",
                "automatic_merge": False,
                "ai_trust_state": "suggestions_only",
                "companion_network_scope": "loopback_only",
            },
            "metrics": {
                "captures": len(captures),
                "changed_pages": sum(1 for row in captures if row.get("change_state") == "changed"),
                "quarantined_captures": sum(1 for row in captures if row.get("status") == "quarantined_untrusted"),
                "identity_hypotheses": len(hypotheses),
                "pending_identity_reviews": sum(1 for row in hypotheses if row.get("state") == "candidate"),
                "pending_ai_suggestions": sum(1 for row in suggestions if row.get("review_status") == "pending"),
            },
            "captures": captures,
            "changes": changes,
            "hypotheses": hypotheses,
            "suggestions": suggestions,
            "entities": entities,
            "latest_benchmark": latest_benchmark,
        }
