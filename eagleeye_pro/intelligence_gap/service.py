from __future__ import annotations
from typing import Any, Dict, List
import json
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService

COVERAGE_AREAS = [
    ("identity", "Identitätsanker", "target, review and evidence anchors"),
    ("profiles", "Profile/Beruf/Kontext", "public profile, career and context traces"),
    ("image_media", "Bild-/Medienlage", "image, media and reverse-search traces"),
    ("geo", "Geo-/Ortslage", "location and map context"),
    ("documents", "Dokumente/PDFs/Archive", "documents, PDFs, press and archives"),
    ("company_register", "Firma/Register/Domain", "company, register and domain traces"),
    ("counter_evidence", "Gegenbelege/Namensdoppler", "counter-evidence and name-doppler checks"),
    ("review", "Review-Abdeckung", "review queue status"),
    ("evidence", "Evidence-Stärke", "evidence and manifest quality"),
    ("graph", "Graph-Beziehungen", "explainable relationship map"),
    ("timeline", "Timeline", "chronological event coverage"),
    ("reporting", "Report Readiness", "report/export readiness"),
]

class IntelligenceGapDetectorService:
    """Build 38/39 Intelligence Gap Detector.

    Measures workflow/evidence coverage only. It never scores people, guilt, danger,
    location certainty, or biometric identity. Outputs are operational gaps and next
    research steps for the analyst.
    """
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS intelligence_gap_profiles (
          profile_id TEXT PRIMARY KEY, profile_key TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
          purpose TEXT NOT NULL, areas_json TEXT NOT NULL, created_at TEXT NOT NULL, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS coverage_matrix (
          coverage_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, area_key TEXT NOT NULL, area_title TEXT NOT NULL,
          status TEXT NOT NULL, score REAL DEFAULT 0.0, observed_count INTEGER DEFAULT 0,
          required_count INTEGER DEFAULT 1, evidence_refs_json TEXT DEFAULT '[]', warnings_json TEXT DEFAULT '[]',
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS research_gap_scores (
          score_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, research_completeness REAL DEFAULT 0.0,
          evidence_strength REAL DEFAULT 0.0, counter_evidence_coverage REAL DEFAULT 0.0,
          identity_confidence REAL DEFAULT 0.0, report_readiness REAL DEFAULT 0.0,
          overall_workflow_score REAL DEFAULT 0.0, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS gap_recommendations (
          recommendation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, area_key TEXT NOT NULL,
          priority INTEGER DEFAULT 3, title TEXT NOT NULL, recommendation TEXT NOT NULL,
          next_phase_key TEXT DEFAULT '', status TEXT DEFAULT 'open', created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS coverage_snapshots (
          snapshot_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, snapshot_json TEXT NOT NULL,
          created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS report_readiness_metrics (
          metric_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, report_type TEXT NOT NULL,
          readiness_status TEXT NOT NULL, score REAL DEFAULT 0.0, blockers_json TEXT NOT NULL,
          warnings_json TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_coverage_matrix_case ON coverage_matrix(case_id, created_at, area_key);
        CREATE INDEX IF NOT EXISTS idx_gap_scores_case ON research_gap_scores(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_gap_recommendations_case ON gap_recommendations(case_id, status, priority);
        CREATE INDEX IF NOT EXISTS idx_coverage_snapshots_case ON coverage_snapshots(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_report_readiness_metrics_case ON report_readiness_metrics(case_id, report_type, created_at);
        ''')
        self.db.conn.commit()

    def seed_defaults(self) -> None:
        self.ensure_schema()
        self.db.execute("""INSERT OR IGNORE INTO intelligence_gap_profiles(profile_id,profile_key,title,purpose,areas_json,created_at,active)
        VALUES(?,?,?,?,?,?,1)""", [new_id("igp"), "person_osint_standard", "PersonenOSINT Standard Coverage", "Coverage- und Gap-Prüfung für legale PersonenOSINT-Fälle.", dumps([a[0] for a in COVERAGE_AREAS]), now_ts()])

    def _counts(self, case_id: str) -> Dict[str, Any]:
        def c(table: str, where: str = "case_id=?", params: List[Any] | None = None) -> int:
            row = self.db.one(f"SELECT COUNT(*) AS n FROM {table} WHERE {where}", params or [case_id]) or {}
            return int(row.get("n") or 0)
        review_open = c("review_items", "case_id=? AND status IN ('new','in_review','needs_source_review')", [case_id])
        review_done = c("review_items", "case_id=? AND status IN ('accepted_as_lead','ready_for_evidence','promoted_to_evidence','rejected','duplicate','conflicting')", [case_id])
        evidence = c("evidence_items")
        exportable = c("evidence_items", "case_id=? AND export_allowed=1 AND redaction_required=0", [case_id])
        counter = c("review_items", "case_id=? AND (status='conflicting' OR markers_json LIKE '%gegen%' OR markers_json LIKE '%counter%')", [case_id])
        counter += c("graph_contradictions", "case_id=?", [case_id])
        return {
            "targets": c("targets"),
            "search_tasks": c("search_tasks"),
            "search_captures": c("source_captures"),
            "review_items": c("review_items"),
            "review_open": review_open,
            "review_done": review_done,
            "evidence_items": evidence,
            "exportable_evidence": exportable,
            "graph_nodes": c("graph_nodes"),
            "graph_edges": c("graph_edges"),
            "timeline_events": c("timeline_events"),
            "identity_candidates": c("identity_candidates"),
            "risk_findings": c("risk_findings"),
            "privacy_flags_open": c("sensitive_data_flags", "case_id=? AND status IN ('open','auto_detected')", [case_id]),
            "counter_evidence": counter,
            "reports": c("professional_reports"),
            "query_matrix": c("query_factory_queries") if self._table_exists("query_factory_queries") else 0,
            "capture_inbox": c("capture_inbox_items") if self._table_exists("capture_inbox_items") else 0,
        }

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]))

    @staticmethod
    def _status(score: float) -> str:
        if score >= 0.75:
            return "green"
        if score >= 0.40:
            return "yellow"
        if score > 0:
            return "red"
        return "grey"

    def assess_case(self, case_id: str, persist: bool = True) -> Dict[str, Any]:
        self.ensure_schema()
        counts = self._counts(case_id)
        area_scores = {
            "identity": min(1, (counts["targets"] + counts["identity_candidates"] + counts["evidence_items"]) / 3),
            "profiles": min(1, (counts["review_items"] + counts["search_tasks"]) / 8),
            "image_media": min(1, self._category_count(case_id, ["image", "media", "bild", "photo"]) / 2),
            "geo": min(1, self._category_count(case_id, ["geo", "ort", "maps", "location"]) / 2),
            "documents": min(1, self._category_count(case_id, ["pdf", "document", "archive", "presse", "news"]) / 3),
            "company_register": min(1, self._category_count(case_id, ["firma", "company", "register", "domain", "impressum"]) / 3),
            "counter_evidence": min(1, counts["counter_evidence"] / 2),
            "review": 1.0 if counts["review_items"] == 0 else max(0.0, min(1.0, counts["review_done"] / max(1, counts["review_items"]))),
            "evidence": min(1, counts["evidence_items"] / 5),
            "graph": min(1, (counts["graph_nodes"] + counts["graph_edges"] * 2) / 10),
            "timeline": min(1, counts["timeline_events"] / 4),
            "reporting": min(1, (counts["reports"] + counts["exportable_evidence"]) / 3),
        }
        matrix=[]
        recs=[]
        phase_map={"identity":"02_identity_web","profiles":"03_profiles_context","image_media":"04_image_media_reverse","geo":"05_geo_maps_context","documents":"06_documents_registers_archives","company_register":"06_documents_registers_archives","counter_evidence":"07_counter_evidence","review":"08_capture_review_duplicates","evidence":"09_evidence_graph_timeline","graph":"09_evidence_graph_timeline","timeline":"09_evidence_graph_timeline","reporting":"10_report_export"}
        for key,title,purpose in COVERAGE_AREAS:
            score=round(float(area_scores.get(key,0)),3)
            status=self._status(score)
            warnings=[]
            if status in {"red","grey"}:
                warnings.append(f"{title} ist schwach oder offen.")
                recs.append({"area_key":key,"priority":1 if status=="red" else 2,"title":f"{title} nacharbeiten","recommendation":f"Phase {phase_map.get(key,'')} öffnen und gezielt öffentliche/autorisiert verfügbare Quellen prüfen.","next_phase_key":phase_map.get(key,"")})
            matrix.append({"area_key":key,"area_title":title,"purpose":purpose,"status":status,"score":score,"observed_count":self._observed_for_area(counts,key),"required_count":1,"warnings":warnings})
        research = round(sum(area_scores[k] for k in ["identity","profiles","image_media","geo","documents","company_register"]) / 6, 3)
        evidence_strength = round((area_scores["evidence"]*0.55 + area_scores["review"]*0.25 + area_scores["graph"]*0.20), 3)
        counter_cov = round(area_scores["counter_evidence"],3)
        identity_conf = round((area_scores["identity"]*0.65 + counter_cov*0.35),3)
        report_ready = round((area_scores["reporting"]*0.5 + evidence_strength*0.3 + counter_cov*0.2),3)
        overall = round((research + evidence_strength + counter_cov + identity_conf + report_ready) / 5, 3)
        payload={"case_id":case_id,"counts":counts,"coverage_matrix":matrix,"gap_recommendations":recs,"scores":{"research_completeness":research,"evidence_strength":evidence_strength,"counter_evidence_coverage":counter_cov,"identity_confidence":identity_conf,"report_readiness":report_ready,"overall_workflow_score":overall},"created_at":now_ts(),"safety":"Scores measure workflow/evidence coverage only, not a person."}
        if persist:
            self._persist(case_id,payload)
        return payload

    def _category_count(self, case_id: str, needles: List[str]) -> int:
        parts=[]; params=[case_id]
        for n in needles:
            parts.append("LOWER(category || ' ' || title || ' ' || COALESCE(statement,'')) LIKE ?")
            params.append(f"%{n.lower()}%")
        ev = self.db.one("SELECT COUNT(*) AS n FROM evidence_items WHERE case_id=? AND ("+" OR ".join(parts)+")", params) or {}
        parts2=[]; params2=[case_id]
        for n in needles:
            parts2.append("LOWER(category || ' ' || query || ' ' || engine) LIKE ?")
            params2.append(f"%{n.lower()}%")
        st = self.db.one("SELECT COUNT(*) AS n FROM search_tasks WHERE case_id=? AND ("+" OR ".join(parts2)+")", params2) or {}
        return int(ev.get("n") or 0)+int(st.get("n") or 0)

    @staticmethod
    def _observed_for_area(counts: Dict[str, int], key: str) -> int:
        mapping={"identity":"targets","profiles":"review_items","image_media":"search_tasks","geo":"search_tasks","documents":"search_tasks","company_register":"search_tasks","counter_evidence":"counter_evidence","review":"review_done","evidence":"evidence_items","graph":"graph_edges","timeline":"timeline_events","reporting":"reports"}
        return int(counts.get(mapping.get(key,"search_tasks"),0))

    def _persist(self, case_id: str, payload: Dict[str, Any]) -> None:
        ts=now_ts()
        for row in payload["coverage_matrix"]:
            self.db.execute("""INSERT INTO coverage_matrix(coverage_id,case_id,area_key,area_title,status,score,observed_count,required_count,evidence_refs_json,warnings_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [new_id("cov"), case_id, row["area_key"], row["area_title"], row["status"], row["score"], row["observed_count"], row["required_count"], dumps([]), dumps(row.get("warnings",[])), ts])
        s=payload["scores"]
        self.db.execute("""INSERT INTO research_gap_scores(score_id,case_id,research_completeness,evidence_strength,counter_evidence_coverage,identity_confidence,report_readiness,overall_workflow_score,created_at)
        VALUES(?,?,?,?,?,?,?,?,?)""", [new_id("igs"), case_id, s["research_completeness"], s["evidence_strength"], s["counter_evidence_coverage"], s["identity_confidence"], s["report_readiness"], s["overall_workflow_score"], ts])
        for r in payload["gap_recommendations"]:
            self.db.execute("""INSERT INTO gap_recommendations(recommendation_id,case_id,area_key,priority,title,recommendation,next_phase_key,status,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""", [new_id("gap"), case_id, r["area_key"], r["priority"], r["title"], r["recommendation"], r["next_phase_key"], "open", ts])
        self.db.execute("INSERT INTO coverage_snapshots(snapshot_id,case_id,snapshot_json,created_at,notes) VALUES(?,?,?,?,?)", [new_id("covsnap"), case_id, dumps(payload), ts, "Build 39 Gap Detector Snapshot"])
        self.audit.log("assess", "intelligence_gap", case_id, case_id, {"overall": s["overall_workflow_score"], "recommendations": len(payload["gap_recommendations"])})

    def latest_dashboard(self, case_id: str) -> Dict[str, Any]:
        snap=self.db.one("SELECT * FROM coverage_snapshots WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if snap:
            return loads(snap.get("snapshot_json"), {})
        return self.assess_case(case_id, persist=True)
