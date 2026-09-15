from __future__ import annotations
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts, SCHEMA_VERSION
from eagleeye_pro.audit.service import AuditService

BUILD_VERSION = "37.0"
DEFAULT_EXCLUDES = {
    "data", "reports", "backups", "qa_deep_workspace", ".pytest_cache", "__pycache__",
    "legacy_reference", "dist", "release", "qa_selftest_workspace",
}
DEFAULT_EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3"}

DEFAULT_DEPLOYMENT_PROFILES = [
    {
        "profile_key": "portable_local",
        "title": "Portable lokale ZIP-Version",
        "target": "single_workstation",
        "includes_runtime_data": 0,
        "requires_admin": 0,
        "description": "Saubere portable Distribution ohne Fall-/Evidence-/Report-Runtime-Daten. Für Einzelarbeitsplatz oder gesicherte Übergabe.",
    },
    {
        "profile_key": "local_installer_staged",
        "title": "Lokaler Windows-Installationsordner",
        "target": "managed_workstation",
        "includes_runtime_data": 0,
        "requires_admin": 0,
        "description": "Vorbereiteter Installations-/Startordner mit Launcher, README, Migrationscheck und Rollback-Hinweisen.",
    },
    {
        "profile_key": "team_on_prem_staged",
        "title": "Team/On-Prem Vorbereitungsprofil",
        "target": "team_on_prem",
        "includes_runtime_data": 0,
        "requires_admin": 1,
        "description": "Strukturprofil für späteres Team-/On-Prem-Deployment mit gesonderter Datenhaltung, Backup und Admin-Kontrollen.",
    },
]

DEFAULT_CHECKLIST = [
    ("python_version", "Python 3.10+ verfügbar", "critical", "python --version prüfen; Build 31 bleibt Python-basiert und speichert keine Provider-Keys im Klartext."),
    ("venv_optional", "Virtuelle Umgebung empfohlen", "medium", "Optional: python -m venv .venv und pip install -r requirements.txt."),
    ("runtime_dirs", "data/reports/backups-Verzeichnisse getrennt", "critical", "Runtime-Daten nie in Release-ZIP mitliefern; Backup/Restore nur kontrolliert."),
    ("backup_before_update", "Backup vor Migration/Rollback erzeugt", "critical", "Vor Update von 30 auf 31 Backup-/Rollbackpunkt erstellen."),
    ("integrity_baseline", "Integrity Baseline nach Installation erzeugt", "high", "Security-Tab: Baseline erzeugen und prüfen."),
    ("secrets_env_only", "API Keys nur als Umgebungsvariablen", "high", "Keine Klartext-Key-Dateien; secret_references prüfen."),
    ("legal_privacy_review", "Legal/Privacy Gates für Produktivfälle aktiv", "critical", "Vor produktiver Nutzung: Zweck, Rechtsgrundlage, Scope, Retention, Exportblocker."),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class EnterprisePackagingService:
    """Build 31 release/installation/migration/rollback layer.

    The service does not create an executable installer. It creates verifiable
    enterprise-ready release packages, portable bundles, migration plans,
    rollback points and deployment checklists. Runtime case/evidence data is
    excluded by default to avoid leaking sensitive PersonOSINT data.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    # ------------------------------------------------------------------
    # Bootstrap/defaults
    # ------------------------------------------------------------------
    def seed_defaults(self) -> Dict[str, int]:
        profiles_inserted = 0
        for profile in DEFAULT_DEPLOYMENT_PROFILES:
            if not self.db.one("SELECT profile_id FROM deployment_profiles WHERE profile_key=?", [profile["profile_key"]]):
                self.db.execute(
                    "INSERT INTO deployment_profiles(profile_id,profile_key,title,description,target,includes_runtime_data,requires_admin,created_at,active) VALUES(?,?,?,?,?,?,?,?,?)",
                    [new_id("dprof"), profile["profile_key"], profile["title"], profile["description"], profile["target"], profile["includes_runtime_data"], profile["requires_admin"], now_ts(), 1],
                )
                profiles_inserted += 1
        checklist_inserted = 0
        for profile in DEFAULT_DEPLOYMENT_PROFILES:
            for item_key, title, severity, notes in DEFAULT_CHECKLIST:
                exists = self.db.one("SELECT check_id FROM installer_checklist WHERE profile_key=? AND item_key=?", [profile["profile_key"], item_key])
                if not exists:
                    self.db.execute(
                        "INSERT INTO installer_checklist(check_id,profile_key,item_key,title,status,severity,created_at,notes) VALUES(?,?,?,?,?,?,?,?)",
                        [new_id("check"), profile["profile_key"], item_key, title, "open", severity, now_ts(), notes],
                    )
                    checklist_inserted += 1
        settings = {
            "release_build_version": BUILD_VERSION,
            "runtime_data_policy": "exclude_from_release_by_default",
            "rollback_required_before_migration": "true",
            "portable_bundle_profile": "portable_local",
        }
        settings_inserted = 0
        for key, value in settings.items():
            if not self.db.one("SELECT setting_key FROM deployment_settings WHERE setting_key=?", [key]):
                self.db.execute("INSERT INTO deployment_settings(setting_key,setting_value,updated_at,notes) VALUES(?,?,?,?)", [key, value, now_ts(), "Build 31 packaging default"])
                settings_inserted += 1
        self.audit.log("PACKAGING_DEFAULTS_SEEDED", "packaging", details={"profiles_inserted": profiles_inserted, "checklist_inserted": checklist_inserted, "settings_inserted": settings_inserted})
        return {"profiles_inserted": profiles_inserted, "checklist_inserted": checklist_inserted, "settings_inserted": settings_inserted}

    def list_profiles(self) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM deployment_profiles WHERE active=1 ORDER BY profile_key")

    def list_checklist(self, profile_key: str = "portable_local") -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM installer_checklist WHERE profile_key=? ORDER BY severity, item_key", [profile_key])

    def update_checklist_item(self, profile_key: str, item_key: str, status: str, notes: str = "") -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM installer_checklist WHERE profile_key=? AND item_key=?", [profile_key, item_key])
        if not row:
            raise ValueError(f"Checklist-Item nicht gefunden: {profile_key}/{item_key}")
        self.db.execute("UPDATE installer_checklist SET status=?, notes=? WHERE check_id=?", [status, notes or row.get("notes", ""), row["check_id"]])
        self.audit.log("INSTALL_CHECKLIST_UPDATED", "installer_checklist", row["check_id"], details={"profile_key": profile_key, "item_key": item_key, "status": status})
        return self.db.one("SELECT * FROM installer_checklist WHERE check_id=?", [row["check_id"]])

    # ------------------------------------------------------------------
    # Release file selection/manifests
    # ------------------------------------------------------------------
    def _should_include_release_file(self, root: Path, path: Path, include_runtime_data: bool = False) -> bool:
        rel = path.relative_to(root)
        parts = set(rel.parts)
        if not include_runtime_data and parts & DEFAULT_EXCLUDES:
            return False
        if any(part in {"__pycache__", ".pytest_cache"} for part in rel.parts):
            return False
        if path.suffix.lower() in DEFAULT_EXCLUDE_SUFFIXES:
            return False
        if path.name.startswith("TEST_OUTPUT_BUILD_") or path.name.startswith("DEEP_QA_BUILD_") or path.name.startswith("ZIP_TEST_BUILD_"):
            return False
        if path.name.startswith("RELEASE_MANIFEST_BUILD_"):
            return False
        return True

    def build_distribution_manifest(self, base_dir: str | Path, profile_key: str = "portable_local", include_runtime_data: bool = False) -> Dict[str, Any]:
        base = Path(base_dir).resolve()
        files: List[Dict[str, Any]] = []
        total = 0
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if not self._should_include_release_file(base, path, include_runtime_data=include_runtime_data):
                continue
            rel = path.relative_to(base).as_posix()
            size = path.stat().st_size
            total += size
            files.append({"path": rel, "size": size, "sha256": sha256_file(path)})
        manifest = {
            "build_version": BUILD_VERSION,
            "schema_version": SCHEMA_VERSION,
            "profile_key": profile_key,
            "created_at": now_ts(),
            "python_version": sys.version.split()[0],
            "includes_runtime_data": bool(include_runtime_data),
            "file_count": len(files),
            "total_bytes": total,
            "files": files,
            "guardrails": [
                "runtime_case_data_excluded_by_default",
                "api_keys_env_var_reference_only",
                "no_private_account_bypass",
                "legal_privacy_gates_required_for_productive_cases",
            ],
        }
        manifest_hash = sha256_bytes(json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        manifest["manifest_hash"] = manifest_hash
        return manifest

    def register_artifact(self, build_version: str, artifact_type: str, profile_key: str, path: str | Path, file_count: int = 0, total_bytes: int = 0, status: str = "created", notes: str = "") -> Dict[str, Any]:
        p = Path(path)
        artifact_id = new_id("artifact")
        digest = sha256_file(p) if p.exists() and p.is_file() else ""
        if p.exists() and p.is_file() and not total_bytes:
            total_bytes = p.stat().st_size
        self.db.execute(
            "INSERT INTO release_artifacts(artifact_id,build_version,artifact_type,profile_key,path,sha256,file_count,total_bytes,created_at,status,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            [artifact_id, build_version, artifact_type, profile_key, str(p), digest, file_count, total_bytes, now_ts(), status, notes],
        )
        self.audit.log("RELEASE_ARTIFACT_REGISTERED", "release_artifact", artifact_id, details={"artifact_type": artifact_type, "profile_key": profile_key, "path": str(p), "sha256": digest})
        return self.db.one("SELECT * FROM release_artifacts WHERE artifact_id=?", [artifact_id])

    def create_portable_bundle(self, base_dir: str | Path, out_dir: str | Path, profile_key: str = "portable_local", include_runtime_data: bool = False, notes: str = "") -> Dict[str, Any]:
        base = Path(base_dir).resolve()
        out = Path(out_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        manifest = self.build_distribution_manifest(base, profile_key=profile_key, include_runtime_data=include_runtime_data)
        zip_path = out / f"EagleEye_PersonOSINT_Pro_Build_36_0_{profile_key}.zip"
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("RELEASE_MANIFEST_BUILD_37_0.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
            for item in manifest["files"]:
                zf.write(base / item["path"], arcname=item["path"])
        artifact = self.register_artifact(BUILD_VERSION, "portable_bundle", profile_key, zip_path, manifest["file_count"], zip_path.stat().st_size, notes=notes)
        validation = self.validate_release_package(zip_path, artifact_id=artifact["artifact_id"])
        self.audit.log("PORTABLE_BUNDLE_CREATED", "release_artifact", artifact["artifact_id"], details={"zip_path": str(zip_path), "validation": validation})
        return {"artifact": artifact, "validation": validation, "manifest_hash": manifest["manifest_hash"], "zip_path": str(zip_path)}

    # ------------------------------------------------------------------
    # Migration / rollback / update planning
    # ------------------------------------------------------------------
    def create_migration_plan(self, from_version: str = "30.0", to_version: str = BUILD_VERSION, migration_type: str = "schema_and_release", notes: str = "") -> Dict[str, Any]:
        migration_id = new_id("mig")
        self.db.execute(
            "INSERT INTO migration_plans(migration_id,from_version,to_version,migration_type,status,required_backup,created_at,notes) VALUES(?,?,?,?,?,?,?,?)",
            [migration_id, from_version, to_version, migration_type, "planned", 1, now_ts(), notes],
        )
        default_steps = [
            ("backup", "pending", "Backup/Rollbackpunkt vor Migration erstellen."),
            ("schema_check", "pending", "SQLite schema_version und Integrität prüfen."),
            ("runtime_dirs", "pending", "data/reports/backups getrennt halten."),
            ("launchers", "pending", "Windows-Launcher und Test-Launcher prüfen."),
            ("integrity", "pending", "Integrity Baseline nach Update neu erzeugen."),
        ]
        for step_key, status, message in default_steps:
            self.db.execute("INSERT INTO migration_events(event_id,migration_id,step_key,status,message,created_at) VALUES(?,?,?,?,?,?)", [new_id("migev"), migration_id, step_key, status, message, now_ts()])
        self.audit.log("MIGRATION_PLAN_CREATED", "migration_plan", migration_id, details={"from_version": from_version, "to_version": to_version})
        return self.get_migration_plan(migration_id)

    def get_migration_plan(self, migration_id: str) -> Dict[str, Any]:
        plan = self.db.one("SELECT * FROM migration_plans WHERE migration_id=?", [migration_id])
        if not plan:
            raise ValueError("Migration Plan nicht gefunden")
        plan["events"] = self.db.all("SELECT * FROM migration_events WHERE migration_id=? ORDER BY created_at, step_key", [migration_id])
        return plan

    def record_migration_event(self, migration_id: str, step_key: str, status: str, message: str) -> Dict[str, Any]:
        event_id = new_id("migev")
        self.db.execute("INSERT INTO migration_events(event_id,migration_id,step_key,status,message,created_at) VALUES(?,?,?,?,?,?)", [event_id, migration_id, step_key, status, message, now_ts()])
        if status in {"failed", "blocked"}:
            self.db.execute("UPDATE migration_plans SET status=? WHERE migration_id=?", ["blocked", migration_id])
        self.audit.log("MIGRATION_EVENT_RECORDED", "migration_plan", migration_id, details={"step_key": step_key, "status": status, "message": message})
        return self.get_migration_plan(migration_id)

    def run_migration_readiness(self, base_dir: str | Path, from_version: str = "30.0", to_version: str = BUILD_VERSION) -> Dict[str, Any]:
        base = Path(base_dir)
        db_ok = self.db.one("PRAGMA integrity_check")
        fk = self.db.all("PRAGMA foreign_key_check")
        checks = {
            "schema_version": self.db.one("SELECT value FROM meta WHERE key='schema_version'") or {},
            "db_integrity": db_ok,
            "foreign_key_issues": len(fk),
            "start_launcher": (base / "START_EAGLEEYE_PRO_37_0.bat").exists(),
            "test_launcher": (base / "RUN_TESTS_BUILD_37_0.bat").exists(),
            "readme": (base / "README_BUILD_37_0.md").exists(),
            "docs": (base / "docs" / "ENTERPRISE_PACKAGING_BUILD_37_0.md").exists(),
            "runtime_excluded_policy": True,
        }
        status = "ready" if checks["foreign_key_issues"] == 0 and checks["start_launcher"] and checks["test_launcher"] and checks["readme"] else "review_required"
        self.audit.log("MIGRATION_READINESS_CHECKED", "migration", details={"from_version": from_version, "to_version": to_version, "status": status, "checks": checks})
        return {"status": status, "from_version": from_version, "to_version": to_version, "checks": checks}

    def create_rollback_point(self, base_dir: str | Path, label: str = "pre_update", notes: str = "") -> Dict[str, Any]:
        base = Path(base_dir).resolve()
        out = base / "backups"
        out.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        zip_path = out / f"rollback_Build_36_0_{timestamp}.zip"
        included = []
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for folder_name in ["data", "reports"]:
                folder = base / folder_name
                if not folder.exists():
                    continue
                for p in sorted(folder.rglob("*")):
                    if p.is_file() and "backups" not in p.parts:
                        zf.write(p, arcname=p.relative_to(base).as_posix())
                        included.append(p)
        rollback_id = new_id("rollback")
        digest = sha256_file(zip_path) if zip_path.exists() else ""
        self.db.execute(
            "INSERT INTO rollback_points(rollback_id,build_version,label,backup_path,backup_hash,file_count,total_bytes,created_at,status,notes) VALUES(?,?,?,?,?,?,?,?,?,?)",
            [rollback_id, BUILD_VERSION, label, str(zip_path), digest, len(included), zip_path.stat().st_size if zip_path.exists() else 0, now_ts(), "created", notes],
        )
        self.audit.log("ROLLBACK_POINT_CREATED", "rollback_point", rollback_id, details={"backup_path": str(zip_path), "file_count": len(included), "sha256": digest})
        return self.db.one("SELECT * FROM rollback_points WHERE rollback_id=?", [rollback_id])

    # ------------------------------------------------------------------
    # Validation / dashboard
    # ------------------------------------------------------------------
    def validate_release_package(self, zip_path: str | Path, artifact_id: str = "") -> Dict[str, Any]:
        zip_path = Path(zip_path)
        details: Dict[str, Any] = {"zip_path": str(zip_path), "exists": zip_path.exists(), "sha256": "", "zip_test": "not_run", "manifest_present": False, "manifest_hash": ""}
        status = "fail"
        if zip_path.exists():
            details["sha256"] = sha256_file(zip_path)
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    bad = zf.testzip()
                    details["zip_test"] = "pass" if bad is None else f"bad:{bad}"
                    names = set(zf.namelist())
                    details["manifest_present"] = "RELEASE_MANIFEST_BUILD_37_0.json" in names
                    if details["manifest_present"]:
                        raw = zf.read("RELEASE_MANIFEST_BUILD_37_0.json")
                        manifest = json.loads(raw.decode("utf-8"))
                        details["manifest_hash"] = manifest.get("manifest_hash", "")
                        details["manifest_file_count"] = manifest.get("file_count", 0)
                        runtime_leaks = [n for n in names if n.startswith("data/eagleeye") or n.startswith("data/evidence_vault") or n.startswith("reports/") and not n.endswith(".gitkeep")]
                        details["runtime_leaks"] = runtime_leaks[:20]
                    status = "pass" if details["zip_test"] == "pass" and details["manifest_present"] and not details.get("runtime_leaks") else "review_required"
            except Exception as exc:
                details["error"] = str(exc)
                status = "fail"
        validation_id = new_id("val")
        self.db.execute("INSERT INTO release_validations(validation_id,artifact_id,validation_type,status,details_json,created_at) VALUES(?,?,?,?,?,?)", [validation_id, artifact_id, "zip_integrity_manifest_runtime_leak_check", status, dumps(details), now_ts()])
        self.audit.log("RELEASE_PACKAGE_VALIDATED", "release_validation", validation_id, details={"status": status, "zip_path": str(zip_path)})
        return {"validation_id": validation_id, "status": status, "details": details}

    def dashboard(self) -> Dict[str, Any]:
        profiles = self.db.all("SELECT profile_key,title,target,active FROM deployment_profiles ORDER BY profile_key")
        artifacts = self.db.all("SELECT * FROM release_artifacts ORDER BY created_at DESC LIMIT 20")
        migrations = self.db.all("SELECT * FROM migration_plans ORDER BY created_at DESC LIMIT 10")
        rollbacks = self.db.all("SELECT * FROM rollback_points ORDER BY created_at DESC LIMIT 10")
        validations = self.db.all("SELECT * FROM release_validations ORDER BY created_at DESC LIMIT 20")
        open_checks = self.db.all("SELECT profile_key,item_key,title,severity,status FROM installer_checklist WHERE status!='passed' ORDER BY severity,item_key LIMIT 50")
        status = "packaging_ready" if profiles else "needs_seed"
        if any(v.get("status") == "fail" for v in validations[:5]):
            status = "validation_issue"
        return {
            "status": status,
            "build_version": BUILD_VERSION,
            "profiles": profiles,
            "artifact_count": len(artifacts),
            "latest_artifacts": artifacts[:5],
            "migration_count": len(migrations),
            "latest_migrations": migrations[:5],
            "rollback_count": len(rollbacks),
            "latest_rollbacks": rollbacks[:5],
            "latest_validations": validations[:5],
            "open_checklist_items": open_checks,
        }
