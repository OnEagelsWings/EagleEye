from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import json
import zipfile

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class ProfessionalOperationsReleaseService:
    """Build 58.0 – Professional Operations Release.

    Integrates the high-performance research stack into one operational report:
    person workspace, source quality, deep-research sessions, benchmark/learning,
    document intelligence, register/archive paths, privacy/export checks and
    casefile bundle creation.
    """

    def __init__(self, db: Database, audit: AuditService, reports_root: str | Path, *, person_workspace=None, source_intel=None, deep_session=None, learning=None, document_intel=None, register_archive=None, person_detail=None, privacy_finish=None):
        self.db = db
        self.audit = audit
        self.reports_root = Path(reports_root)
        self.reports_root.mkdir(parents=True, exist_ok=True)
        self.person_workspace = person_workspace
        self.source_intel = source_intel
        self.deep_session = deep_session
        self.learning = learning
        self.document_intel = document_intel
        self.register_archive = register_archive
        self.person_detail = person_detail
        self.privacy_finish = privacy_finish
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS professional_operations_runs_58_0 (
          run_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          decision TEXT NOT NULL,
          readiness_score INTEGER DEFAULT 0,
          package_path TEXT DEFAULT '',
          summary_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def run_professional_cycle(self, case_id: str, entity: Dict[str, Any]) -> Dict[str, Any]:
        entity_id = entity.get("entity_id")
        if not entity_id:
            raise ValueError("entity_id required")
        # Prepare core quality artifacts without external/live scraping.
        workspace = self.person_workspace.build_workspace(case_id, entity_id) if self.person_workspace else {}
        source_assess = self.source_intel.assess_search_results(case_id, entity_id) if self.source_intel else {"assessed": 0}
        session = self.deep_session.start_session(case_id, entity_id, objective="Professional Operations QA / Guided Research") if self.deep_session else {}
        phase = self.deep_session.run_phase(session["session_id"]) if self.deep_session and session else {}
        paths = self.register_archive.build_paths(case_id, entity) if self.register_archive else {"path_count": 0}
        learning = self.learning.build_learning_report(case_id, entity_id) if self.learning else {"score": 0}
        docs = self.document_intel.list_extracts(case_id, entity_id) if self.document_intel else []
        decision = self._decision(workspace, learning)
        summary = {
            "workspace_readiness": workspace.get("readiness_score", 0),
            "workspace_label": workspace.get("readiness_label", ""),
            "source_assessed": source_assess.get("assessed", 0),
            "session_id": session.get("session_id", ""),
            "phase_run": phase.get("phase_run_id", ""),
            "register_paths": paths.get("path_count", 0),
            "learning_score": learning.get("score", 0),
            "document_extracts": len(docs),
            "decision": decision,
        }
        run_id = new_id("ops580")
        self.db.execute("INSERT INTO professional_operations_runs_58_0(run_id,case_id,entity_id,decision,readiness_score,package_path,summary_json,created_at) VALUES(?,?,?,?,?,?,?,?)", [run_id, case_id, entity_id, decision, int(summary["workspace_readiness"] or 0), "", dumps(summary), now_ts()])
        self.audit.log("run", "professional_operations_58_0", run_id, case_id, {"entity_id": entity_id, "decision": decision})
        return {"run_id": run_id, "case_id": case_id, "entity_id": entity_id, "decision": decision, "summary": summary, "workspace": workspace, "source_assessment": source_assess, "session": session, "phase": phase, "register_paths": paths, "learning": learning, "document_extracts": docs}

    def export_professional_case_package(self, case_id: str, entity_id: str, *, run_id: str = "") -> Dict[str, Any]:
        workspace = self.person_workspace.build_workspace(case_id, entity_id, persist_snapshot=False) if self.person_workspace else {}
        source_dash = self.source_intel.dashboard(case_id, entity_id) if self.source_intel else {}
        learning_reports = self.learning.latest_reports(case_id, entity_id, limit=5) if self.learning else []
        register_paths = self.register_archive.dashboard(case_id, entity_id) if self.register_archive else {}
        docs = self.document_intel.list_extracts(case_id, entity_id, limit=50) if self.document_intel else []
        narratives = workspace.get("narratives", [])
        findings = workspace.get("findings", [])
        claims = workspace.get("claims", [])
        md = self._casefile_markdown(workspace, source_dash, learning_reports, register_paths, docs)
        out_dir = self.reports_root / f"Professional_Case_Package_{case_id}_{entity_id}_{now_ts().replace(':','').replace('-','')}"
        out_dir.mkdir(parents=True, exist_ok=True)
        files: Dict[str, str] = {}
        def write(name: str, content: str):
            p = out_dir / name; p.write_text(content, encoding="utf-8"); files[name] = str(p)
        write("01_PROFESSIONAL_CASEFILE.md", md)
        write("02_WORKSPACE.json", json.dumps(workspace, ensure_ascii=False, indent=2, default=str))
        write("03_SOURCE_QUALITY.json", json.dumps(source_dash, ensure_ascii=False, indent=2, default=str))
        write("04_LEARNING_REPORTS.json", json.dumps(learning_reports, ensure_ascii=False, indent=2, default=str))
        write("05_REGISTER_ARCHIVE_PATHS.json", json.dumps(register_paths, ensure_ascii=False, indent=2, default=str))
        write("06_DOCUMENT_EXTRACTS.json", json.dumps(docs, ensure_ascii=False, indent=2, default=str))
        manifest = {"build": "58.0", "case_id": case_id, "entity_id": entity_id, "run_id": run_id, "created_at": now_ts(), "files": sorted(files), "counts": {"findings": len(findings), "claims": len(claims), "narratives": len(narratives), "document_extracts": len(docs)}}
        write("07_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zip_path = out_dir.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for name, path in files.items():
                z.write(path, arcname=name)
        if run_id:
            self.db.execute("UPDATE professional_operations_runs_58_0 SET package_path=? WHERE run_id=?", [str(zip_path), run_id])
        self.audit.log("export", "professional_operations_package_58_0", run_id or entity_id, case_id, {"entity_id": entity_id, "zip": str(zip_path)})
        return {"case_id": case_id, "entity_id": entity_id, "package_dir": str(out_dir), "zip_path": str(zip_path), "manifest": manifest}

    def dashboard(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM professional_operations_runs_58_0 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT 30"
        rows = self.db.all(sql, params)
        for r in rows:
            r["summary"] = loads(r.pop("summary_json", "{}"), {})
        return {"case_id": case_id, "entity_id": entity_id, "run_count": len(rows), "runs": rows}

    def _decision(self, workspace: Dict[str, Any], learning: Dict[str, Any]) -> str:
        ws = int(workspace.get("readiness_score") or 0)
        ls = int(learning.get("score") or 0)
        if ws >= 85 and ls >= 75:
            return "professional_ready"
        if ws >= 65:
            return "usable_with_review"
        return "continue_research"

    def _casefile_markdown(self, workspace: Dict[str, Any], source_dash: Dict[str, Any], learning_reports: List[Dict[str, Any]], register_paths: Dict[str, Any], docs: List[Dict[str, Any]]) -> str:
        entity = workspace.get("entity", {})
        lines = [
            f"# Professional Operations Casefile – {entity.get('display_name', workspace.get('entity_id',''))}",
            "", "## Readiness", f"- Score: {workspace.get('readiness_score', 0)}", f"- Label: {workspace.get('readiness_label', '')}", "",
            "## Kernmetriken", json.dumps(workspace.get("metrics", {}), ensure_ascii=False, indent=2), "",
            "## Offene Prüffragen",
        ]
        for q in workspace.get("open_questions", []) or ["Keine offenen Prüffragen erfasst."]:
            lines.append(f"- {q}")
        lines += ["", "## Berichtsfähige Funde / Claims"]
        lanes = workspace.get("status_lanes", {})
        for item in lanes.get("fakten_hinweise", [])[:30]:
            title = item.get("title") or item.get("claim_text") or item.get("claim_type") or item.get("finding_note_id", "Fund")
            lines.append(f"- {title}")
        lines += ["", "## Quellenqualität", f"- Assessments: {source_dash.get('assessment_count', 0)}", f"- Durchschnitt: {source_dash.get('average_score', 0)}", f"- Quellenmix: {source_dash.get('by_type', {})}", "", "## Learning / Benchmark"]
        for r in learning_reports[:3]:
            lines.append(f"- Score {r.get('score')}: {', '.join(r.get('lessons', [])[:3])}")
        lines += ["", "## Register-/Archivpfade", f"- Pfade: {register_paths.get('path_count', 0)}", f"- Status: {register_paths.get('by_status', {})}", "", "## Dokumentextrakte", f"- Extrakte: {len(docs)}", "", "## Hinweis", "Dieses Paket ist review-first. Öffentlich auffindbar bedeutet nicht automatisch frei verwertbar; Namensdoppler, sensible Daten und Gegenbelege sind vor Weitergabe zu prüfen."]
        return "\n".join(lines)
