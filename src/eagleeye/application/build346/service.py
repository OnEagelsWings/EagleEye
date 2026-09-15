from __future__ import annotations

import ast
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from eagleeye.security.opsec_intelligence import OPSECIntelligenceV2, POLICY_VERSION as OPSEC_V2_POLICY
from eagleeye.security.search_capsule import POLICY_VERSION as CAPSULE_POLICY, SearchSessionCapsuleManager

DIMENSIONS = ("implemented", "integrated", "tested", "benchmarked", "externally_validated")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class Build346OPSECIntelligenceV2Service:
    BUILD = "346.0"

    def __init__(self, db: Any, audit: Any, *, build345: Any, capsule_manager: SearchSessionCapsuleManager, opsec_v2: OPSECIntelligenceV2, install_dir: str | Path, base_dir: str | Path, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build345 = build345
        self.capsules = capsule_manager
        self.opsec = opsec_v2
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor
        self._root = self.install_dir

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/infrastructure/schema_v1/schema.py",
            "src/eagleeye/security/search_capsule.py",
            "src/eagleeye/security/opsec_intelligence.py",
            "src/eagleeye/application/build346/service.py",
            "src/eagleeye/interfaces/web/app346.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "EAGLEEYE_PRO_346_0.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_346_0.py",
            "tests/test_build346.py",
        )

    def code_fingerprint(self) -> str:
        h = hashlib.sha256()
        for rel in self._fingerprint_paths():
            path = self._root / rel
            h.update(rel.encode()); h.update(b"\0")
            h.update(path.read_bytes() if path.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()

    def _test_evidence(self) -> dict[str, Any]:
        data = _read_json(self._root / "BUILD_346_TEST_EVIDENCE.json")
        if data.get("build") == self.BUILD and data.get("result") == "pass" and data.get("code_fingerprint") == self.code_fingerprint() and isinstance(data.get("probes"), dict):
            return data
        return {}

    def _probe(self, name: str) -> bool:
        return self._test_evidence().get("probes", {}).get(name) == "pass"

    def _benchmark(self) -> dict[str, Any]:
        data = _read_json(self._root / "BENCHMARK_BUILD_346_OPSEC_V2.json")
        if data.get("build") != self.BUILD or data.get("code_fingerprint") != self.code_fingerprint():
            return {}
        if data.get("cases", 0) < 300 or data.get("violations") != 0 or data.get("result") != "pass":
            return {}
        return data

    def active_gate_literal_true_lines(self) -> list[int]:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "qualified_gate":
                return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c, ast.Constant) and c.value is True and hasattr(c, "lineno")})
        return []

    def schema_metrics(self) -> dict[str, Any]:
        return self.build345.schema_metrics()

    def version_status(self) -> dict[str, Any]:
        version_text = (self._root / "eagleeye_pro/version.py").read_text(encoding="utf-8")
        project_text = (self._root / "pyproject.toml").read_text(encoding="utf-8")
        rb = re.search(r'^BUILD\s*=\s*["\']([^"\']+)', version_text, re.M)
        rs = re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', version_text, re.M)
        rp = re.search(r'^version\s*=\s*["\']([^"\']+)', project_text, re.M)
        runtime = rb.group(1) if rb else "unknown"; schema = rs.group(1) if rs else "unknown"; package = rp.group(1) if rp else "unknown"
        return {"runtime_build": runtime, "schema_version": schema, "package_version": package, "coherent": runtime == schema == self.BUILD and package == "346.0.0"}

    def register_darknet_source(self, **kwargs: Any) -> dict[str, Any]:
        return self.build345.register_darknet_source(**kwargs)

    def review_darknet_source(self, source_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.build345.review_darknet_source(source_id, **kwargs)

    def create_clearnet_capsule(self, **kwargs: Any) -> dict[str, Any]:
        return self.build345.create_clearnet_capsule(**kwargs)

    def create_darknet_research(self, **kwargs: Any) -> dict[str, Any]:
        return self.build345.create_darknet_research(**kwargs)

    def preflight_request(
        self,
        search_run_id: str,
        *,
        url: str,
        method: str = "GET",
        headers: Mapping[str, Any] | None = None,
        redirect_chain: list[str] | None = None,
        source_id: str | None = None,
        expected_response_bytes: int = 0,
        resolved_ips: Sequence[str] | None = None,
        browser_webrtc_disabled: bool | None = None,
        dns_via_approved_profile: bool | None = None,
    ) -> dict[str, Any]:
        base = self.capsules.preflight_request(search_run_id, url=url, method=method, headers=headers, redirect_chain=redirect_chain, source_id=source_id, expected_response_bytes=expected_response_bytes)
        if base["disposition"] != "allow_for_gateway":
            return {**base, "opsec_v2": None, "final_disposition": "block", "network_execution": False}
        intelligence = self.opsec.assess_request_descriptor(
            search_run_id,
            url=url,
            headers=headers,
            resolved_ips=resolved_ips,
            redirect_from=(redirect_chain or [None])[-1] if redirect_chain else None,
            browser_webrtc_disabled=browser_webrtc_disabled,
            dns_via_approved_profile=dns_via_approved_profile,
        )
        final = "allow_for_gateway" if intelligence["disposition"] in {"allow", "allow_with_sanitization"} else "block"
        self.db.execute("UPDATE phase15_search_runs SET opsec_state=? WHERE search_run_id=?", ("opsec_v2_passed" if final == "allow_for_gateway" else "blocked", search_run_id))
        return {**base, "opsec_v2": intelligence, "final_disposition": final, "sanitization_required": intelligence["disposition"] == "allow_with_sanitization", "network_execution": False}

    def inspect_content(self, search_run_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.opsec.inspect_content(search_run_id, **kwargs)

    def register_training_case(self, **kwargs: Any) -> dict[str, Any]:
        return self.opsec.register_training_case(**kwargs)

    def review_training_case(self, training_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.opsec.review_training_case(training_id, **kwargs)

    def training_status(self) -> dict[str, int]:
        return self.opsec.training_status()

    def close_capsule(self, search_run_id: str, *, actor: str | None = None) -> dict[str, Any]:
        return self.build345.close_capsule(search_run_id, actor=actor or self.actor)

    def list_capsules(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.build345.list_capsules(**kwargs)

    def decisions(self, search_run_id: str) -> list[dict[str, Any]]:
        return self.build345.decisions(search_run_id)

    def assessments(self, search_run_id: str) -> list[dict[str, Any]]:
        return self.opsec.assessments(search_run_id)

    def architecture_status(self) -> dict[str, Any]:
        files = [self._root / "src/eagleeye/security/search_capsule.py", self._root / "src/eagleeye/security/opsec_intelligence.py"]
        text = "\n".join(p.read_text(encoding="utf-8") for p in files)
        forbidden_imports = [name for name in ("subprocess", "socket", "requests", "httpx", "urllib.request") if re.search(rf"(^|\n)\s*(?:from\s+{re.escape(name)}\b|import\s+{re.escape(name)}\b)", text)]
        profiles = self.db.all("SELECT profile_id,profile_kind,runtime_execution_enabled,system_mutation_allowed,review_status FROM phase15_network_profiles ORDER BY profile_id")
        return {
            "capsule_policy": CAPSULE_POLICY,
            "opsec_v2_policy": OPSEC_V2_POLICY,
            "security_module_network_imports": forbidden_imports,
            "system_mutation_calls_present": any(x in text for x in ("subprocess.", "os.system(", "Popen(", "socket.socket(")),
            "runtime_network_execution": False,
            "deterministic_policy_final_authority": True,
            "ml_may_override_policy": False,
            "request_v2_preflight_required": True,
            "content_quarantine_supported": True,
            "human_review_training_workflow": True,
            "profiles": profiles,
        }

    @staticmethod
    def _maturity(states: dict[str, bool]) -> str:
        last = "declared"
        for key in DIMENSIONS:
            if states[key]: last = key
            else: break
        return last

    def capabilities(self) -> list[dict[str, Any]]:
        m=self.schema_metrics(); v=self.version_status(); a=self.architecture_status(); bench=bool(self._benchmark()); train=self.training_status(); fp=self.code_fingerprint()
        specs = [
            ("schema_baseline_v1_346", "Schema Baseline retained", "schema", m["within_gate"], m["within_gate"], "schema", False),
            ("search_session_capsule_v1_346", "Search Session Capsule retained", "opsec", True, True, "capsule", bench),
            ("opsec_intelligence_v2", "Deterministic OPSEC Intelligence v2", "opsec", True, True, "opsec_v2", bench),
            ("dns_ssrf_rebinding_defense_v2", "DNS/SSRF/rebinding evidence gate", "opsec", True, True, "network_leakage", bench),
            ("webrtc_redirect_tracking_defense_v2", "WebRTC/redirect/tracking leakage controls", "opsec", True, True, "network_leakage", bench),
            ("content_prompt_injection_quarantine_v2", "Content, secret and prompt-injection quarantine", "opsec", True, True, "content", bench),
            ("opsec_reviewed_training_workflow_v2", "OPSEC training review workflow with provenance and split", "training", True, True, "training", False),
            ("human_reviewed_opsec_corpus", "Human-reviewed OPSEC training corpus", "training", train["human_reviewed"] > 0, train["human_reviewed"] > 0, "human_corpus", False),
            ("no_autonomous_security_mutation_346", "No autonomous Tor/proxy/firewall/OS/credential mutation", "opsec", not a["system_mutation_calls_present"] and not a["security_module_network_imports"], not a["system_mutation_calls_present"] and not a["security_module_network_imports"], "boundary", bench),
            ("canonical_versioning_346", "Canonical Build 346 version contract", "packaging", v["coherent"], v["coherent"], "version", False),
            ("live_search_gateway", "Live external Search/Crawler gateway", "network", False, False, "future", False),
            ("postgres_team_backend", "PostgreSQL team backend", "infrastructure", False, False, "future", False),
        ]
        required={"schema_baseline_v1_346","search_session_capsule_v1_346","opsec_intelligence_v2","dns_ssrf_rebinding_defense_v2","webrtc_redirect_tracking_defense_v2","content_prompt_injection_quarantine_v2","opsec_reviewed_training_workflow_v2","no_autonomous_security_mutation_346","canonical_versioning_346"}
        rows=[]
        for key,name,category,implemented,integrated,probe,benchmarkable in specs:
            tested=bool(integrated and self._probe(probe)); states={"implemented":bool(implemented),"integrated":bool(implemented and integrated),"tested":tested,"benchmarked":bool(tested and benchmarkable),"externally_validated":False}
            rows.append({"capability_key":key,"display_name":name,"category":category,**states,"maturity":self._maturity(states),"required_for_build":key in required,"required_for_production":key not in {"schema_baseline_v1_346","human_reviewed_opsec_corpus"},"code_fingerprint":fp})
        return rows

    def qualified_gate(self) -> dict[str, Any]:
        rows=self.capabilities(); required=[r for r in rows if r["required_for_build"]]; tested=bool(required) and all(r["tested"] for r in required); benchmarked=any(r["capability_key"]=="opsec_intelligence_v2" and r["benchmarked"] for r in rows); production=[r for r in rows if r["required_for_production"]]; production_ready=bool(production) and all(r["externally_validated"] for r in production)
        return {"build":self.BUILD,"phase":"15","gate_authority":"build346_opsec_v2_evidence_gate","build_acceptance_ready":tested and benchmarked,"production_release_ready":production_ready,"release_ready":production_ready,"baseline_tested":tested,"opsec_v2_benchmarked":benchmarked,"active_gate_literal_true_lines":self.active_gate_literal_true_lines(),"rule":"Deterministic OPSEC policy is final authority. Statistical/ML ranking may never override a block. No autonomous Tor/proxy/firewall/OS/credential mutation."}

    def dashboard(self) -> dict[str, Any]:
        return {"build":self.BUILD,"phase":"15","name":"OPSEC Intelligence v2 + Darknet Research Hardening","gate":self.qualified_gate(),"version":self.version_status(),"schema":self.schema_metrics(),"architecture":self.architecture_status(),"training":self.training_status(),"capabilities":self.capabilities(),"capsule_count":len(self.list_capsules(limit=500)),"runtime_network_execution":False}

    def render_workspace_panel(self, *, case_id: str, csrf: str, section: str = "cockpit") -> str:
        if section not in {"cockpit","sources","operations","expert"}: return ""
        caps=self.list_capsules(case_id=case_id,limit=20); assessment_count=int(self.db.one("SELECT COUNT(*) c FROM phase15_opsec_assessments WHERE case_id=?",(case_id,))["c"]); training=self.training_status()
        rows="".join(f"<tr><td><code>{html.escape(c['search_run_id'])}</code></td><td>{html.escape(c['search_kind'])}</td><td>{html.escape(c['capsule_state'])}</td><td>{len(self.assessments(c['search_run_id']))}</td></tr>" for c in caps) or "<tr><td colspan='4'>Noch keine Search Capsules.</td></tr>"
        return f"<section class='card'><h2>Build 346 · OPSEC Intelligence v2</h2><p>Deterministische Leakage-, SSRF/Rebinding-, Redirect-, Tracking-, Secret- und Content/Prompt-Injection-Prüfung. Policy-Blöcke können durch ML nicht überschrieben werden.</p><p><b>Security Assessments:</b> {assessment_count} · <b>menschlich reviewte Trainingsfälle:</b> {training['human_reviewed']} · <b>Netzwerkausführung:</b> OFF</p><table><thead><tr><th>Run</th><th>Typ</th><th>Status</th><th>v2 Assessments</th></tr></thead><tbody>{rows}</tbody></table></section>"
