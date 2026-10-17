from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime,timezone


BUILD="459.0"


def _canon(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def _sha(obj):
    return hashlib.sha256(_canon(obj).encode("utf-8")).hexdigest()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class FieldReadiness459:
    """Read-only, bounded case snapshot and restart/resume verification.

    Field checks do not launch acquisition, modify Evidence/Claims, or create
    autonomous analysis decisions. PASS means bounded local state is intact,
    not that a case's facts are true or that the app is production qualified.
    """

    def __init__(self,db,audit,*,governance,workspace457,documents458,entity_lineage456,qualification455,context_instance_id,actor="local-analyst"):
        self.db,self.audit=db,audit
        self.governance=governance
        self.workspace457=workspace457
        self.documents458=documents458
        self.entity_lineage456=entity_lineage456
        self.qualification455=qualification455
        self.context_instance_id=str(context_instance_id)
        self.actor=actor
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS phase20_case_resume_run_459(
                run_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,context_instance_id TEXT NOT NULL,
                source_state_sha256 TEXT NOT NULL,snapshot_json TEXT NOT NULL,
                created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_resume459_case ON phase20_case_resume_run_459(case_id,created_at);
            """
        )
        self.db.conn.commit()

    def _rh(self,item):
        return _sha({k:v for k,v in item.items() if k!="record_hash"})

    def _authorize(self,identity,case_id,capability,object_id):
        if not isinstance(identity,dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("canonical active identity required")
        try:
            user=self.governance.identity.public_user(identity["username"])
        except (ValueError,KeyError):
            raise PermissionError("canonical active identity required") from None
        if not user["active"] or str(user["user_id"])!=str(identity["user_id"]):
            raise PermissionError("canonical active identity required")
        user={**user,"session_id":str(identity.get("session_id") or "build459")}
        self.governance.authorize(user,case_id=str(case_id),capability=capability,
            object_type="field_readiness_459",object_id=str(object_id))
        return user

    def _case_state(self,identity,case_id):
        docs=self.documents458.documents(identity=identity,case_id=case_id)
        # Currentness, not mere existence, is the export/resume criterion.
        claim_rows=self.db.all("SELECT claim_id FROM claim_447 WHERE case_id=? ORDER BY claim_id",(str(case_id),))
        source_rows=[]
        failed=[]
        for doc in docs:
            present=self.documents458._payload_current(doc)
            source_rows.append({"document_id":doc["document_id"],"sha256":doc["document_sha256"],
                                "record_hash":doc["record_hash"],"state":doc["state"],
                                "payload_current":present})
            if not present:
                failed.append({"document_id":doc["document_id"],"reason":"document_payload_not_current"})
        claim_refs=[]
        for item in claim_rows:
            cid=item["claim_id"]
            try:
                refs=self.documents458.claim_citations(identity=identity,claim_id=cid)
            except (PermissionError,ValueError,KeyError,RuntimeError):
                failed.append({"claim_id":cid,"reason":"unresolvable_claim_reference"})
                continue
            claim_refs.append({"claim_id":cid,"citations":len(refs["citations"]),
                               "all_current":refs["all_references_current"]})
            if not refs["all_references_current"]:
                failed.append({"claim_id":cid,"reason":"stale_citation_reference"})
        case_state={
            "case_id":str(case_id),
            "documents":source_rows,
            "claims":claim_refs,
            "entity_lineage_integrity":bool(self.entity_lineage456.verify_integrity()["valid"]),
            "document_integrity":bool(self.documents458.verify_integrity()["valid"]),
        }
        if not case_state["entity_lineage_integrity"]:
            failed.append({"reason":"entity_lineage_integrity_failure"})
        if not case_state["document_integrity"]:
            failed.append({"reason":"document_integrity_failure"})
        return case_state,failed

    def snapshot(self,*,identity,case_id):
        self._authorize(identity,case_id,"case.read",case_id)
        state,blockers=self._case_state(identity,case_id)
        return {
            "build":BUILD,"case_id":str(case_id),
            "context_instance_id":self.context_instance_id,
            "integrity_valid":not blockers,
            "status":"readiness" if not blockers else "hold",
            "blockers":blockers,
            "document_count":len(state["documents"]),
            "claim_count":len(state["claims"]),
            "source_state_sha256":_sha(state),
            "snapshot":state,
            "no_background_network_actions":True,
            "no_auto_claim_acceptance":True,
            "not_a_full_research_gate":True,
            "next_full_checkpoint":"460.0",
        }

    def checkpoint(self,*,identity,case_id):
        ident=self._authorize(identity,case_id,"research.run",case_id)
        snap=self.snapshot(identity=identity,case_id=case_id)
        row={
            "run_id":"resume459_"+secrets.token_hex(10),
            "case_id":str(case_id),
            "context_instance_id":self.context_instance_id,
            "source_state_sha256":snap["source_state_sha256"],
            "snapshot_json":_canon(snap["snapshot"]),
            "created_by":str(ident["username"]),"created_at":_now(),
        }
        row["record_hash"]=self._rh(row)
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO phase20_case_resume_run_459 VALUES("+",".join("?" for _ in row)+")",tuple(row.values()))
            self.audit.log("case_resume_checkpoint_459","case",row["run_id"],case_id,
                           {"source_state_sha256":snap["source_state_sha256"],"initial_readiness":snap["status"]})
        return {"run_id":row["run_id"],"case_id":case_id,"status":snap["status"],
                "source_state_sha256":row["source_state_sha256"],
                "requires_restart_verification":True}

    def verify_reopened(self,*,identity,run_id):
        row=self.db.one("SELECT * FROM phase20_case_resume_run_459 WHERE run_id=?",(str(run_id),))
        if not row:
            raise KeyError("Build-459 checkpoint not found")
        self._authorize(identity,row["case_id"],"case.read",run_id)
        item=dict(row)
        row_valid=self._rh(item)==item["record_hash"]
        try:
            frozen=json.loads(item["snapshot_json"])
            snapshot_valid=isinstance(frozen,dict) and _sha(frozen)==item["source_state_sha256"]
        except (TypeError,ValueError,json.JSONDecodeError):
            snapshot_valid=False
        fresh=self.snapshot(identity=identity,case_id=item["case_id"])
        lifecycle=self.qualification455._context_lifecycle_checks(item["context_instance_id"])
        lifecycle_valid=all(bool(x) for x in lifecycle.values())
        current_match=fresh["source_state_sha256"]==item["source_state_sha256"]
        # FAIL CLOSED: an overlap is not a restart; a changed source invalidates
        # the old checkpoint until a human creates a new one.
        passed=bool(row_valid and snapshot_valid and lifecycle_valid and current_match and fresh["integrity_valid"])
        return {
            "build":BUILD,"case_id":item["case_id"],"run_id":str(run_id),
            "result":"pass" if passed else "hold",
            "record_hash_valid":row_valid,
            "snapshot_hash_valid":snapshot_valid,
            "close_then_reopen_verified":lifecycle_valid,
            "context_lifecycle":lifecycle,
            "source_state_current":current_match,
            "case_integrity_valid":fresh["integrity_valid"],
            "blockers":fresh["blockers"],
            "automatic_truth_determination":False,
            "production_release_ready":False,
        }

    def verify_integrity(self):
        violations=[]
        for item in self.db.all("SELECT * FROM phase20_case_resume_run_459"):
            if self._rh(item)!=item["record_hash"]:
                violations.append({"run_id":item["run_id"],"reason":"run_record_hash_mismatch"})
            try:
                snapshot=json.loads(item["snapshot_json"])
                if _sha(snapshot)!=item["source_state_sha256"]:
                    violations.append({"run_id":item["run_id"],"reason":"snapshot_hash_mismatch"})
            except (ValueError,TypeError,json.JSONDecodeError):
                violations.append({"run_id":item["run_id"],"reason":"invalid_snapshot"})
        return {"build":BUILD,"valid":not violations,"violations":violations}

    def status(self):
        integrity=self.verify_integrity()
        return {"build":BUILD,"policy":"bounded_field_readiness_and_restart_references",
                "integrity_valid":integrity["valid"],
                "checkpoints":self.db.one("SELECT COUNT(*) AS n FROM phase20_case_resume_run_459")["n"],
                "read_only_resume_verification":True,
                "requires_actual_close_then_reopen":True,
                "automatic_research_actions":False,
                "full_research_gate_this_build":False,
                "next_checkpoint":"460.0","production_release_ready":False}
