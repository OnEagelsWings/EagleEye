from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, new_id, now_ts


class ProfessionalResearchOperations62Service:
    """Build 62.0: integrated maturity cycle after 61.2."""

    def __init__(self, db: Database, audit: AuditService, reports_root: str | Path, *, browser_helper=None, claim_report=None, benchmark_suite=None, adaptive_tuning=None, dashboard=None):
        self.db = db
        self.audit = audit
        self.reports_root = Path(reports_root)
        self.reports_root.mkdir(parents=True, exist_ok=True)
        self.browser_helper = browser_helper
        self.claim_report = claim_report
        self.benchmark_suite = benchmark_suite
        self.adaptive_tuning = adaptive_tuning
        self.dashboard = dashboard
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS professional_research_cycles_62 (
          cycle_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          imported_count INTEGER DEFAULT 0,
          report_id TEXT DEFAULT '',
          benchmark_id TEXT DEFAULT '',
          tuning_id TEXT DEFAULT '',
          package_path TEXT DEFAULT '',
          manifest_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def run_cycle(self, case_id: str, entity_id: str, *, capture_text: str = "", capture_payload: str | Dict[str, Any] | None = None, category_key: str = "person_core", query: str = "", engine: str = "browser_capture", session_id: str = "") -> Dict[str, Any]:
        imported_count = 0
        if capture_payload:
            imp = self.browser_helper.import_payload(case_id, entity_id, capture_payload, category_key=category_key, query=query, engine=engine) if self.browser_helper else {}
            imported_count += 1 if imp else 0
        if capture_text:
            res = self.browser_helper.import_serp_clipboard(case_id, entity_id, capture_text, category_key=category_key, query=query, engine=engine) if self.browser_helper else {"count": 0}
            imported_count += int(res.get("count", 0))
        dash = self.dashboard.dashboard(case_id, entity_id) if self.dashboard else {}
        report = self.claim_report.build_report(case_id, entity_id, session_id=session_id, save_to_person_file=True) if self.claim_report else {}
        bench = self.benchmark_suite.run_suite(case_id, entity_id, session_id=session_id, scenario_key="person_org") if self.benchmark_suite else {}
        tune = self.adaptive_tuning.create_profile(case_id, entity_id) if self.adaptive_tuning else {}
        package = self._write_package(case_id, entity_id, report, bench, tune, dash)
        cycle_id = new_id("cycle62")
        manifest = {"build": "62.0", "imported_count": imported_count, "report_id": report.get("report_id", ""), "benchmark_id": bench.get("suite_run_id", ""), "tuning_id": tune.get("profile_id", ""), "package": package}
        self.db.execute('''INSERT INTO professional_research_cycles_62(cycle_id,case_id,entity_id,imported_count,report_id,benchmark_id,tuning_id,package_path,manifest_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)''', [cycle_id, case_id, entity_id, imported_count, report.get("report_id", ""), bench.get("suite_run_id", ""), tune.get("profile_id", ""), package.get("path", ""), dumps(manifest), now_ts()])
        self.audit.log("run", "professional_research_cycle_62", cycle_id, case_id, {"entity_id": entity_id, "imported_count": imported_count})
        return {"cycle_id": cycle_id, "imported_count": imported_count, "dashboard": dash, "report": report, "benchmark": bench, "tuning": tune, "package": package}

    def _write_package(self, case_id: str, entity_id: str, report: Dict[str, Any], bench: Dict[str, Any], tune: Dict[str, Any], dash: Dict[str, Any]) -> Dict[str, Any]:
        outdir = self.reports_root / case_id / entity_id / new_id("pro62pkg")
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "01_PERSON_REPORT.md").write_text(report.get("body", ""), encoding="utf-8")
        (outdir / "02_DASHBOARD.json").write_text(dumps(dash), encoding="utf-8")
        (outdir / "03_BENCHMARK.json").write_text(dumps(bench), encoding="utf-8")
        (outdir / "04_ADAPTIVE_TUNING.json").write_text(dumps(tune), encoding="utf-8")
        manifest = {"build": "62.0", "case_id": case_id, "entity_id": entity_id, "files": ["01_PERSON_REPORT.md", "02_DASHBOARD.json", "03_BENCHMARK.json", "04_ADAPTIVE_TUNING.json"]}
        (outdir / "MANIFEST.json").write_text(dumps(manifest), encoding="utf-8")
        return {"path": str(outdir), "manifest": manifest}
