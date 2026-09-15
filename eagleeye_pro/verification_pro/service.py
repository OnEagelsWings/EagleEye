from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security_kernel.policy import FORBIDDEN_CLAIM_TYPES

DIMENSIONS = [
    "source_reliability", "source_independence", "identity_fit", "time_fit", "place_fit",
    "name_doppler_risk", "document_quality", "freshness", "counter_evidence", "sensitivity", "reportability",
]


class VerificationProService:
    """Build 50 corroboration engine.

    It produces an evidence assessment, not a truth verdict. Strong labels require
    independent public evidence and explicit uncertainty/counter-evidence accounting.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS verification_pro_assessments_50 (
          assessment_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          target_id TEXT DEFAULT '',
          profile_type TEXT DEFAULT 'case',
          assessment_label TEXT NOT NULL,
          score INTEGER DEFAULT 0,
          dimensions_json TEXT NOT NULL,
          support_summary_json TEXT NOT NULL,
          counter_evidence_json TEXT NOT NULL,
          uncertainty_json TEXT NOT NULL,
          blocked_claims_json TEXT NOT NULL,
          required_actions_json TEXT NOT NULL,
          reportability TEXT DEFAULT 'internal_only',
          created_at TEXT NOT NULL,
          created_by TEXT DEFAULT 'local-analyst',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_vpro50_case ON verification_pro_assessments_50(case_id, created_at);
        ''')
        self.db.conn.commit()

    def assess_case(self, case_id: str, *, target_id: str = "", profile_type: str = "case", notes: str = "") -> Dict[str, Any]:
        claims = self.db.all("SELECT * FROM verified_claims WHERE case_id=? ORDER BY created_at", [case_id]) if self._table_exists("verified_claims") else []
        review = self.db.all("SELECT * FROM review_inbox_pro_46 WHERE case_id=? ORDER BY updated_at", [case_id]) if self._table_exists("review_inbox_pro_46") else []
        vault = self.db.all("SELECT * FROM evidence_vault_artifacts_50 WHERE case_id=? ORDER BY created_at", [case_id]) if self._table_exists("evidence_vault_artifacts_50") else []
        extracts = self.db.all("SELECT * FROM public_document_extracts_46 WHERE case_id=? ORDER BY retrieved_at", [case_id]) if self._table_exists("public_document_extracts_46") else []

        support_items = [r for r in review if r.get("stage") in {"evidence_item", "relevant_candidate", "needs_second_source"}]
        counter_items = [r for r in review if r.get("stage") == "counter_evidence"]
        vault_evidence = [v for v in vault if v.get("review_status") in {"evidence", "counter_evidence", "needs_second_source"}]

        sensitive = 0
        for v in vault:
            sens = loads(v.get("sensitivity_json"), {})
            if sens.get("markers"):
                sensitive += 1
        for r in review:
            sens = loads(r.get("sensitivity_json"), {})
            if sens.get("markers"):
                sensitive += 1

        unique_hosts = set()
        for item in review:
            url = item.get("source_url") or ""
            host = url.split("/")[2].lower() if "://" in url and len(url.split("/")) > 2 else url.lower()
            if host:
                unique_hosts.add(host)
        for v in vault:
            url = v.get("source_url") or ""
            host = url.split("/")[2].lower() if "://" in url and len(url.split("/")) > 2 else url.lower()
            if host:
                unique_hosts.add(host)

        dimensions = {
            "source_reliability": min(1.0, (len(support_items) + len(vault_evidence) + len(extracts)) / 6.0),
            "source_independence": min(1.0, len(unique_hosts) / 2.0),
            "identity_fit": 0.55 if claims or support_items else 0.25,
            "time_fit": 0.60 if extracts or support_items else 0.30,
            "place_fit": 0.50,
            "name_doppler_risk": 0.40 if not claims else 0.65,
            "document_quality": min(1.0, len(vault) / 3.0 + len(extracts) / 5.0),
            "freshness": 0.55,
            "counter_evidence": 0.25 if not counter_items else 0.70,
            "sensitivity": 0.20 if sensitive else 0.80,
            "reportability": 0.35,
        }
        independent = dimensions["source_independence"] >= 1.0
        has_counter_check = bool(counter_items) or any((loads(c.get("contra_evidence_json"), []) if c.get("contra_evidence_json") else []) for c in claims)
        support_count = len(support_items) + len(vault_evidence) + len(claims)
        score = int(round(sum(dimensions.values()) / len(dimensions) * 100))
        required_actions: List[str] = []
        uncertainties: List[str] = []
        blocked_claims: List[str] = []
        if support_count < 2:
            required_actions.append("second_independent_source_required")
            uncertainties.append("Weniger als zwei unterstützende Belege vorhanden.")
        if not independent:
            required_actions.append("source_independence_review")
            uncertainties.append("Quellenunabhängigkeit ist noch nicht ausreichend belegt.")
        if not has_counter_check:
            required_actions.append("counter_evidence_review")
            uncertainties.append("Gegenbelegprüfung fehlt oder ist nicht dokumentiert.")
        if sensitive:
            required_actions.append("privacy_redaction_review")
            uncertainties.append("Sensible Marker vorhanden; Export nur redigiert.")
        for c in claims:
            if c.get("claim_type") in FORBIDDEN_CLAIM_TYPES:
                blocked_claims.append(c.get("claim_type"))
        if blocked_claims:
            required_actions.append("blocked_claim_remove_or_rewrite")

        if score >= 70 and independent and support_count >= 2 and has_counter_check and not blocked_claims:
            label = "stark plausibler öffentlicher Hinweis – keine automatische Identitäts-/Schuldbehauptung"
            reportability = "reportable_with_uncertainty"
        elif score >= 50:
            label = "prüfpflichtiger öffentlicher Hinweis"
            reportability = "internal_only"
        else:
            label = "schwache oder unvollständige Beleglage"
            reportability = "not_reportable"

        assessment_id = new_id("vpro50")
        self.db.execute('''INSERT INTO verification_pro_assessments_50(assessment_id,case_id,target_id,profile_type,assessment_label,score,dimensions_json,support_summary_json,counter_evidence_json,uncertainty_json,blocked_claims_json,required_actions_json,reportability,created_at,created_by)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [assessment_id, case_id, target_id, profile_type, label, score, dumps(dimensions), dumps({"claims": len(claims), "review_support": len(support_items), "vault_evidence": len(vault_evidence), "extracts": len(extracts), "unique_hosts": sorted(unique_hosts)}), dumps({"counter_review_items": len(counter_items)}), dumps(uncertainties), dumps(blocked_claims), dumps(required_actions), reportability, now_ts(), "local-analyst"])
        self.audit.log("assess", "verification_pro_50", assessment_id, case_id, {"score": score, "label": label, "required_actions": required_actions})
        return self.get_assessment(assessment_id)

    def get_latest_assessment(self, case_id: str) -> Dict[str, Any] | None:
        row = self.db.one("SELECT assessment_id FROM verification_pro_assessments_50 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        return self.get_assessment(row["assessment_id"]) if row else None

    def get_assessment(self, assessment_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM verification_pro_assessments_50 WHERE assessment_id=?", [assessment_id])
        if not row:
            raise KeyError(assessment_id)
        for key in ["dimensions_json", "support_summary_json", "counter_evidence_json", "uncertainty_json", "blocked_claims_json", "required_actions_json"]:
            row[key.replace("_json", "")] = loads(row.pop(key, "{}"), [] if key.endswith("evidence_json") or key in {"uncertainty_json", "blocked_claims_json", "required_actions_json"} else {})
        return row

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]))
