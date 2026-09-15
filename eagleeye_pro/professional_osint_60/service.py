from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import json
import hashlib

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


def _sha_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


class ProfessionalOSINTAlternative60Service:
    """Build 60.0 professional OSINT alternative release orchestrator.

    This service ties together provider connectors, browser capture, OSINT core,
    evaluation and reporting into one auditable operational package while keeping
    the existing compact UI model intact.
    """

    def __init__(self, db: Database, audit: AuditService, output_dir: str | Path, *, provider_sdk, browser_capture, evaluation_lab, osint_core, person_detail=None, privacy_finish=None):
        self.db = db
        self.audit = audit
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.provider_sdk = provider_sdk
        self.browser_capture = browser_capture
        self.evaluation_lab = evaluation_lab
        self.osint_core = osint_core
        self.person_detail = person_detail
        self.privacy_finish = privacy_finish
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS professional_osint60_packages (
          package_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          session_id TEXT DEFAULT '',
          eval_id TEXT DEFAULT '',
          package_path TEXT NOT NULL,
          readiness_score REAL DEFAULT 0,
          readiness_label TEXT DEFAULT '',
          manifest_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def run_professional_cycle(self, case_id: str, entity: Dict[str, Any], category_key: str, *, serp_text: str = "", engine: str = "manual_serp_capture") -> Dict[str, Any]:
        session = self.osint_core.latest_or_start(case_id, entity, category_key)
        feed = None
        if serp_text.strip():
            feed = self.osint_core.import_result_feed(session["session_id"], serp_text, engine=engine)
        else:
            self.osint_core.build_source_graph(session["session_id"])
            self.osint_core.build_claims(session["session_id"])
            self.osint_core.generate_next_actions(session["session_id"])
        evaluation = self.evaluation_lab.evaluate_session(session["session_id"])
        preflight = self.provider_sdk.preflight_query("manual_serp_capture", self._top_query(session["session_id"]), case_id=case_id, entity_id=entity.get("entity_id", ""), category_key=category_key)
        package = self.create_operations_package(case_id, entity.get("entity_id", ""), session["session_id"], evaluation["eval_id"])
        return {"session": session, "feed": feed or {}, "evaluation": evaluation, "provider_preflight": preflight, "package": package}

    def _top_query(self, session_id: str) -> str:
        dash = self.osint_core.dashboard(session_id)
        queries = dash.get("spearhead", {}).get("top_queries", [])
        return queries[0].get("query", "") if queries else ""

    def create_operations_package(self, case_id: str, entity_id: str, session_id: str, eval_id: str = "") -> Dict[str, Any]:
        dash = self.osint_core.dashboard(session_id)
        evaluation = None
        if eval_id:
            rows = self.evaluation_lab.latest(case_id, entity_id, limit=10)
            evaluation = next((r for r in rows if r.get("eval_id") == eval_id), None)
        if not evaluation:
            evaluation = self.evaluation_lab.evaluate_session(session_id)
        package_id = new_id("ops60")
        pkg_dir = self.output_dir / package_id
        pkg_dir.mkdir(parents=True, exist_ok=True)
        casefile_md = self._render_casefile(dash, evaluation)
        files = {
            "01_PROFESSIONAL_OSINT_CASEFILE.md": casefile_md,
            "02_OSINT_DASHBOARD.json": json.dumps(dash, ensure_ascii=False, indent=2, default=str),
            "03_EVALUATION.json": json.dumps(evaluation, ensure_ascii=False, indent=2, default=str),
            "04_PROVIDER_CONNECTORS.json": json.dumps(self.provider_sdk.list_connectors(), ensure_ascii=False, indent=2, default=str),
            "05_NEXT_ACTIONS.json": json.dumps(dash.get("next_actions", []), ensure_ascii=False, indent=2, default=str),
        }
        manifest_files: List[Dict[str, Any]] = []
        for name, content in files.items():
            path = pkg_dir / name
            path.write_text(content, encoding="utf-8")
            manifest_files.append({"path": name, "sha256": _sha_text(content), "size": path.stat().st_size})
        manifest = {"build": "60.0", "package_id": package_id, "case_id": case_id, "entity_id": entity_id, "session_id": session_id, "eval_id": evaluation.get("eval_id", eval_id), "created_at": now_ts(), "files": manifest_files, "readiness_score": evaluation.get("overall_score", 0), "readiness_label": evaluation.get("professional_label", "")}
        (pkg_dir / "06_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self.db.execute('''INSERT INTO professional_osint60_packages(package_id,case_id,entity_id,session_id,eval_id,package_path,readiness_score,readiness_label,manifest_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)''', [package_id, case_id, entity_id, session_id, evaluation.get("eval_id", eval_id), str(pkg_dir), evaluation.get("overall_score", 0), evaluation.get("professional_label", ""), dumps(manifest), now_ts()])
        self.audit.log("export", "professional_osint_package_60", package_id, case_id, {"readiness": evaluation.get("overall_score", 0)})
        return {"package_id": package_id, "path": str(pkg_dir), "manifest": manifest}

    def dashboard(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        evals = self.evaluation_lab.latest(case_id, entity_id, limit=5)
        packages = self.db.all("SELECT * FROM professional_osint60_packages WHERE case_id=? AND (?='' OR entity_id=?) ORDER BY created_at DESC LIMIT 5", [case_id, entity_id, entity_id])
        connectors = self.provider_sdk.list_connectors()
        return {"build": "60.0", "connectors": connectors, "latest_evaluations": evals, "packages": packages, "readiness": evals[0]["professional_label"] if evals else "not_evaluated"}

    def _render_casefile(self, dash: Dict[str, Any], evaluation: Dict[str, Any]) -> str:
        session = dash.get("session", {})
        lines = [
            "# EagleEye Professional OSINT Casefile – Build 60.0",
            "",
            f"Session: `{session.get('session_id','')}`",
            f"Mission: `{session.get('mission_id','')}`",
            f"Readiness: **{evaluation.get('overall_score',0)}** ({evaluation.get('professional_label','')})",
            "",
            "## Qualitätsmetriken",
        ]
        for k, v in (evaluation.get("metrics") or {}).items():
            lines.append(f"- {k}: {v}")
        if evaluation.get("gaps"):
            lines += ["", "## Offene Qualitätslücken"] + [f"- {g}" for g in evaluation.get("gaps", [])]
        lines += ["", "## Claims"]
        for c in dash.get("claims", [])[:20]:
            lines.append(f"- **{c.get('confidence_label','candidate')}**: {c.get('statement','')} | Quellen: {c.get('evidence_count',0)} | Reportability: {c.get('reportability','')}")
        lines += ["", "## Nächste Suchaktionen"]
        for a in dash.get("next_actions", [])[:15]:
            lines.append(f"- Prio {a.get('priority')}: {a.get('title')} — `{a.get('query','')}`")
        lines += ["", "## Quellen-/Trefferhinweis", "Dieses Paket enthält nur öffentliche, dokumentierte Trefferkandidaten. Jeder Claim bleibt prüfpflichtig und muss vor externer Übergabe redigiert werden."]
        return "\n".join(lines) + "\n"
