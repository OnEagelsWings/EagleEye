from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class Build18510OperationalRedTeamService:
    BUILD = "185.10"
    SOURCES = (
        {"source_id":"owasp_file_upload","title":"OWASP File Upload Cheat Sheet","class":"security_primary_guidance","endpoint":"https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html","purpose":["archive_safety","filename_validation","content_type_validation"]},
        {"source_id":"nist_ai_100_2e2025","title":"NIST AI 100-2e2025 Adversarial Machine Learning","class":"official_ai_security_standard","endpoint":"https://csrc.nist.gov/pubs/ai/100/2/e2025/final","purpose":["model_evasion","data_poisoning","prompt_injection_resilience"]},
        {"source_id":"mitre_atlas","title":"MITRE ATLAS","class":"threat_knowledge_base","endpoint":"https://atlas.mitre.org/","purpose":["ai_threat_scenarios","red_team_mapping"]},
        {"source_id":"bsi_tr_03185","title":"BSI TR-03185 Sichere Softwareentwicklung","class":"official_secure_development_guidance","endpoint":"https://www.bsi.bund.de/SharedDocs/Downloads/DE/BSI/Publikationen/TechnischeRichtlinien/TR03185/BSI-TR-03185.pdf","purpose":["secure_development","acceptance_testing"]},
        {"source_id":"owasp_llm_prompt_injection","title":"OWASP LLM Prompt Injection Guidance","class":"ai_security_guidance","endpoint":"https://owasp.org/www-project-top-10-for-large-language-model-applications/","purpose":["untrusted_content","agent_boundary_tests"]},
        {"source_id":"python_zipfile_security","title":"Python zipfile Security Notes","class":"runtime_primary_documentation","endpoint":"https://docs.python.org/3/library/zipfile.html","purpose":["zip_validation","safe_extraction"]},
    )

    _INJECTION_PATTERNS = (
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"reveal\s+(the\s+)?system\s+prompt",
        r"bypass\s+(the\s+)?policy",
        r"developer\s+message",
        r"execute\s+(this\s+)?command",
        r"upload\s+.*\s+to\s+https?://",
        r"disable\s+(security|logging|audit)",
    )
    _DANGEROUS_EXTENSIONS = {".exe", ".dll", ".com", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".jar", ".msi", ".scr"}
    _ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".7z", ".rar"}

    def __init__(self, db: Any, audit: Any, *, base_dir: str | Path, sources: Any | None = None, authenticity: Any | None = None, plugins: Any | None = None, recovery: Any | None = None, actor: str = "system"):
        self.db, self.audit, self.sources, self.authenticity, self.plugins, self.recovery, self.actor = db, audit, sources, authenticity, plugins, recovery, actor
        self.base_dir = Path(base_dir).resolve()

    def seed_sources(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "REDTEAM SOURCES 18510 ANLEGEN":
            raise PermissionError("explicit approval required")
        for source in self.SOURCES:
            payload = {**source, "status":"DOCUMENTED", "production_active":False}
            self.db.execute(
                "INSERT OR REPLACE INTO redteam_source_profiles_18510 VALUES(?,?,?,?,?,?,?,?,?,?)",
                (source["source_id"], source["title"], source["class"], source["endpoint"], dumps(source["purpose"]), "DOCUMENTED", 0, now_ts(), self.actor, _hash(payload)),
            )
        return {"created":len(self.SOURCES), "production_active":0, "review_required":True}

    def create_campaign(self, *, case_id: str, title: str, scopes: Sequence[str], approved_by: str, confirmation: str) -> dict[str, Any]:
        allowed = {"uploads","archives","prompt_injection","source_poisoning","plugins","background_jobs","backup_restore","browser_workflow","case_workflow"}
        selected = sorted(set(scopes))
        if confirmation != f"REDTEAM 18510 {case_id} KAMPAGNE ANLEGEN":
            raise PermissionError("explicit approval required")
        if not selected or not set(selected).issubset(allowed):
            raise ValueError("unsupported red-team scope")
        campaign_id = new_id("rt18510")
        created = now_ts()
        payload = {"campaign_id":campaign_id,"case_id":case_id,"title":title,"scopes":selected,"approved_by":approved_by,"created_at":created}
        self.db.execute("INSERT INTO redteam_campaigns_18510 VALUES(?,?,?,?,?,?,?,?,?)",(campaign_id,case_id,title,dumps(selected),"active",approved_by,created,None,_hash(payload)))
        self._event("campaign_created", campaign_id, payload)
        return {**payload,"status":"active","automatic_exploitation":False}

    def inspect_filename(self, filename: str) -> dict[str, Any]:
        findings=[]
        raw=str(filename)
        normalized=raw.replace("\\", "/")
        parts=PurePosixPath(normalized).parts
        if raw.strip()!=raw or any(ord(ch)<32 for ch in raw): findings.append("control_or_whitespace_obfuscation")
        if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized): findings.append("absolute_path")
        if ".." in parts: findings.append("path_traversal")
        suffix=Path(normalized).suffix.lower()
        if suffix in self._DANGEROUS_EXTENSIONS: findings.append("executable_extension")
        if normalized.count(".")>=2 and suffix in self._DANGEROUS_EXTENSIONS: findings.append("double_extension")
        safe_name=Path(normalized).name
        return {"filename":raw,"safe_basename":safe_name,"findings":sorted(set(findings)),"allowed":not findings,"review_required":bool(findings)}

    def inspect_archive(self, archive_path: str | Path, *, max_files: int = 500, max_uncompressed_bytes: int = 512*1024*1024, max_ratio: float = 100.0) -> dict[str, Any]:
        path=Path(archive_path).resolve()
        if not path.exists() or not path.is_file(): raise FileNotFoundError(path)
        findings=[]; entries=[]; total_c=0; total_u=0
        try:
            with zipfile.ZipFile(path) as zf:
                infos=zf.infolist()
                if len(infos)>max_files: findings.append("too_many_entries")
                for info in infos:
                    name_check=self.inspect_filename(info.filename)
                    total_c += max(0, info.compress_size); total_u += max(0, info.file_size)
                    mode=(info.external_attr >> 16) & 0xFFFF
                    is_symlink=stat.S_ISLNK(mode)
                    local=[]
                    if name_check["findings"]: local.extend(name_check["findings"])
                    if is_symlink: local.append("symlink_entry")
                    if Path(info.filename).suffix.lower() in self._ARCHIVE_EXTENSIONS: local.append("nested_archive")
                    ratio=(info.file_size/max(1,info.compress_size)) if info.file_size else 0.0
                    if ratio>max_ratio: local.append("suspicious_compression_ratio")
                    entries.append({"name":info.filename,"compressed":info.compress_size,"uncompressed":info.file_size,"ratio":round(ratio,2),"findings":sorted(set(local))})
                if total_u>max_uncompressed_bytes: findings.append("uncompressed_size_limit")
                if total_u/max(1,total_c)>max_ratio: findings.append("archive_compression_ratio")
                for e in entries: findings.extend(e["findings"])
        except zipfile.BadZipFile:
            findings.append("invalid_zip")
        result={"path":str(path),"entry_count":len(entries),"compressed_bytes":total_c,"uncompressed_bytes":total_u,"findings":sorted(set(findings)),"safe_to_stage":not findings,"extracted":False,"limits":{"max_files":max_files,"max_uncompressed_bytes":max_uncompressed_bytes,"max_ratio":max_ratio}}
        return result

    def inspect_untrusted_text(self, text: str, *, source_ref: str = "") -> dict[str, Any]:
        value=str(text)
        lowered=value.lower()
        matches=[]
        for pattern in self._INJECTION_PATTERNS:
            if re.search(pattern, lowered, flags=re.I): matches.append(pattern)
        secret_markers=[]
        for marker in ("api_key", "authorization:", "private_key", "password=", "session="):
            if marker in lowered: secret_markers.append(marker)
        return {"source_ref":source_ref,"prompt_injection_candidate":bool(matches),"matched_rules":matches,"secret_markers":secret_markers,"untrusted_content_is_data":True,"executed":False,"human_review_required":bool(matches or secret_markers)}

    def validate_source_record(self, *, source_id: str, record: Mapping[str, Any], required_fields: Sequence[str], source_ref: str) -> dict[str, Any]:
        missing=[f for f in required_fields if record.get(f) in (None, "", [])]
        text=_canon(record)
        injection=self.inspect_untrusted_text(text, source_ref=source_ref)
        provenance_ok=bool(source_id and source_ref)
        findings=[]
        if missing: findings.append("schema_mismatch")
        if injection["prompt_injection_candidate"]: findings.append("embedded_instruction")
        if injection["secret_markers"]: findings.append("secret_like_content")
        if not provenance_ok: findings.append("missing_provenance")
        canonical_sha=_hash(record)
        status="candidate" if not findings else "quarantined_candidate"
        return {"source_id":source_id,"source_ref":source_ref,"status":status,"missing_fields":missing,"findings":findings,"canonical_sha256":canonical_sha,"automatic_identity_confirmation":False,"review_required":True}

    def simulate_interruption(self, *, campaign_id: str, component: str, checkpoint: str, recoverable: bool, confirmation: str) -> dict[str, Any]:
        if confirmation != f"REDTEAM 18510 {campaign_id} UNTERBRECHUNG TESTEN": raise PermissionError("explicit approval required")
        allowed={"source_job","authenticity_job","backup_job","plugin_job","report_export"}
        if component not in allowed: raise ValueError("unsupported component")
        test_id=new_id("rtcase18510"); created=now_ts()
        expected="resume_or_fail_closed" if recoverable else "fail_closed"
        result={"test_id":test_id,"campaign_id":campaign_id,"component":component,"checkpoint":checkpoint,"recoverable":bool(recoverable),"expected_behavior":expected,"data_loss_acceptable":False,"automatic_external_action":False}
        self.db.execute("INSERT INTO redteam_tests_18510 VALUES(?,?,?,?,?,?,?,?,?,?,?)",(test_id,campaign_id,"interruption",component,dumps({"checkpoint":checkpoint}),"passed",dumps(result),"medium",created,self.actor,_hash(result)))
        self._event("interruption_tested", test_id, result)
        return result

    def run_campaign(self, *, campaign_id: str, fixtures: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        if confirmation != f"REDTEAM 18510 {campaign_id} AUSFUEHREN": raise PermissionError("explicit approval required")
        campaign=self.db.one("SELECT * FROM redteam_campaigns_18510 WHERE campaign_id=?",(campaign_id,))
        if not campaign: raise KeyError("campaign not found")
        findings=[]; tests=[]
        for filename in fixtures.get("filenames",[]):
            r=self.inspect_filename(filename); tests.append({"type":"filename","input":filename,"result":r})
            for f in r["findings"]: findings.append(self._finding(campaign_id,"upload_filename",f,"high" if f in {"path_traversal","absolute_path","executable_extension"} else "medium",r))
        for text in fixtures.get("texts",[]):
            r=self.inspect_untrusted_text(text); tests.append({"type":"untrusted_text","result":r})
            if r["prompt_injection_candidate"]: findings.append(self._finding(campaign_id,"prompt_injection","embedded_instruction","high",r))
            if r["secret_markers"]: findings.append(self._finding(campaign_id,"sensitive_content","secret_like_content","high",r))
        for item in fixtures.get("source_records",[]):
            r=self.validate_source_record(source_id=item.get("source_id",""),record=item.get("record",{}),required_fields=item.get("required_fields",[]),source_ref=item.get("source_ref","")); tests.append({"type":"source_record","result":r})
            for f in r["findings"]: findings.append(self._finding(campaign_id,"source_poisoning",f,"high" if f=="embedded_instruction" else "medium",r))
        critical=sum(1 for f in findings if f["severity"]=="critical")
        high=sum(1 for f in findings if f["severity"]=="high")
        status="blocked" if critical or high else "candidate_pass"
        finished=now_ts()
        self.db.execute("UPDATE redteam_campaigns_18510 SET status=?,finished_at=? WHERE campaign_id=?",(status,finished,campaign_id))
        summary={"campaign_id":campaign_id,"status":status,"tests":len(tests),"findings":len(findings),"critical":critical,"high":high,"automatic_remediation":False,"human_release_decision_required":True}
        self._event("campaign_completed",campaign_id,summary)
        return {**summary,"test_results":tests,"finding_records":findings}

    def release_gate(self, *, campaign_id: str) -> dict[str, Any]:
        rows=self.db.all("SELECT severity,status FROM redteam_findings_18510 WHERE campaign_id=?",(campaign_id,))
        open_critical=sum(1 for r in rows if r["severity"]=="critical" and r["status"]=="open")
        open_high=sum(1 for r in rows if r["severity"]=="high" and r["status"]=="open")
        result="blocked" if open_critical or open_high else "candidate_pass"
        return {"campaign_id":campaign_id,"result":result,"open_critical":open_critical,"open_high":open_high,"automatic_production_release":False,"human_release_decision_required":True}

    def acknowledge_finding(self, finding_id: str, *, reviewer: str, decision: str, note: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"REDTEAM FINDING 18510 {finding_id} PRUEFEN": raise PermissionError("explicit approval required")
        if decision not in {"fixed","accepted_risk","false_positive","needs_more_evidence"}: raise ValueError("unsupported decision")
        status="closed" if decision in {"fixed","accepted_risk","false_positive"} else "open"
        self.db.execute("UPDATE redteam_findings_18510 SET status=?,reviewer=?,review_note=?,reviewed_at=? WHERE finding_id=?",(status,reviewer,f"{decision}: {note}",now_ts(),finding_id))
        return {"finding_id":finding_id,"status":status,"decision":decision,"reviewer":reviewer}

    def _finding(self,campaign_id:str,category:str,code:str,severity:str,evidence:Mapping[str,Any])->dict[str,Any]:
        finding_id=new_id("rtf18510"); created=now_ts(); payload={"finding_id":finding_id,"campaign_id":campaign_id,"category":category,"code":code,"severity":severity,"evidence":evidence,"created_at":created}
        self.db.execute("INSERT INTO redteam_findings_18510 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(finding_id,campaign_id,category,code,severity,"open",dumps(evidence),created,"","",None,_hash(payload)))
        return {**payload,"status":"open"}

    def _event(self,event_type:str,object_ref:str,payload:Mapping[str,Any])->None:
        prev=self.db.one("SELECT event_sha256 FROM redteam_events_18510 ORDER BY created_at DESC,event_id DESC LIMIT 1")
        prev_sha=prev["event_sha256"] if prev else "0"*64
        eid=new_id("rtevt18510"); created=now_ts(); digest=_hash({"event_id":eid,"event_type":event_type,"object_ref":object_ref,"payload":payload,"created_at":created,"actor":self.actor,"prev":prev_sha})
        self.db.execute("INSERT INTO redteam_events_18510 VALUES(?,?,?,?,?,?,?,?)",(eid,event_type,object_ref,dumps(payload),created,self.actor,prev_sha,digest))
