from __future__ import annotations
import re
from pathlib import Path


class Build402AuthorizationMatrixAuditService:
    BUILD = "402.0"
    PACKAGE = "402.0.0"
    POLICY = "phase18.authorization-matrix-audit.v402"

    def __init__(self, db, audit, *, build401, matrix402, install_dir, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build401 = build401
        self.matrix402 = matrix402
        self.install_dir = Path(install_dir)
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build401, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def version_status(self):
        vt = (self.install_dir / "eagleeye_pro/version.py").read_text()
        pt = (self.install_dir / "pyproject.toml").read_text()
        pick = lambda pattern, text: (re.search(pattern, text, re.M).group(1) if re.search(pattern, text, re.M) else "unknown")
        runtime = pick(r'^BUILD\s*=\s*["\']([^"\']+)', vt)
        schema = pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', vt)
        package = pick(r'^version\s*=\s*["\']([^"\']+)', pt)
        return {"runtime_build": runtime, "schema_version": schema, "package_version": package, "coherent": runtime == schema == self.BUILD and package == self.PACKAGE}

    def authorization_matrix(self):
        return self.matrix402.matrix()

    def authorization_audit(self):
        return self.matrix402.audit()

    def role_matrix(self):
        return self.matrix402.role_matrix()

    def phase18_status(self, case_id=""):
        previous = dict(self.build401.phase18_status(case_id))
        auth = self.authorization_audit()
        previous.update({
            "build": self.BUILD,
            "phase": 18,
            "phase18_builds_completed": 2,
            "authorization_matrix_audit": auth["authorization_audit_pass"],
            "authorization_mutation_surfaces": len(auth["source_checks"]),
            "github_feedback_integrated": True,
            "five_build_feedback_cycle": True,
            "next_public_feedback_build": "405.0",
            "production_release_ready": False,
        })
        return previous

    def qualified_gate(self):
        version = self.version_status()
        security401 = self.build401.security_gate()
        auth = self.authorization_audit()
        role = self.role_matrix()
        checks = {
            "version_coherent": version["coherent"],
            "build401_security_gate_pass": security401["security_gate_pass"],
            "authorization_audit_pass": auth["authorization_audit_pass"],
            "read_only_has_no_catalogued_mutation_capability": role["read_only_has_mutation_capability"] is False,
            "global_scope_protected": auth["checks"]["global_acceptance_requires_review_capability"],
            "production_not_released": auth["production_release_ready"] is False,
        }
        return {"build": self.BUILD, "checks": checks, "build_acceptance_ready": all(checks.values()), "production_release_ready": False}
