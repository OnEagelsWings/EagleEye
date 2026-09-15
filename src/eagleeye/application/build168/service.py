from __future__ import annotations

import csv
import hashlib
import html
import json
import mimetypes
import re
from pathlib import Path
from typing import Any, Mapping

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


class Build168AuthorityHandoverService:
    BUILD = "168.0"
    MISSION = "Authority dossier, chain of custody, export validation and documented handover"
    SENSITIVE = re.compile(r"(password|token|secret|api[_-]?key|authorization|cookie|session)", re.I)
    ROLES = {"analyst", "supervisor"}
    DECISIONS = {"approved", "rejected"}
    CUSTODY_EVENTS = {"registered", "accessed", "copied_for_export", "transferred", "returned", "sealed", "verified"}

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        build160: Any | None = None,
        build166: Any | None = None,
        build167: Any | None = None,
        actor: str = "system",
        export_root: str | Path | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.build160 = build160
        self.build166 = build166
        self.build167 = build167
        self.actor = actor
        db_path = Path(getattr(db, "path", getattr(db, "db_path", "eagleeye.db")))
        self.export_root = Path(export_root) if export_root else db_path.parent / "exports" / "build168"
        self.export_root.mkdir(parents=True, exist_ok=True)
        self._ensure_profiles()

    def register_evidence(
        self,
        *,
        case_id: str,
        item_type: str,
        source_ref: str,
        collected_by: str,
        confirmation: str,
        file_path: str | Path | None = None,
        content_sha256: str | None = None,
        byte_size: int = 0,
        media_type: str | None = None,
        classification: str = "RESTRICTED - OSINT",
        provenance: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if confirmation != f"EVIDENCE 168 {case_id} REGISTRIEREN":
            raise PermissionError("explicit evidence registration approval required")
        if not case_id.strip() or not source_ref.strip() or not collected_by.strip():
            raise ValueError("case, source and collector required")
        prov = dict(provenance or {})
        if self.SENSITIVE.search(_canon(prov)):
            raise ValueError("secret or session material prohibited")
        resolved_path: Path | None = None
        if file_path is not None:
            resolved_path = Path(file_path).resolve()
            if not resolved_path.is_file():
                raise FileNotFoundError(resolved_path)
            actual_hash, actual_size = _file_hash(resolved_path)
            content_sha256 = content_sha256 or actual_hash
            byte_size = actual_size
            if content_sha256.lower() != actual_hash:
                raise ValueError("provided hash does not match file")
            media_type = media_type or mimetypes.guess_type(resolved_path.name)[0] or "application/octet-stream"
        if not content_sha256 or not re.fullmatch(r"[0-9a-fA-F]{64}", content_sha256):
            raise ValueError("valid SHA-256 required")
        evidence_id = new_id("evidence168")
        collected_at = now_ts()
        payload = {
            "evidence_id": evidence_id,
            "case_id": case_id,
            "item_type": item_type,
            "source_ref": source_ref,
            "content_sha256": content_sha256.lower(),
            "byte_size": int(byte_size),
            "classification": classification,
            "provenance": prov,
        }
        self.db.execute(
            "INSERT INTO evidence_registry_168 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                evidence_id,
                case_id,
                item_type[:100],
                source_ref,
                str(resolved_path) if resolved_path else None,
                content_sha256.lower(),
                int(byte_size),
                media_type or "application/octet-stream",
                classification,
                collected_by,
                collected_at,
                dumps(prov),
                "needs_review",
                _hash(payload),
            ),
        )
        self._custody(evidence_id, "registered", collected_by, "Initial registration", None, collected_by)
        self.audit.log(
            "evidence_registered_168",
            "evidence168",
            evidence_id,
            case_id,
            {"sha256": content_sha256.lower(), "classification": classification},
        )
        return self.evidence(evidence_id)

    def record_custody(
        self,
        evidence_id: str,
        *,
        event_type: str,
        actor: str,
        purpose: str,
        from_custodian: str | None = None,
        to_custodian: str | None = None,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"CUSTODY 168 {evidence_id} ERFASSEN":
            raise PermissionError("explicit custody approval required")
        return self._custody(evidence_id, event_type, actor, purpose, from_custodian, to_custodian)

    def _custody(
        self,
        evidence_id: str,
        event_type: str,
        actor: str,
        purpose: str,
        from_custodian: str | None,
        to_custodian: str | None,
    ) -> dict[str, Any]:
        if event_type not in self.CUSTODY_EVENTS:
            raise ValueError("invalid custody event")
        if not self.db.one("SELECT evidence_id FROM evidence_registry_168 WHERE evidence_id=?", (evidence_id,)):
            raise KeyError("evidence not found")
        previous_row = self.db.one(
            "SELECT sequence_no,payload_sha256 FROM custody_events_168 WHERE evidence_id=? ORDER BY sequence_no DESC LIMIT 1",
            (evidence_id,),
        )
        sequence_no = int(previous_row["sequence_no"]) + 1 if previous_row else 1
        previous_hash = previous_row["payload_sha256"] if previous_row else None
        event_id = new_id("custody168")
        occurred_at = now_ts()
        payload = {
            "event_id": event_id,
            "evidence_id": evidence_id,
            "sequence_no": sequence_no,
            "event_type": event_type,
            "actor": actor,
            "purpose": purpose,
            "from": from_custodian,
            "to": to_custodian,
            "occurred_at": occurred_at,
            "previous_sha256": previous_hash,
        }
        payload_hash = _hash(payload)
        self.db.execute(
            "INSERT INTO custody_events_168 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                event_id,
                evidence_id,
                sequence_no,
                event_type,
                actor,
                purpose,
                from_custodian,
                to_custodian,
                occurred_at,
                previous_hash,
                payload_hash,
            ),
        )
        return {**payload, "payload_sha256": payload_hash}

    def build_package(
        self,
        *,
        case_id: str,
        title: str,
        profile_key: str = "authority_standard",
        created_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"AKTE 168 {case_id} ERSTELLEN":
            raise PermissionError("explicit dossier export approval required")
        profile = self.db.one("SELECT * FROM export_profiles_168 WHERE profile_key=? AND active=1", (profile_key,))
        if not profile:
            raise KeyError("export profile not found")
        package_id = new_id("package168")
        export_dir = self.export_root / package_id
        export_dir.mkdir(parents=True, exist_ok=False)
        evidence = [dict(row) for row in self.db.all("SELECT * FROM evidence_registry_168 WHERE case_id=? ORDER BY collected_at", (case_id,))]
        for item in evidence:
            item["provenance"] = loads(item.pop("provenance_json"), {})
            item["custody"] = [
                dict(row)
                for row in self.db.all(
                    "SELECT * FROM custody_events_168 WHERE evidence_id=? ORDER BY sequence_no",
                    (item["evidence_id"],),
                )
            ]
        previous = self.db.one(
            "SELECT manifest_sha256 FROM authority_packages_168 WHERE case_id=? ORDER BY created_at DESC LIMIT 1",
            (case_id,),
        )
        manifest = {
            "format": "EagleEye Authority Dossier 168",
            "package_id": package_id,
            "case_id": case_id,
            "title": title,
            "profile_key": profile_key,
            "classification": "RESTRICTED - AUTHORITY HANDOVER",
            "created_by": created_by,
            "created_at": now_ts(),
            "previous_package_sha256": previous["manifest_sha256"] if previous else None,
            "case_summary": self._case_summary(case_id),
            "evidence_inventory": evidence,
            "methodological_notice": "OSINT intelligence leads are not findings of guilt. Identities, allegations and evidentiary value require independent authority verification.",
            "trusted_timestamp": {
                "present": False,
                "standard_reference": "RFC 3161",
                "note": "No external timestamp authority invoked by default.",
            },
        }
        (export_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_inventory(export_dir / "evidence_inventory.csv", evidence)
        (export_dir / "report.html").write_text(self._html_report(manifest), encoding="utf-8")
        package_files: list[dict[str, Any]] = []
        for path in sorted(export_dir.iterdir()):
            if path.is_file():
                digest, size = _file_hash(path)
                package_files.append({"name": path.name, "sha256": digest, "bytes": size})
        manifest["package_files"] = package_files
        manifest_hash = _hash(manifest)
        (export_dir / "package_index.json").write_text(
            json.dumps({"manifest_sha256": manifest_hash, "files": package_files}, indent=2),
            encoding="utf-8",
        )
        self.db.execute(
            "INSERT INTO authority_packages_168 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                package_id,
                case_id,
                title[:500],
                profile_key,
                manifest["classification"],
                "draft",
                str(export_dir),
                dumps(manifest),
                manifest_hash,
                created_by,
                manifest["created_at"],
                None,
                "pending",
                manifest["previous_package_sha256"],
            ),
        )
        for item in evidence:
            self._custody(
                item["evidence_id"],
                "copied_for_export",
                created_by,
                f"Included in authority package {package_id}",
                created_by,
                "export-package",
            )
        self.audit.log(
            "authority_package_created_168",
            "authority_package",
            package_id,
            case_id,
            {"profile_key": profile_key, "evidence_count": len(evidence), "manifest_sha256": manifest_hash},
        )
        return self.package(package_id)

    def validate_package(self, package_id: str, *, validated_by: str = "validator") -> dict[str, Any]:
        package = self.package(package_id)
        export_dir = Path(package["export_dir"])
        manifest = package["manifest"]
        checks: list[dict[str, Any]] = [{"check": "manifest_hash", "ok": _hash(manifest) == package["manifest_sha256"]}]
        for entry in manifest.get("package_files", []):
            path = export_dir / entry["name"]
            actual_hash = None
            ok = path.is_file()
            if ok:
                actual_hash, _ = _file_hash(path)
                ok = actual_hash == entry["sha256"]
            checks.append({"check": "file_hash", "file": entry["name"], "ok": ok, "actual_sha256": actual_hash})
        for item in manifest.get("evidence_inventory", []):
            checks.append(
                {
                    "check": "custody_chain",
                    "evidence_id": item["evidence_id"],
                    "ok": self.verify_custody_chain(item["evidence_id"])["valid"],
                }
            )
        status = "passed" if all(check["ok"] for check in checks) else "failed"
        validation_id = new_id("validation168")
        validated_at = now_ts()
        payload = {
            "validation_id": validation_id,
            "package_id": package_id,
            "status": status,
            "checks": checks,
            "validated_by": validated_by,
            "validated_at": validated_at,
        }
        self.db.execute(
            "INSERT INTO package_validations_168 VALUES(?,?,?,?,?,?,?)",
            (validation_id, package_id, status, dumps(checks), validated_by, validated_at, _hash(payload)),
        )
        self.db.execute(
            "UPDATE authority_packages_168 SET validation_status=?,validated_at=?,status=? WHERE package_id=?",
            (status, validated_at, "validated" if status == "passed" else "invalid", package_id),
        )
        return {**payload, "payload_sha256": _hash(payload)}

    def approve(
        self,
        package_id: str,
        *,
        role: str,
        reviewer: str,
        decision: str = "approved",
        note: str = "",
        confirmation: str,
    ) -> dict[str, Any]:
        if role not in self.ROLES or decision not in self.DECISIONS:
            raise ValueError("invalid role or decision")
        if confirmation != f"FREIGABE 168 {package_id} {role.upper()}":
            raise PermissionError("explicit role approval required")
        package = self.package(package_id)
        if package["validation_status"] != "passed":
            raise ValueError("package must pass validation before approval")
        approval_id = new_id("approval168")
        payload = {
            "approval_id": approval_id,
            "package_id": package_id,
            "role": role,
            "reviewer": reviewer,
            "decision": decision,
            "note": note,
            "approved_at": now_ts(),
        }
        self.db.execute(
            "INSERT OR REPLACE INTO handover_approvals_168 VALUES(?,?,?,?,?,?,?,?)",
            (approval_id, package_id, role, reviewer, decision, note, payload["approved_at"], _hash(payload)),
        )
        approvals = self.db.all("SELECT role,decision FROM handover_approvals_168 WHERE package_id=?", (package_id,))
        approved_roles = {row["role"] for row in approvals if row["decision"] == "approved"}
        ready = self.ROLES <= approved_roles
        self.db.execute("UPDATE authority_packages_168 SET status=? WHERE package_id=?", ("approved" if ready else "review", package_id))
        return {**payload, "payload_sha256": _hash(payload), "package_ready": ready}

    def record_handover(
        self,
        package_id: str,
        *,
        recipient_agency: str,
        handed_over_by: str,
        transfer_method: str,
        receipt_note: str,
        recipient_reference: str | None = None,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"UEBERGABE 168 {package_id} DOKUMENTIEREN":
            raise PermissionError("explicit handover approval required")
        package = self.package(package_id)
        if package["status"] != "approved":
            raise ValueError("dual approval required before handover")
        previous = self.db.one(
            "SELECT payload_sha256 FROM handover_receipts_168 WHERE package_id=? ORDER BY handed_over_at DESC LIMIT 1",
            (package_id,),
        )
        receipt_id = new_id("receipt168")
        payload = {
            "receipt_id": receipt_id,
            "package_id": package_id,
            "recipient_agency": recipient_agency,
            "recipient_reference": recipient_reference,
            "handed_over_by": handed_over_by,
            "handed_over_at": now_ts(),
            "transfer_method": transfer_method,
            "receipt_note": receipt_note,
            "package_sha256": package["manifest_sha256"],
            "previous_sha256": previous["payload_sha256"] if previous else None,
        }
        self.db.execute(
            "INSERT INTO handover_receipts_168 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                receipt_id,
                package_id,
                recipient_agency,
                recipient_reference,
                handed_over_by,
                payload["handed_over_at"],
                transfer_method,
                receipt_note,
                package["manifest_sha256"],
                payload["previous_sha256"],
                _hash(payload),
            ),
        )
        self.db.execute("UPDATE authority_packages_168 SET status='handed_over' WHERE package_id=?", (package_id,))
        self.audit.log(
            "authority_package_handed_over_168",
            "authority_package",
            package_id,
            package["case_id"],
            {"recipient_agency": recipient_agency, "transfer_method": transfer_method},
        )
        return {**payload, "payload_sha256": _hash(payload)}

    def verify_custody_chain(self, evidence_id: str) -> dict[str, Any]:
        rows = [dict(row) for row in self.db.all("SELECT * FROM custody_events_168 WHERE evidence_id=? ORDER BY sequence_no", (evidence_id,))]
        previous_hash = None
        errors: list[str] = []
        for expected_sequence, row in enumerate(rows, 1):
            payload = {
                "event_id": row["event_id"],
                "evidence_id": row["evidence_id"],
                "sequence_no": row["sequence_no"],
                "event_type": row["event_type"],
                "actor": row["actor"],
                "purpose": row["purpose"],
                "from": row["from_custodian"],
                "to": row["to_custodian"],
                "occurred_at": row["occurred_at"],
                "previous_sha256": row["previous_sha256"],
            }
            if row["sequence_no"] != expected_sequence:
                errors.append(f"sequence:{expected_sequence}")
            if row["previous_sha256"] != previous_hash:
                errors.append(f"previous:{expected_sequence}")
            if _hash(payload) != row["payload_sha256"]:
                errors.append(f"hash:{expected_sequence}")
            previous_hash = row["payload_sha256"]
        return {
            "evidence_id": evidence_id,
            "events": len(rows),
            "valid": bool(rows) and not errors,
            "errors": errors,
            "head_sha256": previous_hash,
        }

    def evidence(self, evidence_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_registry_168 WHERE evidence_id=?", (evidence_id,))
        if not row:
            raise KeyError("evidence not found")
        result = dict(row)
        result["provenance"] = loads(result.pop("provenance_json"), {})
        return result

    def package(self, package_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM authority_packages_168 WHERE package_id=?", (package_id,))
        if not row:
            raise KeyError("package not found")
        result = dict(row)
        result["manifest"] = loads(result.pop("manifest_json"), {})
        return result

    def dashboard(self, case_id: str) -> dict[str, Any]:
        evidence_count = self.db.one("SELECT COUNT(*) AS n FROM evidence_registry_168 WHERE case_id=?", (case_id,))["n"]
        packages = [
            dict(row)
            for row in self.db.all(
                "SELECT package_id,title,status,validation_status,created_at,manifest_sha256 FROM authority_packages_168 WHERE case_id=? ORDER BY created_at DESC",
                (case_id,),
            )
        ]
        return {
            "case_id": case_id,
            "evidence_count": evidence_count,
            "packages": packages,
            "requirements": [
                "evidence_inventory",
                "chain_of_custody",
                "hash_validation",
                "analyst_approval",
                "supervisor_approval",
                "handover_receipt",
            ],
            "limitations": [
                "OSINT lead is not a judicial finding",
                "Authority must independently assess admissibility and legal basis",
                "No trusted external timestamp unless separately configured",
            ],
        }

    def _case_summary(self, case_id: str) -> dict[str, Any]:
        summary: dict[str, Any] = {"case_id": case_id, "missing_person": None, "crime_threat": None, "cockpit": None}
        try:
            if self.build166:
                row = self.db.one("SELECT workflow_id FROM missing_person_cases_166 WHERE case_id=?", (case_id,))
                summary["missing_person"] = self.build166.situation(row["workflow_id"]) if row else None
        except Exception as exc:
            summary["missing_person"] = {"unavailable": type(exc).__name__}
        try:
            if self.build167:
                row = self.db.one("SELECT workflow_id FROM crime_threat_cases_167 WHERE case_id=?", (case_id,))
                summary["crime_threat"] = self.build167.situation(row["workflow_id"]) if row else None
        except Exception as exc:
            summary["crime_threat"] = {"unavailable": type(exc).__name__}
        try:
            summary["cockpit"] = self.build160.build_cockpit(case_id) if self.build160 else None
        except Exception as exc:
            summary["cockpit"] = {"unavailable": type(exc).__name__}
        return summary

    def _ensure_profiles(self) -> None:
        profiles = [
            ("authority_standard", "Behördenakte Standard", 0, 1, 1, 1, "Analytische Akte mit Evidenzinventar, Provenienz und Redaktionspflicht."),
            ("authority_minimized", "Behördenakte datensparsam", 0, 1, 0, 1, "Minimierte Übergabe ohne unnötige personenbezogene Rohdaten."),
            ("forensic_inventory", "Forensisches Inventar", 1, 0, 1, 0, "Technisches Inventar und Chain-of-Custody-Nachweis; Rohmaterial nur als Referenz."),
        ]
        for key, title, raw, analysis, personal, redact, description in profiles:
            payload = {
                "profile_key": key,
                "title": title,
                "include_raw_material": raw,
                "include_analysis": analysis,
                "include_personal_data": personal,
                "redaction_required": redact,
                "description": description,
            }
            self.db.execute(
                "INSERT OR IGNORE INTO export_profiles_168 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (new_id("profile168"), key, title, raw, analysis, personal, redact, description, 1, now_ts(), _hash(payload)),
            )

    @staticmethod
    def _write_inventory(path: Path, evidence: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["evidence_id", "item_type", "source_ref", "sha256", "bytes", "media_type", "classification", "collected_by", "collected_at", "review_status"])
            for item in evidence:
                writer.writerow([
                    item["evidence_id"],
                    item["item_type"],
                    item["source_ref"],
                    item["content_sha256"],
                    item["byte_size"],
                    item["media_type"],
                    item["classification"],
                    item["collected_by"],
                    item["collected_at"],
                    item["review_status"],
                ])

    @staticmethod
    def _html_report(manifest: Mapping[str, Any]) -> str:
        rows = "".join(
            f"<tr><td>{html.escape(item['evidence_id'])}</td><td>{html.escape(item['item_type'])}</td><td><code>{html.escape(item['content_sha256'])}</code></td><td>{html.escape(item['review_status'])}</td></tr>"
            for item in manifest["evidence_inventory"]
        )
        summary = html.escape(json.dumps(manifest["case_summary"], ensure_ascii=False, indent=2, default=str))
        return (
            "<!doctype html><html lang='de'><meta charset='utf-8'>"
            f"<title>{html.escape(manifest['title'])}</title>"
            "<style>body{font:14px Arial;max-width:1100px;margin:35px auto;line-height:1.45}table{border-collapse:collapse;width:100%}td,th{border:1px solid #aaa;padding:6px;text-align:left}code{font-size:11px;word-break:break-all}.warn{border:2px solid #555;padding:12px}</style>"
            f"<h1>{html.escape(manifest['title'])}</h1>"
            f"<p><b>Fall:</b> {html.escape(manifest['case_id'])}<br><b>Klassifikation:</b> {html.escape(manifest['classification'])}<br><b>Erstellt:</b> {html.escape(manifest['created_at'])}</p>"
            f"<div class='warn'>{html.escape(manifest['methodological_notice'])}</div>"
            f"<h2>Evidenzinventar</h2><table><tr><th>ID</th><th>Typ</th><th>SHA-256</th><th>Review</th></tr>{rows}</table>"
            f"<h2>Provenienz und Fallzusammenfassung</h2><pre>{summary}</pre></html>"
        )
