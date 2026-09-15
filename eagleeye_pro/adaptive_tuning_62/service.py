from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class AdaptiveSearchTuning62Service:
    """Build 62.0: adaptive tuning from benchmark/calibration runs."""

    def __init__(self, db: Database, audit: AuditService, *, benchmark_suite=None, calibration=None, tuning_61=None):
        self.db = db
        self.audit = audit
        self.benchmark_suite = benchmark_suite
        self.calibration = calibration
        self.tuning_61 = tuning_61
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS adaptive_tuning_profiles_62 (
          profile_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT DEFAULT '',
          query_weights_json TEXT NOT NULL,
          source_weights_json TEXT NOT NULL,
          recommendations_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def create_profile(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        bench = self.benchmark_suite.latest(case_id, entity_id, limit=10) if self.benchmark_suite else []
        cal = self.calibration.latest(case_id, entity_id, limit=10) if self.calibration else []
        tuning = self.tuning_61.create_tuning_report(case_id, entity_id) if self.tuning_61 else {"recommendations": [], "weight_changes": {}}
        query_weights = {"high_precision": 100, "context_expansion": 82, "source_dork": 88, "counter_doppler": 78, "recall": 65}
        source_weights = {"registry": 94, "court_or_justice": 92, "public_pdf": 82, "newspaper_press": 76, "public_web": 58, "image_media": 52, "social_public_profile": 48}
        recommendations: List[str] = list(tuning.get("recommendations", []))
        if bench:
            avg_precision = sum(float(b.get("metrics", {}).get("precision_at_10_proxy", 0)) for b in bench) / max(1, len(bench))
            avg_doppler = sum(int(b.get("metrics", {}).get("doppler_high", 0)) for b in bench) / max(1, len(bench))
            avg_claims = sum(int(b.get("metrics", {}).get("claim_count", 0)) for b in bench) / max(1, len(bench))
            if avg_precision < 0.65:
                query_weights["high_precision"] += 12; query_weights["recall"] -= 10
                recommendations.append("Präzisionsqueries vor Recall-Queries öffnen; breite Namensqueries nachrangig behandeln.")
            if avg_doppler > 0:
                query_weights["counter_doppler"] += 18
                recommendations.append("Gegenprüfungs- und Ausschlussqueries wegen Doppler-Risiko höher priorisieren.")
            if avg_claims < 2:
                source_weights["registry"] += 5; source_weights["public_pdf"] += 5; source_weights["newspaper_press"] += 4
                recommendations.append("Quellen mit Claim-Potenzial höher gewichten: Register, PDFs, Presse/Amtsblatt.")
        elif cal:
            recommendations.append("Benchmark-Suite ergänzen; bisher nur Kalibrierungsläufe vorhanden.")
        else:
            recommendations.append("Zuerst Benchmark-/Kalibrierungslauf ausführen, bevor Feintuning belastbar ist.")
        profile_id = new_id("tune62")
        self.db.execute('''INSERT INTO adaptive_tuning_profiles_62(profile_id,case_id,entity_id,query_weights_json,source_weights_json,recommendations_json,created_at)
        VALUES(?,?,?,?,?,?,?)''', [profile_id, case_id, entity_id, dumps(query_weights), dumps(source_weights), dumps(recommendations), now_ts()])
        self.audit.log("create", "adaptive_tuning_profile_62", profile_id, case_id, {"entity_id": entity_id})
        return {"profile_id": profile_id, "case_id": case_id, "entity_id": entity_id, "query_weights": query_weights, "source_weights": source_weights, "recommendations": recommendations}

    def latest(self, case_id: str, entity_id: str = "", limit: int = 10) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM adaptive_tuning_profiles_62 WHERE case_id=? AND (?='' OR entity_id=?) ORDER BY created_at DESC LIMIT ?", [case_id, entity_id, entity_id, int(limit)])
        for r in rows:
            r["query_weights"] = loads(r.pop("query_weights_json", "{}"), {})
            r["source_weights"] = loads(r.pop("source_weights_json", "{}"), {})
            r["recommendations"] = loads(r.pop("recommendations_json", "[]"), [])
        return rows
