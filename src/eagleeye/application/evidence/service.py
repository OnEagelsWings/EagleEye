from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit, urlunsplit


class EvidenceValidationError(ValueError):
    pass


class EvidenceIntegrityError(RuntimeError):
    pass


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_json(value: Any) -> str:
    return _sha_bytes(_json(value).encode("utf-8"))


def _safe_url(value: str) -> str:
    if not value:
        return ""
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise EvidenceValidationError("source_url must be a public HTTP(S) URL")
    if parts.username or parts.password:
        raise EvidenceValidationError("URL credentials are prohibited")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())[:120]
    if not cleaned or cleaned in {".", ".."}:
        raise EvidenceValidationError("invalid path component")
    return cleaned


class EvidencePreservation121Service:
    """Immutable raw evidence store with reproducible derived artifacts.

    Raw bytes are written once, addressed by SHA-256 and never modified by this
    service. Normalized and derived outputs live in separate layers. Every custody
    transition is append-only and hash chained per package.
    """

    MAX_RAW_BYTES = 100 * 1024 * 1024
    MAX_ARTIFACT_BYTES = 50 * 1024 * 1024
    REDACT_KEYS = {"authorization", "cookie", "set-cookie", "token", "secret", "password", "api_key", "apikey"}

    def __init__(self, db: Any, audit: Any, storage_root: str | Path) -> None:
        self.db = db
        self.audit = audit
        self.root = Path(storage_root).resolve()
        self.raw_root = self.root / "raw"
        self.normalized_root = self.root / "normalized"
        self.derived_root = self.root / "derived"
        self.export_root = self.root / "exports"
        for path in (self.raw_root, self.normalized_root, self.derived_root, self.export_root):
            path.mkdir(parents=True, exist_ok=True)
        from eagleeye.infrastructure.evidence.schema import ensure_evidence_schema_121
        ensure_evidence_schema_121(db)

    def _require_case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise EvidenceValidationError("unknown case")

    def _resolve_under(self, base: Path, relpath: str) -> Path:
        target = (base / relpath).resolve()
        try:
            target.relative_to(base.resolve())
        except ValueError as exc:
            raise EvidenceValidationError("path traversal rejected") from exc
        return target

    @staticmethod
    def _atomic_write_new(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise EvidenceIntegrityError("immutable artifact path already exists")
        fd, temporary = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            try:
                path.chmod(0o444)
            except OSError:
                pass
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def _append_custody(self, package_id: str, case_id: str, event_type: str, actor: str, details: dict[str, Any]) -> str:
        previous = self.db.one(
            "SELECT event_hash FROM evidence_custody_events_121 WHERE package_id=? ORDER BY rowid DESC LIMIT 1",
            (package_id,),
        )
        previous_hash = previous["event_hash"] if previous else "0" * 64
        event_id = _id("ecust121")
        timestamp = _now()
        clean_details = self._sanitize(details)
        event_hash = _sha_json({
            "event_id": event_id, "package_id": package_id, "case_id": case_id,
            "event_type": event_type, "actor": actor, "timestamp": timestamp,
            "details": clean_details, "previous_hash": previous_hash,
        })
        self.db.execute(
            "INSERT INTO evidence_custody_events_121(event_id,package_id,case_id,event_type,actor,timestamp,details_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?,?,?)",
            (event_id, package_id, case_id, event_type, actor, timestamp, _json(clean_details), previous_hash, event_hash),
        )
        return event_id

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): ("[REDACTED]" if str(k).casefold() in self.REDACT_KEYS else self._sanitize(v)) for k, v in value.items()}
        if isinstance(value, list):
            return [self._sanitize(v) for v in value]
        if isinstance(value, tuple):
            return [self._sanitize(v) for v in value]
        if isinstance(value, str) and len(value) > 20000:
            return value[:20000] + "…[TRUNCATED]"
        return value

    def preserve_bytes(
        self, *, case_id: str, title: str, data: bytes, media_type: str,
        captured_by: str, source_url: str = "", source_kind: str = "manual_public_capture",
        source_ref: str = "", metadata: dict[str, Any] | None = None, notes: str = "",
    ) -> dict[str, Any]:
        self._require_case(case_id)
        if not title.strip() or not captured_by.strip() or not media_type.strip():
            raise EvidenceValidationError("title, media_type and captured_by are required")
        if not isinstance(data, bytes) or not data or len(data) > self.MAX_RAW_BYTES:
            raise EvidenceValidationError("raw content is empty or exceeds the size limit")
        safe_url = _safe_url(source_url) if source_url else ""
        captured_at = _now()
        raw_hash = _sha_bytes(data)
        clean_metadata = self._sanitize(metadata or {})
        metadata_record = {
            "title": title.strip(), "source_url": safe_url, "source_kind": source_kind.strip(),
            "source_ref": source_ref.strip(), "media_type": media_type.strip().lower(),
            "byte_size": len(data), "captured_at": captured_at, "captured_by": captured_by.strip(),
            "metadata": clean_metadata,
        }
        metadata_hash = _sha_json(metadata_record)
        package_id = _id("epkg121")
        package_hash = _sha_json({"raw_sha256": raw_hash, "metadata_sha256": metadata_hash, "case_id": case_id})
        suffix = ".bin"
        if media_type.casefold().startswith("application/json"):
            suffix = ".json"
        elif media_type.casefold().startswith("text/"):
            suffix = ".txt"
        elif media_type.casefold() == "application/pdf":
            suffix = ".pdf"
        relpath = f"{_safe_component(case_id)}/{raw_hash[:2]}/{package_id}-{raw_hash}{suffix}"
        path = self._resolve_under(self.raw_root, relpath)
        try:
            with self.db.transaction(immediate=True):
                self._atomic_write_new(path, data)
                self.db.execute(
                    """INSERT INTO evidence_packages_121(package_id,case_id,source_kind,source_ref,title,source_url,media_type,byte_size,raw_relpath,raw_sha256,metadata_sha256,metadata_json,package_sha256,captured_at,captured_by,status,candidate_only,export_allowed,redaction_required,notes)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (package_id, case_id, source_kind.strip(), source_ref.strip(), title.strip(), safe_url,
                     media_type.strip().lower(), len(data), relpath, raw_hash, metadata_hash, _json(clean_metadata), package_hash,
                     captured_at, captured_by.strip(), "preserved", 1, 0, 1, notes.strip()),
                )
                self._append_custody(package_id, case_id, "raw_preserved", captured_by.strip(), {
                    "raw_sha256": raw_hash, "metadata_sha256": metadata_hash, "byte_size": len(data), "source_ref": source_ref,
                })
                self.audit.log("preserve", "evidence_package_121", package_id, case_id, {"raw_sha256": raw_hash, "candidate_only": True})
                package = self.get_package(package_id)
            return package
        except BaseException:
            try:
                if path.exists():
                    path.chmod(0o600)
                    path.unlink()
            except OSError:
                pass
            raise

    def discard_uncommitted_package(self, package: dict[str, Any] | None) -> bool:
        """Best-effort filesystem compensation after an outer transaction rolls back."""
        if not package or not package.get("raw_relpath"):
            return True
        path = self._resolve_under(self.raw_root, str(package["raw_relpath"]))
        try:
            if path.exists():
                path.chmod(0o600)
                path.unlink()
            parent = path.parent
            while parent != self.raw_root and parent.exists():
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
            return True
        except OSError:
            return False

    def preserve_intake_item(self, *, intake_id: str, captured_by: str, title: str = "") -> dict[str, Any]:
        row = self.db.one("SELECT * FROM provider_intake_120 WHERE intake_id=?", (intake_id,))
        if not row:
            raise EvidenceValidationError("unknown provider intake item")
        payload = json.loads(row.get("raw_payload_json") or "{}")
        body = _json(payload).encode("utf-8")
        return self.preserve_bytes(
            case_id=row["case_id"], title=title.strip() or row.get("title") or f"Provider intake {intake_id}",
            data=body, media_type="application/json", captured_by=captured_by,
            source_url=row.get("canonical_url") or row.get("url") or "", source_kind="provider_intake_120",
            source_ref=intake_id, metadata={"provider_key": row.get("provider_key"), "run_id": row.get("run_id"), "candidate_only": True},
        )

    def create_artifact(
        self, *, package_id: str, layer: str, data: bytes, media_type: str,
        created_by: str, parser_name: str, parser_version: str,
        parser_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if layer not in {"normalized", "derived"}:
            raise EvidenceValidationError("layer must be normalized or derived")
        package = self.get_package(package_id)
        if not data or len(data) > self.MAX_ARTIFACT_BYTES:
            raise EvidenceValidationError("artifact is empty or exceeds the size limit")
        if not parser_name.strip() or not parser_version.strip() or not created_by.strip():
            raise EvidenceValidationError("parser identity and creator are required")
        artifact_id = _id("eart121")
        content_hash = _sha_bytes(data)
        relpath = f"{_safe_component(package['case_id'])}/{package_id}/{artifact_id}-{content_hash}.bin"
        base = self.normalized_root if layer == "normalized" else self.derived_root
        path = self._resolve_under(base, relpath)
        self._atomic_write_new(path, data)
        created_at = _now()
        config = self._sanitize(parser_config or {})
        self.db.execute(
            """INSERT INTO evidence_artifacts_121(artifact_id,package_id,case_id,layer,media_type,relpath,content_sha256,byte_size,parser_name,parser_version,parser_config_json,input_sha256,created_at,created_by)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (artifact_id, package_id, package["case_id"], layer, media_type.strip().lower(), relpath,
             content_hash, len(data), parser_name.strip(), parser_version.strip(), _json(config),
             package["raw_sha256"], created_at, created_by.strip()),
        )
        self._append_custody(package_id, package["case_id"], f"{layer}_artifact_created", created_by.strip(), {
            "artifact_id": artifact_id, "content_sha256": content_hash, "parser_name": parser_name,
            "parser_version": parser_version, "parser_config_sha256": _sha_json(config),
        })
        return self.get_artifact(artifact_id)

    def run_parser(
        self, *, package_id: str, layer: str, parser_name: str, parser_version: str,
        parser: Callable[[bytes, dict[str, Any]], bytes | str | dict[str, Any] | list[Any]],
        created_by: str, config: dict[str, Any] | None = None, media_type: str = "application/json",
    ) -> dict[str, Any]:
        package = self.get_package(package_id)
        raw = self.read_raw(package_id)
        cfg = self._sanitize(config or {})
        output = parser(raw, cfg)
        if isinstance(output, bytes):
            data = output
        elif isinstance(output, str):
            data = output.encode("utf-8")
        else:
            data = _json(output).encode("utf-8")
        return self.create_artifact(
            package_id=package_id, layer=layer, data=data, media_type=media_type,
            created_by=created_by, parser_name=parser_name, parser_version=parser_version, parser_config=cfg,
        )

    def get_package(self, package_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_packages_121 WHERE package_id=?", (package_id,))
        if not row:
            raise EvidenceValidationError("unknown evidence package")
        for key in ("candidate_only", "export_allowed", "redaction_required"):
            row[key] = bool(row[key])
        row["metadata"] = json.loads(row.pop("metadata_json") or "{}")
        return row

    def get_artifact(self, artifact_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_artifacts_121 WHERE artifact_id=?", (artifact_id,))
        if not row:
            raise EvidenceValidationError("unknown evidence artifact")
        row["parser_config"] = json.loads(row.pop("parser_config_json") or "{}")
        return row

    def read_raw(self, package_id: str) -> bytes:
        package = self.get_package(package_id)
        path = self._resolve_under(self.raw_root, package["raw_relpath"])
        data = path.read_bytes()
        if _sha_bytes(data) != package["raw_sha256"]:
            raise EvidenceIntegrityError("raw evidence hash mismatch")
        return data

    def verify_package(self, package_id: str) -> dict[str, Any]:
        package = self.get_package(package_id)
        errors: list[str] = []
        metadata_record = {
            "title": package["title"], "source_url": package["source_url"], "source_kind": package["source_kind"],
            "source_ref": package["source_ref"], "media_type": package["media_type"],
            "byte_size": package["byte_size"], "captured_at": package["captured_at"],
            "captured_by": package["captured_by"], "metadata": package["metadata"],
        }
        expected_metadata = _sha_json(metadata_record)
        expected_package = _sha_json({"raw_sha256": package["raw_sha256"], "metadata_sha256": expected_metadata, "case_id": package["case_id"]})
        if expected_metadata != package["metadata_sha256"]:
            errors.append("metadata_hash_mismatch")
        if expected_package != package["package_sha256"]:
            errors.append("package_hash_mismatch")
        try:
            raw = self.read_raw(package_id)
            if len(raw) != int(package["byte_size"]):
                errors.append("raw_size_mismatch")
        except (OSError, EvidenceIntegrityError) as exc:
            errors.append(str(exc))
        artifacts = self.db.all("SELECT * FROM evidence_artifacts_121 WHERE package_id=? ORDER BY created_at,artifact_id", (package_id,))
        for artifact in artifacts:
            base = self.normalized_root if artifact["layer"] == "normalized" else self.derived_root
            path = self._resolve_under(base, artifact["relpath"])
            try:
                data = path.read_bytes()
                if _sha_bytes(data) != artifact["content_sha256"] or len(data) != int(artifact["byte_size"]):
                    errors.append(f"artifact_mismatch:{artifact['artifact_id']}")
            except OSError:
                errors.append(f"artifact_missing:{artifact['artifact_id']}")
        events = self.db.all("SELECT * FROM evidence_custody_events_121 WHERE package_id=? ORDER BY rowid", (package_id,))
        previous = "0" * 64
        for event in events:
            details = json.loads(event["details_json"])
            expected = _sha_json({
                "event_id": event["event_id"], "package_id": event["package_id"], "case_id": event["case_id"],
                "event_type": event["event_type"], "actor": event["actor"], "timestamp": event["timestamp"],
                "details": details, "previous_hash": previous,
            })
            if event["previous_hash"] != previous or event["event_hash"] != expected:
                errors.append(f"custody_chain_mismatch:{event['event_id']}")
            previous = event["event_hash"]
        result = {"package_id": package_id, "ok": not errors, "errors": errors, "artifact_count": len(artifacts), "custody_event_count": len(events)}
        self.audit.log("verify", "evidence_package_121", package_id, package["case_id"], result)
        return result

    def set_export_policy(self, *, package_id: str, export_allowed: bool, redaction_required: bool, actor: str, reason: str) -> None:
        package = self.get_package(package_id)
        if len(reason.strip()) < 10:
            raise EvidenceValidationError("substantive reason required")
        self.db.execute(
            "UPDATE evidence_packages_121 SET export_allowed=?,redaction_required=? WHERE package_id=?",
            (int(export_allowed), int(redaction_required), package_id),
        )
        self._append_custody(package_id, package["case_id"], "export_policy_changed", actor, {
            "export_allowed": export_allowed, "redaction_required": redaction_required, "reason": reason,
        })

    def export_packages(self, *, case_id: str, package_ids: Iterable[str], created_by: str, redaction_profile: str = "client_safe") -> dict[str, Any]:
        self._require_case(case_id)
        ids = list(dict.fromkeys(package_ids))
        if not ids:
            raise EvidenceValidationError("at least one package is required")
        packages = [self.get_package(pid) for pid in ids]
        for package in packages:
            if package["case_id"] != case_id:
                raise EvidenceValidationError("cross-case export rejected")
            if not package["export_allowed"]:
                raise EvidenceValidationError(f"package not approved for export: {package['package_id']}")
            verification = self.verify_package(package["package_id"])
            if not verification["ok"]:
                raise EvidenceIntegrityError(f"package failed integrity verification: {package['package_id']}")
        export_id = _id("eexp121")
        manifest: dict[str, Any] = {
            "format": "eagleeye-evidence-export-121", "export_id": export_id, "case_id": case_id,
            "created_at": _now(), "created_by": created_by, "redaction_profile": redaction_profile,
            "packages": [],
        }
        target = self.export_root / f"{export_id}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for package in packages:
                raw = self.read_raw(package["package_id"])
                entry_name = f"packages/{package['package_id']}/raw/{Path(package['raw_relpath']).name}"
                archive.writestr(entry_name, raw)
                public_record = {
                    "package_id": package["package_id"], "title": package["title"], "media_type": package["media_type"],
                    "byte_size": package["byte_size"], "raw_sha256": package["raw_sha256"],
                    "package_sha256": package["package_sha256"], "captured_at": package["captured_at"],
                    "source_url": "[REDACTED]" if package["redaction_required"] else package["source_url"],
                    "raw_entry": entry_name,
                }
                manifest["packages"].append(public_record)
            manifest_bytes = _json(manifest).encode("utf-8")
            archive.writestr("manifest.json", manifest_bytes)
            archive.writestr("manifest.sha256", _sha_bytes(manifest_bytes) + "  manifest.json\n")
        manifest_hash = _sha_json(manifest)
        self.db.execute(
            "INSERT INTO evidence_exports_121(export_id,case_id,export_relpath,manifest_sha256,package_count,redaction_profile,created_at,created_by) VALUES(?,?,?,?,?,?,?,?)",
            (export_id, case_id, target.name, manifest_hash, len(packages), redaction_profile, manifest["created_at"], created_by),
        )
        for package in packages:
            self._append_custody(package["package_id"], case_id, "exported", created_by, {"export_id": export_id, "manifest_sha256": manifest_hash})
        return {"export_id": export_id, "path": str(target), "manifest_sha256": manifest_hash, "package_count": len(packages)}

    def verify_export(self, export_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_exports_121 WHERE export_id=?", (export_id,))
        if not row:
            raise EvidenceValidationError("unknown evidence export")
        path = self._resolve_under(self.export_root, row["export_relpath"])
        errors: list[str] = []
        try:
            with zipfile.ZipFile(path) as archive:
                if archive.testzip() is not None:
                    errors.append("zip_crc_failure")
                manifest_bytes = archive.read("manifest.json")
                declared = archive.read("manifest.sha256").decode("utf-8").split()[0]
                if _sha_bytes(manifest_bytes) != declared:
                    errors.append("manifest_file_hash_mismatch")
                manifest = json.loads(manifest_bytes)
                if _sha_json(manifest) != row["manifest_sha256"]:
                    errors.append("manifest_database_hash_mismatch")
                if manifest.get("case_id") != row["case_id"] or len(manifest.get("packages", [])) != int(row["package_count"]):
                    errors.append("manifest_scope_mismatch")
                for package in manifest.get("packages", []):
                    data = archive.read(package["raw_entry"])
                    if _sha_bytes(data) != package["raw_sha256"]:
                        errors.append(f"raw_export_hash_mismatch:{package['package_id']}")
        except (OSError, KeyError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
            errors.append(f"export_read_error:{type(exc).__name__}")
        return {"export_id": export_id, "ok": not errors, "errors": errors}
