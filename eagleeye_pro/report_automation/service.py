from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List
import json, hashlib
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.reporting.service import ReportService
from eagleeye_pro.intelligence_gap.service import IntelligenceGapDetectorService

class EvidenceToReportAutomationService:
    """Build 39.0 Evidence-to-Report Automation.

    Creates report drafts from reviewed evidence, graph/timeline narratives, gap
    signals and readiness checks. It remains assistive: no automatic identity,
    guilt, danger or private-address assertions.
    """
    def __init__(self, db: Database, audit: AuditService, reports: ReportService):
        self.db = db
        self.audit = audit
        self.reports = reports
        self.gaps = IntelligenceGapDetectorService(db, audit)

    def ensure_schema(self) -> None:
        self.gaps.ensure_schema()
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS report_automation_blueprints (
          blueprint_id TEXT PRIMARY KEY, blueprint_key TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
          report_type TEXT NOT NULL, sections_json TEXT NOT NULL, audience TEXT NOT NULL,
          created_at TEXT NOT NULL, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS report_automation_runs (
          run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, report_type TEXT NOT NULL,
          redaction_profile TEXT NOT NULL, status TEXT NOT NULL, readiness_status TEXT DEFAULT '',
          gap_score REAL DEFAULT 0.0, created_at TEXT NOT NULL, completed_at TEXT DEFAULT '', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS report_section_drafts (
          draft_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, section_key TEXT NOT NULL,
          title TEXT NOT NULL, draft_text TEXT NOT NULL, source_refs_json TEXT NOT NULL,
          confidence TEXT DEFAULT 'draft', requires_review INTEGER DEFAULT 1, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(run_id) REFERENCES report_automation_runs(run_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS report_automation_findings (
          finding_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, finding_type TEXT NOT NULL,
          severity TEXT DEFAULT 'info', title TEXT NOT NULL, description TEXT NOT NULL, status TEXT DEFAULT 'open', created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(run_id) REFERENCES report_automation_runs(run_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS report_automation_exports (
          export_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, report_id TEXT DEFAULT '',
          export_paths_json TEXT NOT NULL, content_hash TEXT DEFAULT '', status TEXT DEFAULT 'created', created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(run_id) REFERENCES report_automation_runs(run_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_report_auto_runs_case ON report_automation_runs(case_id, created_at, status);
        CREATE INDEX IF NOT EXISTS idx_report_section_drafts_case ON report_section_drafts(case_id, section_key, created_at);
        CREATE INDEX IF NOT EXISTS idx_report_auto_findings_case ON report_automation_findings(case_id, severity, status);
        CREATE INDEX IF NOT EXISTS idx_report_auto_exports_case ON report_automation_exports(case_id, created_at, status);
        ''')
        self.db.conn.commit()

    def seed_defaults(self) -> None:
        self.ensure_schema()
        sections = ["executive_summary", "scope", "methodology", "source_matrix", "identity_candidates", "timeline_narrative", "graph_narrative", "uncertainties", "counter_evidence", "evidence_annex", "next_steps"]
        self.db.execute("""INSERT OR IGNORE INTO report_automation_blueprints(blueprint_id,blueprint_key,title,report_type,sections_json,audience,created_at,active)
        VALUES(?,?,?,?,?,?,?,1)""", [new_id("rab"), "evidence_to_report_standard", "Evidence-to-Report Standard Pipeline", "redacted_client", dumps(sections), "client_or_internal", now_ts()])

    @staticmethod
    def _hash(obj: Any) -> str:
        return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()

    def pipeline_dashboard(self, case_id: str, report_type: str="redacted_client") -> Dict[str, Any]:
        self.ensure_schema()
        data = self.reports.collect_case_data(case_id)
        readiness = self.reports.report_readiness(case_id, report_type)
        gaps = self.gaps.assess_case(case_id, persist=True)
        metrics = {
            "review_items": len(data.get("review_items", [])),
            "evidence_items": len(data.get("evidence_items", [])),
            "exportable_evidence": len([e for e in data.get("evidence_items", []) if e.get("export_allowed") and not e.get("redaction_required")]),
            "timeline_events": len(data.get("timeline_events", [])),
            "graph_edges": len(data.get("graph_edges", [])),
            "counter_evidence": len(data.get("graph_contradictions", [])),
            "gap_overall": gaps.get("scores", {}).get("overall_workflow_score", 0),
            "report_readiness_score": gaps.get("scores", {}).get("report_readiness", 0),
        }
        blockers = list(readiness.get("blockers", []))
        warnings = list(readiness.get("warnings", []))
        if metrics["evidence_items"] == 0:
            blockers.append("Keine Evidence Items vorhanden: Report-Automation kann nur einen leeren Strukturentwurf erzeugen.")
        if metrics["counter_evidence"] == 0:
            warnings.append("Keine Gegenbelege/Widersprüche im Graph: Namensdoppler- und Gegenbelegphase prüfen.")
        status = "blocked" if blockers else ("review_required" if warnings else "ready")
        return {"case_id":case_id,"report_type":report_type,"status":status,"metrics":metrics,"readiness":readiness,"gap_scores":gaps.get("scores",{}),"gap_recommendations":gaps.get("gap_recommendations",[]),"blockers":blockers,"warnings":warnings}

    def _section_texts(self, data: Dict[str, Any], gaps: Dict[str, Any], report_type: str) -> Dict[str, str]:
        evidence = data.get("evidence_items", [])
        exportable = [e for e in evidence if e.get("export_allowed") and not e.get("redaction_required")]
        lines_ev = [f"- {e.get('title')} | {e.get('category')} | Reliability {e.get('reliability_score')} | {e.get('source_url')}" for e in (exportable or evidence)[:20]]
        timeline = data.get("timeline_events", [])
        graph_edges = data.get("graph_edges", [])
        uncertainty = self.reports.build_uncertainty_register(data)
        source_critique = self.reports.build_source_critique(data)
        return {
            "executive_summary": self.reports.build_executive_summary(data, report_type),
            "scope": f"Fallzweck: {data['case'].get('purpose')}\nRechtsgrundlage: {data['case'].get('legal_basis')}\nGrenze: öffentliche oder autorisierte Quellen, keine privaten Accountbereiche, keine automatischen Identitäts-/Schuld-/Gefährlichkeitsbehauptungen.",
            "methodology": self.reports.build_methodology(data, "short" if report_type in {"client_short","redacted_client"} else "full"),
            "source_matrix": "Quellenkritik:\n" + "\n".join(f"- {s.get('source_reliability')}: {s.get('count')} Items, Ø {s.get('avg_reliability_score')}" for s in source_critique),
            "identity_candidates": "Identitätskandidaten werden nur als Plausibilitäten geführt:\n" + "\n".join(f"- {i.get('label','Kandidat')} | Score {i.get('score','')} | Status {i.get('status','candidate')}" for i in data.get("identity_candidates", [])[:10]) or "Keine Identitätskandidaten vorhanden.",
            "timeline_narrative": "Timeline-Narrativ:\n" + "\n".join(f"- {t.get('event_date')}: {t.get('title')} ({t.get('confidence')})" for t in timeline[:20]) if timeline else "Timeline ist noch leer oder nicht ausreichend belegt.",
            "graph_narrative": "Graph-Narrativ:\n" + "\n".join(f"- {g.get('relationship_type')} | Confidence {g.get('confidence')} | {g.get('explanation','')}" for g in graph_edges[:20]) if graph_edges else "Graph enthält noch keine belastbaren Beziehungen/Kanten.",
            "uncertainties": "Unsicherheiten:\n" + "\n".join(f"- {u.get('type')} / {u.get('severity')}: {u.get('title')} – {u.get('description')}" for u in uncertainty[:20]) if uncertainty else "Keine dokumentierten Unsicherheiten; Gegenbelegphase trotzdem prüfen.",
            "counter_evidence": "Gegenbelege/Gaps:\n" + "\n".join(f"- {r.get('title')}: {r.get('recommendation')}" for r in gaps.get("gap_recommendations", [])[:12]),
            "evidence_annex": "Evidence-Anlagenindex:\n" + ("\n".join(lines_ev) if lines_ev else "Keine Evidence Items vorhanden."),
            "next_steps": "Empfohlene nächste Schritte:\n" + "\n".join(f"- {r.get('recommendation')}" for r in gaps.get("gap_recommendations", [])[:8]),
        }

    def generate_report_draft(self, case_id: str, report_type: str="redacted_client", redaction_profile: str="client_safe", notes: str="") -> Dict[str, Any]:
        self.ensure_schema()
        data = self.reports.collect_case_data(case_id)
        gaps = self.gaps.assess_case(case_id, persist=True)
        dash = self.pipeline_dashboard(case_id, report_type)
        run_id = new_id("raut")
        ts = now_ts()
        self.db.execute("""INSERT INTO report_automation_runs(run_id,case_id,report_type,redaction_profile,status,readiness_status,gap_score,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?)""", [run_id, case_id, report_type, redaction_profile, dash["status"], dash.get("readiness",{}).get("status",""), float(gaps.get("scores",{}).get("overall_workflow_score",0)), ts, notes])
        sections = self._section_texts(data, gaps, report_type)
        drafts=[]
        for key, text in sections.items():
            did = new_id("draft")
            refs = {"evidence_ids":[e.get("evidence_id") for e in data.get("evidence_items", [])[:30]], "source":"Build39 deterministic pipeline"}
            self.db.execute("""INSERT INTO report_section_drafts(draft_id,run_id,case_id,section_key,title,draft_text,source_refs_json,confidence,requires_review,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", [did, run_id, case_id, key, key.replace("_"," ").title(), text, dumps(refs), "draft_requires_human_review", 1, ts])
            drafts.append({"draft_id":did,"section_key":key,"title":key.replace("_"," ").title(),"draft_text":text})
        for b in dash.get("blockers", []):
            self.db.execute("INSERT INTO report_automation_findings(finding_id,run_id,case_id,finding_type,severity,title,description,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)", [new_id("raf"), run_id, case_id, "blocker", "high", "Report-Blocker", b, "open", ts])
        for w in dash.get("warnings", []):
            self.db.execute("INSERT INTO report_automation_findings(finding_id,run_id,case_id,finding_type,severity,title,description,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)", [new_id("raf"), run_id, case_id, "warning", "medium", "Report-Warnung", w, "open", ts])
        self.audit.log("create", "report_automation_run", run_id, case_id, {"report_type":report_type,"status":dash["status"],"draft_sections":len(drafts)})
        return {"run_id":run_id,"draft_id":run_id,"status":dash["status"],"sections":drafts,"metrics":dash["metrics"],"safety":"Draft only; human review required."}

    def export_automated_report(self, case_id: str, outdir: str|Path, report_type: str="redacted_client", redaction_profile: str="client_safe") -> Dict[str, Any]:
        draft = self.generate_report_draft(case_id, report_type, redaction_profile, notes="Automated pre-export draft generated.")
        paths = self.reports.export_professional_report(case_id, outdir, report_type, redaction_profile, notes="Build 39 Evidence-to-Report Automation export; draft requires human review.")
        export_id = new_id("raex")
        self.db.execute("INSERT INTO report_automation_exports(export_id,run_id,case_id,report_id,export_paths_json,content_hash,status,created_at) VALUES(?,?,?,?,?,?,?,?)", [export_id, draft["run_id"], case_id, paths.get("report_id",""), dumps(paths), paths.get("content_hash",""), "created", now_ts()])
        self.audit.log("export", "report_automation", export_id, case_id, {"report_type": report_type, "paths": paths})
        return {"export_id": export_id, "run_id": draft["run_id"], **paths}
