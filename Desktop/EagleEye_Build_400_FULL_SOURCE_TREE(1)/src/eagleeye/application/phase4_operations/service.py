from __future__ import annotations

import base64
import hashlib
import importlib
import json
import os
import platform
import re
import shutil
import socket
import sys
from pathlib import Path
from typing import Any, Iterable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts
from eagleeye_pro.version import BUILD, SCHEMA_VERSION


class Phase4OperationsError(ValueError):
    pass


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$")
_HOST = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    text = _canonical(value) if isinstance(value, (dict, list, tuple)) else str(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _redact_path(path: Path) -> str:
    return path.name or str(path)


class Phase4Operations134Service:
    """Phase-4 operational foundation and connector-package trust boundary.

    Build 140 deliberately does *not* execute third-party connector code. It
    verifies catalog manifests, records trust, runs deterministic contracts
    against already registered built-in adapters and produces local routing
    advice. Network and autonomous AI actions remain outside this service.
    """

    BUILD = "150.0"
    MANIFEST_SCHEMA = "eagleeye.connector-manifest.v1"
    TRUST_STATES = {
        "builtin_trusted", "signed_trusted", "unsigned_quarantine",
        "invalid_signature_quarantine", "unknown_signer_quarantine",
        "invalid_manifest_quarantine",
    }

    def __init__(
        self,
        db: Any,
        audit: Any,
        install_dir: str | Path,
        *,
        providers: Any,
        research_strategy: Any,
        protection: Any,
        registry_getter: Any,
    ) -> None:
        self.db = db
        self.audit = audit
        self.install_dir = Path(install_dir).resolve()
        self.providers = providers
        self.research_strategy = research_strategy
        self.protection = protection
        self._registry_getter = registry_getter
        from eagleeye.infrastructure.phase4_operations.schema import ensure_phase4_operations_schema_134

        ensure_phase4_operations_schema_134(self.db)
        self._seed_builtin_packages()

    def status(self) -> dict[str, Any]:
        policy = self.db.one("SELECT * FROM phase4_operational_policy_134 WHERE policy_id='phase4'") or {}
        packages = self.list_packages()
        return {
            "build": self.BUILD,
            "schema": SCHEMA_VERSION,
            "mode": "operational_connector_trust_foundation",
            "package_count": len(packages),
            "trusted_packages": sum(1 for item in packages if item["trust_state"] in {"builtin_trusted", "signed_trusted"}),
            "quarantined_packages": sum(1 for item in packages if "quarantine" in item["trust_state"]),
            "external_connector_code_execution": policy.get("external_connector_code_execution", "disabled"),
            "ai_trust_state": policy.get("ai_trust_state", "suggestions_only"),
            "max_external_ai_actions": int(policy.get("max_external_ai_actions") or 0),
            "remote_server_mode": policy.get("remote_server_mode", "disabled_loopback_only"),
        }

    # ---------- manifest and trust store ----------
    def _seed_builtin_packages(self) -> None:
        stamp = now_ts()
        connectors = self.research_strategy.list_connectors()
        providers = {item["provider_key"]: item for item in self.providers.list_providers(enabled_only=False)}
        with self.db.transaction(immediate=True):
            for connector in connectors:
                provider = providers.get(connector.get("provider_key"), {})
                manifest = {
                    "schema": self.MANIFEST_SCHEMA,
                    "package_name": f"eagleeye-builtin-{connector['connector_key']}",
                    "package_version": str(connector.get("connector_version") or "1.0.0") if str(connector.get("connector_version") or "").count(".") == 2 else "1.0.0",
                    "connector_key": connector["connector_key"],
                    "provider_key": connector["provider_key"],
                    "public_only": True,
                    "http_methods": ["GET"],
                    "input_types": list(connector.get("input_types") or []),
                    "output_types": list(connector.get("output_types") or []),
                    "allowed_hosts": sorted(set(connector.get("allowed_hosts") or provider.get("allowed_hosts") or [])),
                    "terms_profile": str(connector.get("terms_profile") or provider.get("terms_profile") or "public-only"),
                    "query_minimization": "required",
                    "candidate_only": True,
                    "automatic_promotion": False,
                    "code_execution": False,
                    "source_kind": "builtin",
                }
                canonical = _canonical(manifest)
                package_id = "cpkg134_builtin_" + _sha((manifest["connector_key"], manifest["package_version"]))[:24]
                self.db.execute(
                    """INSERT INTO connector_packages_134(
                       package_id,connector_key,provider_key,package_name,package_version,
                       manifest_json,manifest_sha256,signature_algorithm,signer_fingerprint,
                       signature_b64,trust_state,execution_state,source_kind,enabled,
                       created_by,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,'builtin','','','builtin_trusted',
                              'catalog_only_no_code_execution','builtin',1,'system',?,?)
                       ON CONFLICT(connector_key,package_version) DO UPDATE SET
                         provider_key=excluded.provider_key,package_name=excluded.package_name,
                         manifest_json=excluded.manifest_json,manifest_sha256=excluded.manifest_sha256,
                         trust_state='builtin_trusted',execution_state='catalog_only_no_code_execution',
                         source_kind='builtin',enabled=1,updated_at=excluded.updated_at""",
                    (
                        package_id, manifest["connector_key"], manifest["provider_key"], manifest["package_name"],
                        manifest["package_version"], canonical, _sha(canonical), stamp, stamp,
                    ),
                )

    @staticmethod
    def _decode_b64(value: str, *, expected: int | None = None) -> bytes:
        try:
            raw = base64.b64decode(value.strip(), validate=True)
        except Exception as exc:
            raise Phase4OperationsError("Ungültige Base64-Kodierung") from exc
        if expected is not None and len(raw) != expected:
            raise Phase4OperationsError(f"Unerwartete Schlüssellänge; erwartet {expected} Bytes")
        return raw

    def add_trusted_signer(self, *, label: str, public_key_b64: str, actor: str, confirmation: str) -> dict[str, Any]:
        if confirmation.strip() != "TRUST SIGNER":
            raise Phase4OperationsError("Freigabephrase TRUST SIGNER fehlt")
        raw = self._decode_b64(public_key_b64, expected=32)
        Ed25519PublicKey.from_public_bytes(raw)
        fingerprint = hashlib.sha256(raw).hexdigest()
        signer_id = "signer134_" + fingerprint[:24]
        stamp = now_ts()
        self.db.execute(
            """INSERT INTO connector_trusted_signers_134(
               signer_id,label,public_key_b64,fingerprint_sha256,active,added_by,added_at)
               VALUES(?,?,?,?,1,?,?)
               ON CONFLICT(fingerprint_sha256) DO UPDATE SET
                 label=excluded.label,public_key_b64=excluded.public_key_b64,
                 active=1,added_by=excluded.added_by,added_at=excluded.added_at,
                 revoked_by='',revoked_at=''""",
            (signer_id, label.strip()[:200] or "Connector signer", public_key_b64.strip(), fingerprint, actor, stamp),
        )
        self._opsec(None, "trusted_signer_added", "connector_signer", signer_id, actor, {"fingerprint": fingerprint, "public_key_in_audit": False})
        self.audit.log("trust", "connector_signer_134", signer_id, None, {"fingerprint": fingerprint})
        return self.db.one("SELECT signer_id,label,fingerprint_sha256,active,added_by,added_at FROM connector_trusted_signers_134 WHERE signer_id=?", (signer_id,))

    def revoke_signer(self, *, signer_id: str, actor: str, confirmation: str) -> None:
        if confirmation.strip() != "REVOKE SIGNER":
            raise Phase4OperationsError("Freigabephrase REVOKE SIGNER fehlt")
        if not self.db.one("SELECT signer_id FROM connector_trusted_signers_134 WHERE signer_id=?", (signer_id,)):
            raise Phase4OperationsError("Signer nicht gefunden")
        stamp = now_ts()
        self.db.execute("UPDATE connector_trusted_signers_134 SET active=0,revoked_by=?,revoked_at=? WHERE signer_id=?", (actor, stamp, signer_id))
        self.db.execute(
            """UPDATE connector_packages_134 SET trust_state='unknown_signer_quarantine',enabled=0,updated_at=?
               WHERE signer_fingerprint=(SELECT fingerprint_sha256 FROM connector_trusted_signers_134 WHERE signer_id=?)
                 AND source_kind='external'""",
            (stamp, signer_id),
        )
        self._opsec(None, "trusted_signer_revoked", "connector_signer", signer_id, actor, {"packages_disabled": True})

    def _validate_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "schema", "package_name", "package_version", "connector_key", "provider_key",
            "public_only", "http_methods", "input_types", "output_types", "allowed_hosts",
            "terms_profile", "query_minimization", "candidate_only", "automatic_promotion",
            "code_execution", "source_kind",
        }
        unknown = set(manifest) - allowed
        if unknown:
            raise Phase4OperationsError("Manifest enthält nicht erlaubte Felder: " + ", ".join(sorted(unknown)))
        if manifest.get("schema") != self.MANIFEST_SCHEMA:
            raise Phase4OperationsError("Unbekannte Connector-Manifest-Version")
        for key in ("package_name", "connector_key", "provider_key"):
            value = str(manifest.get(key) or "")
            if not _SAFE_ID.fullmatch(value):
                raise Phase4OperationsError(f"Ungültiger Manifest-Identifier: {key}")
        version = str(manifest.get("package_version") or "")
        if not _SEMVER.fullmatch(version):
            raise Phase4OperationsError("package_version muss SemVer entsprechen")
        if manifest.get("public_only") is not True:
            raise Phase4OperationsError("Nur public-only Connectoren sind zulässig")
        methods = [str(item).upper() for item in (manifest.get("http_methods") or [])]
        if methods != ["GET"]:
            raise Phase4OperationsError("Build 140 erlaubt ausschließlich GET-Connectorverträge")
        hosts = sorted({str(item).casefold().strip(".") for item in (manifest.get("allowed_hosts") or [])})
        if not hosts or any(not _HOST.fullmatch(host) or host in {"localhost", "testserver"} for host in hosts):
            raise Phase4OperationsError("allowed_hosts muss exakte öffentliche DNS-Namen enthalten")
        for key in ("input_types", "output_types"):
            values = manifest.get(key)
            if not isinstance(values, list) or not values or any(not _SAFE_ID.fullmatch(str(item)) for item in values):
                raise Phase4OperationsError(f"{key} muss eine nichtleere sichere Liste sein")
        if manifest.get("query_minimization") != "required":
            raise Phase4OperationsError("Query-Minimierung muss required sein")
        if manifest.get("candidate_only") is not True or manifest.get("automatic_promotion") is not False:
            raise Phase4OperationsError("Connectoren müssen candidate-only und ohne automatische Promotion arbeiten")
        if manifest.get("code_execution") is not False:
            raise Phase4OperationsError("Drittcode-Ausführung ist in Build 140 deaktiviert")
        normalized = dict(manifest)
        normalized["http_methods"] = methods
        normalized["allowed_hosts"] = hosts
        normalized["input_types"] = sorted({str(item) for item in manifest["input_types"]})
        normalized["output_types"] = sorted({str(item) for item in manifest["output_types"]})
        normalized["source_kind"] = "external"
        normalized["terms_profile"] = str(manifest.get("terms_profile") or "public-only")[:2000]
        return normalized

    def register_manifest(
        self,
        *,
        manifest_json: str,
        signature_b64: str = "",
        signer_fingerprint: str = "",
        actor: str,
    ) -> dict[str, Any]:
        try:
            parsed = json.loads(manifest_json)
            if not isinstance(parsed, dict):
                raise Phase4OperationsError("Manifest muss ein JSON-Objekt sein")
            manifest = self._validate_manifest(parsed)
            canonical = _canonical(manifest)
            manifest_hash = _sha(canonical)
            trust_state = "unsigned_quarantine"
            algorithm = ""
            fingerprint = signer_fingerprint.casefold().strip()
            signature = signature_b64.strip()
            if signature or fingerprint:
                if not (signature and re.fullmatch(r"[0-9a-f]{64}", fingerprint)):
                    trust_state = "invalid_signature_quarantine"
                else:
                    signer = self.db.one(
                        "SELECT * FROM connector_trusted_signers_134 WHERE fingerprint_sha256=? AND active=1",
                        (fingerprint,),
                    )
                    if not signer:
                        trust_state = "unknown_signer_quarantine"
                    else:
                        try:
                            public_key = Ed25519PublicKey.from_public_bytes(self._decode_b64(signer["public_key_b64"], expected=32))
                            public_key.verify(self._decode_b64(signature, expected=64), canonical.encode("utf-8"))
                            trust_state = "signed_trusted"
                            algorithm = "ed25519"
                        except (InvalidSignature, Phase4OperationsError, ValueError):
                            trust_state = "invalid_signature_quarantine"
            package_id = "cpkg134_" + _sha((manifest["connector_key"], manifest["package_version"], manifest_hash))[:32]
        except Exception as exc:
            if isinstance(exc, Phase4OperationsError):
                raise
            raise Phase4OperationsError("Ungültiges Connector-Manifest") from exc

        stamp = now_ts()
        enabled = int(trust_state == "signed_trusted")
        self.db.execute(
            """INSERT INTO connector_packages_134(
               package_id,connector_key,provider_key,package_name,package_version,manifest_json,
               manifest_sha256,signature_algorithm,signer_fingerprint,signature_b64,trust_state,
               execution_state,source_kind,enabled,created_by,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,'catalog_only_no_code_execution','external',?,?,?,?)
               ON CONFLICT(connector_key,package_version) DO UPDATE SET
                 provider_key=excluded.provider_key,package_name=excluded.package_name,
                 manifest_json=excluded.manifest_json,manifest_sha256=excluded.manifest_sha256,
                 signature_algorithm=excluded.signature_algorithm,signer_fingerprint=excluded.signer_fingerprint,
                 signature_b64=excluded.signature_b64,trust_state=excluded.trust_state,
                 execution_state='catalog_only_no_code_execution',source_kind='external',
                 enabled=excluded.enabled,updated_at=excluded.updated_at""",
            (
                package_id, manifest["connector_key"], manifest["provider_key"], manifest["package_name"],
                manifest["package_version"], canonical, manifest_hash, algorithm, fingerprint, signature,
                trust_state, enabled, actor, stamp, stamp,
            ),
        )
        self._opsec(None, "connector_manifest_registered", "connector_package", package_id, actor, {
            "manifest_sha256": manifest_hash,
            "trust_state": trust_state,
            "signature_present": bool(signature),
            "raw_manifest_in_audit": False,
            "code_execution": False,
        })
        self.audit.log("register", "connector_package_134", package_id, None, {"manifest_sha256": manifest_hash, "trust_state": trust_state, "code_execution": False})
        return self.package(package_id)

    def list_signers(self) -> list[dict[str, Any]]:
        return self.db.all(
            "SELECT signer_id,label,fingerprint_sha256,active,added_by,added_at,revoked_by,revoked_at FROM connector_trusted_signers_134 ORDER BY added_at DESC"
        )

    def list_packages(self) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM connector_packages_134 ORDER BY source_kind,package_name,package_version")
        for row in rows:
            row["manifest"] = loads(row.pop("manifest_json"), {})
            row["enabled"] = bool(row.get("enabled"))
            row.pop("signature_b64", None)
        return rows

    def package(self, package_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM connector_packages_134 WHERE package_id=?", (package_id,))
        if not row:
            raise Phase4OperationsError("Connector-Paket nicht gefunden")
        row["manifest"] = loads(row.pop("manifest_json"), {})
        row["enabled"] = bool(row.get("enabled"))
        row.pop("signature_b64", None)
        return row

    # ---------- deterministic provider contracts ----------
    def run_contract_check(self, *, package_id: str, actor: str) -> dict[str, Any]:
        package = self.package(package_id)
        manifest = package["manifest"]
        checks: list[dict[str, Any]] = []

        def add(key: str, title: str, status: str, severity: str = "high", **details: Any) -> None:
            checks.append({"key": key, "title": title, "status": status, "severity": severity, "details": details})

        try:
            provider = self.providers.provider(package["provider_key"])
            add("provider_registered", "Provider ist registriert", "pass", provider_key=package["provider_key"])
        except KeyError:
            provider = {}
            add("provider_registered", "Provider ist registriert", "blocker", provider_key=package["provider_key"])

        trusted = package["trust_state"] in {"builtin_trusted", "signed_trusted"}
        add("package_trust", "Paket besitzt vertrauenswürdigen Manifeststatus", "pass" if trusted else "blocker", trust_state=package["trust_state"])
        add("code_execution", "Drittcode-Ausführung ist deaktiviert", "pass" if package["execution_state"] == "catalog_only_no_code_execution" and manifest.get("code_execution") is False else "blocker")
        if provider:
            add("public_only", "Provider und Manifest sind public-only", "pass" if provider.get("public_only") and manifest.get("public_only") is True else "blocker")
            provider_hosts = sorted(set(provider.get("allowed_hosts") or []))
            manifest_hosts = sorted(set(manifest.get("allowed_hosts") or []))
            add("host_allowlist", "Host-Allowlist stimmt mit Providervertrag überein", "pass" if provider_hosts == manifest_hosts else "blocker", provider_hosts=provider_hosts, manifest_hosts=manifest_hosts)
            add("replay", "Provider unterstützt reproduzierbaren Replay-Modus", "pass" if provider.get("supports_replay") else "warning", severity="medium")
            add("rate_limit", "Rate Limit liegt innerhalb sicherer Grenzen", "pass" if 1 <= int(provider.get("rate_limit_per_minute") or 0) <= 600 else "blocker", value=provider.get("rate_limit_per_minute"))
            add("response_limit", "Antwortgröße ist begrenzt", "pass" if 1 <= int(provider.get("max_response_bytes") or 0) <= 25_000_000 else "blocker", value=provider.get("max_response_bytes"))
            health = self.providers.health_check(package["provider_key"])
            add("provider_health", "Providerzustand ist nicht circuit-open", "pass" if health.get("status") != "blocked" else "warning", severity="medium", health_status=health.get("status"), circuit_state=health.get("circuit_state"))
        add("candidate_only", "Ergebnisse bleiben candidate-only", "pass" if manifest.get("candidate_only") is True and manifest.get("automatic_promotion") is False else "blocker")
        add("query_minimization", "Query-Minimierung ist verpflichtend", "pass" if manifest.get("query_minimization") == "required" else "blocker")

        blockers = sum(1 for item in checks if item["status"] == "blocker")
        warnings = sum(1 for item in checks if item["status"] == "warning")
        status = "pass" if blockers == 0 and warnings == 0 else "conditional" if blockers == 0 else "blocked"
        report = {"build": self.BUILD, "package_id": package_id, "provider_key": package["provider_key"], "mode": "offline_contract_only", "status": status, "checks": checks, "network_used": False, "code_executed": False}
        run_id = new_id("contract134")
        self.db.execute(
            """INSERT INTO connector_contract_runs_134(
               run_id,package_id,provider_key,mode,status,check_count,blocker_count,warning_count,
               report_json,created_by,created_at) VALUES(?,?,?,'offline_contract_only',?,?,?,?,?,?,?)""",
            (run_id, package_id, package["provider_key"], status, len(checks), blockers, warnings, dumps(report), actor, now_ts()),
        )
        self._opsec(None, "connector_contract_checked", "connector_package", package_id, actor, {"run_id": run_id, "status": status, "network_used": False, "code_executed": False})
        return {"run_id": run_id, **report, "blocker_count": blockers, "warning_count": warnings}

    def contract_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM connector_contract_runs_134 ORDER BY created_at DESC LIMIT ?", (max(1, min(int(limit), 500)),))

    # ---------- operational preflight ----------
    def runtime_preflight(self, *, actor: str) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        def add(key: str, title: str, status: str, severity: str = "high", **details: Any) -> None:
            checks.append({"key": key, "title": title, "status": status, "severity": severity, "details": details})

        add("build", "Build- und Schemavertrag", "pass" if BUILD == self.BUILD and SCHEMA_VERSION == "150.0" else "blocker", build=BUILD, schema=SCHEMA_VERSION)
        integrity = self.db.one("PRAGMA quick_check")
        add("database", "SQLite quick_check", "pass" if integrity == "ok" or integrity == {"quick_check": "ok"} else "blocker", result=integrity)
        registry = self._registry_getter() if callable(self._registry_getter) else None
        required_services = {
            "production_candidate_126", "intelligence_orchestrator_127", "research_strategy_128",
            "capture_identity_129", "graph_hypothesis_130", "investigative_synthesis_131",
            "collaboration_governance_132", "phase3_production_candidate_133", "phase4_operations_134", "build135", "build136", "build137", "build138", "build139", "build140", "build141", "build142", "build143", "build144", "build145", "build146", "build147", "build148",
        }
        registered = {item.name for item in registry.descriptors()} if registry else set()
        missing_services = sorted(required_services - registered)
        add("services", "Phase-2/3/4-Dienste registriert", "pass" if not missing_services else "blocker", missing=missing_services)

        required_files = [
            "START_EAGLEEYE_PRO.bat", "START_EAGLEEYE_PRO_150_0.bat", "EAGLEEYE_PRO_150_0.py",
            "INSTALL_EAGLEEYE_RUNTIME_150_0.bat", "RUN_WINDOWS_ACCEPTANCE_150_0.bat",
            "requirements-runtime.txt", "tools/windows/firefox_acceptance_probe_150.py",
            "tools/firefox_companion_136/manifest.json", "src/eagleeye/interfaces/web/assets/photo136.js",
        ]
        missing_files = [name for name in required_files if not (self.install_dir / name).is_file()]
        add("release_files", "Windows-Start- und Acceptance-Dateien vorhanden", "pass" if not missing_files else "blocker", missing=missing_files)
        launcher = (self.install_dir / "START_EAGLEEYE_PRO_150_0.bat")
        launcher_text = launcher.read_text(encoding="utf-8", errors="replace") if launcher.exists() else ""
        launcher_ok = all(token in launcher_text for token in ("--gui", ".venv\\Scripts\\python.exe", "INSTALL_EAGLEEYE_RUNTIME_150_0.bat", "EAGLEEYE_PRO_150_0.py"))
        add("launcher_contract", "Doppelklick startet Build 150 über lokale Runtime", "pass" if launcher_ok else "blocker")
        entry = self.install_dir / "EAGLEEYE_PRO_150_0.py"
        entry_text = entry.read_text(encoding="utf-8", errors="replace") if entry.exists() else ""
        add("entry_contract", "Direkter Python-Aufruf startet standardmäßig GUI", "pass" if 'sys.argv[1:] or ["--gui"]' in entry_text else "blocker")

        dependency_results: dict[str, str] = {}
        dependency_failures: list[str] = []
        for module in ("pydantic", "sqlalchemy", "alembic", "fastapi", "uvicorn", "cryptography", "PIL", "cv2", "reportlab"):
            try:
                loaded = importlib.import_module(module)
                dependency_results[module] = str(getattr(loaded, "__version__", "installed"))
            except Exception:
                dependency_failures.append(module)
        add("dependencies", "Runtime-Abhängigkeiten importierbar", "pass" if not dependency_failures else "blocker", versions=dependency_results, missing=dependency_failures)
        add("python", "Python-Version", "pass" if sys.version_info >= (3, 11) else "blocker", version=sys.version.split()[0])

        writable: dict[str, bool] = {}
        for name in ("data", "logs"):
            directory = self.install_dir / name
            try:
                directory.mkdir(parents=True, exist_ok=True)
                probe = directory / ".eagleeye_write_probe_134"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink()
                writable[name] = True
            except OSError:
                writable[name] = False
        add("writable", "Daten- und Logverzeichnisse sind beschreibbar", "pass" if all(writable.values()) else "blocker", directories=writable)

        loopback_ok = False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            loopback_ok = True
            sock.close()
        except OSError:
            loopback_ok = False
        add("loopback", "Lokaler Loopback-Port kann gebunden werden", "pass" if loopback_ok else "blocker")

        firefox_candidates: list[str] = []
        found_firefox = shutil.which("firefox") or shutil.which("firefox.exe")
        if found_firefox:
            firefox_candidates.append(_redact_path(Path(found_firefox)))
        if os.name == "nt":
            for env_key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
                root = os.environ.get(env_key)
                if root:
                    candidate = Path(root) / "Mozilla Firefox" / "firefox.exe"
                    if candidate.is_file():
                        firefox_candidates.append(candidate.name)
        add("firefox", "Firefox wurde erkannt", "pass" if firefox_candidates else "warning", severity="medium", candidates=sorted(set(firefox_candidates)), platform=platform.system())

        packages = self.list_packages()
        trusted = [item for item in packages if item["trust_state"] in {"builtin_trusted", "signed_trusted"}]
        quarantined_enabled = [item["package_id"] for item in packages if "quarantine" in item["trust_state"] and item.get("enabled")]
        add("connector_catalog", "Connector-Katalog besitzt mindestens zehn vertrauenswürdige Pakete", "pass" if len(trusted) >= 10 else "blocker", trusted=len(trusted), total=len(packages))
        add("quarantine", "Quarantänisierte Pakete sind deaktiviert", "pass" if not quarantined_enabled else "blocker", enabled_quarantined=quarantined_enabled)
        policy = self.db.one("SELECT * FROM phase4_operational_policy_134 WHERE policy_id='phase4'") or {}
        add("external_code", "Drittcode-Ausführung bleibt deaktiviert", "pass" if policy.get("external_connector_code_execution") == "disabled" else "blocker")
        add("ai_boundary", "AI bleibt suggestions-only ohne externe Aktionen", "pass" if policy.get("ai_trust_state") == "suggestions_only" and int(policy.get("max_external_ai_actions") or 0) == 0 else "blocker")
        add("remote_server", "Remote-Servermodus bleibt deaktiviert", "pass" if policy.get("remote_server_mode") == "disabled_loopback_only" else "blocker")

        blockers = sum(1 for item in checks if item["status"] == "blocker")
        warnings = sum(1 for item in checks if item["status"] == "warning")
        score = max(0, 100 - blockers * 20 - warnings * 3)
        status = "pass" if blockers == 0 and warnings == 0 else "conditional" if blockers == 0 else "blocked"
        report = {"build": self.BUILD, "status": status, "score": score, "checks": checks, "blocker_count": blockers, "warning_count": warnings, "repair_mode": "advisory_only", "automatic_repair_actions": 0}
        run_id = new_id("preflight134")
        self.db.execute(
            """INSERT INTO runtime_preflight_runs_134(
               run_id,status,score,check_count,blocker_count,warning_count,report_json,created_by,created_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (run_id, status, score, len(checks), blockers, warnings, dumps(report), actor, now_ts()),
        )
        self._opsec(None, "runtime_preflight", "runtime", run_id, actor, {"status": status, "score": score, "blockers": blockers, "warnings": warnings, "full_paths_recorded": False, "automatic_repair_actions": 0})
        return {"run_id": run_id, **report}

    def preflight_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM runtime_preflight_runs_134 ORDER BY created_at DESC LIMIT ?", (max(1, min(int(limit), 200)),))

    def repair_plan(self, run_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM runtime_preflight_runs_134 WHERE run_id=?", (run_id,))
        if not row:
            raise Phase4OperationsError("Preflight-Lauf nicht gefunden")
        report = loads(row["report_json"], {})
        actions: list[dict[str, str]] = []
        mapping = {
            "release_files": "Build 150 erneut in einen neuen Ordner entpacken; keine alten Launcher darüberkopieren.",
            "launcher_contract": "START_EAGLEEYE_PRO_150_0.bat aus dem Originalpaket wiederherstellen.",
            "entry_contract": "EAGLEEYE_PRO_150_0.py aus dem Originalpaket wiederherstellen.",
            "dependencies": "INSTALL_EAGLEEYE_RUNTIME_150_0.bat ausführen und das Runtime-Log prüfen.",
            "python": "Python 3.11 oder neuer installieren und den Runtime-Installer erneut ausführen.",
            "writable": "EagleEye in einen normal beschreibbaren Benutzerordner verschieben.",
            "loopback": "Lokale Portblockaden oder Sicherheitssoftware prüfen; keinen Remote-Host konfigurieren.",
            "firefox": "Mozilla Firefox installieren oder dessen Standardpfad prüfen.",
            "database": "EagleEye schließen, Backup sichern und den Reliability-Restorepfad verwenden.",
            "quarantine": "Quarantänisierte Connectorpakete deaktiviert lassen und Signatur/Signer prüfen.",
        }
        for item in report.get("checks") or []:
            if item.get("status") in {"blocker", "warning"}:
                actions.append({"check_key": item.get("key", ""), "severity": item.get("severity", ""), "action": mapping.get(item.get("key"), "Prüfung manuell anhand der Diagnoseinformationen wiederholen.")})
        return {"run_id": run_id, "trust_state": "advisory_only", "automatic_actions": 0, "actions": actions}

    # ---------- local AI connector routing ----------
    def generate_connector_advice(self, *, case_id: str, target_id: str, objective: str, actor: str) -> dict[str, Any]:
        case = self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,))
        target = self.db.one("SELECT case_id FROM targets WHERE target_id=?", (target_id,))
        if not case or not target or target.get("case_id") != case_id:
            raise Phase4OperationsError("Fall-/Zielbindung verletzt")
        objective = " ".join(objective.strip().split())
        if not objective:
            raise Phase4OperationsError("Analyseziel fehlt")
        packages = [item for item in self.list_packages() if item["trust_state"] in {"builtin_trusted", "signed_trusted"} and item.get("enabled")]
        profile = self.research_strategy.scale.build_profile(case_id, target_id, persist=False)
        anchor_types = sorted({str(item.get("type") or "") for item in profile.get("anchors", []) if item.get("value")})
        lower = objective.casefold()
        ranked: list[dict[str, Any]] = []
        for package in packages:
            manifest = package["manifest"]
            inputs = set(manifest.get("input_types") or [])
            matched = sorted(inputs & set(anchor_types))
            health = self.providers.health_check(package["provider_key"])
            score = 0
            score += 50 if matched else 0
            score += 20 if health.get("status") == "healthy" else 5 if health.get("status") == "degraded" else -20
            connector_type = next((item.get("connector_type") for item in self.research_strategy.list_connectors() if item["connector_key"] == package["connector_key"]), "")
            keyword_map = {
                "publikation": {"scholarly_metadata", "scholarly_identity", "bibliographic_identity"},
                "autor": {"scholarly_metadata", "scholarly_identity", "bibliographic_identity"},
                "archiv": {"web_archive", "public_archive"},
                "domain": {"registry", "web_archive"},
                "username": {"code_profile"},
                "organisation": {"knowledge_base", "scholarly_identity"},
            }
            for keyword, types in keyword_map.items():
                if keyword in lower and connector_type in types:
                    score += 20
            ranked.append({
                "connector_key": package["connector_key"],
                "provider_key": package["provider_key"],
                "label": manifest.get("package_name"),
                "score": max(0, min(score, 100)),
                "matched_anchor_types": matched,
                "health": health.get("status"),
                "data_minimization": "single_reviewed_anchor",
                "network_state": "not_executed",
                "trust_state": package["trust_state"],
                "rationale": "Priorisiert vertrauenswürdige Connectoren mit passenden überprüften Ankertypen und stabilem Providerzustand.",
            })
        ranked.sort(key=lambda item: (-item["score"], item["connector_key"]))
        content = {
            "objective_sha256": _sha(objective),
            "anchor_types": anchor_types,
            "recommended_connectors": ranked[:10],
            "warnings": [
                "Empfehlung ist keine autonome Recherchefreigabe.",
                "Live-Zugriffe benötigen weiterhin die fallgebundene einmalige Providerfreigabe.",
                "Connectorergebnisse bleiben candidate-only und müssen unabhängig geprüft werden.",
            ],
            "trust_state": "suggestions_only",
            "external_actions": 0,
            "automatic_provider_runs": False,
            "automatic_evidence_promotion": False,
            "automatic_identity_confirmation": False,
        }
        serialized = dumps(content)
        advice_id = new_id("advice134")
        self.db.execute(
            """INSERT INTO connector_routing_advice_134(
               advice_id,case_id,target_id,objective_sha256,trust_state,review_status,external_actions,
               content_json,content_sha256,created_by,created_at)
               VALUES(?,?,?,?,'suggestions_only','pending',0,?,?,?,?)""",
            (advice_id, case_id, target_id, _sha(objective), serialized, hashlib.sha256(serialized.encode()).hexdigest(), actor, now_ts()),
        )
        self._opsec(case_id, "connector_advice_created", "connector_advice", advice_id, actor, {"objective_sha256": _sha(objective), "connector_count": len(ranked[:10]), "raw_objective_in_audit": False, "external_actions": 0})
        return {"advice_id": advice_id, **content}

    def advice_rows(self, case_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM connector_routing_advice_134 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, max(1, min(int(limit), 200))))

    def dashboard(self, case_id: str) -> dict[str, Any]:
        return {
            "status": self.status(),
            "packages": self.list_packages(),
            "signers": self.list_signers(),
            "contract_runs": self.contract_runs(50),
            "preflight_runs": self.preflight_runs(20),
            "advice": self.advice_rows(case_id, 20) if case_id else [],
        }

    def _opsec(self, case_id: str | None, event_type: str, object_type: str, object_id: str, actor: str, details: dict[str, Any]) -> None:
        self.db.execute(
            """INSERT INTO phase4_opsec_events_134(
               event_id,case_id,event_type,object_type,object_id,actor,details_json,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (new_id("opsec134"), case_id, event_type, object_type, object_id, actor, dumps(details), now_ts()),
        )
