from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import hashlib, json, re, secrets

BUILD = "404.0"
POLICY_ID = "phase18.ai-review-release-gate.v404"
SEVERITIES = {"P0", "P1", "P2", "P3"}
STATUSES = {"open", "fix_in_progress", "fixed_pending_verification", "verified_closed"}
BLOCKING = {"P0", "P1"}
BLOCKING_TRANSITIONS = {
    "open": {"fix_in_progress"},
    "fix_in_progress": {"fixed_pending_verification"},
    "fixed_pending_verification": {"verified_closed"},
    "verified_closed": set(),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _sid(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(12)}"

def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

def _sha(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode()).hexdigest()


@dataclass(frozen=True)
class ReviewGateRule:
    key: str
    requirement: str


RULES = (
    ReviewGateRule("blocking_severity", "Open P0/P1 findings block cycle acceptance"),
    ReviewGateRule("verified_closure", "Blocking findings close only through ordered fix and independent verification"),
    ReviewGateRule("regression_required", "Every P0/P1 finding requires an existing named regression test with passed verification evidence"),
    ReviewGateRule("human_governed", "An authenticated reviewer with dossier.review must verify blocking closures"),
    ReviewGateRule("source_traceability", "Every finding and closure evidence is integrity-bound"),
    ReviewGateRule("feedback_cycle", "Builds 401-405 publish together for renewed GitHub/external review"),
)


class AIReviewGate404:
    """Persistent review ledger with fail-closed, human-governed blocking closure."""

    def __init__(self, db: Any, audit: Any, *, build403: Any, governance: Any = None, install_dir: str | Path | None = None, actor: str = "local-analyst"):
        self.db = db
        self.audit = audit
        self.build403 = build403
        self.governance = governance
        self.install_dir = Path(install_dir or ".")
        self.actor = actor
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS ai_review_finding_404(
          finding_id TEXT PRIMARY KEY, source TEXT NOT NULL, external_ref TEXT NOT NULL,
          title TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL,
          description TEXT NOT NULL, component TEXT NOT NULL, regression_test TEXT NOT NULL DEFAULT '',
          fix_evidence TEXT NOT NULL DEFAULT '', verification_evidence TEXT NOT NULL DEFAULT '',
          opened_at TEXT NOT NULL, updated_at TEXT NOT NULL, content_hash TEXT NOT NULL,
          fixed_by TEXT NOT NULL DEFAULT '', verified_by TEXT NOT NULL DEFAULT '', verification_receipt TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_ai_review_finding_404_gate ON ai_review_finding_404(severity,status);
        """)
        cols={str(r['name']) for r in self.db.all("PRAGMA table_info(ai_review_finding_404)")}
        for name in ("fixed_by","verified_by","verification_receipt"):
            if name not in cols:
                self.db.conn.execute(f"ALTER TABLE ai_review_finding_404 ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
        self.db.conn.commit()

    def rules(self) -> dict[str, Any]:
        return {"build":BUILD,"policy":POLICY_ID,"rules":[asdict(r) for r in RULES],"blocking_severities":sorted(BLOCKING),"production_release_ready":False}

    def _hash_fields(self, row: Mapping[str, Any]) -> dict[str, Any]:
        keys=("source","external_ref","title","severity","status","description","component","regression_test","fix_evidence","verification_evidence","opened_at","updated_at","fixed_by","verified_by","verification_receipt")
        return {k:row.get(k,"") for k in keys}

    @staticmethod
    def _identity_name(identity: Mapping[str, Any] | None) -> str:
        if not identity: return ""
        return str(identity.get("user_id") or identity.get("username") or "").strip()

    @staticmethod
    def _structured_evidence(value: Any, *, required_type: str) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise ValueError("blocking review evidence must be a structured object")
        body=dict(value)
        if str(body.get("type") or "").strip() != required_type:
            raise ValueError(f"evidence.type must be {required_type}")
        ref=str(body.get("ref") or "").strip()
        if not ref:
            raise ValueError("evidence.ref is required")
        return body

    def _regression_exists(self, regression_test: str) -> bool:
        m=re.fullmatch(r"(tests/[A-Za-z0-9_./-]+\.py)::(test_[A-Za-z0-9_]+)", regression_test.strip())
        if not m: return False
        path=(self.install_dir/m.group(1)).resolve()
        try:
            path.relative_to(self.install_dir.resolve())
        except ValueError:
            return False
        if not path.is_file(): return False
        text=path.read_text(encoding="utf-8",errors="replace")
        return re.search(rf"^def\s+{re.escape(m.group(2))}\s*\(", text, re.M) is not None

    def record_finding(self, *, source:str, external_ref:str, title:str, severity:str, description:str, component:str, actor:str|None=None) -> dict[str,Any]:
        severity=severity.upper().strip()
        if severity not in SEVERITIES: raise ValueError("severity must be P0/P1/P2/P3")
        if not source.strip() or not title.strip() or not description.strip(): raise ValueError("source, title and description are required")
        fid=_sid("review404"); now=_now()
        body={"finding_id":fid,"source":source.strip(),"external_ref":external_ref.strip(),"title":title.strip(),"severity":severity,"status":"open","description":description.strip(),"component":component.strip(),"regression_test":"","fix_evidence":"","verification_evidence":"","opened_at":now,"updated_at":now,"fixed_by":"","verified_by":"","verification_receipt":""}
        body["content_hash"]=_sha(self._hash_fields(body))
        self.db.execute("""INSERT INTO ai_review_finding_404(finding_id,source,external_ref,title,severity,status,description,component,regression_test,fix_evidence,verification_evidence,opened_at,updated_at,content_hash,fixed_by,verified_by,verification_receipt) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", tuple(body[k] for k in ("finding_id","source","external_ref","title","severity","status","description","component","regression_test","fix_evidence","verification_evidence","opened_at","updated_at","content_hash","fixed_by","verified_by","verification_receipt")))
        self.audit.log('ai_review_finding_recorded','ai_review_finding_404',fid,'',{'severity':severity,'source':source,'component':component,'actor':actor or self.actor})
        return self.finding(fid)

    def finding(self, finding_id:str) -> dict[str,Any]:
        row=self.db.one("SELECT * FROM ai_review_finding_404 WHERE finding_id=?",(finding_id,))
        if not row: raise KeyError("review finding not found")
        return dict(row)

    def transition(self, *, finding_id:str, status:str, regression_test:str="", fix_evidence:Any="", verification_evidence:Any="", actor:str|None=None, verifier_identity:Mapping[str,Any]|None=None) -> dict[str,Any]:
        status=status.strip()
        if status not in STATUSES: raise ValueError("unsupported review finding status")
        old=self.finding(finding_id); sev=old['severity']; old_status=old['status']
        if sev in BLOCKING and status not in BLOCKING_TRANSITIONS.get(old_status,set()):
            raise ValueError(f"blocking finding transition {old_status}->{status} is not allowed")
        now=_now(); merged={**old,"status":status,"updated_at":now}
        if status=="fix_in_progress":
            merged["fixed_by"] = str(actor or self.actor).strip()
        elif status=="fixed_pending_verification":
            evidence=self._structured_evidence(fix_evidence,required_type="fix") if sev in BLOCKING else ({"type":"fix","ref":str(fix_evidence)} if not isinstance(fix_evidence,Mapping) else dict(fix_evidence))
            merged["fix_evidence"]=_canon(evidence)
            merged["fixed_by"]=old.get("fixed_by") or str(actor or self.actor).strip()
        elif status=="verified_closed":
            if sev in BLOCKING:
                if not old.get("fix_evidence"): raise ValueError("fix evidence missing from fixed_pending_verification state")
                verification=self._structured_evidence(verification_evidence,required_type="verification")
                reg=regression_test.strip() or str(verification.get("test") or "").strip()
                if not self._regression_exists(reg): raise ValueError("P0/P1 closure requires an existing named regression test")
                if verification.get("result") != "passed" or str(verification.get("test") or "") != reg:
                    raise ValueError("verification evidence must attest the named regression passed")
                verifier=self._identity_name(verifier_identity)
                if not verifier: raise PermissionError("authenticated independent verifier required")
                if self.governance is None: raise PermissionError("review governance unavailable")
                self.governance.authorize(dict(verifier_identity),case_id='',capability='dossier.review',object_type='ai_review_finding_404',object_id=finding_id)
                if verifier == str(old.get("fixed_by") or ""):
                    raise PermissionError("blocking finding requires independent verifier")
                merged["regression_test"]=reg
                merged["verification_evidence"]=_canon(verification)
                merged["verified_by"]=verifier
                merged["verification_receipt"]=_sha({"finding_id":finding_id,"fix_evidence":old['fix_evidence'],"verification":verification,"regression_test":reg,"verified_by":verifier})
            else:
                merged["regression_test"]=regression_test.strip() or old.get("regression_test","")
                merged["verification_evidence"]=_canon(verification_evidence) if isinstance(verification_evidence,Mapping) else str(verification_evidence)
                merged["verified_by"]=self._identity_name(verifier_identity) or str(actor or self.actor)
        elif status=="open":
            pass
        merged["content_hash"]=_sha(self._hash_fields(merged))
        self.db.execute("""UPDATE ai_review_finding_404 SET status=?,regression_test=?,fix_evidence=?,verification_evidence=?,updated_at=?,content_hash=?,fixed_by=?,verified_by=?,verification_receipt=? WHERE finding_id=?""",(merged['status'],merged.get('regression_test',''),merged.get('fix_evidence',''),merged.get('verification_evidence',''),now,merged['content_hash'],merged.get('fixed_by',''),merged.get('verified_by',''),merged.get('verification_receipt',''),finding_id))
        self.audit.log('ai_review_finding_transitioned','ai_review_finding_404',finding_id,'',{'from':old_status,'to':status,'severity':sev,'actor':actor or self.actor,'verified_by':merged.get('verified_by','')})
        return self.finding(finding_id)

    def _closed_blocking_valid(self, r: Mapping[str,Any]) -> bool:
        if not (r.get('fix_evidence') and r.get('verification_evidence') and r.get('regression_test') and r.get('verified_by') and r.get('verification_receipt')): return False
        if not self._regression_exists(str(r['regression_test'])): return False
        try: verification=json.loads(str(r['verification_evidence']))
        except Exception: return False
        if verification.get('type')!='verification' or verification.get('result')!='passed' or verification.get('test')!=r['regression_test']: return False
        expected=_sha({"finding_id":r['finding_id'],"fix_evidence":r['fix_evidence'],"verification":verification,"regression_test":r['regression_test'],"verified_by":r['verified_by']})
        return expected==r['verification_receipt']

    def gate_status(self) -> dict[str,Any]:
        rows=[dict(r) for r in self.db.all("SELECT * FROM ai_review_finding_404 ORDER BY opened_at,finding_id")]
        open_blocking=[r for r in rows if r['severity'] in BLOCKING and r['status']!='verified_closed']
        closed_blocking=[r for r in rows if r['severity'] in BLOCKING and r['status']=='verified_closed']
        closure_integrity=all(self._closed_blocking_valid(r) for r in closed_blocking)
        ledger_integrity=self.verify_integrity()['valid']
        neg=self.build403.negative_path_status()
        checks={
            "build403_negative_contracts_preserved": bool(neg.get('contract_audit_pass')),
            "build403_negative_runtime_preserved": bool(neg.get('runtime_probe_pass')),
            "build403_scenario_catalog_preserved": int(neg.get('scenario_count',0)) >= 15,
            "no_open_p0_p1": len(open_blocking)==0,
            "closed_p0_p1_have_verified_evidence": closure_integrity,
            "review_ledger_integrity": ledger_integrity,
            "production_not_released": True,
        }
        return {"build":BUILD,"finding_count":len(rows),"open_blocking_count":len(open_blocking),"closed_blocking_count":len(closed_blocking),"open_blocking":[{"finding_id":r['finding_id'],"severity":r['severity'],"title":r['title'],"source":r['source']} for r in open_blocking],"checks":checks,"ai_review_gate_pass":all(checks.values()),"five_build_feedback_cycle":True,"next_public_feedback_build":"405.0","production_release_ready":False}

    def verify_integrity(self) -> dict[str,Any]:
        bad=[]
        for r0 in self.db.all("SELECT * FROM ai_review_finding_404"):
            r=dict(r0)
            if r['content_hash'] != _sha(self._hash_fields(r)): bad.append(r['finding_id'])
        return {"build":BUILD,"valid":not bad,"violations":bad}
