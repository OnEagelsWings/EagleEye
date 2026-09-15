from __future__ import annotations

from typing import Any, Dict, List
import hashlib
import json

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class AuditHashChainService:
    """Build 51/54 append-only audit hash-chain verifier."""

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS audit_hash_chain_54 (
          hash_event_id TEXT PRIMARY KEY,
          case_id TEXT DEFAULT '',
          source_audit_event_id TEXT NOT NULL,
          sequence_no INTEGER NOT NULL,
          previous_hash TEXT DEFAULT '',
          event_hash TEXT NOT NULL,
          payload_hash TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(source_audit_event_id)
        );
        CREATE INDEX IF NOT EXISTS idx_audithash54_case ON audit_hash_chain_54(case_id, sequence_no);
        ''')
        self.db.conn.commit()

    def build_for_case(self, case_id: str = "") -> Dict[str, Any]:
        if case_id:
            rows = self.db.all("SELECT * FROM audit_events WHERE case_id=? ORDER BY timestamp,event_id", [case_id])
        else:
            rows = self.db.all("SELECT * FROM audit_events ORDER BY timestamp,event_id")
        previous = ""
        created = 0
        for idx, row in enumerate(rows, start=1):
            if self.db.one("SELECT hash_event_id FROM audit_hash_chain_54 WHERE source_audit_event_id=?", [row["event_id"]]):
                last = self.db.one("SELECT event_hash FROM audit_hash_chain_54 WHERE case_id=? ORDER BY sequence_no DESC LIMIT 1", [case_id]) if case_id else self.db.one("SELECT event_hash FROM audit_hash_chain_54 ORDER BY sequence_no DESC LIMIT 1")
                previous = last["event_hash"] if last else previous
                continue
            payload = {k: row.get(k) for k in sorted(row)}
            payload_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            event_hash = hashlib.sha256(f"{previous}:{payload_hash}:{idx}".encode("utf-8")).hexdigest()
            hid = new_id("audhash54")
            self.db.execute('''INSERT INTO audit_hash_chain_54(hash_event_id,case_id,source_audit_event_id,sequence_no,previous_hash,event_hash,payload_hash,created_at)
            VALUES(?,?,?,?,?,?,?,?)''', [hid, row.get("case_id") or "", row["event_id"], idx, previous, event_hash, payload_hash, now_ts()])
            previous = event_hash
            created += 1
        result = self.verify(case_id)
        result["created"] = created
        self.audit.log("build", "audit_hash_chain_54", case_id or "global", case_id or None, {"created": created, "valid": result["valid"]})
        return result

    def verify(self, case_id: str = "") -> Dict[str, Any]:
        if case_id:
            rows = self.db.all("SELECT * FROM audit_hash_chain_54 WHERE case_id=? ORDER BY sequence_no", [case_id])
        else:
            rows = self.db.all("SELECT * FROM audit_hash_chain_54 ORDER BY sequence_no")
        previous = ""
        problems: List[str] = []
        for row in rows:
            if row.get("previous_hash", "") != previous:
                problems.append(f"broken_previous_hash:{row['hash_event_id']}")
            previous = row.get("event_hash", "")
        return {"case_id": case_id, "events": len(rows), "valid": not problems, "problems": problems, "last_hash": previous}
