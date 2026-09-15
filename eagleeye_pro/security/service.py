from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService

PBKDF2_ITERATIONS = 200_000

DEFAULT_ROLES: Dict[str, Dict[str, Any]] = {
    "admin": {
        "name": "Administrator",
        "permissions": ["*"] ,
        "description": "Lokale Administration, Security, Backup, Restore und Benutzerverwaltung.",
    },
    "case_manager": {
        "name": "Case Manager",
        "permissions": ["case:read", "case:write", "target:write", "workflow:write", "report:prepare"],
        "description": "Fallanlage, Zielpersonenanker, Workflow-Steuerung und Report-Vorbereitung.",
    },
    "analyst": {
        "name": "Analyst",
        "permissions": ["case:read", "target:read", "search:run", "review:write", "evidence:propose", "graph:write", "timeline:write"],
        "description": "Recherche, Review, Evidence-Vorschläge und Analysearbeit.",
    },
    "senior_analyst": {
        "name": "Senior Analyst",
        "permissions": ["case:read", "target:read", "search:run", "review:write", "evidence:approve", "graph:approve", "timeline:approve", "report:prepare"],
        "description": "Prüfung, Freigabe von Evidence und Analyse-Narrativen.",
    },
    "legal_reviewer": {
        "name": "Legal Reviewer",
        "permissions": ["case:read", "legal:approve", "privacy:approve", "export:approve", "report:approve"],
        "description": "Legal/Privacy Review, Exportfreigabe und Compliance-Entscheidungen.",
    },
    "auditor": {
        "name": "Auditor",
        "permissions": ["case:read", "audit:read", "security:read", "integrity:verify"],
        "description": "Audit-, Integrity- und Kontrollsicht ohne operative Änderungen.",
    },
}

DEFAULT_SECURITY_SETTINGS = {
    "local_auth_required": "true",
    "session_timeout_minutes": "60",
    "api_keys_storage_policy": "env_var_reference_only",
    "audit_chain_required": "true",
    "integrity_baseline_required": "true",
    "backup_recommended_interval_days": "7",
    "export_watermark_required": "true",
    "vault_encryption_note": "Build 25 nutzt lokale Security-Controls und Manifest-Härtung; für Produktion OS-Keychain/DPAPI/Fernet ergänzen.",
}

SENSITIVE_FILE_SUFFIXES = {".py", ".md", ".json", ".bat", ".ps1", ".cmd", ".txt"}
EXCLUDED_DIR_NAMES = {".pytest_cache", "__pycache__", "data", "reports", "legacy_reference"}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data.encode("ascii"))


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_text(text: str) -> str:
    return _hash_bytes(text.encode("utf-8"))


class SecurityHardeningService:
    """Build 25 local security controls.

    This service intentionally avoids storing raw secrets. API keys are referenced by
    environment variable name only. Passwords use PBKDF2-HMAC-SHA256. Audit-chain
    hardening creates a hash chain over existing audit rows so tampering becomes visible.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    # ------------------------------------------------------------------
    # Role/user/session controls
    # ------------------------------------------------------------------
    def seed_security_defaults(self) -> Dict[str, int]:
        roles = 0
        for role_key, cfg in DEFAULT_ROLES.items():
            role_id = f"role_{role_key}"
            existing = self.db.one("SELECT role_id FROM user_roles WHERE role_key=?", [role_key])
            if not existing:
                self.db.execute(
                    "INSERT INTO user_roles(role_id,role_key,name,permissions_json,description,created_at) VALUES(?,?,?,?,?,?)",
                    [role_id, role_key, cfg["name"], dumps(cfg["permissions"]), cfg["description"], now_ts()],
                )
                roles += 1
        settings = 0
        for key, value in DEFAULT_SECURITY_SETTINGS.items():
            existing = self.db.one("SELECT setting_key FROM security_settings WHERE setting_key=?", [key])
            if not existing:
                self.db.execute(
                    "INSERT INTO security_settings(setting_key,setting_value,classification,updated_at,updated_by) VALUES(?,?,?,?,?)",
                    [key, value, "internal", now_ts(), "security-bootstrap"],
                )
                settings += 1
        self.audit.log("SECURITY_DEFAULTS_SEEDED", "security", details={"roles_inserted": roles, "settings_inserted": settings})
        return {"roles_inserted": roles, "settings_inserted": settings, "roles_total": len(DEFAULT_ROLES)}

    def _password_hash(self, password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        return _b64(salt), _b64(digest)

    def create_local_user(self, username: str, display_name: str, password: str, role: str = "analyst", notes: str = "") -> Dict[str, Any]:
        username = (username or "").strip().lower()
        if not username or len(username) < 3:
            raise ValueError("Username muss mindestens 3 Zeichen haben.")
        if len(password or "") < 10:
            raise ValueError("Passwort muss mindestens 10 Zeichen haben.")
        if role not in DEFAULT_ROLES:
            raise ValueError(f"Unbekannte Rolle: {role}")
        existing = self.db.one("SELECT * FROM local_users WHERE username=?", [username])
        if existing:
            return existing
        salt, pwd_hash = self._password_hash(password)
        user_id = new_id("user")
        self.db.execute(
            "INSERT INTO local_users(user_id,username,display_name,role,password_salt,password_hash,active,created_at,notes) VALUES(?,?,?,?,?,?,?,?,?)",
            [user_id, username, display_name, role, salt, pwd_hash, 1, now_ts(), notes],
        )
        self.audit.log("LOCAL_USER_CREATED", "local_user", user_id, details={"username": username, "role": role})
        return self.db.one("SELECT * FROM local_users WHERE user_id=?", [user_id])

    def authenticate_user(self, username: str, password: str, ttl_minutes: int = 60) -> Dict[str, Any]:
        username = (username or "").strip().lower()
        user = self.db.one("SELECT * FROM local_users WHERE username=? AND active=1", [username])
        if not user:
            self.audit.log("AUTH_FAILED", "auth", details={"username": username, "reason": "no_active_user"})
            raise PermissionError("Authentifizierung fehlgeschlagen.")
        salt = _unb64(user["password_salt"])
        _, candidate = self._password_hash(password, salt=salt)
        if not hmac.compare_digest(candidate, user["password_hash"]):
            self.audit.log("AUTH_FAILED", "auth", user.get("user_id"), details={"username": username, "reason": "bad_password"})
            raise PermissionError("Authentifizierung fehlgeschlagen.")
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_text(raw_token)
        session_id = new_id("sess")
        now = now_ts()
        expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + ttl_minutes * 60))
        self.db.execute(
            "INSERT INTO auth_sessions(session_id,user_id,username,role,session_token_hash,created_at,expires_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?)",
            [session_id, user["user_id"], username, user["role"], token_hash, now, expires, now],
        )
        self.db.execute("UPDATE local_users SET last_login_at=? WHERE user_id=?", [now, user["user_id"]])
        self.audit.log("AUTH_SESSION_CREATED", "auth_session", session_id, details={"username": username, "role": user["role"], "expires_at": expires})
        return {"session_id": session_id, "session_token": raw_token, "username": username, "role": user["role"], "expires_at": expires}

    def list_users(self) -> List[Dict[str, Any]]:
        return self.db.all("SELECT user_id,username,display_name,role,active,created_at,last_login_at,notes FROM local_users ORDER BY username")

    def list_roles(self) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM user_roles ORDER BY role_key")
        for r in rows:
            r["permissions"] = loads(r.get("permissions_json"), [])
        return rows

    def role_allows(self, role: str, permission: str) -> bool:
        row = self.db.one("SELECT permissions_json FROM user_roles WHERE role_key=?", [role])
        permissions = loads(row["permissions_json"], []) if row else []
        return "*" in permissions or permission in permissions

    # ------------------------------------------------------------------
    # Secrets and configuration
    # ------------------------------------------------------------------
    def create_secret_reference(self, name: str, env_var: str, purpose: str, provider_id: str = "", required: bool = False, notes: str = "") -> Dict[str, Any]:
        env_var = (env_var or "").strip()
        if not env_var:
            raise ValueError("env_var darf nicht leer sein. API-Schlüssel werden nicht im Klartext gespeichert.")
        existing = self.db.one("SELECT * FROM secret_references WHERE env_var=?", [env_var])
        if existing:
            return existing
        secret_id = new_id("sec")
        self.db.execute(
            "INSERT INTO secret_references(secret_id,name,env_var,purpose,provider_id,required,status,created_at,notes) VALUES(?,?,?,?,?,?,?,?,?)",
            [secret_id, name, env_var, purpose, provider_id, 1 if required else 0, "unchecked", now_ts(), notes],
        )
        self.audit.log("SECRET_REFERENCE_CREATED", "secret_reference", secret_id, details={"env_var": env_var, "provider_id": provider_id, "required": required})
        return self.db.one("SELECT * FROM secret_references WHERE secret_id=?", [secret_id])

    def validate_secret_references(self) -> Dict[str, Any]:
        refs = self.db.all("SELECT * FROM secret_references ORDER BY name")
        present, missing = [], []
        for ref in refs:
            status = "present" if os.environ.get(ref["env_var"]) else "missing"
            self.db.execute("UPDATE secret_references SET status=?, last_checked_at=? WHERE secret_id=?", [status, now_ts(), ref["secret_id"]])
            (present if status == "present" else missing).append(ref["env_var"])
        self.audit.log("SECRET_REFERENCES_VALIDATED", "security", details={"present": present, "missing": missing})
        return {"total": len(refs), "present": present, "missing": missing, "ok": not any(r.get("required") and r["env_var"] in missing for r in refs)}

    # ------------------------------------------------------------------
    # Integrity baseline and audit-chain hardening
    # ------------------------------------------------------------------
    def _iter_integrity_files(self, root: Path) -> Iterable[Path]:
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            rel_parts = p.relative_to(root).parts
            if any(part in EXCLUDED_DIR_NAMES for part in rel_parts):
                continue
            if p.suffix.lower() not in SENSITIVE_FILE_SUFFIXES:
                continue
            yield p

    def create_integrity_baseline(self, root_path: str | Path, label: str = "Build 25 application baseline", notes: str = "") -> Dict[str, Any]:
        root = Path(root_path).resolve()
        manifest = []
        for p in self._iter_integrity_files(root):
            rel = str(p.relative_to(root)).replace("\\", "/")
            data = p.read_bytes()
            manifest.append({"path": rel, "sha256": _hash_bytes(data), "bytes": len(data)})
        manifest_json = dumps(manifest)
        manifest_hash = _hash_text(manifest_json)
        baseline_id = new_id("base")
        self.db.execute(
            "INSERT INTO integrity_baselines(baseline_id,label,root_path,manifest_json,manifest_hash,created_at,notes) VALUES(?,?,?,?,?,?,?)",
            [baseline_id, label, str(root), manifest_json, manifest_hash, now_ts(), notes],
        )
        self.audit.log("INTEGRITY_BASELINE_CREATED", "integrity_baseline", baseline_id, details={"root": str(root), "files": len(manifest), "manifest_hash": manifest_hash})
        return self.db.one("SELECT * FROM integrity_baselines WHERE baseline_id=?", [baseline_id])

    def verify_integrity_baseline(self, baseline_id: str) -> Dict[str, Any]:
        baseline = self.db.one("SELECT * FROM integrity_baselines WHERE baseline_id=?", [baseline_id])
        if not baseline:
            raise ValueError("Integrity baseline nicht gefunden.")
        root = Path(baseline["root_path"])
        expected = {item["path"]: item for item in loads(baseline["manifest_json"], [])}
        current = {}
        for p in self._iter_integrity_files(root):
            rel = str(p.relative_to(root)).replace("\\", "/")
            current[rel] = {"path": rel, "sha256": _hash_bytes(p.read_bytes()), "bytes": p.stat().st_size}
        changed = [path for path, item in expected.items() if path in current and current[path]["sha256"] != item["sha256"]]
        missing = [path for path in expected if path not in current]
        new = [path for path in current if path not in expected]
        status = "pass" if not changed and not missing else "fail"
        check_id = new_id("ichk")
        self.db.execute(
            "INSERT INTO integrity_checks(check_id,baseline_id,status,changed_files_json,missing_files_json,new_files_json,checked_at,notes) VALUES(?,?,?,?,?,?,?,?)",
            [check_id, baseline_id, status, dumps(changed), dumps(missing), dumps(new), now_ts(), "Integrity Check Build 25"],
        )
        self.audit.log("INTEGRITY_BASELINE_VERIFIED", "integrity_check", check_id, details={"status": status, "changed": len(changed), "missing": len(missing), "new": len(new)})
        return {"check_id": check_id, "status": status, "changed_files": changed, "missing_files": missing, "new_files": new, "baseline_id": baseline_id}

    def harden_audit_chain(self) -> Dict[str, Any]:
        events = self.db.all("SELECT * FROM audit_events ORDER BY timestamp, event_id")
        existing = {r["event_id"] for r in self.db.all("SELECT event_id FROM audit_chain_hashes")}
        last = self.db.one("SELECT event_hash, sequence_no FROM audit_chain_hashes ORDER BY sequence_no DESC LIMIT 1")
        prev_hash = last["event_hash"] if last else "GENESIS"
        seq = int(last["sequence_no"]) + 1 if last else 1
        added = 0
        for ev in events:
            if ev["event_id"] in existing:
                continue
            canonical = dumps({k: ev[k] for k in sorted(ev.keys())})
            event_hash = _hash_text(prev_hash + "|" + canonical)
            self.db.execute(
                "INSERT INTO audit_chain_hashes(chain_id,event_id,sequence_no,previous_hash,event_hash,chained_at) VALUES(?,?,?,?,?,?)",
                [new_id("chain"), ev["event_id"], seq, prev_hash, event_hash, now_ts()],
            )
            prev_hash = event_hash
            seq += 1
            added += 1
        self.audit.log("AUDIT_CHAIN_HARDENED", "audit_chain", details={"events_chained": added, "last_hash": prev_hash})
        return {"events_chained": added, "last_hash": prev_hash, "total_chain_rows": len(self.db.all("SELECT event_id FROM audit_chain_hashes"))}

    def verify_audit_chain(self) -> Dict[str, Any]:
        chain = self.db.all("SELECT * FROM audit_chain_hashes ORDER BY sequence_no")
        issues = []
        prev = "GENESIS"
        for row in chain:
            ev = self.db.one("SELECT * FROM audit_events WHERE event_id=?", [row["event_id"]])
            if not ev:
                issues.append({"sequence_no": row["sequence_no"], "issue": "missing_audit_event", "event_id": row["event_id"]})
                continue
            if row["previous_hash"] != prev:
                issues.append({"sequence_no": row["sequence_no"], "issue": "previous_hash_mismatch"})
            canonical = dumps({k: ev[k] for k in sorted(ev.keys())})
            expected = _hash_text(row["previous_hash"] + "|" + canonical)
            if expected != row["event_hash"]:
                issues.append({"sequence_no": row["sequence_no"], "issue": "event_hash_mismatch", "event_id": row["event_id"]})
            prev = row["event_hash"]
        self.audit.log("AUDIT_CHAIN_VERIFIED", "audit_chain", details={"ok": not issues, "issues": issues[:20], "rows": len(chain)})
        return {"ok": not issues, "issues": issues, "rows": len(chain), "last_hash": prev if chain else "GENESIS"}

    # ------------------------------------------------------------------
    # Backup and export controls
    # ------------------------------------------------------------------
    def create_backup_bundle(self, base_dir: str | Path, backup_dir: str | Path, notes: str = "") -> Dict[str, Any]:
        base = Path(base_dir).resolve()
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_id = new_id("bak")
        zip_path = backup_dir / f"eagleeye_backup_{backup_id}.zip"
        file_count = 0
        total_bytes = 0
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for folder in [base / "data", base / "reports"]:
                if not folder.exists():
                    continue
                for p in sorted(folder.rglob("*")):
                    if p.is_file():
                        rel = p.relative_to(base)
                        zf.write(p, rel.as_posix())
                        file_count += 1
                        total_bytes += p.stat().st_size
        backup_hash = _hash_bytes(zip_path.read_bytes()) if zip_path.exists() else ""
        self.db.execute(
            "INSERT INTO backup_manifests(backup_id,backup_path,backup_hash,file_count,total_bytes,created_at,notes) VALUES(?,?,?,?,?,?,?)",
            [backup_id, str(zip_path), backup_hash, file_count, total_bytes, now_ts(), notes],
        )
        self.audit.log("BACKUP_BUNDLE_CREATED", "backup_manifest", backup_id, details={"path": str(zip_path), "file_count": file_count, "backup_hash": backup_hash})
        return self.db.one("SELECT * FROM backup_manifests WHERE backup_id=?", [backup_id])

    def create_export_watermark(self, audience: str, case_id: str = "", report_id: str = "", notes: str = "") -> Dict[str, Any]:
        raw_token = secrets.token_urlsafe(18)
        text = f"EagleEye Pro Export | audience={audience} | case={case_id or 'n/a'} | token={raw_token[:10]}"
        watermark_id = new_id("wm")
        self.db.execute(
            "INSERT INTO export_watermarks(watermark_id,case_id,report_id,audience,watermark_text,token_hash,created_at,notes) VALUES(?,?,?,?,?,?,?,?)",
            [watermark_id, case_id or None, report_id, audience, text, _hash_text(raw_token), now_ts(), notes],
        )
        self.audit.log("EXPORT_WATERMARK_CREATED", "export_watermark", watermark_id, case_id=case_id or None, details={"audience": audience, "report_id": report_id})
        return self.db.one("SELECT * FROM export_watermarks WHERE watermark_id=?", [watermark_id])

    # ------------------------------------------------------------------
    # Dashboard / findings
    # ------------------------------------------------------------------
    def create_security_finding(self, severity: str, finding_type: str, title: str, description: str, case_id: str = "", status: str = "open") -> Dict[str, Any]:
        finding_id = new_id("sf")
        self.db.execute(
            "INSERT INTO security_findings(finding_id,case_id,severity,finding_type,title,description,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
            [finding_id, case_id or None, severity, finding_type, title, description, status, now_ts()],
        )
        self.audit.log("SECURITY_FINDING_CREATED", "security_finding", finding_id, case_id=case_id or None, details={"severity": severity, "type": finding_type})
        return self.db.one("SELECT * FROM security_findings WHERE finding_id=?", [finding_id])

    def security_dashboard(self) -> Dict[str, Any]:
        users = self.db.one("SELECT COUNT(*) AS n FROM local_users WHERE active=1") or {"n": 0}
        roles = self.db.one("SELECT COUNT(*) AS n FROM user_roles") or {"n": 0}
        sessions = self.db.one("SELECT COUNT(*) AS n FROM auth_sessions WHERE revoked=0") or {"n": 0}
        secrets_total = self.db.one("SELECT COUNT(*) AS n FROM secret_references") or {"n": 0}
        secrets_missing = self.db.one("SELECT COUNT(*) AS n FROM secret_references WHERE status='missing' AND required=1") or {"n": 0}
        baselines = self.db.one("SELECT COUNT(*) AS n FROM integrity_baselines") or {"n": 0}
        last_integrity = self.db.one("SELECT * FROM integrity_checks ORDER BY checked_at DESC LIMIT 1")
        audit_chain = self.verify_audit_chain() if (self.db.one("SELECT COUNT(*) AS n FROM audit_chain_hashes") or {"n": 0})["n"] else {"ok": False, "rows": 0, "issues": ["no_chain"]}
        open_findings = self.db.all("SELECT severity, COUNT(*) AS n FROM security_findings WHERE status='open' GROUP BY severity")
        dashboard = {
            "users_active": users["n"],
            "roles": roles["n"],
            "active_sessions": sessions["n"],
            "secret_refs": secrets_total["n"],
            "required_secret_refs_missing": secrets_missing["n"],
            "integrity_baselines": baselines["n"],
            "last_integrity_check": last_integrity,
            "audit_chain_ok": audit_chain["ok"],
            "audit_chain_rows": audit_chain["rows"],
            "open_findings_by_severity": open_findings,
        }
        return dashboard
