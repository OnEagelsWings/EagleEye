from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

SCENARIOS = [
    {"scenario_key": "unique_person", "title": "Eindeutige Person", "target_precision": 0.75, "doppler_expected": "low"},
    {"scenario_key": "common_name", "title": "Häufiger Name / Namensdoppler", "target_precision": 0.55, "doppler_expected": "high"},
    {"scenario_key": "person_org", "title": "Person mit Organisationsbezug", "target_precision": 0.70, "doppler_expected": "medium"},
    {"scenario_key": "court_pdf_press", "title": "Gericht/PDF/Presse", "target_precision": 0.65, "doppler_expected": "medium"},
    {"scenario_key": "register_finance", "title": "Register-/Finanzkontext", "target_precision": 0.65, "doppler_expected": "medium"},
]


class OSINTBenchmarkSuite62Service:
    """Build 62.0: practical benchmark presets and operational scoring suite."""

    def __init__(self, db: Database, audit: AuditService, *, calibration=None, dashboard=None, osint_core=None):
        self.db = db
        self.audit = audit
        self.calibration = calibration
        self.dashboard = dashboard
        self.osint_core = osint_core
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS osint_benchmark_suite_runs_62 (
          suite_run_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          scenario_key TEXT NOT NULL,
          score REAL DEFAULT 0,
          metrics_json TEXT NOT NULL,
          findings_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def scenarios(self) -> List[Dict[str, Any]]:
        return list(SCENARIOS)

    def run_suite(self, case_id: str, entity_id: str, *, session_id: str = "", scenario_key: str = "person_org") -> Dict[str, Any]:
        scenario = next((s for s in SCENARIOS if s["scenario_key"] == scenario_key), SCENARIOS[2])
        cal = self.calibration.evaluate_entity(case_id, entity_id, session_id=session_id, scenario_type=scenario_key) if self.calibration else {"metrics": {}}
        dash = self.dashboard.dashboard(case_id, entity_id) if self.dashboard else {}
        core = self.osint_core.dashboard(session_id) if (session_id and self.osint_core) else (dash.get("latest_core") or {})
        metrics = self._metrics(cal.get("metrics", {}), dash, core, scenario)
        findings = self._findings(metrics, scenario)
        suite_id = new_id("bench62")
        self.db.execute('''INSERT INTO osint_benchmark_suite_runs_62(suite_run_id,case_id,entity_id,scenario_key,score,metrics_json,findings_json,created_at)
        VALUES(?,?,?,?,?,?,?,?)''', [suite_id, case_id, entity_id, scenario_key, metrics["suite_score"], dumps(metrics), dumps(findings), now_ts()])
        self.audit.log("evaluate", "osint_benchmark_suite_62", suite_id, case_id, {"entity_id": entity_id, "score": metrics["suite_score"], "scenario": scenario_key})
        return {"suite_run_id": suite_id, "scenario": scenario, "metrics": metrics, "findings": findings}

    def latest(self, case_id: str, entity_id: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM osint_benchmark_suite_runs_62 WHERE case_id=? AND (?='' OR entity_id=?) ORDER BY created_at DESC LIMIT ?", [case_id, entity_id, entity_id, int(limit)])
        for r in rows:
            r["metrics"] = loads(r.pop("metrics_json", "{}"), {})
            r["findings"] = loads(r.pop("findings_json", "[]"), [])
        return rows

    def _metrics(self, cal: Dict[str, Any], dash: Dict[str, Any], core: Dict[str, Any], scenario: Dict[str, Any]) -> Dict[str, Any]:
        dm = dash.get("metrics", {})
        ready = (core.get("professional_readiness") or {}).get("score", cal.get("core_readiness", 0))
        finding_count = int(dm.get("finding_count", cal.get("finding_count", 0)) or 0)
        claim_count = int(dm.get("claim_count", cal.get("claim_count", 0)) or 0)
        doppler_high = int(dm.get("doppler_high", cal.get("doppler_high", 0)) or 0)
        report_rate = float(cal.get("reportable_findings_rate_proxy", 0) or 0)
        precision_proxy = min(1.0, (0.35 * report_rate) + (0.25 if claim_count >= 2 else 0.1 if claim_count else 0) + (0.25 if ready >= 70 else 0.1) + (0.15 if doppler_high == 0 else 0.02))
        manual_effort = max(0, 100 - max(0, finding_count - claim_count) * 4)
        suite_score = round(min(100, precision_proxy * 45 + min(20, claim_count * 5) + min(20, finding_count * 2.5) + manual_effort * 0.15 - doppler_high * 6), 1)
        return {"suite_score": suite_score, "precision_at_10_proxy": round(precision_proxy, 2), "target_precision": scenario["target_precision"], "finding_count": finding_count, "claim_count": claim_count, "doppler_high": doppler_high, "manual_effort_score": round(manual_effort, 1), "core_readiness": ready}

    def _findings(self, metrics: Dict[str, Any], scenario: Dict[str, Any]) -> List[str]:
        out: List[str] = []
        if metrics["precision_at_10_proxy"] < scenario["target_precision"]:
            out.append("Top-Treffer-Präzision unter Zielwert: Query-Pyramide schärfen und zu breite Queries senken.")
        if metrics["doppler_high"] > 0:
            out.append("Namensdoppler-Risiko sichtbar: Gegenqueries und Ausschlussanker priorisieren.")
        if metrics["claim_count"] < 2:
            out.append("Zu wenige Claims: reportfähige Funde in Claims überführen.")
        if metrics["finding_count"] < 5:
            out.append("Zu wenige Funde: SERP-/Browser-Capture für Top-Queries nutzen.")
        if not out:
            out.append("Benchmark stabil: Suchstrategie weiter mit echten Fällen kalibrieren.")
        return out
