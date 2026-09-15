from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts
from eagleeye_pro.core.versioning import version_at_least

MAINTENANCE_CONFIRMATION = "SICHERE PHASE-4-WARTUNG ANWENDEN"
BASELINE_CONFIRMATION = "PHASE 4 BASELINE ERZEUGEN"
BASELINE_REVIEW_CONFIRMATION = "PHASE-4-BASELINE PRÜFEN"
SEAL_CONFIRMATION = "PHASE 4 ABSCHLUSS FREIGEBEN"
REVIEW_DECISIONS = {"approved", "revision_required", "rejected"}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canonical(value).encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()


def _safe_name(value: str, limit: int = 100) -> str:
    text = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(value or ""))
    return text[:limit] or "item"


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


class Build145Service:
    """Final Phase-4 baseline, maintenance and immutable completion seal.

    Build 145 is deliberately conservative. It improves local query paths,
    performs safe SQLite maintenance, cleans only expired derivative bytes and
    refuses to seal Phase 4 while critical audit, backup, OPSEC or risk gates
    remain unresolved.
    """

    BUILD = "145.0"

    def __init__(
        self,
        db: Any,
        audit: Any,
        base_dir: str | Path,
        install_dir: str | Path,
        *,
        governance: Any,
        build144: Any,
        build143: Any,
        build142: Any,
        build141: Any,
        build140: Any,
        build138: Any,
        build137: Any,
    ) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.install_dir = Path(install_dir).resolve()
        self.governance = governance
        self.build144 = build144
        self.build143 = build143
        self.build142 = build142
        self.build141 = build141
        self.build140 = build140
        self.build138 = build138
        self.build137 = build137
        self.final_root = (self.base_dir / "reports" / "phase4_final_145").resolve()
        self.final_root.mkdir(parents=True, exist_ok=True)
        self._chmod(self.final_root, 0o700)

    @staticmethod
    def _chmod(path: Path, mode: int) -> None:
        try:
            path.chmod(mode)
        except OSError:
            pass

    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not row:
            raise KeyError("Fall nicht gefunden")
        return row

    def _authorize(self, actor: str, case_id: str, permission: str = "security.review") -> None:
        self.governance.authorize(username=actor, case_id=case_id, permission=permission)

    def _event(self, *, case_id: str, event_type: str, object_type: str, object_id: str, actor: str, payload: Mapping[str, Any] | None = None) -> None:
        previous = self.db.one("SELECT event_hash FROM build145_events WHERE case_id=? ORDER BY sequence DESC LIMIT 1", (case_id,))
        previous_hash = str((previous or {}).get("event_hash") or "GENESIS")
        safe = dict(payload or {})
        for key in list(safe):
            if any(mark in key.casefold() for mark in ("password", "secret", "token", "credential")):
                safe[key] = "[redacted]"
        stamp = now_ts()
        body = {"case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "payload": safe, "previous_hash": previous_hash, "created_by": actor, "created_at": stamp}
        event_hash = _sha(body)
        self.db.execute("INSERT INTO build145_events(event_id,case_id,event_type,object_type,object_id,payload_json,previous_hash,event_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (new_id("evt145"), case_id, event_type, object_type, object_id, dumps(safe), previous_hash, event_hash, actor, stamp))
        self.audit.log(event_type, f"build145_{object_type}", object_id, case_id, safe)

    def _table_count(self, table: str, case_id: str = "") -> int:
        if not self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)):
            return 0
        columns = {row.get("name") for row in self.db.all(f"PRAGMA table_info({table})")}
        if case_id and "case_id" in columns:
            return int((self.db.one(f"SELECT COUNT(*) AS n FROM {table} WHERE case_id=?", (case_id,)) or {}).get("n") or 0)
        return int((self.db.one(f"SELECT COUNT(*) AS n FROM {table}") or {}).get("n") or 0)

    def _maintenance_metrics(self, case_id: str) -> dict[str, Any]:
        page_count = int((self.db.one("PRAGMA page_count") or {}).get("page_count") or 0)
        free_pages = int((self.db.one("PRAGMA freelist_count") or {}).get("freelist_count") or 0)
        wal = Path(str(self.db.path) + "-wal")
        duplicates = self.db.all(
            """SELECT category,query,engine,COUNT(*) AS n,MIN(created_at) AS first_created
               FROM search_tasks WHERE case_id=? AND status='planned'
               GROUP BY category,query,engine HAVING COUNT(*)>1 ORDER BY n DESC LIMIT 100""",
            (case_id,),
        )
        now = datetime.now(timezone.utc)
        expired_copies = 0
        for table in ("photo_research_copies_137", "photo_variants_138"):
            if self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)):
                for row in self.db.all(f"SELECT expires_at FROM {table} WHERE case_id=? AND status='ready' AND expires_at!=''", (case_id,)):
                    parsed = _parse_iso(row.get("expires_at") or "")
                    expired_copies += int(bool(parsed and parsed <= now))
        expired_sessions = int((self.db.one("SELECT COUNT(*) AS n FROM research_persona_sessions_143 WHERE case_id=? AND status='active' AND expires_epoch>0 AND expires_epoch<?", (case_id, int(time.time()))) or {}).get("n") or 0)
        return {
            "page_count": page_count,
            "free_pages": free_pages,
            "free_page_ratio": round(free_pages / max(page_count, 1), 4),
            "wal_bytes": wal.stat().st_size if wal.is_file() else 0,
            "duplicate_planned_groups": len(duplicates),
            "duplicate_planned_tasks": sum(max(0, int(row.get("n") or 0) - 1) for row in duplicates),
            "duplicate_sample": duplicates[:20],
            "expired_derivatives": expired_copies,
            "expired_active_sessions": expired_sessions,
            "table_counts": {
                "search_tasks": self._table_count("search_tasks", case_id),
                "workflow_tasks": self._table_count("investigation_workflow_tasks_137", case_id),
                "evidence_assertions": self._table_count("evidence_assertions_138", case_id),
                "photos": self._table_count("photo_assets_136", case_id),
                "reports": self._table_count("professional_reports_142", case_id),
            },
        }

    def _cleanup_expired_derivatives(self, case_id: str) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        removed = failed = 0
        specs = (
            ("photo_research_copies_137", "copy_id", self.build137.photo_root),
            ("photo_variants_138", "variant_id", self.build138.photo_root),
        )
        for table, id_col, root_value in specs:
            if not self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)):
                continue
            root = Path(root_value).resolve()
            rows = self.db.all(f"SELECT {id_col} AS object_id,storage_relpath,expires_at FROM {table} WHERE case_id=? AND status='ready' AND expires_at!=''", (case_id,))
            for row in rows:
                expires = _parse_iso(row.get("expires_at") or "")
                if not expires or expires > now:
                    continue
                path = (self.base_dir / str(row.get("storage_relpath") or "")).resolve()
                if root != path and root not in path.parents:
                    failed += 1
                    continue
                try:
                    path.unlink(missing_ok=True)
                    self.db.execute(f"UPDATE {table} SET status='expired_removed' WHERE {id_col}=? AND case_id=?", (row["object_id"], case_id))
                    removed += 1
                except OSError:
                    failed += 1
        return {"removed": removed, "failed": failed}

    def run_maintenance(self, *, case_id: str, dry_run: bool = True, confirmation: str = "", actor: str) -> dict[str, Any]:
        self._case(case_id)
        self._authorize(actor, case_id)
        before = self._maintenance_metrics(case_id)
        actions: list[dict[str, Any]] = [
            {"action": "index_contract", "status": "present", "detail": "Additive Build-145-Indizes sind im Schema aktiviert."},
            {"action": "duplicate_review", "status": "advisory", "count": before["duplicate_planned_tasks"], "detail": "Dubletten werden nicht automatisch gelöscht; die Ermittlungshistorie bleibt erhalten."},
            {"action": "expired_session_review", "status": "advisory", "count": before["expired_active_sessions"], "detail": "Abgelaufene aktive Browserprozesse müssen manuell geprüft und geschlossen werden."},
        ]
        status = "dry_run"
        if not dry_run:
            if str(confirmation or "").strip() != MAINTENANCE_CONFIRMATION:
                raise PermissionError(f"Freigabephrase {MAINTENANCE_CONFIRMATION} fehlt")
            with self.db._lock:
                self.db.conn.execute("PRAGMA optimize")
                self.db.conn.execute("ANALYZE")
                checkpoint = self.db.conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
                self.db.conn.commit()
            cleanup = self._cleanup_expired_derivatives(case_id)
            actions.extend([
                {"action": "pragma_optimize", "status": "applied"},
                {"action": "analyze", "status": "applied"},
                {"action": "wal_checkpoint_passive", "status": "applied", "result": list(checkpoint or ())},
                {"action": "expired_derivative_cleanup", "status": "applied" if cleanup["failed"] == 0 else "warning", **cleanup},
            ])
            status = "pass" if cleanup["failed"] == 0 else "conditional"
        after = self._maintenance_metrics(case_id)
        savings = {
            "wal_bytes_reduced": max(0, int(before["wal_bytes"]) - int(after["wal_bytes"])),
            "expired_derivatives_removed": max(0, int(before["expired_derivatives"]) - int(after["expired_derivatives"])),
            "potential_duplicate_steps": int(before["duplicate_planned_tasks"]),
            "data_rows_deleted": 0,
            "investigation_tasks_deleted": 0,
        }
        maintenance_id = new_id("maint145")
        self.db.execute("INSERT INTO phase4_maintenance_runs_145(maintenance145_id,case_id,dry_run,status,before_json,actions_json,after_json,estimated_savings_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (maintenance_id, case_id, int(bool(dry_run)), status, dumps(before), dumps(actions), dumps(after), dumps(savings), actor, now_ts()))
        self._event(case_id=case_id, event_type="phase4_maintenance_completed", object_type="maintenance", object_id=maintenance_id, actor=actor, payload={"dry_run": bool(dry_run), "status": status, "expired_derivatives_removed": savings["expired_derivatives_removed"], "tasks_deleted": 0})
        return {"maintenance_id": maintenance_id, "case_id": case_id, "dry_run": bool(dry_run), "status": status, "before": before, "actions": actions, "after": after, "estimated_savings": savings}

    def create_health_snapshot(self, *, case_id: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        self._authorize(actor, case_id)
        audit_row = self.db.one("SELECT * FROM release_candidate_audits_144 WHERE case_id=? ORDER BY completed_at DESC LIMIT 1", (case_id,)) or {}
        backup_row = self.db.one("SELECT * FROM verified_backups_144 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", (case_id,)) or {}
        quick = (self.db.one("PRAGMA quick_check") or {}).get("quick_check", "")
        foreign_keys = self.db.all("PRAGMA foreign_key_check")
        open_high = int((self.db.one("SELECT COUNT(*) AS n FROM phase4_risks_144 WHERE case_id=? AND status='open' AND severity IN ('critical','high')", (case_id,)) or {}).get("n") or 0)
        active_sessions = int((self.db.one("SELECT COUNT(*) AS n FROM research_persona_sessions_143 WHERE case_id=? AND status='active'", (case_id,)) or {}).get("n") or 0)
        checks = [
            {"key": "database", "ok": quick == "ok" and not foreign_keys},
            {"key": "latest_audit", "ok": bool(audit_row) and int(audit_row.get("blocker_count") or 0) == 0 and int(audit_row.get("score") or 0) >= 90},
            {"key": "verified_backup", "ok": bool(backup_row) and backup_row.get("status") == "pass" and backup_row.get("restore_status") == "pass"},
            {"key": "open_high_risks", "ok": open_high == 0},
            {"key": "active_sessions", "ok": active_sessions == 0},
            {"key": "schema", "ok": version_at_least((self.db.one("SELECT value FROM meta WHERE key='schema_version'") or {}).get("value"), self.BUILD)},
        ]
        failed = [row for row in checks if not row["ok"]]
        score = round(100 * (len(checks) - len(failed)) / len(checks))
        status = "ready" if not failed else "blocked"
        metrics = {"quick_check": quick, "foreign_key_violations": len(foreign_keys), "audit_score": int(audit_row.get("score") or 0), "audit_blockers": int(audit_row.get("blocker_count") or 0), "backup_status": backup_row.get("status", "missing"), "restore_status": backup_row.get("restore_status", "missing"), "open_high_risks": open_high, "active_sessions": active_sessions, "safety_contract": self.safety_contract()}
        snapshot_id = new_id("health145")
        self.db.execute("INSERT INTO phase4_health_snapshots_145(snapshot145_id,case_id,status,score,audit144_id,backup144_id,metrics_json,findings_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (snapshot_id, case_id, status, score, audit_row.get("audit144_id", ""), backup_row.get("backup144_id", ""), dumps(metrics), dumps(failed), actor, now_ts()))
        self._event(case_id=case_id, event_type="phase4_health_snapshot_created", object_type="health_snapshot", object_id=snapshot_id, actor=actor, payload={"status": status, "score": score, "failed": [row["key"] for row in failed]})
        return {"snapshot_id": snapshot_id, "case_id": case_id, "status": status, "score": score, "checks": checks, "findings": failed, "metrics": metrics, "audit_id": audit_row.get("audit144_id", ""), "backup_id": backup_row.get("backup144_id", "")}

    @staticmethod
    def safety_contract() -> dict[str, Any]:
        return {
            "automatic_external_actions": 0,
            "automatic_identity_claims": 0,
            "automatic_person_merges": 0,
            "automatic_image_uploads": 0,
            "biometric_templates": 0,
            "face_identity_matches": 0,
            "automatic_account_creation": 0,
            "automatic_login": 0,
            "anti_bot_bypass": 0,
            "untraceability_guarantee": False,
            "manual_review_required": True,
            "case_isolation_required": True,
        }

    def _baseline_manifest(self, case_id: str, audit_row: dict[str, Any], backup_row: dict[str, Any], label: str, actor: str) -> dict[str, Any]:
        health = self.create_health_snapshot(case_id=case_id, actor=actor)
        maintenance = self.db.one("SELECT * FROM phase4_maintenance_runs_145 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", (case_id,)) or {}
        tables = [row["name"] for row in self.db.all("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {
            "schema": "eagleeye.phase4-baseline.145",
            "build": self.BUILD,
            "schema_version": (self.db.one("SELECT value FROM meta WHERE key='schema_version'") or {}).get("value", ""),
            "case_id": case_id,
            "baseline_label": label,
            "created_at": now_ts(),
            "created_by": actor,
            "release_candidate_audit": {"audit_id": audit_row["audit144_id"], "status": audit_row["status"], "score": audit_row["score"], "blockers": audit_row["blocker_count"], "warnings": audit_row["warning_count"]},
            "verified_backup": {"backup_id": backup_row["backup144_id"], "status": backup_row["status"], "restore_status": backup_row["restore_status"], "database_sha256": backup_row["database_sha256"], "manifest_sha256": backup_row["manifest_sha256"]},
            "health_snapshot": health,
            "maintenance": {"maintenance_id": maintenance.get("maintenance145_id", ""), "status": maintenance.get("status", "not_run"), "dry_run": bool(maintenance.get("dry_run", 1))},
            "inventory": {"table_count": len(tables), "tables_sha256": _sha(tables), "targets": self._table_count("targets", case_id), "assertions": self._table_count("evidence_assertions_138", case_id), "photos": self._table_count("photo_assets_136", case_id), "reports": self._table_count("professional_reports_142", case_id), "report_releases": self._table_count("report_releases_142", case_id)},
            "safety_contract": self.safety_contract(),
            "field_validation_boundaries": ["Windows-Doppelklick und DPAPI", "sichtbarer Firefox-/Companion-Betrieb", "realer Proxy-/Tor-Egress und DNS-Leak-Test", "Live-Connectoren", "externer Security Review"],
            "claims": {"phase4_functional_baseline": True, "independent_security_certification": False, "automatic_external_transfer": False},
        }

    def create_baseline(self, *, case_id: str, baseline_label: str, confirmation: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        self._authorize(actor, case_id, "export.approve")
        if str(confirmation or "").strip() != BASELINE_CONFIRMATION:
            raise PermissionError(f"Freigabephrase {BASELINE_CONFIRMATION} fehlt")
        audit_row = self.db.one("SELECT * FROM release_candidate_audits_144 WHERE case_id=? ORDER BY completed_at DESC LIMIT 1", (case_id,))
        backup_row = self.db.one("SELECT * FROM verified_backups_144 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", (case_id,))
        if not audit_row or int(audit_row.get("blocker_count") or 0) != 0 or int(audit_row.get("score") or 0) < 90:
            raise PermissionError("Aktuelles Build-144-Audit ist nicht freigabefähig")
        if not backup_row or backup_row.get("status") != "pass" or backup_row.get("restore_status") != "pass":
            raise PermissionError("Verifiziertes Backup mit bestandenem Restore-Test fehlt")
        if self._table_count("research_persona_sessions_143", case_id) and int((self.db.one("SELECT COUNT(*) AS n FROM research_persona_sessions_143 WHERE case_id=? AND status='active'", (case_id,)) or {}).get("n") or 0):
            raise PermissionError("Aktive Research-Sitzungen verhindern die Phase-4-Baseline")
        open_high = int((self.db.one("SELECT COUNT(*) AS n FROM phase4_risks_144 WHERE case_id=? AND status='open' AND severity IN ('critical','high')", (case_id,)) or {}).get("n") or 0)
        if open_high:
            raise PermissionError("Offene kritische oder hohe Phase-4-Risiken verhindern die Baseline")
        label = str(baseline_label or "Phase 4 Final Baseline").strip()[:160]
        manifest = self._baseline_manifest(case_id, audit_row, backup_row, label, actor)
        manifest_hash = _sha(manifest)
        baseline_id = new_id("baseline145")
        rel_dir = Path(_safe_name(case_id)) / _safe_name(baseline_id)
        out_dir = (self.final_root / rel_dir).resolve()
        if self.final_root not in out_dir.parents:
            raise PermissionError("Baseline-Pfad verlässt den finalen Tresor")
        out_dir.mkdir(parents=True, exist_ok=False)
        self._chmod(out_dir, 0o700)
        manifest_path = out_dir / "phase4_baseline_manifest.json"
        manifest_bytes = (_canonical(manifest) + "\n").encode("utf-8")
        manifest_path.write_bytes(manifest_bytes)
        self._chmod(manifest_path, 0o600)
        stamp = now_ts()
        self.db.execute("INSERT INTO phase4_baselines_145(baseline145_id,case_id,audit144_id,backup144_id,status,baseline_label,manifest_json,manifest_sha256,manifest_relpath,requested_by,requested_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (baseline_id, case_id, audit_row["audit144_id"], backup_row["backup144_id"], "pending_review", label, dumps(manifest), manifest_hash, (rel_dir / manifest_path.name).as_posix(), actor, stamp, stamp, stamp))
        self._event(case_id=case_id, event_type="phase4_baseline_created", object_type="phase4_baseline", object_id=baseline_id, actor=actor, payload={"manifest_sha256": manifest_hash, "audit_id": audit_row["audit144_id"], "backup_id": backup_row["backup144_id"], "status": "pending_review"})
        return self.get_baseline(case_id=case_id, baseline_id=baseline_id)

    def review_baseline(self, *, case_id: str, baseline_id: str, decision: str, reason: str, confirmation: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        self._authorize(actor, case_id, "export.approve")
        if str(confirmation or "").strip() != BASELINE_REVIEW_CONFIRMATION:
            raise PermissionError(f"Freigabephrase {BASELINE_REVIEW_CONFIRMATION} fehlt")
        decision = str(decision or "").strip().casefold()
        if decision not in REVIEW_DECISIONS:
            raise ValueError("Unbekannte Reviewentscheidung")
        if len(str(reason or "").strip()) < 12:
            raise ValueError("Substanzielle Reviewbegründung erforderlich")
        row = self.db.one("SELECT * FROM phase4_baselines_145 WHERE case_id=? AND baseline145_id=?", (case_id, baseline_id))
        if not row:
            raise KeyError("Phase-4-Baseline nicht gefunden")
        if row["requested_by"].casefold() == actor.casefold():
            raise PermissionError("Vier-Augen-Prinzip: Antragsteller darf die Baseline nicht selbst prüfen")
        if row["sealed"]:
            raise PermissionError("Versiegelte Baseline kann nicht erneut geprüft werden")
        status = "approved" if decision == "approved" else decision
        stamp = now_ts()
        self.db.execute("UPDATE phase4_baselines_145 SET status=?,reviewed_by=?,reviewed_at=?,review_decision=?,review_reason=?,updated_at=? WHERE baseline145_id=?", (status, actor, stamp, decision, str(reason).strip()[:3000], stamp, baseline_id))
        self._event(case_id=case_id, event_type="phase4_baseline_reviewed", object_type="phase4_baseline", object_id=baseline_id, actor=actor, payload={"decision": decision, "status": status})
        return self.get_baseline(case_id=case_id, baseline_id=baseline_id)

    def _baseline_path(self, relpath: str) -> Path:
        path = (self.final_root / str(relpath)).resolve()
        if path != self.final_root and self.final_root not in path.parents:
            raise PermissionError("Finaler Exportpfad verlässt den Tresor")
        return path

    def seal_baseline(self, *, case_id: str, baseline_id: str, confirmation: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        self._authorize(actor, case_id, "export.approve")
        if str(confirmation or "").strip() != SEAL_CONFIRMATION:
            raise PermissionError(f"Freigabephrase {SEAL_CONFIRMATION} fehlt")
        baseline = self.db.one("SELECT * FROM phase4_baselines_145 WHERE case_id=? AND baseline145_id=?", (case_id, baseline_id))
        if not baseline:
            raise KeyError("Phase-4-Baseline nicht gefunden")
        if baseline["status"] != "approved" or baseline["review_decision"] != "approved":
            raise PermissionError("Nur unabhängig genehmigte Baselines dürfen versiegelt werden")
        if actor.casefold() == baseline["requested_by"].casefold():
            raise PermissionError("Antragsteller darf den Phase-4-Abschluss nicht allein versiegeln")
        if baseline["sealed"]:
            existing = self.db.one("SELECT * FROM phase4_release_seals_145 WHERE baseline145_id=?", (baseline_id,))
            return {"baseline": self.get_baseline(case_id=case_id, baseline_id=baseline_id), "seal": existing}
        manifest = loads(baseline["manifest_json"], {})
        if _sha(manifest) != baseline["manifest_sha256"]:
            raise PermissionError("Baseline-Manifest wurde verändert")
        manifest_path = self._baseline_path(baseline["manifest_relpath"])
        if not manifest_path.is_file() or _sha(json.loads(manifest_path.read_text(encoding="utf-8"))) != baseline["manifest_sha256"]:
            raise PermissionError("Baseline-Manifestdatei besteht Integritätsprüfung nicht")
        health = self.create_health_snapshot(case_id=case_id, actor=actor)
        if health["status"] != "ready":
            raise PermissionError("Aktueller Phase-4-Gesundheitszustand ist nicht freigabefähig")
        seal_id = new_id("seal145")
        seal = {
            "schema": "eagleeye.phase4-release-seal.145",
            "build": self.BUILD,
            "seal_id": seal_id,
            "baseline_id": baseline_id,
            "case_id": case_id,
            "baseline_manifest_sha256": baseline["manifest_sha256"],
            "audit_id": baseline["audit144_id"],
            "backup_id": baseline["backup144_id"],
            "health_snapshot_id": health["snapshot_id"],
            "health_score": health["score"],
            "reviewed_by": baseline["reviewed_by"],
            "sealed_by": actor,
            "sealed_at": now_ts(),
            "safety_contract": self.safety_contract(),
            "claims": {"phase4_completed": True, "functional_release_candidate": True, "enterprise_certification": False, "independent_penetration_test": False},
        }
        seal_bytes = (_canonical(seal) + "\n").encode("utf-8")
        seal_hash = hashlib.sha256(seal_bytes).hexdigest()
        manifest_parent = manifest_path.parent
        seal_path = manifest_parent / "PHASE4_RELEASE_SEAL.json"
        if seal_path.exists():
            raise FileExistsError("Release-Seal-Datei existiert bereits")
        seal_path.write_bytes(seal_bytes)
        self._chmod(seal_path, 0o600)
        rel = seal_path.relative_to(self.final_root).as_posix()
        stamp = now_ts()
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO phase4_release_seals_145(seal145_id,baseline145_id,case_id,status,seal_relpath,seal_sha256,manifest_sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (seal_id, baseline_id, case_id, "sealed", rel, seal_hash, baseline["manifest_sha256"], actor, stamp))
            self.db.execute("UPDATE phase4_baselines_145 SET status='sealed',sealed=1,sealed_by=?,sealed_at=?,updated_at=? WHERE baseline145_id=?", (actor, stamp, stamp, baseline_id))
            self._event(case_id=case_id, event_type="phase4_release_sealed", object_type="phase4_release_seal", object_id=seal_id, actor=actor, payload={"baseline_id": baseline_id, "seal_sha256": seal_hash, "manifest_sha256": baseline["manifest_sha256"], "phase4_completed": True})
        return {"baseline": self.get_baseline(case_id=case_id, baseline_id=baseline_id), "seal": self.db.one("SELECT * FROM phase4_release_seals_145 WHERE seal145_id=?", (seal_id,)), "seal_document": seal}

    def verify_seal(self, *, case_id: str, seal_id: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        self._authorize(actor, case_id, "case.read")
        seal = self.db.one("SELECT * FROM phase4_release_seals_145 WHERE case_id=? AND seal145_id=?", (case_id, seal_id))
        if not seal:
            raise KeyError("Phase-4-Seal nicht gefunden")
        baseline = self.db.one("SELECT * FROM phase4_baselines_145 WHERE baseline145_id=? AND case_id=?", (seal["baseline145_id"], case_id))
        path = self._baseline_path(seal["seal_relpath"])
        exists = path.is_file()
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if exists else ""
        manifest_ok = bool(baseline) and baseline["manifest_sha256"] == seal["manifest_sha256"] and _sha(loads(baseline["manifest_json"], {})) == seal["manifest_sha256"]
        status = "pass" if exists and actual == seal["seal_sha256"] and manifest_ok else "fail"
        self.db.execute("UPDATE phase4_release_seals_145 SET verification_count=verification_count+1,last_verification_status=?,last_verified_at=? WHERE seal145_id=?", (status, now_ts(), seal_id))
        self._event(case_id=case_id, event_type="phase4_release_seal_verified", object_type="phase4_release_seal", object_id=seal_id, actor=actor, payload={"status": status, "file_exists": exists, "seal_hash_ok": actual == seal["seal_sha256"], "manifest_ok": manifest_ok})
        return {"seal_id": seal_id, "case_id": case_id, "status": status, "file_exists": exists, "expected_sha256": seal["seal_sha256"], "actual_sha256": actual, "manifest_ok": manifest_ok}

    def get_baseline(self, *, case_id: str, baseline_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase4_baselines_145 WHERE case_id=? AND baseline145_id=?", (case_id, baseline_id))
        if not row:
            raise KeyError("Phase-4-Baseline nicht gefunden")
        row["manifest"] = loads(row.get("manifest_json"), {})
        return row

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        where = " WHERE case_id=?" if case_id else ""
        params = (case_id,) if case_id else ()
        snapshots = self.db.all("SELECT snapshot145_id,case_id,status,score,audit144_id,backup144_id,created_by,created_at FROM phase4_health_snapshots_145" + where + " ORDER BY created_at DESC LIMIT 20", params)
        maintenance = self.db.all("SELECT maintenance145_id,case_id,dry_run,status,created_by,created_at FROM phase4_maintenance_runs_145" + where + " ORDER BY created_at DESC LIMIT 20", params)
        baselines = self.db.all("SELECT baseline145_id,case_id,status,baseline_label,manifest_sha256,requested_by,requested_at,reviewed_by,review_decision,sealed,sealed_by,sealed_at,updated_at FROM phase4_baselines_145" + where + " ORDER BY updated_at DESC LIMIT 20", params)
        seals = self.db.all("SELECT seal145_id,baseline145_id,case_id,status,seal_sha256,verification_count,last_verification_status,last_verified_at,created_by,created_at FROM phase4_release_seals_145" + where + " ORDER BY created_at DESC LIMIT 20", params)
        return {
            "build": self.BUILD,
            "case_id": case_id,
            "safety_contract": self.safety_contract(),
            "snapshots": snapshots,
            "maintenance": maintenance,
            "baselines": baselines,
            "seals": seals,
            "metrics": {"ready_snapshots": sum(1 for row in snapshots if row["status"] == "ready"), "sealed_baselines": sum(1 for row in baselines if row["sealed"]), "verified_seals": sum(1 for row in seals if row["last_verification_status"] == "pass")},
            "phase4_status": "completed" if any(row["last_verification_status"] == "pass" for row in seals) else "not_sealed",
            "limitations": ["Phase-4-Seal ist eine lokale Integritäts- und Freigabebaseline, keine behördliche Zertifizierung.", "Reale Windows-, Firefox-, Egress-, Connector- und externe Security-Feldprüfungen bleiben dokumentierte Betriebsaufgaben."],
        }
