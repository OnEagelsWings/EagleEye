from __future__ import annotations

from typing import Any, Dict

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class ResearchEngineIntegratedStableService:
    """Build 56.0 integration layer: Fundimport → Entity Resolution → Query Optimizer → Claims → Benchmark."""

    def __init__(self, db: Database, audit: AuditService, search_quality=None, result_capture=None, entity_resolution=None, query_optimizer=None, claim_builder=None):
        self.db = db
        self.audit = audit
        self.search_quality = search_quality
        self.result_capture = result_capture
        self.entity_resolution = entity_resolution
        self.query_optimizer = query_optimizer
        self.claim_builder = claim_builder
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS research_engine_sessions_56_0 (
          session_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          category_key TEXT NOT NULL,
          status TEXT NOT NULL,
          summary_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def run_integrated_quality_cycle(self, case_id: str, entity: Dict[str, Any], category_key: str, *, sample_import: Dict[str, Any] | None = None) -> Dict[str, Any]:
        entity_id = entity.get("entity_id")
        if not entity_id:
            raise ValueError("entity_id required")
        fp = self.search_quality.build_entity_fingerprint(case_id, entity) if self.search_quality else {}
        pyramid = self.search_quality.build_query_pyramid(case_id, entity, category_key, max_per_level=4) if self.search_quality else {"queries": []}
        imported = None
        if sample_import and self.result_capture:
            qid = sample_import.get("quality_query_id") or (pyramid.get("queries", [{}])[0].get("quality_query_id") if pyramid.get("queries") else "")
            imported = self.result_capture.import_public_result(case_id, entity_id, quality_query_id=qid, category_key=category_key, **{k:v for k,v in sample_import.items() if k != "quality_query_id"})
        scored = self.search_quality.score_chain_findings(case_id, entity_id=entity_id) if self.search_quality else {"created_or_updated": 0}
        resolutions = self.entity_resolution.assess_ranked_results(case_id, entity_id, limit=20) if self.entity_resolution else {"assessment_count": 0}
        qreviews = self.query_optimizer.optimize_entity_queries(case_id, entity_id) if self.query_optimizer else {"review_count": 0}
        claims = self.claim_builder.build_claims_from_person_findings(case_id, entity_id) if self.claim_builder else {"claim_count": 0}
        bench = self.search_quality.compute_benchmark(case_id, entity_id=entity_id) if self.search_quality else {"metrics": {}}
        summary = {
            "fingerprint_hash": fp.get("fingerprint_hash", ""), "query_count": pyramid.get("query_count", 0),
            "import_id": imported.get("import_id") if imported else "", "ranked_results": scored.get("created_or_updated", 0),
            "entity_resolution_assessments": resolutions.get("assessment_count", 0), "query_reviews": qreviews.get("review_count", 0),
            "claims": claims.get("claim_count", 0), "benchmark": bench.get("metrics", {}),
        }
        sid = new_id("rs560")
        now = now_ts()
        self.db.execute("INSERT INTO research_engine_sessions_56_0(session_id,case_id,entity_id,category_key,status,summary_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", [sid, case_id, entity_id, category_key, "completed", dumps(summary), now, now])
        self.audit.log("run", "research_engine_integrated_cycle_56_0", sid, case_id, summary)
        return {"session_id": sid, "case_id": case_id, "entity_id": entity_id, "category_key": category_key, "summary": summary, "fingerprint": fp, "pyramid": pyramid, "imported": imported, "resolutions": resolutions, "query_reviews": qreviews, "claims": claims, "benchmark": bench}

    def dashboard(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        params = [case_id]
        sql = "SELECT * FROM research_engine_sessions_56_0 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT 20"
        rows = self.db.all(sql, params)
        for r in rows:
            r["summary"] = loads(r.pop("summary_json", "{}"), {})
        return {"build": "56.0", "case_id": case_id, "entity_id": entity_id, "session_count": len(rows), "sessions": rows}
