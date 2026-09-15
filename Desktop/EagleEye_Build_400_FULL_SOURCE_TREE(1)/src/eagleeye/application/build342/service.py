from __future__ import annotations

import ast
import hashlib
import html
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


DIMENSIONS = ("implemented", "integrated", "tested", "benchmarked", "externally_validated")
_ONION_V3 = re.compile(r"^[a-z2-7]{56}\.onion$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Build342PackagingDarknetService:
    """Phase-15 Build 342 composition layer.

    Build 342 makes release metadata, launch paths and CI evidence coherent and adds
    the safe governance baseline for the Darknet Research Hardening workstream.
    The new v2 darknet path is intentionally non-networked in this build: it can
    register/review approved onion sources and create bounded research plans, but it
    cannot fetch, authenticate, submit forms, upload, contact, pay, execute binaries,
    bypass access controls, or acquire stolen/private datasets.
    """

    BUILD = "342.0"

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        build341: Any,
        build301: Any,
        install_dir: str | Path,
        base_dir: str | Path,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.build341 = build341
        self.build301 = build301
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor
        self._root = self.install_dir

    # ---------- evidence binding ----------
    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/application/build342/service.py",
            "src/eagleeye/infrastructure/build342/schema.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/app.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "requirements-runtime.txt",
            "requirements-windows.txt",
            "EAGLEEYE_PRO_342_0.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_342_0.py",
            "START_EAGLEEYE_PRO.bat",
            "START_EAGLEEYE_PRO_342_0.bat",
            "START_EAGLEEYE_PRO.sh",
            "tools/build_release_342.py",
            "tools/generate_sbom_342.py",
            "tests/test_build342.py",
            ".github/workflows/build342.yml",
            "RELEASE_PROFILE_BUILD_342_0.json",
            "DARKNET_RESEARCH_ROADMAP_BUILD_342_TO_360.md",
        )

    def code_fingerprint(self) -> str:
        digest = hashlib.sha256()
        for rel in self._fingerprint_paths():
            path = self._root / rel
            digest.update(rel.encode("utf-8")); digest.update(b"\0")
            digest.update(path.read_bytes() if path.is_file() else b"<missing>")
            digest.update(b"\0")
        return digest.hexdigest()

    def _test_evidence(self) -> dict[str, Any]:
        data = _read_json(self._root / "BUILD_342_TEST_EVIDENCE.json")
        if data.get("build") != self.BUILD or data.get("result") != "pass":
            return {}
        if data.get("code_fingerprint") != self.code_fingerprint():
            return {}
        return data if isinstance(data.get("probes"), dict) else {}

    def _probe_passed(self, probe: str) -> bool:
        return self._test_evidence().get("probes", {}).get(probe) == "pass"

    def _benchmark_evidence(self) -> dict[str, Any]:
        data = _read_json(self._root / "BENCHMARK_BUILD_342_REPRODUCIBILITY.json")
        if data.get("build") != self.BUILD or data.get("result") != "pass":
            return {}
        if data.get("code_fingerprint") != self.code_fingerprint():
            return {}
        digest = str(data.get("package_content_digest", ""))
        return data if re.fullmatch(r"[0-9a-f]{64}", digest) else {}

    def _wheel_benchmark_evidence(self) -> dict[str, Any]:
        data = _read_json(self._root / "BENCHMARK_BUILD_342_WHEEL_REPRODUCIBILITY.json")
        if data.get("build") != self.BUILD or data.get("result") != "pass":
            return {}
        if data.get("code_fingerprint") != self.code_fingerprint():
            return {}
        wheel_sha = str(data.get("wheel_sha256", ""))
        return data if re.fullmatch(r"[0-9a-f]{64}", wheel_sha) and data.get("wheel_version") == "342.0.0" else {}

    def active_gate_literal_true_lines(self) -> list[int]:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=str(Path(__file__)))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "qualified_gate":
                return sorted({
                    int(child.lineno) for child in ast.walk(node)
                    if isinstance(child, ast.Constant) and child.value is True and hasattr(child, "lineno")
                })
        return []

    # ---------- canonical release metadata ----------
    def version_status(self) -> dict[str, Any]:
        version_text = (self._root / "eagleeye_pro/version.py").read_text(encoding="utf-8", errors="replace")
        project_text = (self._root / "pyproject.toml").read_text(encoding="utf-8", errors="replace")
        runtime = re.search(r'^BUILD\s*=\s*["\']([^"\']+)', version_text, re.MULTILINE)
        schema = re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', version_text, re.MULTILINE)
        package = re.search(r'^version\s*=\s*["\']([^"\']+)', project_text, re.MULTILINE)
        runtime_v = runtime.group(1) if runtime else "unknown"
        schema_v = schema.group(1) if schema else "unknown"
        package_v = package.group(1) if package else "unknown"
        normalized = runtime_v if runtime_v.count(".") >= 2 else runtime_v + ".0"
        canonical_launcher = (self._root / "START_EAGLEEYE_PRO.bat").read_text(encoding="utf-8", errors="replace") if (self._root / "START_EAGLEEYE_PRO.bat").is_file() else ""
        posix_launcher = (self._root / "START_EAGLEEYE_PRO.sh").read_text(encoding="utf-8", errors="replace") if (self._root / "START_EAGLEEYE_PRO.sh").is_file() else ""
        coherent = normalized == package_v and runtime_v == schema_v == self.BUILD
        return {
            "runtime_build": runtime_v,
            "schema_version": schema_v,
            "package_version": package_v,
            "coherent": coherent,
            "windows_launcher_current": "EAGLEEYE_PRO_342_0.py" in canonical_launcher,
            "posix_launcher_current": "EAGLEEYE_PRO_342_0.py" in posix_launcher,
        }

    def runtime_manifest_status(self) -> dict[str, Any]:
        path = self._root / "RUNTIME_MANIFEST_BUILD_342_0.json"
        data = _read_json(path)
        files = data.get("files", [])
        failures: list[str] = []
        if data.get("build") != self.BUILD or not isinstance(files, list) or not files:
            failures.append("manifest_shape")
            files = []
        for item in files:
            rel = str(item.get("path", ""))
            expected = str(item.get("sha256", ""))
            target = self._root / rel
            if not rel or not target.is_file() or _file_sha(target) != expected:
                failures.append(rel or "missing_path")
        return {"valid": not failures, "file_count": len(files), "failures": failures[:20]}

    def sbom_status(self) -> dict[str, Any]:
        data = _read_json(self._root / "SBOM_BUILD_342_0.cdx.json")
        components = data.get("components", [])
        valid = (
            data.get("bomFormat") == "CycloneDX"
            and str(data.get("specVersion")) in {"1.5", "1.6"}
            and isinstance(components, list)
            and len(components) >= 10
        )
        return {
            "valid": valid,
            "component_count": len(components) if isinstance(components, list) else 0,
            "scope": data.get("metadata", {}).get("properties", []),
        }

    def ci_status(self) -> dict[str, Any]:
        path = self._root / ".github/workflows/build342.yml"
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        required = ("pytest", "build_release_342.py", "pip wheel", "SOURCE_DATE_EPOCH", "compileall")
        missing = [token for token in required if token not in text]
        return {"configured": path.is_file() and not missing, "missing_tokens": missing}

    def release_profile(self) -> dict[str, Any]:
        return _read_json(self._root / "RELEASE_PROFILE_BUILD_342_0.json")

    # ---------- safe darknet research v2 governance ----------
    def darknet_policy(self) -> dict[str, Any]:
        row = self.db.one("SELECT value_json FROM phase15_build342_state WHERE state_key=?", ("darknet_research_v2_policy",))
        return json.loads(row["value_json"]) if row else {}

    @staticmethod
    def _normalize_onion(value: str) -> str:
        raw = str(value or "").strip().lower()
        if "://" not in raw:
            raw = "http://" + raw
        parsed = urlsplit(raw)
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
            raise ValueError("Nur eine öffentliche/autorisiert genutzte v3-Onion-Adresse ohne Credentials ist zulässig.")
        host = (parsed.hostname or "").lower()
        if not _ONION_V3.fullmatch(host):
            raise ValueError("Es ist eine gültige Tor-v3 .onion-Adresse erforderlich.")
        return host

    def register_darknet_source(
        self,
        *,
        onion_url: str,
        display_name: str,
        source_class: str,
        jurisdiction: str = "unknown",
        allowed_use: str = "public_or_authorized_read_only",
        actor: str | None = None,
    ) -> dict[str, Any]:
        host = self._normalize_onion(onion_url)
        source_class = str(source_class or "unknown").strip().lower()
        if source_class not in {"journalism", "archive", "forum", "organization", "document_repository", "other"}:
            raise ValueError("Unbekannte Source-Class.")
        if allowed_use != "public_or_authorized_read_only":
            raise ValueError("Build 342 erlaubt nur public_or_authorized_read_only.")
        actor = actor or self.actor
        now = _now()
        source_id = "dsrc342_" + uuid.uuid4().hex[:16]
        payload = {
            "source_id": source_id,
            "onion_host": host,
            "display_name": str(display_name or host).strip()[:160],
            "source_class": source_class,
            "jurisdiction": str(jurisdiction or "unknown").strip()[:80],
            "allowed_use": allowed_use,
            "review_status": "candidate",
            "risk_class": "unreviewed",
            "created_by": actor,
            "created_at": now,
            "updated_at": now,
        }
        self.db.execute(
            """INSERT INTO phase15_darknet_sources_342
            (source_id,onion_host,display_name,source_class,jurisdiction,allowed_use,review_status,risk_class,
             created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                source_id, host, payload["display_name"], source_class, payload["jurisdiction"], allowed_use,
                "candidate", "unreviewed", actor, now, now, _sha(payload),
            ),
        )
        return payload | {"record_hash": _sha(payload)}

    def review_darknet_source(
        self,
        source_id: str,
        *,
        decision: str,
        rationale: str,
        reviewer: str | None = None,
    ) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase15_darknet_sources_342 WHERE source_id=?", (source_id,))
        if not row:
            raise KeyError(source_id)
        decision = str(decision or "").strip().lower()
        if decision not in {"approve_read_only", "reject", "quarantine"}:
            raise ValueError("Ungültige Review-Entscheidung.")
        rationale = str(rationale or "").strip()
        if len(rationale) < 8:
            raise ValueError("Review-Begründung ist erforderlich.")
        reviewer = reviewer or self.actor
        status = {"approve_read_only": "approved_read_only", "reject": "rejected", "quarantine": "quarantined"}[decision]
        risk = "reviewed" if decision == "approve_read_only" else ("blocked" if decision == "reject" else "quarantined")
        now = _now()
        event_id = "dre342_" + uuid.uuid4().hex[:16]
        event = {"event_id": event_id, "source_id": source_id, "decision": decision, "rationale": rationale, "reviewer": reviewer, "created_at": now}
        self.db.execute(
            "INSERT INTO phase15_darknet_review_events_342(event_id,source_id,decision,rationale,reviewer,created_at,record_hash) VALUES(?,?,?,?,?,?,?)",
            (event_id, source_id, decision, rationale, reviewer, now, _sha(event)),
        )
        updated = dict(row)
        updated.update({"review_status": status, "risk_class": risk, "updated_at": now})
        payload = {k: updated[k] for k in ("source_id","onion_host","display_name","source_class","jurisdiction","allowed_use","review_status","risk_class","created_by","created_at","updated_at")}
        self.db.execute(
            "UPDATE phase15_darknet_sources_342 SET review_status=?,risk_class=?,updated_at=?,record_hash=? WHERE source_id=?",
            (status, risk, now, _sha(payload), source_id),
        )
        return event | {"review_status": status, "risk_class": risk}

    def darknet_sources(self) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM phase15_darknet_sources_342 ORDER BY created_at, source_id")

    def create_darknet_research_plan(self, *, case_id: str, query: str, source_ids: list[str]) -> dict[str, Any]:
        query = str(query or "").strip()
        if not query:
            raise ValueError("Rechercheauftrag fehlt.")
        source_ids = list(dict.fromkeys(str(x) for x in source_ids if str(x).strip()))
        if not source_ids:
            raise ValueError("Mindestens eine reviewte Quelle ist erforderlich.")
        placeholders = ",".join("?" for _ in source_ids)
        rows = self.db.all(f"SELECT * FROM phase15_darknet_sources_342 WHERE source_id IN ({placeholders})", tuple(source_ids))
        approved = {row["source_id"] for row in rows if row["review_status"] == "approved_read_only"}
        if approved != set(source_ids):
            raise PermissionError("Alle Quellen müssen vor Planung als approved_read_only reviewt sein.")
        plan = {
            "plan_id": "drp342_" + uuid.uuid4().hex[:16],
            "case_id": str(case_id),
            "query": query,
            "source_ids": sorted(source_ids),
            "mode": "governance_only_no_network_execution",
            "network_execution": False,
            "allowed_methods_future": ["GET"],
            "credentials": False,
            "forms": False,
            "uploads": False,
            "contact": False,
            "payments": False,
            "binary_execution": False,
            "access_control_bypass": False,
            "stolen_or_private_dataset_acquisition": False,
            "opsec_preflight_required": True,
            "human_confirmation_required_before_future_external_request": True,
            "created_at": _now(),
        }
        return plan | {"plan_hash": _sha(plan)}

    def darknet_roadmap(self) -> list[dict[str, Any]]:
        return [
            {"build": 342, "goal": "Source governance, review states, provenance contract, safe non-networked planning"},
            {"build": 343, "goal": "Agent Task/Result contract; AI has no direct Tor/browser/network access"},
            {"build": 344, "goal": "Consolidated source/search/evidence schema and migration"},
            {"build": 345, "goal": "Per-search capsule with isolated approved Tor profile and state"},
            {"build": 346, "goal": "OPSEC v2 leakage, redirect, DNS/WebRTC, secret and malicious-content gates"},
            {"build": 347, "goal": "Durable evidence/object-store integration for quarantined darknet artifacts"},
            {"build": 348, "goal": "Persistent queue, retry/checkpoints, rate budgets and cancellation"},
            {"build": 349, "goal": "Crawler SDK with source governance and read-only onion contract"},
            {"build": 350, "goal": "Cross-source entity/organization correlation with provenance"},
            {"build": 351, "goal": "Legal/document extraction and contradiction handling"},
            {"build": 352, "goal": "Archive/history snapshots and source-health evidence"},
            {"build": 353, "goal": "Safe image/document extraction from quarantined artifacts"},
            {"build": 354, "goal": "Image similarity/duplicate leads with source separation"},
            {"build": 355, "goal": "Visual geolocation/manipulation signals remain hypotheses"},
            {"build": 356, "goal": "Evidence/graph/timeline fusion without automatic identity promotion"},
            {"build": 357, "goal": "Approved multi-wave investigation and controlled agent delegation"},
            {"build": 358, "goal": "Voice-requested darknet research still requires visible confirmation"},
            {"build": 359, "goal": "Team RBAC, case isolation, exports and release governance"},
            {"build": 360, "goal": "Independent security/red-team/pilot qualification of the complete path"},
        ]

    # ---------- current truthful capabilities ----------
    def _capability_specs(self) -> list[dict[str, Any]]:
        version = self.version_status()
        manifest = self.runtime_manifest_status()
        sbom = self.sbom_status()
        ci = self.ci_status()
        benchmark = self._benchmark_evidence()
        wheel_benchmark = self._wheel_benchmark_evidence()
        return [
            {"key":"phase15_truth_layer_342","name":"Current Phase-15 Truth Layer","category":"foundation","implemented":True,"integrated":True,"probe":"truth_layer","baseline":True,"production":True,"benchmark":False,"limits":["independent external validation is still absent"]},
            {"key":"canonical_versioning_342","name":"Canonical Build/Schema/Package Version","category":"packaging","implemented":version["coherent"],"integrated":version["windows_launcher_current"] and version["posix_launcher_current"],"probe":"packaging","baseline":True,"production":True,"benchmark":False,"limits":[]},
            {"key":"runtime_manifest_342","name":"Hashed Runtime Manifest","category":"packaging","implemented":manifest["valid"],"integrated":manifest["valid"],"probe":"runtime_manifest","baseline":True,"production":True,"benchmark":False,"limits":["manifest is release-integrity evidence, not an external attestation"]},
            {"key":"sbom_342","name":"CycloneDX Dependency Declaration SBOM","category":"supply_chain","implemented":sbom["valid"],"integrated":sbom["valid"],"probe":"sbom","baseline":True,"production":True,"benchmark":False,"limits":["records declared direct/optional dependencies; full transitive lock provenance remains separate"]},
            {"key":"deterministic_release_zip_342","name":"Deterministic Slim Release ZIP","category":"packaging","implemented":bool(self.release_profile()),"integrated":bool(self.release_profile()),"probe":"packaging","baseline":True,"production":True,"benchmark":bool(benchmark),"limits":[]},
            {"key":"deterministic_wheel_342","name":"Deterministic Python Wheel","category":"packaging","implemented":bool(wheel_benchmark),"integrated":bool(wheel_benchmark),"probe":"packaging","baseline":True,"production":True,"benchmark":bool(wheel_benchmark),"limits":["wheel covers Python package distribution; Windows launcher ZIP remains the primary portable desktop artifact"]},
            {"key":"ci_pipeline_342","name":"Canonical CI Pipeline","category":"quality","implemented":ci["configured"],"integrated":ci["configured"],"probe":"ci","baseline":True,"production":True,"benchmark":False,"limits":["repository-host execution remains external evidence and is not self-asserted"]},
            {"key":"darknet_research_v2_governance","name":"Darknet Research v2 Governance","category":"darknet","implemented":bool(self.darknet_policy()),"integrated":True,"probe":"darknet_governance","baseline":True,"production":True,"benchmark":False,"limits":["new v2 path intentionally opens no network connection in Build 342"]},
            {"key":"darknet_source_registry_342","name":"Reviewed Darknet Source Registry","category":"darknet","implemented":True,"integrated":True,"probe":"darknet_registry","baseline":True,"production":True,"benchmark":False,"limits":["source approval is not a truth/credibility endorsement"]},
            {"key":"search_session_capsule","name":"Per-search Search Session Capsule","category":"opsec","implemented":False,"integrated":False,"probe":"future","baseline":False,"production":True,"benchmark":False,"limits":["target Build 345"]},
            {"key":"opsec_intelligence_v2","name":"OPSEC Intelligence v2 Runtime Gate","category":"opsec","implemented":False,"integrated":False,"probe":"future","baseline":False,"production":True,"benchmark":False,"limits":["target Build 346"]},
            {"key":"image_intelligence_agent","name":"Image Intelligence Agent","category":"image","implemented":False,"integrated":False,"probe":"future","baseline":False,"production":True,"benchmark":False,"limits":["target Builds 353-356"]},
            {"key":"voice_gateway","name":"Push-to-talk Voice Gateway","category":"voice","implemented":False,"integrated":False,"probe":"future","baseline":False,"production":True,"benchmark":False,"limits":["target Build 358"]},
        ]

    @staticmethod
    def _maturity(states: dict[str, bool]) -> str:
        last = "declared"
        for key in DIMENSIONS:
            if states[key]:
                last = key
            else:
                break
        return last

    def capabilities(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        fingerprint = self.code_fingerprint()
        for spec in self._capability_specs():
            implemented = bool(spec["implemented"])
            integrated = implemented and bool(spec["integrated"])
            tested = integrated and self._probe_passed(spec["probe"])
            benchmarked = tested and bool(spec["benchmark"])
            externally_validated = False
            states = {
                "implemented": implemented,
                "integrated": integrated,
                "tested": tested,
                "benchmarked": benchmarked,
                "externally_validated": externally_validated,
            }
            rows.append({
                "capability_key": spec["key"], "display_name": spec["name"], "category": spec["category"],
                **states, "maturity": self._maturity(states), "required_for_baseline": bool(spec["baseline"]),
                "required_for_production": bool(spec["production"]), "limitations": spec["limits"],
                "code_fingerprint": fingerprint,
            })
        return rows

    def qualified_gate(self) -> dict[str, Any]:
        capabilities = self.capabilities()
        baseline = [row for row in capabilities if row["required_for_baseline"]]
        production = [row for row in capabilities if row["required_for_production"]]
        baseline_tested = bool(baseline) and all(row["tested"] for row in baseline)
        reproducibility = next((row for row in capabilities if row["capability_key"] == "deterministic_release_zip_342"), {})
        wheel_reproducibility = next((row for row in capabilities if row["capability_key"] == "deterministic_wheel_342"), {})
        build_acceptance = baseline_tested and bool(reproducibility.get("benchmarked")) and bool(wheel_reproducibility.get("benchmarked"))
        production_ready = bool(production) and all(row["externally_validated"] for row in production)
        return {
            "build": self.BUILD,
            "phase": "15",
            "gate_authority": "build342_evidence_backed_capability_registry",
            "build_acceptance_ready": build_acceptance,
            "production_release_ready": production_ready,
            "release_ready": production_ready,
            "baseline_tested": baseline_tested,
            "deterministic_package_benchmarked": bool(reproducibility.get("benchmarked")),
            "deterministic_wheel_benchmarked": bool(wheel_reproducibility.get("benchmarked")),
            "active_gate_literal_true_lines": self.active_gate_literal_true_lines(),
            "rule": "Internal tests can establish tested; reproducibility needs a separate benchmark; production remains external-validation gated.",
        }

    def dashboard(self) -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "phase": "15",
            "name": "Canonical Packaging, CI & Darknet Research v2 Governance",
            "gate": self.qualified_gate(),
            "version": self.version_status(),
            "runtime_manifest": self.runtime_manifest_status(),
            "sbom": self.sbom_status(),
            "ci": self.ci_status(),
            "capabilities": self.capabilities(),
            "darknet_policy": self.darknet_policy(),
            "darknet_sources": self.darknet_sources(),
            "darknet_roadmap": self.darknet_roadmap(),
        }

    def _panel(self) -> str:
        gate = self.qualified_gate()
        policy = self.darknet_policy()
        return (
            '<section class="card" id="phase15-build342">'
            '<h2>Phase 15 · Build 342 · Packaging/CI + Darknet Research Hardening</h2>'
            f'<p><b>Build-Abnahme:</b> {"bereit" if gate["build_acceptance_ready"] else "unvollständig"} · '
            f'<b>Produktionsfreigabe:</b> {"extern validiert" if gate["production_release_ready"] else "nicht qualifiziert"}</p>'
            '<p>Darknet Research v2 ist in Build 342 bewusst governance-only: Quellen können registriert und reviewt, '
            'Recherchepläne erstellt, aber über diesen neuen Pfad <b>keine Netzwerkverbindungen</b> geöffnet werden.</p>'
            f'<p><small>Policy: <code>{html.escape(str(policy.get("policy", "unknown")))}</code> · '
            'keine Credentials/Formulare/Uploads/Kontakt/Payments/Binary-Ausführung/Access-Control-Umgehung.</small></p>'
            '<p><small>Maschinenlesbar: <code>/api/build342</code></small></p></section>'
        )

    def render_workspace_panel(self, *, case_id: str, csrf: str, section: str) -> str:
        legacy = self.build341.render_workspace_panel(case_id=case_id, csrf=csrf, section=section)
        if section in {"cockpit", "sources", "operations", "expert"}:
            return self._panel() + legacy
        return legacy
