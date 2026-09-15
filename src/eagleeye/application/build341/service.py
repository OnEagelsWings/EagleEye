from __future__ import annotations

import ast
import hashlib
import html
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DIMENSIONS = ("implemented", "integrated", "tested", "benchmarked", "externally_validated")


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


class Build341TruthfulBaselineService:
    """Phase-15 root composition service.

    Build 341 intentionally does *not* inherit Build 340. Build 340 remains a frozen
    compatibility layer, while all Phase-15 release claims are derived from explicit
    evidence dimensions. Internal behavioral tests can prove ``tested`` only; they
    cannot manufacture benchmark or independent external validation status.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        build340: Any,
        install_dir: str | Path,
        base_dir: str | Path,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.build340 = build340
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor
        self._root = self.install_dir

    # ---------- evidence binding ----------
    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/application/build341/service.py",
            "src/eagleeye/infrastructure/build341/schema.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/app.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "EAGLEEYE_PRO_341_0.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_341_0.py",
            "START_EAGLEEYE_PRO.bat",
            "START_EAGLEEYE_PRO_341_0.bat",
            "tests/test_build341.py",
        )

    def code_fingerprint(self) -> str:
        digest = hashlib.sha256()
        for rel in self._fingerprint_paths():
            path = self._root / rel
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            if path.is_file():
                digest.update(path.read_bytes())
            else:
                digest.update(b"<missing>")
            digest.update(b"\0")
        return digest.hexdigest()

    def _test_evidence(self) -> dict[str, Any]:
        data = _read_json(self._root / "BUILD_341_TEST_EVIDENCE.json")
        if data.get("build") != "341.0" or data.get("result") != "pass":
            return {}
        if data.get("code_fingerprint") != self.code_fingerprint():
            return {}
        probes = data.get("probes")
        if not isinstance(probes, dict):
            return {}
        return data

    def _probe_passed(self, probe: str) -> bool:
        return self._test_evidence().get("probes", {}).get(probe) == "pass"

    def _benchmark_evidence(self, capability_key: str) -> dict[str, Any]:
        data = _read_json(self._root / "benchmarks_341" / f"{capability_key}.json")
        metrics = data.get("metrics")
        if (
            data.get("result") == "pass"
            and data.get("code_fingerprint") == self.code_fingerprint()
            and isinstance(metrics, dict)
            and bool(metrics)
        ):
            return data
        return {}

    def _external_evidence(self, capability_key: str) -> dict[str, Any]:
        data = _read_json(self._root / "external_validation_341" / f"{capability_key}.json")
        report_sha = str(data.get("report_sha256", ""))
        if (
            data.get("result") == "pass"
            and data.get("code_fingerprint") == self.code_fingerprint()
            and data.get("validator_kind") == "independent"
            and str(data.get("validator", "")).strip()
            and str(data.get("validated_at", "")).strip()
            and re.fullmatch(r"[0-9a-fA-F]{64}", report_sha)
        ):
            return data
        return {}

    def _versions_match(self) -> tuple[bool, dict[str, str]]:
        version_py = (self._root / "eagleeye_pro/version.py").read_text(encoding="utf-8", errors="replace")
        pyproject = (self._root / "pyproject.toml").read_text(encoding="utf-8", errors="replace")
        build_match = re.search(r'^BUILD\s*=\s*["\']([^"\']+)', version_py, flags=re.MULTILINE)
        package_match = re.search(r'^version\s*=\s*["\']([^"\']+)', pyproject, flags=re.MULTILINE)
        build = build_match.group(1) if build_match else "unknown"
        package = package_match.group(1) if package_match else "unknown"
        normalized_build = build if build.count(".") >= 2 else f"{build}.0"
        return normalized_build == package, {"runtime_build": build, "package_version": package}

    def _primary_workspace_wired(self) -> bool:
        path = self._root / "src/eagleeye/interfaces/web/app.py"
        text = path.read_text(encoding="utf-8", errors="replace")
        return text.count("ctx.build341.render_workspace_panel") >= 8 and '@app.get("/api/build341")' in text

    def _capability_specs(self) -> list[dict[str, Any]]:
        versions_match, versions = self._versions_match()
        workspace_wired = self._primary_workspace_wired()
        specs: list[dict[str, Any]] = [
            {
                "key": "truthful_capability_registry", "name": "Truthful Capability Registry", "category": "phase15_foundation",
                "implemented": (self._root / "src/eagleeye/application/build341/service.py").is_file(), "integrated": True,
                "probe": "capability_registry", "baseline": True, "production": True,
                "evidence": ["five independent maturity dimensions", "fingerprint-bound internal test evidence"],
                "limitations": ["independent validation is not created by internal selftests"],
            },
            {
                "key": "phase15_agent_boundaries", "name": "Phase-15 Agent Boundaries", "category": "governance",
                "implemented": len(self.agent_boundaries()) == 6, "integrated": True, "probe": "agent_boundaries",
                "baseline": True, "production": True, "evidence": ["machine-readable six-component contract"],
                "limitations": ["runtime enforcement is expanded in Builds 343-359"],
            },
            {
                "key": "phase15_threat_model", "name": "Phase-15 Threat Model & Test Matrix", "category": "security",
                "implemented": len(self.threat_model()) >= 10 and len(self.test_matrix()) >= 10, "integrated": True,
                "probe": "threat_test_matrix", "baseline": True, "production": True,
                "evidence": ["versioned threat rows", "versioned verification matrix"],
                "limitations": ["specified/planned controls are not treated as implemented"],
            },
            {
                "key": "primary_workspace_phase15", "name": "Phase-15 Truth Layer in Primary Workspace", "category": "integration",
                "implemented": workspace_wired, "integrated": workspace_wired, "probe": "primary_workspace",
                "baseline": True, "production": True, "evidence": ["eight primary workspace views routed through Build 341 truth layer", "authenticated /api/build341 dashboard"],
                "limitations": ["legacy feature execution remains delegated to Build 340 until modular kernel work"],
            },
            {
                "key": "evidence_core", "name": "Evidence / Provenance Core", "category": "investigation_core",
                "implemented": (self._root / "src/eagleeye/application/evidence/service.py").is_file(), "integrated": True,
                "probe": "evidence_core", "baseline": False, "production": True,
                "evidence": ["existing evidence service is wired in AppContext"],
                "limitations": ["Build 341 does not claim fresh end-to-end regression or external validation"],
            },
            {
                "key": "dossier_vnext", "name": "Evidence-first Dossier vNext", "category": "investigation_core",
                "implemented": (self._root / "src/eagleeye/application/build338/service.py").is_file(), "integrated": True,
                "probe": "dossier_vnext", "baseline": False, "production": True,
                "evidence": ["Build 338 dossier service exists and remains compatibility-wired"],
                "limitations": ["no new Build-341 benchmark is inferred from historical selftests"],
            },
            {
                "key": "team_rbac_legacy", "name": "Legacy Team RBAC / Case ACL", "category": "authorization",
                "implemented": (self._root / "src/eagleeye/application/build339/service.py").is_file(), "integrated": True,
                "probe": "rbac_default_deny", "baseline": False, "production": False,
                "evidence": ["Build 339 authorization service present"],
                "limitations": ["not yet enforced consistently across the complete web/API/job surface; Build 359 owns full enforcement"],
            },
            {
                "key": "ai_investigation_supervisor", "name": "AI Investigation Supervisor", "category": "ai",
                "implemented": (self._root / "src/eagleeye/application/build337/service.py").is_file(), "integrated": True,
                "probe": "ai_supervisor", "baseline": False, "production": True,
                "evidence": ["Build 337 supervisor remains wired"],
                "limitations": ["Phase-15 approved Research-Waves and isolated delegation contract are not yet complete; Build 357"],
            },
            {
                "key": "packaging_version_consistency", "name": "Canonical Packaging / Versioning", "category": "packaging",
                "implemented": versions_match, "integrated": versions_match, "probe": "packaging_version",
                "baseline": False, "production": True, "evidence": [versions],
                "limitations": ([] if versions_match else ["pyproject/runtime version drift remains; Build 342 owns canonical packaging"]),
            },
        ]
        future = [
            ("schema_consolidation", "Schema Baseline v1 + Build-340 Migration", "data", 344),
            ("search_session_capsule", "Search-by-Search OPSEC Capsule", "opsec", 345),
            ("opsec_intelligence_v2", "OPSEC Intelligence v2", "opsec", 346),
            ("postgresql_team_backend", "PostgreSQL Team Backend", "infrastructure", 347),
            ("object_store_backend", "Evidence Object Store Backend", "infrastructure", 347),
            ("job_search_backbone", "Persistent Job / Queue / Search Backbone", "infrastructure", 348),
            ("live_data_pipeline", "Governed Live Data Pipelines", "data_access", 349),
            ("image_intelligence_agent", "Image Intelligence Agent", "image", 353),
            ("voice_gateway", "Push-to-talk Voice Gateway", "voice", 358),
            ("team_authorization_enforcement", "Route/Job-wide Team Authorization", "authorization", 359),
            ("independent_security_validation", "Independent Pentest / Red-Team Validation", "security", 360),
        ]
        for key, name, category, target in future:
            specs.append({
                "key": key, "name": name, "category": category, "implemented": False, "integrated": False,
                "probe": key, "baseline": False, "production": True, "evidence": [{"target_build": target}],
                "limitations": [f"not implemented or proven in Build 341; planned target Build {target}"],
            })
        return specs

    @staticmethod
    def _maturity(values: dict[str, bool]) -> str:
        maturity = "unavailable"
        for dimension in DIMENSIONS:
            if not values.get(dimension, False):
                break
            maturity = dimension
        return maturity

    def refresh_capability_registry(self) -> list[dict[str, Any]]:
        fingerprint = self.code_fingerprint()
        rows: list[dict[str, Any]] = []
        for spec in self._capability_specs():
            implemented = bool(spec["implemented"])
            integrated = implemented and bool(spec["integrated"])
            tested = integrated and self._probe_passed(str(spec["probe"]))
            benchmark = self._benchmark_evidence(str(spec["key"])) if tested else {}
            benchmarked = bool(benchmark)
            external = self._external_evidence(str(spec["key"])) if benchmarked else {}
            externally_validated = bool(external)
            states = {
                "implemented": implemented,
                "integrated": integrated,
                "tested": tested,
                "benchmarked": benchmarked,
                "externally_validated": externally_validated,
            }
            evidence = list(spec["evidence"])
            if tested:
                evidence.append({"internal_test_evidence": "BUILD_341_TEST_EVIDENCE.json", "probe": spec["probe"]})
            if benchmarked:
                evidence.append({"benchmark": benchmark})
            if externally_validated:
                evidence.append({"external_validation": external})
            row = {
                "capability_key": spec["key"], "display_name": spec["name"], "category": spec["category"],
                **states, "maturity": self._maturity(states), "evidence": evidence,
                "limitations": list(spec["limitations"]), "required_for_baseline": bool(spec["baseline"]),
                "required_for_production": bool(spec["production"]), "assessed_at": _now(),
                "code_fingerprint": fingerprint,
            }
            record_hash = _sha(row)
            self.db.execute(
                """INSERT OR REPLACE INTO phase15_capability_registry_341
                (capability_key,display_name,category,implemented,integrated,tested,benchmarked,externally_validated,
                 maturity,evidence_json,limitations_json,required_for_baseline,required_for_production,assessed_at,
                 code_fingerprint,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    row["capability_key"], row["display_name"], row["category"], int(implemented), int(integrated),
                    int(tested), int(benchmarked), int(externally_validated), row["maturity"], _canon(evidence),
                    _canon(row["limitations"]), int(row["required_for_baseline"]), int(row["required_for_production"]),
                    row["assessed_at"], fingerprint, record_hash,
                ),
            )
            row["record_hash"] = record_hash
            rows.append(row)
        return rows

    def capabilities(self) -> list[dict[str, Any]]:
        self.refresh_capability_registry()
        rows = self.db.all("SELECT * FROM phase15_capability_registry_341 ORDER BY category, capability_key")
        for row in rows:
            for key in (*DIMENSIONS, "required_for_baseline", "required_for_production"):
                row[key] = bool(row[key])
            row["evidence"] = json.loads(row.pop("evidence_json"))
            row["limitations"] = json.loads(row.pop("limitations_json"))
        return rows

    # ---------- contractual model ----------
    def agent_boundaries(self) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM phase15_agent_boundaries_341 ORDER BY component_key")
        for row in rows:
            row["may"] = json.loads(row.pop("may_json"))
            row["may_not"] = json.loads(row.pop("may_not_json"))
            row["confirmation_required"] = json.loads(row.pop("confirmation_required_json"))
        return rows

    def threat_model(self) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM phase15_threat_model_341 ORDER BY threat_id")

    def test_matrix(self) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM phase15_test_matrix_341 ORDER BY test_id")

    # ---------- quarantine of historical self-claims ----------
    def legacy_claim_audit(self) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        for build in range(304, 341):
            path = self._root / f"src/eagleeye/application/build{build}/service.py"
            if not path.is_file():
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
            except SyntaxError as exc:
                findings.append({"build": build, "path": str(path.relative_to(self._root)), "kind": "parse_error", "line": exc.lineno})
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
                    "qualified_gate", "run_extreme_qualification", "run_security_agent_selftest"
                }:
                    for child in ast.walk(node):
                        if isinstance(child, ast.Constant) and child.value is True:
                            findings.append({
                                "build": build, "path": str(path.relative_to(self._root)), "function": node.name,
                                "line": getattr(child, "lineno", None), "kind": "literal_true_in_legacy_gate",
                            })
        return {
            "authority": "non_authoritative",
            "policy": "Historical selftest/release claims are retained for reproducibility but cannot satisfy any Phase-15 benchmark or production-release dimension.",
            "finding_count": len(findings),
            "findings": findings,
        }

    def active_gate_literal_true_lines(self) -> list[int]:
        path = Path(__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "qualified_gate":
                return sorted({
                    int(child.lineno) for child in ast.walk(node)
                    if isinstance(child, ast.Constant) and child.value is True and hasattr(child, "lineno")
                })
        return []

    # ---------- authoritative gate ----------
    def qualified_gate(self) -> dict[str, Any]:
        capabilities = self.capabilities()
        baseline = [row for row in capabilities if row["required_for_baseline"]]
        production = [row for row in capabilities if row["required_for_production"]]
        baseline_ready = bool(baseline) and all(row["tested"] for row in baseline)
        production_ready = bool(production) and all(row["externally_validated"] for row in production)
        legacy = self.legacy_claim_audit()
        return {
            "build": "341.0",
            "phase": "15",
            "gate_authority": "evidence_backed_capability_registry",
            "legacy_release_claims": legacy["authority"],
            "legacy_literal_true_findings": legacy["finding_count"],
            "baseline_status": "accepted" if baseline_ready else "incomplete",
            "production_status": "externally_validated" if production_ready else "not_qualified",
            "baseline_ready": baseline_ready,
            "production_release_ready": production_ready,
            "release_ready": production_ready,
            "rule": "Internal tests can establish tested only; benchmarked and externally_validated require separate fingerprint-bound evidence.",
        }

    def record_assessment(self, *, created_by: str | None = None) -> dict[str, Any]:
        capabilities = self.capabilities()
        gate = self.qualified_gate()
        created_at = _now()
        payload = {
            "code_fingerprint": self.code_fingerprint(), "registry": capabilities,
            "baseline_status": gate["baseline_status"], "production_status": gate["production_status"],
            "created_by": created_by or self.actor, "created_at": created_at,
        }
        assessment_id = f"p15a341_{uuid.uuid4().hex[:16]}"
        record_hash = _sha(payload)
        self.db.execute(
            """INSERT INTO phase15_capability_assessments_341
            (assessment_id,code_fingerprint,registry_json,baseline_status,production_status,created_by,created_at,record_hash)
            VALUES(?,?,?,?,?,?,?,?)""",
            (assessment_id, payload["code_fingerprint"], _canon(capabilities), payload["baseline_status"],
             payload["production_status"], payload["created_by"], created_at, record_hash),
        )
        return {"assessment_id": assessment_id, **payload, "record_hash": record_hash}

    def dashboard(self) -> dict[str, Any]:
        return {
            "build": "341.0", "phase": "15", "name": "Truthful Baseline",
            "gate": self.qualified_gate(), "capabilities": self.capabilities(),
            "agent_boundaries": self.agent_boundaries(), "threat_model": self.threat_model(),
            "test_matrix": self.test_matrix(), "legacy_claim_audit": self.legacy_claim_audit(),
        }

    # ---------- compatibility rendering ----------
    def _truth_panel(self) -> str:
        gate = self.qualified_gate()
        capabilities = self.capabilities()
        rows = []
        for item in capabilities:
            mark = lambda key: "✓" if item[key] else "—"
            rows.append(
                "<tr>"
                f"<td>{html.escape(item['display_name'])}</td>"
                f"<td>{mark('implemented')}</td><td>{mark('integrated')}</td><td>{mark('tested')}</td>"
                f"<td>{mark('benchmarked')}</td><td>{mark('externally_validated')}</td>"
                f"<td><code>{html.escape(item['maturity'])}</code></td>"
                "</tr>"
            )
        return (
            '<section class="card" id="phase15-truthful-baseline">'
            '<h2>Phase 15 · Build 341 · Truthful Baseline</h2>'
            f"<p><b>Interne Baseline:</b> {html.escape(gate['baseline_status'])} · "
            f"<b>Produktionsfreigabe:</b> {html.escape(gate['production_status'])}</p>"
            '<p>Historische Selftest-/Release-Claims bleiben aus Reproduzierbarkeitsgründen erhalten, sind aber für Phase 15 '
            '<b>nicht autoritativ</b>. Interne Tests können ausschließlich den Status <code>tested</code> belegen.</p>'
            '<div style="overflow:auto"><table><thead><tr><th>Capability</th><th>Impl.</th><th>Integr.</th>'
            '<th>Tested</th><th>Bench.</th><th>External</th><th>Maturity</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>"
            '<p><small>Maschinenlesbar: <code>/api/build341</code></small></p></section>'
        )

    def render_workspace_panel(self, *, case_id: str, csrf: str, section: str) -> str:
        legacy = self.build340.render_workspace_panel(case_id=case_id, csrf=csrf, section=section)
        if section in {"cockpit", "operations", "expert"}:
            return self._truth_panel() + legacy
        return legacy
