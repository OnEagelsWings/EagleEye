from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import sqlite3

BUILD = "453.0"
POLICY_ID = "phase20.recovery-basis.v453"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value):
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class RecoveryBasis453:
    def __init__(self, db, audit, *, recovery_dir, identity_service=None, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.identity_service = identity_service
        self.recovery_dir = Path(recovery_dir).resolve()
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.recovery_dir.chmod(0o700)
        except OSError:
            pass
        self.actor = actor
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS recovery_point_453(
          recovery_id TEXT PRIMARY KEY,
          label TEXT NOT NULL,
          database_file TEXT NOT NULL,
          manifest_file TEXT NOT NULL,
          manifest_sha256 TEXT NOT NULL,
          database_sha256 TEXT NOT NULL,
          database_bytes INTEGER NOT NULL,
          sqlite_quick_check TEXT NOT NULL,
          build TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          record_hash TEXT NOT NULL
        );
        """)
        self.db.conn.commit()

    def _identity(self, identity):
        if not isinstance(identity, dict):
            raise PermissionError("active identity required")
        username = str(identity.get("username") or "").strip()
        user_id = str(identity.get("user_id") or "").strip()
        if not username or not user_id:
            raise PermissionError("canonical active identity required")
        current = identity
        if self.identity_service is not None:
            try:
                current = self.identity_service.public_user(username)
            except (KeyError, ValueError):
                raise PermissionError("canonical active identity required") from None
            if not current.get("active") or str(current.get("user_id") or "") != user_id:
                raise PermissionError("canonical active identity required")
        if current.get("global_role") != "system_administrator":
            raise PermissionError("system administrator role required")
        return username

    def _record_hash(self, record):
        return _hash({k: record[k] for k in record if k != "record_hash"})

    def _inside_root(self, relative):
        path = (self.recovery_dir / relative).resolve()
        if self.recovery_dir not in path.parents and path != self.recovery_dir:
            raise ValueError("recovery path escaped managed directory")
        return path

    def _quick_check(self, path):
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            row = connection.execute("PRAGMA quick_check").fetchone()
            return str(row[0] if row else "")
        finally:
            connection.close()

    def create_recovery_point(self, *, identity, label="", confirmation=""):
        if confirmation != "RECOVERY 453 CREATE":
            raise PermissionError("explicit recovery-point confirmation required")
        actor = self._identity(identity)
        recovery_id = "rec453_" + secrets.token_hex(10)
        target_dir = self.recovery_dir / recovery_id
        target_dir.mkdir(parents=True, exist_ok=False)
        try:
            target_dir.chmod(0o700)
        except OSError:
            pass
        temp_db = target_dir / "eagleeye.sqlite.tmp"
        final_db = target_dir / "eagleeye.sqlite"
        manifest_path = target_dir / "manifest.json"
        try:
            destination = sqlite3.connect(str(temp_db))
            try:
                lock = getattr(self.db, "_lock", None)
                if lock is None:
                    self.db.conn.backup(destination)
                else:
                    with lock:
                        self.db.conn.backup(destination)
            finally:
                destination.close()
            quick = self._quick_check(temp_db)
            if quick != "ok":
                raise RuntimeError("recovery snapshot failed SQLite quick_check")
            temp_db.replace(final_db)
            try:
                final_db.chmod(0o600)
            except OSError:
                pass
            digest = _sha_file(final_db)
            size = final_db.stat().st_size
            manifest = {
                "build": BUILD,
                "recovery_id": recovery_id,
                "database_file": "eagleeye.sqlite",
                "database_sha256": digest,
                "database_bytes": size,
                "sqlite_quick_check": quick,
                "created_by": actor,
                "created_at": _now(),
                "active_database_overwritten": False,
                "restore_requires_explicit_staging": True,
            }
            temp_manifest = manifest_path.with_suffix(".tmp")
            temp_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_manifest.replace(manifest_path)
            try:
                manifest_path.chmod(0o600)
            except OSError:
                pass
            manifest_digest = _sha_file(manifest_path)
            record = {
                "recovery_id": recovery_id,
                "label": str(label or "").strip()[:200],
                "database_file": f"{recovery_id}/eagleeye.sqlite",
                "manifest_file": f"{recovery_id}/manifest.json",
                "manifest_sha256": manifest_digest,
                "database_sha256": digest,
                "database_bytes": size,
                "sqlite_quick_check": quick,
                "build": BUILD,
                "created_by": actor,
                "created_at": manifest["created_at"],
            }
            record["record_hash"] = self._record_hash(record)
            self.db.execute("INSERT INTO recovery_point_453 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", tuple(record.values()))
            self.audit.log(
                "recovery_point_created_453", "recovery_point_453", recovery_id, "",
                {"label": record["label"], "database_sha256": digest, "database_bytes": size},
            )
            return {**record, "verified": True, "snapshot_precedes_catalog_record": True}
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

    def get(self, recovery_id):
        row = self.db.one("SELECT * FROM recovery_point_453 WHERE recovery_id=?", (recovery_id,))
        if not row:
            raise KeyError("recovery point not found")
        return dict(row)

    def verify(self, recovery_id):
        record = self.get(recovery_id)
        database_path = self._inside_root(record["database_file"])
        manifest_path = self._inside_root(record["manifest_file"])
        errors = []
        if not database_path.is_file():
            errors.append("database_missing")
        if not manifest_path.is_file():
            errors.append("manifest_missing")
        digest = _sha_file(database_path) if database_path.is_file() else ""
        if digest and digest != record["database_sha256"]:
            errors.append("database_hash_mismatch")
        quick = ""
        if database_path.is_file():
            try:
                quick = self._quick_check(database_path)
            except sqlite3.Error:
                quick = "error"
            if quick != "ok":
                errors.append("sqlite_quick_check_failed")
        if manifest_path.is_file():
            if _sha_file(manifest_path) != record["manifest_sha256"]:
                errors.append("manifest_file_hash_mismatch")
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest.get("database_sha256") != record["database_sha256"]:
                    errors.append("manifest_hash_mismatch")
                if manifest.get("recovery_id") != recovery_id:
                    errors.append("manifest_recovery_id_mismatch")
            except (OSError, ValueError, json.JSONDecodeError):
                errors.append("manifest_invalid")
        if self._record_hash(record) != record["record_hash"]:
            errors.append("catalog_record_hash_mismatch")
        return {
            "build": BUILD,
            "recovery_id": recovery_id,
            "valid": not errors,
            "errors": errors,
            "database_sha256": digest,
            "sqlite_quick_check": quick,
            "active_database_overwritten": False,
        }

    def stage_restore(self, *, identity, recovery_id, confirmation=""):
        if confirmation != "RECOVERY 453 STAGE":
            raise PermissionError("explicit restore staging confirmation required")
        actor = self._identity(identity)
        verified = self.verify(recovery_id)
        if not verified["valid"]:
            raise RuntimeError("recovery point failed verification")
        record = self.get(recovery_id)
        source = self._inside_root(record["database_file"])
        staged_dir = self.recovery_dir / "staged"
        staged_dir.mkdir(parents=True, exist_ok=True)
        try:
            staged_dir.chmod(0o700)
        except OSError:
            pass
        staged = staged_dir / f"{recovery_id}.sqlite"
        temp = staged.with_suffix(".tmp")
        shutil.copy2(source, temp)
        if _sha_file(temp) != record["database_sha256"] or self._quick_check(temp) != "ok":
            temp.unlink(missing_ok=True)
            raise RuntimeError("staged restore verification failed")
        temp.replace(staged)
        try:
            staged.chmod(0o600)
        except OSError:
            pass
        self.audit.log(
            "restore_staged_453", "recovery_point_453", recovery_id, "",
            {"staged_file": str(staged), "requested_by": actor, "active_database_overwritten": False},
        )
        return {
            "build": BUILD,
            "recovery_id": recovery_id,
            "staged_file": str(staged),
            "database_sha256": record["database_sha256"],
            "verified": True,
            "active_database_overwritten": False,
            "restart_and_explicit_replace_required": True,
        }

    def list_points(self):
        return [dict(row) for row in self.db.all(
            "SELECT * FROM recovery_point_453 ORDER BY created_at DESC, recovery_id DESC"
        )]

    def status(self):
        rows = self.list_points()
        valid = 0
        for row in rows[:20]:
            try:
                valid += int(self.verify(row["recovery_id"])["valid"])
            except Exception:
                pass
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "recovery_points": len(rows),
            "recent_verified_points": valid,
            "sqlite_online_backup": True,
            "sha256_manifest": True,
            "sqlite_quick_check": True,
            "staged_restore": True,
            "automatic_live_database_overwrite": False,
            "rollback_execution": "MANUAL_RESTART_REQUIRED",
            "production_release_ready": False,
        }
