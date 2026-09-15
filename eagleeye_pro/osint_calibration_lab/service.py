from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class OSINTCalibrationLabService:
    """Build 60.5: practical test and calibration lab for search quality."""

    def __init__(self, db: Database, audit: AuditService, *, osint_core=None, person_dashboard=None):
        self.db = db
        self.audit = audit
        self.osint_core = osint_core
        self.person_dashboard = person_dashboard
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS osint_calibration_runs_60_5 (
          run_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          session_id TEXT DEFAULT '',
          scenario_type TEXT NOT NULL,
          metrics_json TEXT NOT NULL,
          recommendations_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cal605_entity ON osint_calibration_runs_60_5(case_id, entity_id, created_at DESC);
        ''')
        self.db.conn.commit()

    def evaluate_entity(self, case_id: str, entity_id: str, *, session_id: str = "", scenario_type: str = "general_person_research") -> Dict[str, Any]:
        dashboard = self.person_dashboard.dashboard(case_id, entity_id) if self.person_dashboard else {}
        core = self.osint_core.dashboard(session_id) if (session_id and self.osint_core) else (dashboard.get("latest_core") or {})
        metrics = self._metrics(dashboard, core)
        recommendations = self._recommendations(metrics, dashboard)
        run_id = new_id("cal605")
        self.db.execute('''INSERT INTO osint_calibration_runs_60_5(run_id,case_id,entity_id,session_id,scenario_type,metrics_json,recommendations_json,created_at)
        VALUES(?,?,?,?,?,?,?,?)''', [run_id, case_id, entity_id, session_id, scenario_type, dumps(metrics), dumps(recommendations), now_ts()])
        self.audit.log("evaluate", "osint_calibration_run_60_5", run_id, case_id, {"entity_id": entity_id, "score": metrics.get("operational_score")})
        return {"run_id": run_id, "case_id": case_id, "entity_id": entity_id, "scenario_type": scenario_type, "metrics": metrics, "recommendations": recommendations}

    def latest(self, case_id: str, entity_id: str = "", limit: int = 10) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM osint_calibration_runs_60_5 WHERE case_id=? AND (?='' OR entity_id=?) ORDER BY created_at DESC LIMIT ?", [case_id, entity_id, entity_id, int(limit)])
        for r in rows:
            r["metrics"] = loads(r.pop("metrics_json", "{}"), {})
            r["recommendations"] = loads(r.pop("recommendations_json", "[]"), [])
        return rows

    def _metrics(self, dash: Dict[str, Any], core: Dict[str, Any]) -> Dict[str, Any]:
        dm = dash.get("metrics", {})
        amp = dash.get("status_ampel", {})
        core_ready = (core.get("professional_readiness") or {}).get("score", 0)
        findings = dm.get("finding_count", 0)
        claims = dm.get("claim_count", 0)
        doppler_high = dm.get("doppler_high", 0)
        green = sum(1 for v in amp.values() if v == "grün")
        yellow = sum(1 for v in amp.values() if v == "gelb")
        operational = round(min(100, 0.25 * core_ready + min(25, findings * 3) + min(20, claims * 5) + green * 6 + yellow * 2 - doppler_high * 6), 1)
        return {"operational_score": max(0, operational), "core_readiness": core_ready, "finding_count": findings, "claim_count": claims, "doppler_high": doppler_high, "green_status_count": green, "yellow_status_count": yellow, "manual_effort_score": max(0, 100 - findings * 2), "reportable_findings_rate_proxy": round(min(1.0, claims / max(1, findings)), 2)}

    def _recommendations(self, metrics: Dict[str, Any], dash: Dict[str, Any]) -> List[str]:
        rec: List[str] = []
        if metrics["finding_count"] < 5: rec.append("mehr Treffer importieren und Fundliste verdichten")
        if metrics["claim_count"] < 3: rec.append("aus Top-Funden Claims bilden")
        if metrics["doppler_high"] > 0: rec.append("Namensdoppler-Cluster prüfen und Gegenqueries ausführen")
        if metrics["core_readiness"] < 70: rec.append("OSINT-Core-Session mit SERP-Import aktualisieren")
        missing = [k for k, v in (dash.get("category_progress") or {}).items() if isinstance(v, dict) and v.get("count", 0) == 0]
        if missing: rec.append("fehlende Kategorien prüfen: " + ", ".join(missing[:5]))
        return rec or ["Workflow wirkt stabil; nächste Praxistest-Kalibrierung durchführen"]
