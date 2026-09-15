from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any, Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
class EvidenceChain64Service:
    """Build 64.0 tamper-evident evidence/export chain."""
    def __init__(self, db: Database, audit: AuditService):
        self.db = db; self.audit = audit; self.ensure_schema()
    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS evidence_chain_events_64 (
          chain_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, sequence_no INTEGER NOT NULL,
          source_type TEXT NOT NULL, source_id TEXT NOT NULL, previous_hash TEXT NOT NULL,
          payload_hash TEXT NOT NULL, event_hash TEXT NOT NULL, payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_evidence_chain64_case ON evidence_chain_events_64(case_id, sequence_no);
        """)
        self.db.conn.commit()
    def append_event(self, case_id: str, source_type: str, source_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        last = self.db.one("SELECT * FROM evidence_chain_events_64 WHERE case_id=? ORDER BY sequence_no DESC LIMIT 1", [case_id])
        seq = int(last["sequence_no"] + 1) if last else 1; previous = last.get("event_hash", "") if last else ""
        normalized = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        event_hash = hashlib.sha256(f"{case_id}:{seq}:{previous}:{payload_hash}:{source_type}:{source_id}".encode("utf-8")).hexdigest()
        cid = new_id("chain64")
        self.db.execute("""INSERT INTO evidence_chain_events_64(chain_id,case_id,sequence_no,source_type,source_id,previous_hash,payload_hash,event_hash,payload_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)""", [cid, case_id, seq, source_type, source_id, previous, payload_hash, event_hash, dumps(payload or {}), now_ts()])
        self.audit.log("append", "evidence_chain_64", cid, case_id, {"seq": seq, "event_hash": event_hash})
        return self.get_event(cid)
    def append_file_event(self, case_id: str, path: str | Path, *, source_type: str = "casefile_zip", source_id: str = "") -> Dict[str, Any]:
        fp = Path(path); digest = self._sha_file(fp)
        payload = {"path": str(fp), "sha256": digest, "bytes": fp.stat().st_size if fp.exists() else 0, "recorded_at": now_ts()}
        return self.append_event(case_id, source_type, source_id or fp.name, payload)
    def build_from_audit(self, case_id: str) -> Dict[str, Any]:
        existing = {r["source_id"] for r in self.db.all("SELECT source_id FROM evidence_chain_events_64 WHERE case_id=? AND source_type='audit_event'", [case_id])}
        rows = self.db.all("SELECT * FROM audit_events WHERE case_id=? ORDER BY timestamp,event_id", [case_id]); created = 0
        for row in rows:
            if row["event_id"] in existing: continue
            self.append_event(case_id, "audit_event", row["event_id"], row); created += 1
        verification = self.verify(case_id); verification["created"] = created; return verification
    def verify(self, case_id: str) -> Dict[str, Any]:
        rows = self.db.all("SELECT * FROM evidence_chain_events_64 WHERE case_id=? ORDER BY sequence_no", [case_id])
        previous = ""; problems: List[str] = []
        for row in rows:
            payload = loads(row.get("payload_json", "{}"), {})
            payload_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
            expected = hashlib.sha256(f"{case_id}:{row['sequence_no']}:{previous}:{payload_hash}:{row['source_type']}:{row['source_id']}".encode("utf-8")).hexdigest()
            if row.get("previous_hash", "") != previous: problems.append(f"broken_previous_hash:{row['chain_id']}")
            if row.get("payload_hash") != payload_hash: problems.append(f"payload_hash_mismatch:{row['chain_id']}")
            if row.get("event_hash") != expected: problems.append(f"event_hash_mismatch:{row['chain_id']}")
            previous = row.get("event_hash", "")
        return {"case_id": case_id, "events": len(rows), "valid": not problems, "problems": problems, "chain_tip": previous}
    def get_event(self, chain_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_chain_events_64 WHERE chain_id=?", [chain_id])
        if not row: raise KeyError(chain_id)
        row["payload"] = loads(row.pop("payload_json", "{}"), {}); return row
    def _sha_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
        return h.hexdigest()
