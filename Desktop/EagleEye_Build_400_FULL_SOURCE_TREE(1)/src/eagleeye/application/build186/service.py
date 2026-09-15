from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class Build186ProductionReleaseService:
    """Final Phase-6 release gate. It records evidence; it never self-approves."""

    BUILD = "186.0"
    REQUIRED_GATES = (
        "firefox_single_session",
        "guided_beginner_workflow",
        "source_query_sanitization",
        "source_processing",
        "ai_authenticity_calibration",
        "backup_restore",
        "operational_red_team",
        "database_integrity",
        "complete_case_export",
        "no_legacy_ui_fallback",
    )
    SOURCES = (
        {"source_id":"nist_ssdf_release","title":"NIST Secure Software Development Framework","class":"official_release_guidance","endpoint":"https://csrc.nist.gov/pubs/sp/800/218/final"},
        {"source_id":"owasp_asvs_release","title":"OWASP Application Security Verification Standard","class":"security_verification_standard","endpoint":"https://owasp.org/www-project-application-security-verification-standard/"},
        {"source_id":"slsa_release_provenance","title":"SLSA Build Provenance","class":"supply_chain_standard","endpoint":"https://slsa.dev/"},
        {"source_id":"sigstore_release","title":"Sigstore Release Signing","class":"artifact_signing_standard","endpoint":"https://docs.sigstore.dev/"},
        {"source_id":"bsi_it_grundschutz_release","title":"BSI IT-Grundschutz","class":"official_operational_security_guidance","endpoint":"https://www.bsi.bund.de/grundschutz"},
        {"source_id":"cisa_secure_by_design","title":"CISA Secure by Design","class":"official_product_security_guidance","endpoint":"https://www.cisa.gov/securebydesign"},
    )

    def __init__(self, db: Any, audit: Any, *, base_dir: str | Path, recovery: Any, redteam: Any, source_processing: Any, calibration: Any, actor: str = "system"):
        self.db, self.audit, self.recovery, self.redteam = db, audit, recovery, redteam
        self.source_processing, self.calibration, self.actor = source_processing, calibration, actor
        self.base_dir = Path(base_dir).resolve()

    def seed_sources(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "RELEASE SOURCES 186 ANLEGEN":
            raise PermissionError("explicit approval required")
        for source in self.SOURCES:
            payload={**source,"status":"DOCUMENTED","production_active":False}
            self.db.execute("INSERT OR REPLACE INTO release_source_profiles_186 VALUES(?,?,?,?,?,?,?,?,?)",(
                source["source_id"],source["title"],source["class"],source["endpoint"],"DOCUMENTED",0,now_ts(),self.actor,_hash(payload)))
        return {"created":len(self.SOURCES),"production_active":0,"review_required":True}

    def create_acceptance(self, *, approved_by: str, evidence: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        if confirmation != "RELEASE 186 ABNAHME ANLEGEN":
            raise PermissionError("explicit approval required")
        acceptance_id=new_id("release186")
        created=now_ts()
        gate_results={gate:self._gate_passed(evidence.get(gate)) for gate in self.REQUIRED_GATES}
        blockers=[gate for gate,passed in gate_results.items() if not passed]
        payload={"acceptance_id":acceptance_id,"gate_results":gate_results,"blockers":blockers,"approved_by":approved_by,"created_at":created}
        status="candidate_pass" if not blockers else "blocked"
        self.db.execute("INSERT INTO production_release_acceptance_186 VALUES(?,?,?,?,?,?,?,?,?)",(
            acceptance_id,status,dumps(gate_results),dumps(blockers),dumps(dict(evidence)),approved_by,created,None,_hash(payload)))
        self._event("acceptance_created",acceptance_id,{**payload,"status":status})
        return {**payload,"status":status,"automatic_release":False,"human_release_decision_required":True}

    def verify_runtime(self) -> dict[str, Any]:
        required=("START_EAGLEEYE_PRO_186_0.bat","START_EAGLEEYE_PRO.bat","EAGLEEYE_PRO_186_0.py","pyproject.toml")
        missing=[name for name in required if not (self.base_dir/name).exists()]
        legacy_starters=sorted(p.name for p in self.base_dir.glob("START_EAGLEEYE_PRO_*.bat") if p.name!="START_EAGLEEYE_PRO_186_0.bat")
        current=(self.base_dir/"EAGLEEYE_PRO_186_0.py").read_text(encoding="utf-8") if (self.base_dir/"EAGLEEYE_PRO_186_0.py").exists() else ""
        forbidden=[token for token in ("-no-remote","-private-window") if token in current]
        return {"passed":not missing and not forbidden,"missing":missing,"forbidden_browser_flags":forbidden,"legacy_starters_present":legacy_starters,"firefox_workspace":True,"automatic_legacy_fallback":False}

    def release_gate(self, acceptance_id: str) -> dict[str, Any]:
        row=self.db.one("SELECT * FROM production_release_acceptance_186 WHERE acceptance_id=?",(acceptance_id,))
        if not row: raise KeyError("acceptance not found")
        recovery=self.recovery.preflight()
        open_redteam=self.db.one("SELECT COUNT(*) AS n FROM redteam_findings_18510 WHERE status='open' AND severity IN ('critical','high')")
        blockers=json.loads(row["blockers_json"])
        if not recovery.get("passed"): blockers.append("database_integrity")
        if open_redteam and int(open_redteam["n"])>0: blockers.append("open_high_redteam_findings")
        blockers=sorted(set(blockers))
        result="candidate_pass" if not blockers else "blocked"
        return {"acceptance_id":acceptance_id,"result":result,"blockers":blockers,"automatic_release":False,"human_release_decision_required":True,"production_label_allowed":result=="candidate_pass"}

    def approve_release(self, acceptance_id: str, *, reviewer: str, decision: str, note: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"RELEASE 186 {acceptance_id} ENTSCHEIDEN": raise PermissionError("explicit approval required")
        if decision not in {"approve","reject","needs_more_evidence"}: raise ValueError("unsupported decision")
        gate=self.release_gate(acceptance_id)
        if decision=="approve" and gate["result"]!="candidate_pass": raise RuntimeError("release gate is blocked")
        status={"approve":"released","reject":"rejected","needs_more_evidence":"blocked"}[decision]
        self.db.execute("UPDATE production_release_acceptance_186 SET status=?,reviewed_at=? WHERE acceptance_id=?",(status,now_ts(),acceptance_id))
        review_id=new_id("review186")
        payload={"review_id":review_id,"acceptance_id":acceptance_id,"reviewer":reviewer,"decision":decision,"note":note,"status":status,"created_at":now_ts()}
        self.db.execute("INSERT INTO production_release_reviews_186 VALUES(?,?,?,?,?,?,?,?)",(review_id,acceptance_id,reviewer,decision,note,status,payload["created_at"],_hash(payload)))
        self._event("release_decided",acceptance_id,payload)
        return payload

    def status(self) -> dict[str, Any]:
        runtime=self.verify_runtime()
        schema=self.db.one("SELECT value FROM meta WHERE key='schema_version'")
        sources=self.db.one("SELECT COUNT(*) AS n FROM production_source_profiles_1857")
        return {"build":self.BUILD,"schema_version":schema["value"] if schema else None,"runtime":runtime,"prioritized_source_profiles":int(sources["n"]) if sources else 0,"phase6_status":"production_release_candidate","next_phase":"return_to_phase_6_extension","automatic_release":False}

    @staticmethod
    def _gate_passed(value: Any) -> bool:
        if value is True: return True
        if isinstance(value, Mapping): return bool(value.get("passed") or value.get("status") in {"passed","candidate_pass","production_ready"})
        return value in {"passed","candidate_pass","production_ready"}

    def _event(self,event_type:str,object_ref:str,payload:Mapping[str,Any])->None:
        prev=self.db.one("SELECT event_sha256 FROM production_release_events_186 ORDER BY created_at DESC,event_id DESC LIMIT 1")
        prev_sha=prev["event_sha256"] if prev else "0"*64
        eid=new_id("releaseevt186"); created=now_ts(); digest=_hash({"event_id":eid,"event_type":event_type,"object_ref":object_ref,"payload":payload,"created_at":created,"actor":self.actor,"prev":prev_sha})
        self.db.execute("INSERT INTO production_release_events_186 VALUES(?,?,?,?,?,?,?,?)",(eid,event_type,object_ref,dumps(payload),created,self.actor,prev_sha,digest))
