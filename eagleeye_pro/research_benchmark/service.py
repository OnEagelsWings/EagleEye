from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class ResearchBenchmarkLearningService:
    """Build 56.4 – benchmark and learning layer.

    Consolidates query/result feedback, precision metrics, source quality and
    session completion into a human-readable learning dashboard per entity.
    """

    def __init__(self, db: Database, audit: AuditService, search_quality=None, source_intel=None, deep_session=None):
        self.db = db
        self.audit = audit
        self.search_quality = search_quality
        self.source_intel = source_intel
        self.deep_session = deep_session
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS research_learning_reports_56_4 (
          report_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          score INTEGER NOT NULL,
          metrics_json TEXT NOT NULL,
          lessons_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def build_learning_report(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        benchmark = self.search_quality.compute_benchmark(case_id, entity_id=entity_id) if self.search_quality else {"metrics": {}}
        source_dash = self.source_intel.dashboard(case_id, entity_id) if self.source_intel else {"assessment_count": 0, "average_score": 0, "by_type": {}}
        session_dash = self.deep_session.dashboard(case_id, entity_id) if self.deep_session else {"sessions": []}
        metrics = {
            "precision_at_10": benchmark.get("metrics", {}).get("precision_at_10", 0),
            "useful_query_rate": benchmark.get("metrics", {}).get("useful_query_rate", 0),
            "duplicate_rate": benchmark.get("metrics", {}).get("duplicate_rate", 0),
            "false_positive_rate": benchmark.get("metrics", {}).get("false_positive_rate", 0),
            "source_assessments": source_dash.get("assessment_count", 0),
            "average_source_score": source_dash.get("average_score", 0),
            "session_count": session_dash.get("session_count", len(session_dash.get("sessions", []))),
        }
        lessons = self._lessons(metrics, source_dash.get("by_type", {}))
        score = self._score(metrics)
        rid = new_id("rbl564")
        self.db.execute("INSERT INTO research_learning_reports_56_4(report_id,case_id,entity_id,score,metrics_json,lessons_json,created_at) VALUES(?,?,?,?,?,?,?)", [rid, case_id, entity_id, score, dumps(metrics), dumps(lessons), now_ts()])
        self.audit.log("create", "research_learning_report_56_4", rid, case_id, {"entity_id": entity_id, "score": score})
        return {"report_id": rid, "case_id": case_id, "entity_id": entity_id, "score": score, "metrics": metrics, "lessons": lessons}

    def latest_reports(self, case_id: str, entity_id: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM research_learning_reports_56_4 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        for r in rows:
            r["metrics"] = loads(r.pop("metrics_json", "{}"), {})
            r["lessons"] = loads(r.pop("lessons_json", "[]"), [])
        return rows

    def _score(self, m: Dict[str, Any]) -> int:
        score = 45
        score += int(float(m.get("precision_at_10") or 0) * 25)
        score += int(float(m.get("useful_query_rate") or 0) * 20)
        score += min(10, int(m.get("source_assessments") or 0))
        score += min(10, int(float(m.get("average_source_score") or 0) / 10))
        score -= int(float(m.get("false_positive_rate") or 0) * 20)
        score -= int(float(m.get("duplicate_rate") or 0) * 10)
        return max(0, min(100, score))

    def _lessons(self, m: Dict[str, Any], by_type: Dict[str, int]) -> List[str]:
        lessons: List[str] = []
        if float(m.get("precision_at_10") or 0) < 0.5:
            lessons.append("Precision@10 niedrig: Query-Pyramide stärker mit Ort/Organisation/Rolle verankern.")
        if float(m.get("false_positive_rate") or 0) > 0.25:
            lessons.append("Viele False Positives: Namensdoppler-/Negativfilter ergänzen.")
        if float(m.get("duplicate_rate") or 0) > 0.3:
            lessons.append("Hohe Dublettenrate: kanonische URL und Quellenclustering nutzen.")
        if not by_type:
            lessons.append("Noch keine Quellengewichtung: Funde über Source Intelligence Pro bewerten.")
        elif max(by_type.values()) == sum(by_type.values()):
            lessons.append("Quellenmix einseitig: zweite unabhängige Quellentypebene ergänzen.")
        if not lessons:
            lessons.append("Research-Qualität solide: Schwerpunkt auf offene Fragen und Berichtsfähigkeit legen.")
        return lessons
