from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class AnalystQualityLayerService:
    """Build 53 quality layer: hypotheses, counter-hypotheses, gaps and readiness."""

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS analyst_hypotheses_54 (
          hypothesis_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          title TEXT NOT NULL,
          hypothesis_text TEXT NOT NULL,
          status TEXT DEFAULT 'open',
          supporting_nodes_json TEXT NOT NULL,
          counter_nodes_json TEXT NOT NULL,
          open_questions_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS analyst_quality_reviews_54 (
          review_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          score INTEGER DEFAULT 0,
          readiness_label TEXT NOT NULL,
          gaps_json TEXT NOT NULL,
          required_actions_json TEXT NOT NULL,
          metrics_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_hyp54_case ON analyst_hypotheses_54(case_id, updated_at);
        CREATE INDEX IF NOT EXISTS idx_qrev54_case ON analyst_quality_reviews_54(case_id, created_at);
        ''')
        self.db.conn.commit()

    def create_hypothesis(self, case_id: str, title: str, hypothesis_text: str, *, supporting_nodes: List[str] | None = None, counter_nodes: List[str] | None = None, open_questions: List[str] | None = None) -> Dict[str, Any]:
        if not title.strip() or not hypothesis_text.strip():
            raise ValueError("Hypothesis title and text are required.")
        hid = new_id("hyp54")
        self.db.execute('''INSERT INTO analyst_hypotheses_54(hypothesis_id,case_id,title,hypothesis_text,status,supporting_nodes_json,counter_nodes_json,open_questions_json,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)''', [hid, case_id, title.strip(), hypothesis_text.strip(), "open", dumps(supporting_nodes or []), dumps(counter_nodes or []), dumps(open_questions or []), now_ts(), now_ts()])
        self.audit.log("create", "analyst_hypothesis_54", hid, case_id, {"title": title})
        return self.get_hypothesis(hid)

    def update_hypothesis(self, hypothesis_id: str, **updates: Any) -> Dict[str, Any]:
        hyp = self.get_hypothesis(hypothesis_id)
        fields = {}
        for k in ["title", "hypothesis_text", "status"]:
            if k in updates:
                fields[k] = str(updates[k])
        for k in ["supporting_nodes", "counter_nodes", "open_questions"]:
            if k in updates:
                fields[f"{k}_json"] = dumps(updates[k] or [])
        if fields:
            sql = ",".join([f"{k}=?" for k in fields]) + ",updated_at=?"
            self.db.execute(f"UPDATE analyst_hypotheses_54 SET {sql} WHERE hypothesis_id=?", [*fields.values(), now_ts(), hypothesis_id])
        self.audit.log("update", "analyst_hypothesis_54", hypothesis_id, hyp["case_id"], {"fields": sorted(fields)})
        return self.get_hypothesis(hypothesis_id)

    def evaluate_case(self, case_id: str) -> Dict[str, Any]:
        metrics = self._metrics(case_id)
        gaps: List[str] = []
        actions: List[str] = []
        if metrics["entities"] == 0:
            gaps.append("Keine Zielperson/-organisation im Case Cockpit angelegt.")
            actions.append("create_investigation_entity")
        if metrics["chain_queries"] == 0:
            gaps.append("Keine Suchanfragen aus Grundinformationen abgeleitet.")
            actions.append("generate_cockpit_search_parameters")
        if metrics["findings"] == 0:
            gaps.append("Keine Funde in der Search/Fund-Chain dokumentiert.")
            actions.append("add_chain_finding")
        if metrics["included_facts"] == 0:
            gaps.append("Keine inkludierten Informationen aus Funden abgeleitet.")
            actions.append("include_chain_information")
        if metrics["evidence"] == 0:
            gaps.append("Keine Evidence-Vault-Belege vorhanden.")
            actions.append("ingest_evidence_text")
        if metrics["counter_evidence"] == 0:
            gaps.append("Gegenbelegprüfung ist noch nicht dokumentiert.")
            actions.append("document_counter_evidence")
        if metrics["hypotheses"] == 0:
            gaps.append("Keine Hypothesen-/Gegenhypothesenmatrix angelegt.")
            actions.append("create_hypothesis")
        if metrics["profiles"] == 0:
            gaps.append("Kein aktuelles Spearhead-Profil erstellt.")
            actions.append("build_spearhead_profile")
        base = 100
        base -= min(70, len(gaps) * 10)
        if metrics["chain_queries"] >= 5 and metrics["included_facts"] >= 1:
            base += 5
        if metrics["evidence"] >= 1 and metrics["profiles"] >= 1:
            base += 5
        score = max(0, min(100, base))
        if score >= 85:
            label = "operational_ready_with_review"
        elif score >= 70:
            label = "usable_but_gaps_remain"
        elif score >= 50:
            label = "foundation_ready_not_operational"
        else:
            label = "incomplete"
        rid = new_id("qrev54")
        self.db.execute('''INSERT INTO analyst_quality_reviews_54(review_id,case_id,score,readiness_label,gaps_json,required_actions_json,metrics_json,created_at)
        VALUES(?,?,?,?,?,?,?,?)''', [rid, case_id, score, label, dumps(gaps), dumps(sorted(set(actions))), dumps(metrics), now_ts()])
        self.audit.log("evaluate", "analyst_quality_review_54", rid, case_id, {"score": score, "label": label})
        return self.get_review(rid)

    def get_hypothesis(self, hypothesis_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM analyst_hypotheses_54 WHERE hypothesis_id=?", [hypothesis_id])
        if not row:
            raise KeyError(hypothesis_id)
        for key in ["supporting_nodes_json", "counter_nodes_json", "open_questions_json"]:
            row[key.replace("_json", "")] = loads(row.pop(key, "[]"), [])
        return row

    def get_review(self, review_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM analyst_quality_reviews_54 WHERE review_id=?", [review_id])
        if not row:
            raise KeyError(review_id)
        for key in ["gaps_json", "required_actions_json", "metrics_json"]:
            row[key.replace("_json", "")] = loads(row.pop(key, "[]"), [] if key != "metrics_json" else {})
        return row

    def _metrics(self, case_id: str) -> Dict[str, int]:
        def count(table: str, where: str = "case_id=?", params: List[Any] | None = None) -> int:
            if not self._table_exists(table):
                return 0
            row = self.db.one(f"SELECT COUNT(*) AS n FROM {table} WHERE {where}", params or [case_id])
            return int(row["n"] if row else 0)
        return {
            "entities": count("investigation_entities_54"),
            "chain_queries": count("search_chain_nodes_54", "case_id=? AND node_type IN ('search_query','derived_query')", [case_id]),
            "findings": count("search_chain_nodes_54", "case_id=? AND node_type='source_hit'", [case_id]),
            "included_facts": count("search_chain_nodes_54", "case_id=? AND node_type='included_fact'", [case_id]),
            "evidence": count("evidence_vault_artifacts_50", "case_id=? AND review_status IN ('evidence','needs_second_source','counter_evidence')", [case_id]),
            "counter_evidence": count("search_chain_nodes_54", "case_id=? AND confidence_label='counter_evidence'", [case_id]) + count("evidence_vault_artifacts_50", "case_id=? AND review_status='counter_evidence'", [case_id]),
            "hypotheses": count("analyst_hypotheses_54"),
            "profiles": count("spearhead_profiles_50"),
            "handover_reports": count("handover_reports_50"),
        }

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]))
