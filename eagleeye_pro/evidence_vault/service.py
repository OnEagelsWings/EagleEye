from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json
import shutil

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security_kernel.policy import classify_sensitivity


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class EvidenceVaultService:
    """Build 50 evidence vault with chain-of-custody metadata.

    The vault stores case artifacts outside the release folder and keeps original,
    reviewed and redacted material separated. It does not decide truth; it preserves
    and indexes material that has been collected lawfully from public or case-provided sources.
    """

    def __init__(self, db: Database, audit: AuditService, vault_root: str | Path):
        self.db = db
        self.audit = audit
        self.vault_root = Path(vault_root)
        self.vault_root.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS evidence_vault_artifacts_50 (
          artifact_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          artifact_type TEXT NOT NULL,
          title TEXT NOT NULL,
          source_url TEXT DEFAULT '',
          source_type TEXT DEFAULT '',
          document_date TEXT DEFAULT '',
          stored_path TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          size_bytes INTEGER DEFAULT 0,
          classification TEXT DEFAULT 'normal',
          sensitivity_json TEXT NOT NULL,
          custody_status TEXT DEFAULT 'original_preserved',
          public_access_proof TEXT DEFAULT '',
          review_status TEXT DEFAULT 'needs_review',
          redaction_status TEXT DEFAULT 'not_redacted',
          linked_object_type TEXT DEFAULT '',
          linked_object_id TEXT DEFAULT '',
          notes TEXT DEFAULT '',
          created_at TEXT NOT NULL,
          created_by TEXT DEFAULT 'local-analyst',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS evidence_chain_events_50 (
          chain_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          artifact_id TEXT NOT NULL,
          event_type TEXT NOT NULL,
          actor TEXT DEFAULT 'local-analyst',
          event_hash TEXT NOT NULL,
          previous_event_hash TEXT DEFAULT '',
          details_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(artifact_id) REFERENCES evidence_vault_artifacts_50(artifact_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_ev50_case ON evidence_vault_artifacts_50(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_ev50_chain ON evidence_chain_events_50(artifact_id, created_at);
        ''')
        self.db.conn.commit()

    def _case_dir(self, case_id: str, area: str = "original") -> Path:
        out = self.vault_root / case_id / area
        out.mkdir(parents=True, exist_ok=True)
        return out

    def _last_chain_hash(self, artifact_id: str) -> str:
        row = self.db.one("SELECT event_hash FROM evidence_chain_events_50 WHERE artifact_id=? ORDER BY created_at DESC LIMIT 1", [artifact_id])
        return row["event_hash"] if row else ""

    def _chain_event(self, case_id: str, artifact_id: str, event_type: str, details: Dict[str, Any], actor: str = "local-analyst") -> Dict[str, Any]:
        previous = self._last_chain_hash(artifact_id)
        payload = {"case_id": case_id, "artifact_id": artifact_id, "event_type": event_type, "actor": actor, "details": details, "previous": previous, "created_at": now_ts()}
        event_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        chain_id = new_id("chain50")
        self.db.execute('''INSERT INTO evidence_chain_events_50(chain_id,case_id,artifact_id,event_type,actor,event_hash,previous_event_hash,details_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?)''', [chain_id, case_id, artifact_id, event_type, actor, event_hash, previous, dumps(details), payload["created_at"]])
        self.audit.log("chain_event", "evidence_vault_artifact_50", artifact_id, case_id, {"event_type": event_type, "event_hash": event_hash})
        return {"chain_id": chain_id, "event_hash": event_hash, "previous_event_hash": previous, "event_type": event_type}

    def ingest_text_artifact(self, case_id: str, title: str, content: str, *, source_url: str = "", source_type: str = "public_document", document_date: str = "", classification: str = "normal", public_access_proof: str = "", linked_object_type: str = "", linked_object_id: str = "", notes: str = "", actor: str = "local-analyst") -> Dict[str, Any]:
        if not title.strip():
            raise ValueError("Artifact title is required.")
        artifact_id = new_id("art50")
        raw = (content or "").encode("utf-8", errors="ignore")
        sha = _sha256_bytes(raw)
        path = self._case_dir(case_id, "original") / f"{artifact_id}.txt"
        path.write_bytes(raw)
        sensitivity = classify_sensitivity(" ".join([title, content, source_url, notes]))
        self.db.execute('''INSERT INTO evidence_vault_artifacts_50(artifact_id,case_id,artifact_type,title,source_url,source_type,document_date,stored_path,sha256,size_bytes,classification,sensitivity_json,custody_status,public_access_proof,review_status,redaction_status,linked_object_type,linked_object_id,notes,created_at,created_by)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [artifact_id, case_id, "text", title.strip(), source_url, source_type, document_date, str(path), sha, len(raw), classification, dumps(sensitivity), "original_preserved", public_access_proof, "needs_review", "not_redacted", linked_object_type, linked_object_id, notes, now_ts(), actor])
        first = self._chain_event(case_id, artifact_id, "ingest_text", {"sha256": sha, "source_url": source_url, "size_bytes": len(raw)}, actor)
        result = self.get_artifact(artifact_id)
        result["chain_event"] = first
        return result

    def ingest_file_artifact(self, case_id: str, path: str | Path, *, title: str = "", source_url: str = "", source_type: str = "public_document", document_date: str = "", classification: str = "normal", public_access_proof: str = "", notes: str = "", actor: str = "local-analyst") -> Dict[str, Any]:
        src = Path(path)
        if not src.exists() or not src.is_file():
            raise FileNotFoundError(str(src))
        artifact_id = new_id("art50")
        name = title.strip() or src.name
        dst = self._case_dir(case_id, "original") / f"{artifact_id}{src.suffix or '.bin'}"
        shutil.copy2(src, dst)
        sha = _sha256_file(dst)
        size = dst.stat().st_size
        preview = name + " " + source_url + " " + notes
        sensitivity = classify_sensitivity(preview)
        self.db.execute('''INSERT INTO evidence_vault_artifacts_50(artifact_id,case_id,artifact_type,title,source_url,source_type,document_date,stored_path,sha256,size_bytes,classification,sensitivity_json,custody_status,public_access_proof,review_status,redaction_status,notes,created_at,created_by)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [artifact_id, case_id, "file", name, source_url, source_type, document_date, str(dst), sha, size, classification, dumps(sensitivity), "original_preserved", public_access_proof, "needs_review", "not_redacted", notes, now_ts(), actor])
        self._chain_event(case_id, artifact_id, "ingest_file", {"sha256": sha, "source_path": str(src), "size_bytes": size}, actor)
        return self.get_artifact(artifact_id)

    def update_review_status(self, artifact_id: str, review_status: str, reason: str, actor: str = "local-analyst") -> Dict[str, Any]:
        allowed = {"needs_review", "candidate", "evidence", "counter_evidence", "discarded", "needs_second_source"}
        if review_status not in allowed:
            raise ValueError(f"Invalid review_status: {review_status}")
        item = self.get_artifact(artifact_id)
        self.db.execute("UPDATE evidence_vault_artifacts_50 SET review_status=? WHERE artifact_id=?", [review_status, artifact_id])
        self._chain_event(item["case_id"], artifact_id, "review_status", {"review_status": review_status, "reason": reason}, actor)
        return self.get_artifact(artifact_id)

    def create_redacted_text(self, artifact_id: str, redacted_content: str, reason: str, actor: str = "local-analyst") -> Dict[str, Any]:
        item = self.get_artifact(artifact_id)
        redacted_dir = self._case_dir(item["case_id"], "redacted")
        path = redacted_dir / f"{artifact_id}_redacted.txt"
        raw = (redacted_content or "").encode("utf-8", errors="ignore")
        path.write_bytes(raw)
        sha = _sha256_bytes(raw)
        self.db.execute("UPDATE evidence_vault_artifacts_50 SET redaction_status=?, custody_status=? WHERE artifact_id=?", ["redacted_version_created", "original_and_redacted_preserved", artifact_id])
        self._chain_event(item["case_id"], artifact_id, "redacted_version", {"redacted_path": str(path), "redacted_sha256": sha, "reason": reason}, actor)
        result = self.get_artifact(artifact_id)
        result["redacted_path"] = str(path)
        result["redacted_sha256"] = sha
        return result

    def get_artifact(self, artifact_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_vault_artifacts_50 WHERE artifact_id=?", [artifact_id])
        if not row:
            raise KeyError(artifact_id)
        row["sensitivity"] = loads(row.pop("sensitivity_json", "{}"), {})
        return row

    def list_artifacts(self, case_id: str, review_status: str | None = None, limit: int = 200) -> List[Dict[str, Any]]:
        if review_status:
            rows = self.db.all("SELECT * FROM evidence_vault_artifacts_50 WHERE case_id=? AND review_status=? ORDER BY created_at DESC LIMIT ?", [case_id, review_status, limit])
        else:
            rows = self.db.all("SELECT * FROM evidence_vault_artifacts_50 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", [case_id, limit])
        out = []
        for row in rows:
            row["sensitivity"] = loads(row.pop("sensitivity_json", "{}"), {})
            out.append(row)
        return out

    def chain_for_artifact(self, artifact_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM evidence_chain_events_50 WHERE artifact_id=? ORDER BY created_at ASC", [artifact_id])
        for row in rows:
            row["details"] = loads(row.pop("details_json", "{}"), {})
        return rows

    def verify_chain(self, artifact_id: str) -> Dict[str, Any]:
        rows = self.chain_for_artifact(artifact_id)
        previous = ""
        problems: List[str] = []
        for row in rows:
            if row.get("previous_event_hash", "") != previous:
                problems.append(f"broken_previous_hash:{row['chain_id']}")
            previous = row.get("event_hash", "")
        return {"artifact_id": artifact_id, "events": len(rows), "valid": not problems, "problems": problems, "last_event_hash": previous}
