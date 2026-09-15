from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import shutil
import platform
import re
import sys
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts


PHOTO_REVIEW_STATUSES = {"unreviewed", "candidate", "supported", "rejected", "duplicate"}
PHOTO_SOURCE_KINDS = {"local_file", "remote_reference"}
PHOTO_MAX_BYTES = 12 * 1024 * 1024
PHOTO_MAX_WIDTH = 20_000
PHOTO_MAX_HEIGHT = 20_000
PHOTO_MAX_PIXELS = 100_000_000
PHOTO_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
PHOTO_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _safe_text(value: Any, limit: int = 1000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _safe_filename(value: Any) -> str:
    name = Path(str(value or "image")).name
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" ._")[:120]
    return stem or "image"


def _detect_image_mime(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("Nicht unterstütztes oder beschädigtes Bildformat. Erlaubt sind JPEG, PNG, WebP und GIF.")


def _image_dimensions(data: bytes, mime_type: str) -> tuple[int, int]:
    width = height = 0
    if mime_type == "image/png":
        if len(data) < 24:
            raise ValueError("PNG-Header ist unvollständig")
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
    elif mime_type == "image/gif":
        if len(data) < 10:
            raise ValueError("GIF-Header ist unvollständig")
        width = int.from_bytes(data[6:8], "little")
        height = int.from_bytes(data[8:10], "little")
    elif mime_type == "image/jpeg":
        offset = 2
        sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while offset + 3 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            while offset < len(data) and data[offset] == 0xFF:
                offset += 1
            if offset >= len(data):
                break
            marker_byte = data[offset]
            offset += 1
            if marker_byte in {0xD8, 0xD9} or 0xD0 <= marker_byte <= 0xD7:
                continue
            if offset + 2 > len(data):
                break
            segment_length = int.from_bytes(data[offset:offset + 2], "big")
            if segment_length < 2 or offset + segment_length > len(data):
                break
            if marker_byte in sof_markers:
                if segment_length < 7:
                    break
                height = int.from_bytes(data[offset + 3:offset + 5], "big")
                width = int.from_bytes(data[offset + 5:offset + 7], "big")
                break
            offset += segment_length
    elif mime_type == "image/webp":
        if len(data) < 30:
            raise ValueError("WebP-Header ist unvollständig")
        chunk = data[12:16]
        if chunk == b"VP8X":
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
        elif chunk == b"VP8L" and data[20] == 0x2F and len(data) >= 25:
            bits = int.from_bytes(data[21:25], "little")
            width = 1 + (bits & 0x3FFF)
            height = 1 + ((bits >> 14) & 0x3FFF)
        elif chunk == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
            width = int.from_bytes(data[26:28], "little") & 0x3FFF
            height = int.from_bytes(data[28:30], "little") & 0x3FFF
    if width <= 0 or height <= 0:
        raise ValueError("Bildabmessungen konnten nicht sicher bestimmt werden")
    if width > PHOTO_MAX_WIDTH or height > PHOTO_MAX_HEIGHT or width * height > PHOTO_MAX_PIXELS:
        raise ValueError(
            f"Bildabmessungen überschreiten das Sicherheitslimit ({PHOTO_MAX_WIDTH}×{PHOTO_MAX_HEIGHT}, maximal {PHOTO_MAX_PIXELS} Pixel)"
        )
    return width, height


def _validated_https_url(value: Any, *, required: bool = False) -> str:
    raw = _safe_text(value, 3000)
    if not raw:
        if required:
            raise ValueError("HTTPS-Quelladresse fehlt")
        return ""
    parts = urlsplit(raw)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Quelladressen müssen öffentliche HTTPS-URLs ohne eingebettete Zugangsdaten sein")
    secret_keys = {"access_token", "token", "api_key", "apikey", "signature", "sig", "auth", "authorization", "password", "secret"}
    tracking_keys = {"fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid"}
    clean_query: list[tuple[str, str]] = []
    for key, item in parse_qsl(parts.query, keep_blank_values=True):
        normalized = key.casefold().strip()
        if normalized in secret_keys or normalized.endswith("_token") or normalized.endswith("_secret"):
            raise ValueError("Quelladresse enthält möglicherweise Zugangsdaten oder signierte Geheimparameter")
        if normalized.startswith("utm_") or normalized in tracking_keys:
            continue
        clean_query.append((key, item))
    return urlunsplit(("https", parts.netloc, parts.path or "/", urlencode(clean_query, doseq=True), ""))


class Build136Service:
    """Windows/Firefox stabilization and local photo-evidence intake for Build 136.

    The service deliberately delegates actual research routing to Build 135's
    fail-closed router. It adds deterministic diagnostics, explicit recovery
    actions and immutable local image capture without introducing browser-profile
    ambiguity or autonomous network downloads.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        base_dir: str | Path,
        install_dir: str | Path,
        *,
        build135: Any,
        protection: Any,
        clock: Any | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.install_dir = Path(install_dir).resolve()
        self.build135 = build135
        self.protection = protection
        self.clock = clock or time.time
        self.photo_root = self.base_dir / "data" / "photo_evidence_136"
        self.photo_root.mkdir(parents=True, exist_ok=True)
        try:
            self.photo_root.chmod(0o700)
        except OSError:
            pass
        self._cleanup_staged_photo_deletions()

    def _cleanup_staged_photo_deletions(self) -> None:
        """Retry only explicit deletion tombstones created by the privacy engine."""
        removed = 0
        failed: list[str] = []
        for candidate in self.photo_root.glob(".deleting_build136_*"):
            try:
                resolved = candidate.resolve()
                if resolved.parent != self.photo_root.resolve():
                    failed.append(candidate.name)
                    continue
                if candidate.is_symlink():
                    candidate.unlink()
                elif candidate.is_dir():
                    shutil.rmtree(candidate)
                else:
                    candidate.unlink()
                removed += 1
            except OSError:
                failed.append(candidate.name)
        if removed or failed:
            self.audit.log(
                "cleanup",
                "photo_deletion_tombstones_136",
                "startup",
                None,
                {"removed": removed, "failed": failed},
            )

    # ---------- common validation ----------
    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT case_id,title,status FROM cases WHERE case_id=?", (case_id,))
        if not row:
            raise KeyError("Fall nicht gefunden")
        return row

    def _target(self, case_id: str, target_id: str) -> dict[str, Any] | None:
        if not target_id:
            return None
        row = self.db.one("SELECT target_id,case_id,name FROM targets WHERE target_id=?", (target_id,))
        if not row or row["case_id"] != case_id:
            raise ValueError("Zielperson gehört nicht zu diesem Fall")
        return row

    def _event(self, *, case_id: str, event_type: str, actor: str, before: str = "", after: str = "", details: Mapping[str, Any] | None = None) -> str:
        event_id = new_id("ffevt136")
        self.db.execute(
            "INSERT INTO firefox_session_events_136(event_id,case_id,event_type,state_before,state_after,details_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (event_id, case_id, event_type, before, after, dumps(dict(details or {})), actor, now_ts()),
        )
        self.audit.log(event_type, "firefox_session_136", event_id, case_id, dict(details or {}))
        return event_id

    # ---------- Firefox stabilization ----------
    def browser_diagnostics(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        firefox = self.protection._find_firefox()
        status135 = self.build135.browser_status(case_id)
        session = status135.get("session") or {}
        orders = status135.get("orders") or []
        now = float(self.clock())
        heartbeat = float(session.get("last_heartbeat_epoch") or 0)
        heartbeat_age = max(0.0, now - heartbeat) if heartbeat else None
        active = bool(status135.get("companion_active"))
        pending_row = self.db.one(
            "SELECT COUNT(*) AS c FROM firefox_tab_orders_135 WHERE case_id=? AND status IN ('queued','delivered')",
            (case_id,),
        ) or {}
        failed_row = self.db.one(
            "SELECT COUNT(*) AS c FROM firefox_tab_orders_135 WHERE case_id=? AND status='failed'",
            (case_id,),
        ) or {}
        launch_row = self.db.one(
            "SELECT COUNT(*) AS c FROM firefox_tab_orders_135 WHERE case_id=? "
            "AND dispatch_mode='existing_firefox_tabs' AND status IN ('opened','acknowledged','fallback_dispatched')",
            (case_id,),
        ) or {}
        legacy_launch_row = self.db.one(
            "SELECT COUNT(*) AS c FROM firefox_tab_orders_135 WHERE case_id=? "
            "AND dispatch_mode IN ('isolated_case_start','isolated_case_recovery')",
            (case_id,),
        ) or {}
        pending = int(pending_row.get("c") or 0)
        failed = int(failed_row.get("c") or 0)
        direct_launches = int(launch_row.get("c") or 0)
        legacy_isolated_launches = int(legacy_launch_row.get("c") or 0)
        registered = bool(session.get("companion_token_hash"))
        companion_status = str(session.get("companion_status") or "unknown")
        companion_files = [
            self.install_dir / "tools" / "firefox_companion_136" / "manifest.json",
            self.install_dir / "tools" / "firefox_companion_136" / "background.js",
            self.install_dir / "tools" / "firefox_companion_136" / "bootstrap.js",
        ]
        companion_package_ok = all(path.exists() and path.stat().st_size > 0 for path in companion_files)

        if firefox is None:
            state = "firefox_missing"
            severity = "blocked"
            summary = "Firefox wurde nicht gefunden; geschützte Recherche bleibt gesperrt."
            actions = ["Firefox installieren oder den Installationspfad prüfen."]
        elif companion_status == "launch_failed" or failed:
            state = "launch_failed"
            severity = "blocked"
            summary = "Der letzte Firefox-Tabstart ist fehlgeschlagen."
            actions = ["Runtime-Diagnose ausführen und fehlgeschlagene Aufträge bereinigen."]
        elif pending and active:
            state = "healthy_pending"
            severity = "ready"
            summary = "Ein optionaler Legacy-Companion verarbeitet noch Tab-Aufträge."
            actions = ["Einige Sekunden warten; bei Stillstand den Companion-Status prüfen."]
        elif direct_launches:
            state = "healthy"
            severity = "ready"
            summary = "Rechercheziele werden als neue Tabs im bereits laufenden Firefox geöffnet."
            actions = ["Weitere Recherchen können im bestehenden Browser fortgesetzt werden."]
        elif registered and not active:
            state = "legacy_companion_stale"
            severity = "ready"
            summary = "Ein früher registrierter Companion ist inaktiv; der aktuelle Direkt-Tab-Modus bleibt funktionsfähig."
            actions = ["Keine Aktion erforderlich; der Companion ist für den aktuellen Browsermodus optional."]
        else:
            state = "first_start_ready"
            severity = "ready"
            summary = "Firefox ist verfügbar; die erste Recherche kann im bestehenden Browser als neuer Tab geöffnet werden."
            actions = ["Recherche starten; EagleEye erzeugt kein separates Browserprofil."]

        return {
            "build": "136.0",
            "case_id": case_id,
            "state": state,
            "severity": severity,
            "summary": summary,
            "recommended_actions": actions,
            "firefox_found": firefox is not None,
            "firefox_path": str(firefox) if firefox else "",
            "companion_active": active,
            "companion_registered": registered,
            "companion_status": companion_status,
            "heartbeat_age_seconds": round(heartbeat_age, 1) if heartbeat_age is not None else None,
            "last_port": int(session.get("last_port") or 0),
            "pending_orders": pending,
            "failed_orders": failed,
            "existing_tab_launches": direct_launches,
            "isolated_launches": legacy_isolated_launches,
            "browser_mode": "existing_firefox_tabs",
            "companion_required": False,
            "companion_package_ok": companion_package_ok,
            "orders": orders[:20],
            "recent_events": self.db.all(
                "SELECT event_type,state_before,state_after,details_json,created_by,created_at FROM firefox_session_events_136 WHERE case_id=? ORDER BY created_at DESC LIMIT 20",
                (case_id,),
            ),
            "recent_recovery": self.db.all(
                "SELECT action_key,status,result_json,created_by,created_at FROM firefox_recovery_actions_136 WHERE case_id=? ORDER BY created_at DESC LIMIT 20",
                (case_id,),
            ),
        }

    def run_runtime_diagnostics(self, *, case_id: str | None = None, actor: str = "local-analyst") -> dict[str, Any]:
        if case_id:
            self._case(case_id)
        checks: list[dict[str, Any]] = []

        def add(key: str, ok: bool, weight: int, detail: str, severity: str = "blocker") -> None:
            checks.append({"key": key, "ok": bool(ok), "weight": int(weight), "detail": detail, "severity": severity})

        add("python_version", sys.version_info >= (3, 11), 10, platform.python_version(), "blocker")
        add("runtime_directory", self.base_dir.exists() and os.access(self.base_dir, os.W_OK), 10, str(self.base_dir), "blocker")
        add("database_exists", Path(self.db.path).exists(), 8, str(self.db.path), "blocker")
        try:
            quick_row = self.db.one("PRAGMA quick_check") or {}
            quick_value = next(iter(quick_row.values()), "")
            quick_ok = str(quick_value).casefold() == "ok"
        except Exception as exc:
            quick_ok = False
            quick_value = str(exc)
        add("database_quick_check", quick_ok, 18, str(quick_value), "blocker")
        schema = self.db.one("SELECT value FROM meta WHERE key='schema_version'") or {}
        schema_value = str(schema.get("value") or "")
        try:
            schema_supported = float(schema_value) >= 136.0
        except (TypeError, ValueError):
            schema_supported = False
        add("schema_136_plus", schema_supported, 8, schema_value or "missing", "blocker")
        firefox = self.protection._find_firefox()
        add("firefox_available", firefox is not None, 15, str(firefox or "not found"), "blocker")
        companion_dir = self.install_dir / "tools" / "firefox_companion_136"
        companion_ok = all((companion_dir / name).exists() for name in ("manifest.json", "background.js", "bootstrap.js", "popup.html", "popup.js"))
        add("companion_package_optional", True, 3, f"optional legacy package: {companion_dir}; present={companion_ok}", "info")
        # Current product readiness must not depend on historical Build-210 launchers.
        # The old monitoring/service entry points remain optional compatibility tools.
        launchers = [
            self.install_dir / "START_EAGLEEYE_PRO_216_0.bat",
            self.install_dir / "EAGLEEYE_PRO_216_0.py",
        ]
        add("current_product_launchers", all(path.exists() for path in launchers), 14, ", ".join(path.name for path in launchers), "warning")
        photo_writable = self.photo_root.exists() and os.access(self.photo_root, os.W_OK)
        add("photo_vault", photo_writable, 7, str(self.photo_root), "blocker")
        if case_id:
            diag = self.browser_diagnostics(case_id)
            add("case_browser_state", diag["severity"] != "blocked", 7, f"{diag['state']}: {diag['summary']}", "warning")

        score = sum(item["weight"] for item in checks if item["ok"])
        max_score = sum(item["weight"] for item in checks) or 1
        normalized = round(score / max_score * 100)
        blockers = [item for item in checks if not item["ok"] and item["severity"] == "blocker"]
        warnings = [item for item in checks if not item["ok"] and item["severity"] == "warning"]
        status = "pass" if not blockers and not warnings else "conditional" if not blockers else "blocked"
        run_id = new_id("diag136")
        result = {
            "run_id": run_id,
            "build": "136.0",
            "status": status,
            "score": normalized,
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "checks": checks,
        }
        self.db.execute(
            "INSERT INTO runtime_diagnostics_136(run_id,case_id,status,score,blocker_count,warning_count,checks_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (run_id, case_id or None, status, normalized, len(blockers), len(warnings), dumps(checks), actor, now_ts()),
        )
        self.audit.log("runtime_diagnostics", "build136", run_id, case_id, {"status": status, "score": normalized, "blockers": len(blockers), "warnings": len(warnings)})
        return result

    def repair_browser_session(self, *, case_id: str, action: str, confirmation: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        action = str(action or "").strip()
        allowed = {
            "expire_pending_orders",
            "clear_failed_orders",
            "prepare_registered_recovery",
            "reset_incomplete_setup",
        }
        if action not in allowed:
            raise ValueError("Unbekannte Wiederherstellungsaktion")
        before = self.browser_diagnostics(case_id)
        result: dict[str, Any] = {"action": action}
        status = "completed"
        if action == "expire_pending_orders":
            cur = self.db.execute(
                "UPDATE firefox_tab_orders_135 SET status='expired',error_text='manually expired by Build 136 recovery' WHERE case_id=? AND status IN ('queued','delivered')",
                (case_id,),
            )
            result["updated_orders"] = int(cur.rowcount or 0)
        elif action == "clear_failed_orders":
            cur = self.db.execute(
                "UPDATE firefox_tab_orders_135 SET status='archived_failed' WHERE case_id=? AND status='failed'",
                (case_id,),
            )
            result["updated_orders"] = int(cur.rowcount or 0)
        elif action == "prepare_registered_recovery":
            if confirmation.strip() != "FALLBROWSER GESCHLOSSEN":
                raise PermissionError("Bestätigung 'FALLBROWSER GESCHLOSSEN' erforderlich")
            session = self.db.one("SELECT * FROM firefox_case_sessions_135 WHERE case_id=?", (case_id,)) or {}
            if not session.get("companion_token_hash"):
                raise PermissionError("Für diese Aktion muss der Companion zuvor registriert gewesen sein")
            self.db.execute(
                "UPDATE firefox_tab_orders_135 SET status='expired',error_text='expired before controlled recovery' WHERE case_id=? AND status IN ('queued','delivered')",
                (case_id,),
            )
            self.db.execute(
                "UPDATE firefox_case_sessions_135 SET last_heartbeat_epoch=0,companion_status='closed_confirmed_recovery_ready',updated_at=? WHERE case_id=?",
                (now_ts(), case_id),
            )
            result["next_launch"] = "existing_firefox_tabs"
        elif action == "reset_incomplete_setup":
            if confirmation.strip() != "FALLBROWSER GESCHLOSSEN":
                raise PermissionError("Bestätigung 'FALLBROWSER GESCHLOSSEN' erforderlich")
            session = self.db.one("SELECT * FROM firefox_case_sessions_135 WHERE case_id=?", (case_id,)) or {}
            if session.get("companion_token_hash"):
                raise PermissionError("Der Companion war bereits registriert; nutze die kontrollierte Wiederherstellung")
            cur = self.db.execute(
                "UPDATE firefox_tab_orders_135 SET status='cancelled_for_recovery',error_text='user confirmed case browser closed' WHERE case_id=? AND dispatch_mode IN ('isolated_case_start','isolated_case_recovery') AND status='fallback_dispatched'",
                (case_id,),
            )
            self.db.execute(
                "UPDATE firefox_case_sessions_135 SET companion_status='setup_reset_ready',last_heartbeat_epoch=0,updated_at=? WHERE case_id=?",
                (now_ts(), case_id),
            )
            result["reset_launches"] = int(cur.rowcount or 0)
            result["next_launch"] = "existing_firefox_tabs"

        after = self.browser_diagnostics(case_id)
        action_id = new_id("repair136")
        self.db.execute(
            "INSERT INTO firefox_recovery_actions_136(action_id,case_id,action_key,confirmation_text,status,result_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (action_id, case_id, action, _safe_text(confirmation, 100), status, dumps(result), actor, now_ts()),
        )
        self._event(case_id=case_id, event_type="browser_recovery", actor=actor, before=before["state"], after=after["state"], details={"action_id": action_id, **result})
        return {"action_id": action_id, "status": status, "before": before["state"], "after": after["state"], **result}

    def launch_research_task(self, **kwargs: Any) -> dict[str, Any]:
        case_id = str(kwargs.get("case_id") or "")
        actor = str(kwargs.get("actor") or "local-analyst")
        before = self.browser_diagnostics(case_id)["state"]
        try:
            result = self.build135.launch_research_task(**kwargs)
        except Exception as exc:
            after = self.browser_diagnostics(case_id)["state"]
            self._event(case_id=case_id, event_type="research_launch_blocked", actor=actor, before=before, after=after, details={"error": _safe_text(exc, 500)})
            raise
        after = self.browser_diagnostics(case_id)["state"]
        self._event(case_id=case_id, event_type="research_launch", actor=actor, before=before, after=after, details={"order_id": result.get("order_id", ""), "dispatch_mode": result.get("dispatch_mode", ""), "count": result.get("count", 0)})
        return result

    def launch_research_tasks_parallel(self, **kwargs: Any) -> dict[str, Any]:
        case_id = str(kwargs.get("case_id") or "")
        actor = str(kwargs.get("actor") or "local-analyst")
        before = self.browser_diagnostics(case_id)["state"]
        try:
            result = self.build135.launch_research_tasks_parallel(**kwargs)
        except Exception as exc:
            after = self.browser_diagnostics(case_id)["state"]
            self._event(case_id=case_id, event_type="parallel_launch_blocked", actor=actor, before=before, after=after, details={"error": _safe_text(exc, 500)})
            raise
        after = self.browser_diagnostics(case_id)["state"]
        self._event(case_id=case_id, event_type="parallel_launch", actor=actor, before=before, after=after, details={"order_id": result.get("order_id", ""), "dispatch_mode": result.get("dispatch_mode", ""), "count": result.get("count", 0)})
        return result

    def bootstrap_view(self, ticket: str) -> dict[str, Any]:
        return self.build135.bootstrap_view(ticket)

    def register_companion(self, ticket: str) -> dict[str, Any]:
        result = self.build135.register_companion(ticket)
        self._event(case_id=str(result["case_id"]), event_type="companion_registered", actor="firefox-companion", after="registered", details={"heartbeat_seconds": result.get("heartbeat_seconds", 3)})
        return result

    def poll_orders(self, **kwargs: Any) -> dict[str, Any]:
        return self.build135.poll_orders(**kwargs)

    def acknowledge_order(self, **kwargs: Any) -> dict[str, Any]:
        result = self.build135.acknowledge_order(**kwargs)
        self._event(case_id=str(kwargs.get("case_id") or ""), event_type="tab_order_ack", actor="firefox-companion", after=str(result.get("status") or ""), details={"order_id": result.get("order_id", "")})
        return result

    # ---------- photo evidence intake ----------
    def _photo_event(self, *, asset_id: str, case_id: str, event_type: str, actor: str, details: Mapping[str, Any] | None = None) -> str:
        event_id = new_id("photoevt136")
        payload = dict(details or {})
        self.db.execute(
            "INSERT INTO photo_asset_events_136(event_id,asset_id,case_id,event_type,details_json,created_by,created_at) VALUES(?,?,?,?,?,?,?)",
            (event_id, asset_id, case_id, event_type, dumps(payload), actor, now_ts()),
        )
        self.audit.log(event_type, "photo_asset_136", asset_id, case_id, payload)
        return event_id

    def capture_photo(self, *, payload: Mapping[str, Any], actor: str) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "")
        target_id = str(payload.get("target_id") or "")
        self._case(case_id)
        self._target(case_id, target_id)
        source_kind = str(payload.get("source_kind") or "local_file")
        if source_kind not in PHOTO_SOURCE_KINDS:
            raise ValueError("Ungültige Fotoquelle")
        title = _safe_text(payload.get("title") or payload.get("filename") or "Personenfoto", 300)
        notes = _safe_text(payload.get("notes"), 4000)
        source_label = _safe_text(payload.get("source_label") or "drag_drop_136", 200)
        source_url = _validated_https_url(payload.get("source_url"), required=(source_kind == "remote_reference"))
        source_page_url = _validated_https_url(payload.get("source_page_url"), required=False)
        now = now_ts()

        if source_kind == "remote_reference":
            digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
            existing = self.db.one(
                "SELECT * FROM photo_assets_136 WHERE case_id=? AND source_kind='remote_reference' AND sha256=? ORDER BY created_at LIMIT 1",
                (case_id, digest),
            )
            if existing:
                return {**existing, "duplicate": True}
            asset_id = new_id("photo136")
            self.db.execute(
                "INSERT INTO photo_assets_136(asset_id,case_id,target_id,source_kind,title,original_filename,mime_type,byte_size,width_px,height_px,sha256,storage_relpath,source_url,source_page_url,source_label,notes,candidate_only,review_status,evidence_integrity,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (asset_id, case_id, target_id or None, source_kind, title, "", "", 0, 0, 0, digest, "", source_url, source_page_url, source_label, notes, 1, "unreviewed", "remote_reference_only_no_download", actor, now, now),
            )
            self._photo_event(asset_id=asset_id, case_id=case_id, event_type="photo_reference_added", actor=actor, details={"source_host": urlsplit(source_url).hostname or "", "candidate_only": True})
            return self.get_photo(case_id=case_id, asset_id=asset_id)

        raw_b64 = str(payload.get("data_base64") or "")
        if raw_b64.startswith("data:"):
            try:
                raw_b64 = raw_b64.split(",", 1)[1]
            except IndexError as exc:
                raise ValueError("Ungültige Data-URL") from exc
        try:
            data = base64.b64decode(raw_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Bilddaten sind nicht gültig base64-kodiert") from exc
        if not data:
            raise ValueError("Leere Bilddatei")
        if len(data) > PHOTO_MAX_BYTES:
            raise ValueError(f"Bilddatei überschreitet {PHOTO_MAX_BYTES // (1024 * 1024)} MB")
        detected_mime = _detect_image_mime(data)
        declared_mime = _safe_text(payload.get("mime_type"), 100).casefold()
        if declared_mime and declared_mime not in PHOTO_ALLOWED_MIME:
            raise ValueError("Nicht erlaubter MIME-Typ")
        if declared_mime and declared_mime != detected_mime:
            raise ValueError("Deklarierter MIME-Typ stimmt nicht mit dem Bildinhalt überein")
        width_px, height_px = _image_dimensions(data, detected_mime)
        digest = hashlib.sha256(data).hexdigest()
        existing = self.db.one(
            "SELECT * FROM photo_assets_136 WHERE case_id=? AND source_kind='local_file' AND sha256=?",
            (case_id, digest),
        )
        if existing:
            return {**existing, "duplicate": True}
        asset_id = new_id("photo136")
        ext = PHOTO_EXTENSIONS[detected_mime]
        case_dir = self.photo_root / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        try:
            case_dir.chmod(0o700)
        except OSError:
            pass
        final_path = case_dir / f"{asset_id}{ext}"
        temp_path = case_dir / f".{asset_id}.tmp"
        temp_path.write_bytes(data)
        try:
            temp_path.chmod(0o600)
        except OSError:
            pass
        os.replace(temp_path, final_path)
        try:
            final_path.chmod(0o600)
        except OSError:
            pass
        relpath = final_path.relative_to(self.base_dir).as_posix()
        filename = _safe_filename(payload.get("filename") or f"image{ext}")
        self.db.execute(
            "INSERT INTO photo_assets_136(asset_id,case_id,target_id,source_kind,title,original_filename,mime_type,byte_size,width_px,height_px,sha256,storage_relpath,source_url,source_page_url,source_label,notes,candidate_only,review_status,evidence_integrity,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (asset_id, case_id, target_id or None, source_kind, title, filename, detected_mime, len(data), width_px, height_px, digest, relpath, source_url, source_page_url, source_label, notes, 1, "unreviewed", "original_bytes_preserved_sha256", actor, now, now),
        )
        self._photo_event(asset_id=asset_id, case_id=case_id, event_type="photo_file_captured", actor=actor, details={"sha256": digest, "byte_size": len(data), "mime_type": detected_mime, "width_px": width_px, "height_px": height_px, "candidate_only": True})
        return self.get_photo(case_id=case_id, asset_id=asset_id)

    def get_photo(self, *, case_id: str, asset_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM photo_assets_136 WHERE asset_id=? AND case_id=?", (asset_id, case_id))
        if not row:
            raise KeyError("Fotoeintrag nicht gefunden")
        return row

    def photo_path(self, *, case_id: str, asset_id: str) -> tuple[dict[str, Any], Path]:
        row = self.get_photo(case_id=case_id, asset_id=asset_id)
        if row["source_kind"] != "local_file" or not row.get("storage_relpath"):
            raise ValueError("Dieser Eintrag enthält keine lokale Bilddatei")
        candidate = (self.base_dir / str(row["storage_relpath"])).resolve()
        root = self.photo_root.resolve()
        if candidate != root and root not in candidate.parents:
            raise PermissionError("Ungültiger Foto-Speicherpfad")
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError("Lokale Bilddatei fehlt")
        data_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if data_hash != row["sha256"]:
            raise PermissionError("Integritätsprüfung der Bilddatei fehlgeschlagen")
        return row, candidate

    def list_photos(self, *, case_id: str, target_id: str = "", limit: int = 200) -> list[dict[str, Any]]:
        self._case(case_id)
        if target_id:
            self._target(case_id, target_id)
            rows = self.db.all(
                "SELECT * FROM photo_assets_136 WHERE case_id=? AND target_id=? ORDER BY created_at DESC LIMIT ?",
                (case_id, target_id, max(1, min(int(limit), 500))),
            )
        else:
            rows = self.db.all(
                "SELECT * FROM photo_assets_136 WHERE case_id=? ORDER BY created_at DESC LIMIT ?",
                (case_id, max(1, min(int(limit), 500))),
            )
        for row in rows:
            row["view_url"] = f"/api/photo136/{row['asset_id']}?case_id={case_id}" if row["source_kind"] == "local_file" else ""
        return rows

    def update_photo_review(self, *, case_id: str, asset_id: str, status: str, notes: str, actor: str) -> dict[str, Any]:
        if status not in PHOTO_REVIEW_STATUSES:
            raise ValueError("Ungültiger Fotoreview-Status")
        row = self.get_photo(case_id=case_id, asset_id=asset_id)
        self.db.execute(
            "UPDATE photo_assets_136 SET review_status=?,notes=?,updated_at=? WHERE asset_id=? AND case_id=?",
            (status, _safe_text(notes, 4000), now_ts(), asset_id, case_id),
        )
        self._photo_event(asset_id=asset_id, case_id=case_id, event_type="photo_review_updated", actor=actor, details={"old_status": row.get("review_status", ""), "new_status": status})
        return self.get_photo(case_id=case_id, asset_id=asset_id)

    def photo_dashboard(self, case_id: str) -> dict[str, Any]:
        rows = self.list_photos(case_id=case_id, limit=200)
        return {
            "case_id": case_id,
            "count": len(rows),
            "local_files": sum(1 for row in rows if row["source_kind"] == "local_file"),
            "remote_references": sum(1 for row in rows if row["source_kind"] == "remote_reference"),
            "unreviewed": sum(1 for row in rows if row["review_status"] == "unreviewed"),
            "photos": rows,
            "limitations": [
                "Build 136 führt keine Gesichtserkennung und keine automatische Identitätsbestätigung durch.",
                "Remote Bild-URLs werden nur als Referenz gespeichert; EagleEye lädt sie nicht autonom herunter.",
                "Lokale Dateien bleiben candidate-only, bis ein Ermittler sie bewertet.",
            ],
        }

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        return {
            "build": "136.0",
            "browser": self.browser_diagnostics(case_id) if case_id else {},
            "photos": self.photo_dashboard(case_id) if case_id else {},
            "diagnostics": self.db.all(
                "SELECT run_id,case_id,status,score,blocker_count,warning_count,created_by,created_at FROM runtime_diagnostics_136 WHERE case_id IS ? OR case_id=? ORDER BY created_at DESC LIMIT 20",
                (case_id or None, case_id),
            ) if case_id else self.db.all(
                "SELECT run_id,case_id,status,score,blocker_count,warning_count,created_by,created_at FROM runtime_diagnostics_136 ORDER BY created_at DESC LIMIT 20"
            ),
        }
