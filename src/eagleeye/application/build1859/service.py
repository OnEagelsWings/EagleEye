from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class Build1859MigrationBackupRecoveryService:
    BUILD = "185.9"
    SOURCES = (
        {"source_id":"sqlite_backup_api","title":"SQLite Online Backup API","class":"primary_technical_standard","endpoint":"https://sqlite.org/backup.html","purpose":["consistent_backup","transactional_snapshot"]},
        {"source_id":"sqlite_integrity_check","title":"SQLite PRAGMA integrity_check","class":"primary_technical_standard","endpoint":"https://sqlite.org/pragma.html#pragma_integrity_check","purpose":["database_integrity","post_restore_validation"]},
        {"source_id":"nist_sp_800_34","title":"NIST SP 800-34 Contingency Planning","class":"official_resilience_guidance","endpoint":"https://csrc.nist.gov/pubs/sp/800/34/r1/upd1/final","purpose":["recovery_plan","testing"]},
        {"source_id":"bsi_notfallmanagement","title":"BSI IT-Grundschutz Notfallmanagement","class":"official_resilience_guidance","endpoint":"https://www.bsi.bund.de/","purpose":["backup_policy","recovery_testing"]},
        {"source_id":"owasp_asvs_backup","title":"OWASP ASVS Stored Data Protection","class":"security_standard","endpoint":"https://owasp.org/www-project-application-security-verification-standard/","purpose":["backup_confidentiality","access_control"]},
        {"source_id":"w3c_prov_recovery","title":"W3C PROV-O","class":"provenance_standard","endpoint":"https://www.w3.org/TR/prov-o/","purpose":["migration_provenance","restore_chain"]},
    )

    def __init__(self, db: Any, audit: Any, *, base_dir: str | Path | None = None, repository: Any | None = None, actor: str = "system"):
        self.db, self.audit, self.repository, self.actor = db, audit, repository, actor
        self.base_dir = Path(base_dir or getattr(db, "base_dir", ".")).resolve()
        self.backup_dir = self.base_dir / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def seed_sources(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "RESILIENCE SOURCES 1859 ANLEGEN":
            raise PermissionError("explicit approval required")
        for source in self.SOURCES:
            payload = {**source, "status": "DOCUMENTED", "production_active": False}
            self.db.execute(
                "INSERT OR REPLACE INTO resilience_source_profiles_1859 VALUES(?,?,?,?,?,?,?,?,?,?)",
                (source["source_id"], source["title"], source["class"], source["endpoint"], dumps(source["purpose"]), "DOCUMENTED", 0, now_ts(), self.actor, _hash(payload)),
            )
        return {"created": len(self.SOURCES), "production_active": 0, "review_required": True}

    def preflight(self) -> dict[str, Any]:
        integrity = self.db.one("PRAGMA integrity_check")
        schema = self.db.one("SELECT value FROM meta WHERE key='schema_version'")
        tables = self.db.all("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        result = {
            "integrity": next(iter(integrity.values())) if integrity else "unknown",
            "schema_version": schema["value"] if schema else "unknown",
            "table_count": len(tables),
            "database_path": str(Path(self.db.path).resolve()),
        }
        result["passed"] = result["integrity"] == "ok"
        return result

    def create_backup(self, *, backup_type: str = "pre_migration", include_paths: Sequence[str | Path] = (), created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != "BACKUP 1859 ERSTELLEN":
            raise PermissionError("explicit approval required")
        if backup_type not in {"manual", "pre_migration", "scheduled", "pre_restore"}:
            raise ValueError("unsupported backup type")
        pre = self.preflight()
        if not pre["passed"]:
            raise RuntimeError("database integrity check failed")
        backup_id = new_id("bak1859")
        work = Path(tempfile.mkdtemp(prefix=f"{backup_id}_", dir=self.backup_dir))
        try:
            db_copy = work / "eagleeye.sqlite3"
            target = sqlite3.connect(str(db_copy))
            try:
                self.db.conn.backup(target)
            finally:
                target.close()
            files = [{"relative_path":"eagleeye.sqlite3","path":db_copy,"classification":"restricted"}]
            for item in include_paths:
                src = Path(item).resolve()
                if not src.exists() or not src.is_file():
                    continue
                dst = work / "files" / src.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                files.append({"relative_path":str(dst.relative_to(work)),"path":dst,"classification":"restricted"})
            manifest_files = [{"relative_path":f["relative_path"],"size_bytes":f["path"].stat().st_size,"sha256":_file_hash(f["path"]),"classification":f["classification"]} for f in files]
            manifest = {"backup_id":backup_id,"build":self.BUILD,"backup_type":backup_type,"created_at":now_ts(),"created_by":created_by,"source_schema":pre["schema_version"],"files":manifest_files,"integrity_preflight":pre,"encrypted":False,"limitations":["backup_archive_requires_os_level_access_protection","restore_requires_explicit_confirmation"]}
            manifest_path = work / "manifest.json"
            manifest_path.write_text(_canon(manifest), encoding="utf-8")
            archive = self.backup_dir / f"{backup_id}.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for p in work.rglob("*"):
                    if p.is_file():
                        zf.write(p, p.relative_to(work))
            db_sha = next(x["sha256"] for x in manifest_files if x["relative_path"] == "eagleeye.sqlite3")
            manifest_sha = _file_hash(manifest_path)
            self.db.execute("INSERT INTO backup_sets_1859 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(backup_id,backup_type,"verified",manifest["created_at"],created_by,pre["schema_version"],self.BUILD,str(archive),db_sha,manifest_sha,len(manifest_files),0,"local encrypted filesystem recommended"))
            for f in manifest_files:
                self.db.execute("INSERT INTO backup_files_1859 VALUES(?,?,?,?,?)",(backup_id,f["relative_path"],f["size_bytes"],f["sha256"],f["classification"]))
            self._event("backup_created", backup_id, {"archive":str(archive),"file_count":len(manifest_files)})
            return {"backup_id":backup_id,"status":"verified","archive":str(archive),"file_count":len(manifest_files),"database_sha256":db_sha,"automatic_restore":False}
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def verify_backup(self, backup_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM backup_sets_1859 WHERE backup_id=?", (backup_id,))
        if not row:
            raise KeyError("backup not found")
        archive = Path(row["backup_path"])
        if not archive.exists():
            return {"backup_id":backup_id,"valid":False,"errors":["archive_missing"]}
        errors=[]
        with tempfile.TemporaryDirectory(prefix="verify1859_") as td:
            with zipfile.ZipFile(archive) as zf:
                bad = zf.testzip()
                if bad: errors.append(f"zip_crc:{bad}")
                zf.extractall(td)
            root=Path(td)
            manifest_path=root/"manifest.json"
            if not manifest_path.exists(): errors.append("manifest_missing")
            else:
                manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
                for f in manifest.get("files",[]):
                    p=root/f["relative_path"]
                    if not p.exists(): errors.append(f"file_missing:{f['relative_path']}")
                    elif _file_hash(p)!=f["sha256"]: errors.append(f"hash_mismatch:{f['relative_path']}")
                dbp=root/"eagleeye.sqlite3"
                if dbp.exists():
                    con=sqlite3.connect(str(dbp)); chk=con.execute("PRAGMA integrity_check").fetchone()[0]; con.close()
                    if chk!="ok": errors.append("database_integrity_failed")
        return {"backup_id":backup_id,"valid":not errors,"errors":errors,"human_restore_approval_required":True}

    def migration_guard(self, *, target_schema: str, migration_callable: Any, approved_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"MIGRATION 1859 {target_schema} AUSFUEHREN":
            raise PermissionError("explicit approval required")
        pre=self.preflight()
        backup=self.create_backup(backup_type="pre_migration",created_by=approved_by,confirmation="BACKUP 1859 ERSTELLEN")
        migration_id=new_id("mig1859"); started=now_ts()
        self.db.execute("INSERT INTO migration_runs_1859 VALUES(?,?,?,?,?,?,?,?,?,?,?)",(migration_id,pre["schema_version"],target_schema,"running",backup["backup_id"],started,None,"",dumps(pre),dumps({}),_hash({"migration_id":migration_id,"started":started})))
        try:
            migration_callable(self.db)
            post=self.preflight()
            if not post["passed"] or post["schema_version"]!=target_schema:
                raise RuntimeError("post-migration validation failed")
            status="candidate_pass"
            self.db.execute("UPDATE migration_runs_1859 SET status=?,finished_at=?,postflight_json=?,payload_sha256=? WHERE migration_id=?",(status,now_ts(),dumps(post),_hash(post),migration_id))
            self._event("migration_completed",migration_id,{"target_schema":target_schema,"backup_id":backup["backup_id"]})
            return {"migration_id":migration_id,"status":status,"backup_id":backup["backup_id"],"preflight":pre,"postflight":post,"automatic_delete_backup":False}
        except Exception as exc:
            self.db.execute("UPDATE migration_runs_1859 SET status='failed',finished_at=?,error_text=? WHERE migration_id=?",(now_ts(),str(exc),migration_id))
            self._event("migration_failed",migration_id,{"error":str(exc),"backup_id":backup["backup_id"]})
            return {"migration_id":migration_id,"status":"failed","backup_id":backup["backup_id"],"error":str(exc),"restore_available":True,"automatic_restore":False}

    def stage_restore(self, *, backup_id: str, requested_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"RESTORE 1859 {backup_id} VORBEREITEN":
            raise PermissionError("explicit approval required")
        verification=self.verify_backup(backup_id)
        if not verification["valid"]:
            raise RuntimeError("backup verification failed")
        row=self.db.one("SELECT * FROM backup_sets_1859 WHERE backup_id=?",(backup_id,))
        restore_id=new_id("restore1859")
        staging=self.backup_dir/"restore_staging"/restore_id
        staging.mkdir(parents=True,exist_ok=False)
        with zipfile.ZipFile(row["backup_path"]) as zf: zf.extractall(staging)
        staged_db=staging/"eagleeye.sqlite3"
        con=sqlite3.connect(str(staged_db)); integrity=con.execute("PRAGMA integrity_check").fetchone()[0]; con.close()
        details={"backup_valid":True,"staged_integrity":integrity,"database_sha256":_file_hash(staged_db)}
        self.db.execute("INSERT INTO restore_runs_1859 VALUES(?,?,?,?,?,?,?,?,?,?,?)",(restore_id,backup_id,"staged",requested_by,now_ts(),None,str(staging),str(Path(self.db.path).resolve()),dumps(details),"",_hash(details)))
        self._event("restore_staged",restore_id,details)
        return {"restore_id":restore_id,"status":"staged","staging_path":str(staging),"verification":details,"application_restart_required":True,"automatic_swap":False}

    def recovery_dashboard(self) -> dict[str, Any]:
        backups=self.db.one("SELECT COUNT(*) AS n FROM backup_sets_1859")
        failed=self.db.one("SELECT COUNT(*) AS n FROM migration_runs_1859 WHERE status='failed'")
        staged=self.db.one("SELECT COUNT(*) AS n FROM restore_runs_1859 WHERE status='staged'")
        return {"build":self.BUILD,"backups":backups["n"],"failed_migrations":failed["n"],"staged_restores":staged["n"],"automatic_restore":False,"human_approval_required":True}

    def _event(self,event_type:str,object_ref:str,payload:Mapping[str,Any])->None:
        prev=self.db.one("SELECT event_sha256 FROM recovery_events_1859 ORDER BY created_at DESC,event_id DESC LIMIT 1")
        prev_sha=prev["event_sha256"] if prev else "0"*64
        eid=new_id("evt1859"); created=now_ts(); digest=_hash({"event_id":eid,"event_type":event_type,"object_ref":object_ref,"payload":payload,"created_at":created,"actor":self.actor,"prev":prev_sha})
        self.db.execute("INSERT INTO recovery_events_1859 VALUES(?,?,?,?,?,?,?,?)",(eid,event_type,object_ref,dumps(payload),created,self.actor,prev_sha,digest))
