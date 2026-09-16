from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
import hashlib, json, secrets

BUILD = "404.0"
POLICY_ID = "phase18.ai-review-release-gate.v404"
SEVERITIES = {"P0", "P1", "P2", "P3"}
STATUSES = {"open", "fix_in_progress", "fixed_pending_verification", "verified_closed"}
BLOCKING = {"P0", "P1"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _sid(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(12)}"

def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",",":"), default=str)

def _sha(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode()).hexdigest()


@dataclass(frozen=True)
class ReviewGateRule:
    key: str
    requirement: str


RULES = (
    ReviewGateRule("blocking_severity", "Open P0/P1 findings block cycle acceptance"),
    ReviewGateRule("verified_closure", "A finding closes only after fix evidence and verification evidence"),
    ReviewGateRule("regression_required", "Every P0/P1 finding requires a named regression test"),
    ReviewGateRule("human_governed", "AI review never grants execution authority or production readiness"),
    ReviewGateRule("source_traceability", "Every finding records reviewer/source and immutable content hash"),
    ReviewGateRule("feedback_cycle", "Builds 401-405 publish together for renewed GitHub/external review"),
)


class AIReviewGate404:
    """Persistent review-finding ledger and deterministic release gate."""

    def __init__(self, db: Any, audit: Any, *, build403: Any, actor: str = "local-analyst"):
        self.db=db; self.audit=audit; self.build403=build403; self.actor=actor; self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS ai_review_finding_404(
          finding_id TEXT PRIMARY KEY, source TEXT NOT NULL, external_ref TEXT NOT NULL,
          title TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL,
          description TEXT NOT NULL, component TEXT NOT NULL, regression_test TEXT NOT NULL DEFAULT '',
          fix_evidence TEXT NOT NULL DEFAULT '', verification_evidence TEXT NOT NULL DEFAULT '',
          opened_at TEXT NOT NULL, updated_at TEXT NOT NULL, content_hash TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ai_review_finding_404_gate ON ai_review_finding_404(severity,status);
        """); self.db.conn.commit()

    def rules(self) -> dict[str, Any]:
        return {"build":BUILD,"policy":POLICY_ID,"rules":[asdict(r) for r in RULES],"blocking_severities":sorted(BLOCKING),"production_release_ready":False}

    def record_finding(self, *, source:str, external_ref:str, title:str, severity:str, description:str, component:str, actor:str|None=None) -> dict[str,Any]:
        severity=severity.upper().strip()
        if severity not in SEVERITIES: raise ValueError("severity must be P0/P1/P2/P3")
        if not source.strip() or not title.strip() or not description.strip(): raise ValueError("source, title and description are required")
        fid=_sid("review404"); now=_now(); body={"source":source.strip(),"external_ref":external_ref.strip(),"title":title.strip(),"severity":severity,"status":"open","description":description.strip(),"component":component.strip(),"regression_test":"","fix_evidence":"","verification_evidence":"","opened_at":now,"updated_at":now}
        content_hash=_sha(body)
        self.db.execute("INSERT INTO ai_review_finding_404 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(fid,body['source'],body['external_ref'],body['title'],body['severity'],body['status'],body['description'],body['component'],body['regression_test'],body['fix_evidence'],body['verification_evidence'],body['opened_at'],body['updated_at'],content_hash))
        self.audit.log('ai_review_finding_recorded','ai_review_finding_404',fid,'',{'severity':severity,'source':source,'component':component,'actor':actor or self.actor})
        return self.finding(fid)

    def finding(self, finding_id:str) -> dict[str,Any]:
        row=self.db.one("SELECT * FROM ai_review_finding_404 WHERE finding_id=?",(finding_id,))
        if not row: raise KeyError("review finding not found")
        return dict(row)

    def transition(self, *, finding_id:str, status:str, regression_test:str="", fix_evidence:str="", verification_evidence:str="", actor:str|None=None) -> dict[str,Any]:
        status=status.strip()
        if status not in STATUSES: raise ValueError("unsupported review finding status")
        old=self.finding(finding_id); sev=old['severity']
        if status in {"fixed_pending_verification","verified_closed"} and not fix_evidence.strip(): raise ValueError("fix evidence required")
        if status=="verified_closed":
            if not verification_evidence.strip(): raise ValueError("verification evidence required")
            if sev in BLOCKING and not regression_test.strip(): raise ValueError("P0/P1 closure requires regression test")
        now=_now(); merged={**old,"status":status,"regression_test":regression_test.strip() or old['regression_test'],"fix_evidence":fix_evidence.strip() or old['fix_evidence'],"verification_evidence":verification_evidence.strip() or old['verification_evidence'],"updated_at":now}
        hashed={k:merged[k] for k in ('source','external_ref','title','severity','status','description','component','regression_test','fix_evidence','verification_evidence','opened_at','updated_at')}
        self.db.execute("UPDATE ai_review_finding_404 SET status=?,regression_test=?,fix_evidence=?,verification_evidence=?,updated_at=?,content_hash=? WHERE finding_id=?",(merged['status'],merged['regression_test'],merged['fix_evidence'],merged['verification_evidence'],now,_sha(hashed),finding_id))
        self.audit.log('ai_review_finding_transitioned','ai_review_finding_404',finding_id,'',{'from':old['status'],'to':status,'severity':sev,'actor':actor or self.actor})
        return self.finding(finding_id)

    def gate_status(self) -> dict[str,Any]:
        rows=[dict(r) for r in self.db.all("SELECT * FROM ai_review_finding_404 ORDER BY opened_at,finding_id")]
        open_blocking=[r for r in rows if r['severity'] in BLOCKING and r['status']!='verified_closed']
        closed_blocking=[r for r in rows if r['severity'] in BLOCKING and r['status']=='verified_closed']
        closure_integrity=all(bool(r['fix_evidence'] and r['verification_evidence'] and r['regression_test']) for r in closed_blocking)
        neg=self.build403.negative_path_status()
        checks={"build403_negative_contracts_preserved": bool(neg.get('contract_audit_pass')),"build403_negative_runtime_preserved": bool(neg.get('runtime_probe_pass')),"build403_scenario_catalog_preserved": int(neg.get('scenario_count',0)) >= 15,"no_open_p0_p1": len(open_blocking)==0,"closed_p0_p1_have_fix_verify_regression": closure_integrity,"production_not_released": True}
        return {"build":BUILD,"finding_count":len(rows),"open_blocking_count":len(open_blocking),"closed_blocking_count":len(closed_blocking),"open_blocking":[{"finding_id":r['finding_id'],"severity":r['severity'],"title":r['title'],"source":r['source']} for r in open_blocking],"checks":checks,"ai_review_gate_pass":all(checks.values()),"five_build_feedback_cycle":True,"next_public_feedback_build":"405.0","production_release_ready":False}

    def verify_integrity(self) -> dict[str,Any]:
        bad=[]
        for r0 in self.db.all("SELECT * FROM ai_review_finding_404"):
            r=dict(r0); hashed={k:r[k] for k in ('source','external_ref','title','severity','status','description','component','regression_test','fix_evidence','verification_evidence','opened_at','updated_at')}
            if r['content_hash'] != _sha(hashed): bad.append(r['finding_id'])
        return {"build":BUILD,"valid":not bad,"violations":bad}
