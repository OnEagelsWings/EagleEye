from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class OSINTEvaluationLab60Service:
    """Build 60.0 evaluation lab for measurable OSINT search quality."""

    def __init__(self, db: Database, audit: AuditService, *, osint_core=None, search_spearhead=None):
        self.db = db
        self.audit = audit
        self.osint_core = osint_core
        self.search_spearhead = search_spearhead
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS osint_eval_runs_60 (
          eval_id TEXT PRIMARY KEY,
          case_id TEXT DEFAULT '',
          entity_id TEXT DEFAULT '',
          session_id TEXT DEFAULT '',
          mission_id TEXT DEFAULT '',
          precision_at_10 REAL DEFAULT 0,
          useful_query_rate REAL DEFAULT 0,
          duplicate_rate REAL DEFAULT 0,
          doppler_risk_rate REAL DEFAULT 0,
          claim_formation_rate REAL DEFAULT 0,
          reportable_findings_rate REAL DEFAULT 0,
          manual_effort_score REAL DEFAULT 0,
          overall_score REAL DEFAULT 0,
          gaps_json TEXT NOT NULL,
          metrics_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def evaluate_session(self, session_id: str) -> Dict[str, Any]:
        if not self.osint_core:
            raise RuntimeError("osint_core service not attached")
        dash = self.osint_core.dashboard(session_id)
        session = dash.get("session", {})
        claims = dash.get("claims", [])
        results = dash.get("spearhead", {}).get("top_results", []) or []
        graph = dash.get("graph", {}) or {}
        top10 = results[:10]
        relevant = [r for r in top10 if int(r.get("total_score") or 0) >= 65 or r.get("ranking_label") in {"top_candidate", "strong_candidate"}]
        doppler = [r for r in top10 if int(r.get("doppler_risk") or 0) >= 60 or "name_doppler_risk" in (r.get("flags") or [])]
        domains = [r.get("domain", "") for r in results if r.get("domain")]
        duplicate_rate = 0.0
        if domains:
            duplicate_rate = round(1 - (len(set(domains)) / max(len(domains), 1)), 3)
        precision_at_10 = round(len(relevant) / max(len(top10), 1), 3) if top10 else 0.0
        useful_query_rate = min(1.0, round(len(results) / max(dash.get("spearhead", {}).get("query_count", 1), 1), 3))
        claim_formation_rate = min(1.0, round(len(claims) / max(len(results), 1), 3)) if results else 0.0
        reportable = [c for c in claims if c.get("reportability") in {"reportable_with_uncertainty", "reportable_with_redaction", "reportable_as_verified_claim"}]
        reportable_findings_rate = round(len(reportable) / max(len(claims), 1), 3) if claims else 0.0
        manual_effort_score = 1.0 if dash.get("feeds") else 0.5 if results else 0.0
        doppler_risk_rate = round(len(doppler) / max(len(top10), 1), 3) if top10 else 0.0
        metrics = {
            "precision_at_10": precision_at_10,
            "useful_query_rate": useful_query_rate,
            "duplicate_rate": duplicate_rate,
            "doppler_risk_rate": doppler_risk_rate,
            "claim_formation_rate": claim_formation_rate,
            "reportable_findings_rate": reportable_findings_rate,
            "manual_effort_score": manual_effort_score,
            "graph_density": graph.get("edge_count", 0),
            "claim_count": len(claims),
            "result_count": len(results),
        }
        gaps: List[str] = []
        if precision_at_10 < 0.5: gaps.append("precision_at_10_below_professional_threshold")
        if duplicate_rate > 0.35: gaps.append("duplicate_rate_too_high")
        if claim_formation_rate < 0.15: gaps.append("too_few_claims_from_results")
        if doppler_risk_rate > 0.4: gaps.append("doppler_risk_requires_more_context_anchors")
        if not reportable: gaps.append("no_reportable_claims_yet")
        overall = round((precision_at_10 * 30 + useful_query_rate * 15 + (1 - duplicate_rate) * 15 + (1 - doppler_risk_rate) * 15 + claim_formation_rate * 15 + reportable_findings_rate * 10), 1)
        eval_id = new_id("eval60")
        self.db.execute('''INSERT INTO osint_eval_runs_60(eval_id,case_id,entity_id,session_id,mission_id,precision_at_10,useful_query_rate,duplicate_rate,doppler_risk_rate,claim_formation_rate,reportable_findings_rate,manual_effort_score,overall_score,gaps_json,metrics_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [eval_id, session.get("case_id", ""), session.get("entity_id", ""), session_id, session.get("mission_id", ""), precision_at_10, useful_query_rate, duplicate_rate, doppler_risk_rate, claim_formation_rate, reportable_findings_rate, manual_effort_score, overall, dumps(gaps), dumps(metrics), now_ts()])
        self.audit.log("evaluate", "osint_eval_60", eval_id, session.get("case_id") or None, {"overall_score": overall, "gaps": gaps})
        return {"eval_id": eval_id, "session_id": session_id, "overall_score": overall, "metrics": metrics, "gaps": gaps, "professional_label": self._label(overall)}

    def latest(self, case_id: str = "", entity_id: str = "", limit: int = 10) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM osint_eval_runs_60 WHERE 1=1"
        params: List[Any] = []
        if case_id:
            sql += " AND case_id=?"; params.append(case_id)
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        for row in rows:
            row["gaps"] = loads(row.pop("gaps_json", "[]"), [])
            row["metrics"] = loads(row.pop("metrics_json", "{}"), {})
            row["professional_label"] = self._label(float(row.get("overall_score") or 0))
        return rows

    def _label(self, score: float) -> str:
        if score >= 85: return "professional_ready"
        if score >= 70: return "operational_with_review"
        if score >= 50: return "research_foundation"
        return "needs_more_signal"
