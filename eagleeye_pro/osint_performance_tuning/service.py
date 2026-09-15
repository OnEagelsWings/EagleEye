from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class OSINTSearchPerformanceTuningService:
    """Build 61.1: tuning suggestions from calibration data."""

    def __init__(self, db: Database, audit: AuditService, *, calibration=None):
        self.db = db
        self.audit = audit
        self.calibration = calibration
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS osint_tuning_reports_61_1 (
          tuning_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT DEFAULT '',
          recommendations_json TEXT NOT NULL,
          weight_changes_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def create_tuning_report(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        runs = self.calibration.latest(case_id, entity_id, limit=20) if self.calibration else []
        recommendations: List[str] = []
        weights: Dict[str, int] = {}
        if not runs:
            recommendations.append("Zuerst Praxistest-/Kalibrierungslauf durchführen.")
        else:
            avg_score = sum(float(r.get("metrics", {}).get("operational_score", 0)) for r in runs) / max(1, len(runs))
            avg_claim_rate = sum(float(r.get("metrics", {}).get("reportable_findings_rate_proxy", 0)) for r in runs) / max(1, len(runs))
            doppler = sum(int(r.get("metrics", {}).get("doppler_high", 0)) for r in runs)
            if avg_score < 70:
                recommendations.append("Präzisionsqueries höher priorisieren; SERP-Importe für Top-Queries erzwingen.")
                weights["precision_queries"] = +10
            if avg_claim_rate < 0.25:
                recommendations.append("Claim-Building stärken: Top-Funde schneller als report_ready/needs_review einstufen.")
                weights["claim_builder"] = +8
            if doppler > 0:
                recommendations.append("Doppler-/Gegenprüfungsqueries höher priorisieren.")
                weights["counter_doppler_queries"] = +12
            if not recommendations:
                recommendations.append("Suchstrategie stabil; Fokus auf UX und weitere echte Testfälle.")
        tuning_id = new_id("tune611")
        self.db.execute("INSERT INTO osint_tuning_reports_61_1(tuning_id,case_id,entity_id,recommendations_json,weight_changes_json,created_at) VALUES(?,?,?,?,?,?)", [tuning_id, case_id, entity_id, dumps(recommendations), dumps(weights), now_ts()])
        return {"tuning_id": tuning_id, "case_id": case_id, "entity_id": entity_id, "recommendations": recommendations, "weight_changes": weights}

    def latest(self, case_id: str, entity_id: str = "", limit: int = 10) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM osint_tuning_reports_61_1 WHERE case_id=? AND (?='' OR entity_id=?) ORDER BY created_at DESC LIMIT ?", [case_id, entity_id, entity_id, int(limit)])
        for r in rows:
            r["recommendations"] = loads(r.pop("recommendations_json", "[]"), [])
            r["weight_changes"] = loads(r.pop("weight_changes_json", "{}"), {})
        return rows
