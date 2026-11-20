"""HMAC-chained, transactional local audit for public-research exchange only.

Records event metadata (not research content, key material, or personal data).
SQLite FULL transactions support restart and concurrent callers. Verification is
fail-closed for edits, interior row deletion, chain breaks and altered receipts.
Tail truncation cannot be detected without an independently stored trusted
checkpoint; an administrator holding the local key is outside this threat model.
"""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3

DOMAIN = b"eagleeye/research-exchange/audit/v1\x00"
GENESIS = "0" * 64
ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
HEX = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _mac(key, message):
    return hmac.new(key, DOMAIN + _canonical(message), hashlib.sha256).hexdigest()


class AuditLedger:
    def __init__(self, filename, key):
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("expected 32-byte local audit key")
        self.path = Path(filename)
        self.key = key

    def _db(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA journal_mode=DELETE")
        return db

    def _check(self, db):
        rows = db.execute(
            "SELECT seq,stamp,id,sha256,status,commit_sha,previous_mac,mac "
            "FROM events ORDER BY seq"
        ).fetchall()
        previous = GENESIS
        for expected, (seq, stamp, ident, sha, status, commit_sha, parent, signature) in enumerate(rows, 1):
            event = {
                "seq": seq, "stamp": stamp, "id": ident, "sha256": sha,
                "status": status, "commit": commit_sha, "previous_mac": parent
            }
            if seq != expected or parent != previous or not hmac.compare_digest(
                _mac(self.key, event), signature
            ):
                raise ValueError("audit integrity violation")
            previous = signature
        return rows

    def append(self, ident, sha256, status, commit=None):
        if not isinstance(ident, str) or not ID.fullmatch(ident):
            raise ValueError("invalid audit record ID")
        if not isinstance(sha256, str) or not HEX.fullmatch(sha256):
            raise ValueError("invalid audit digest")
        if status not in {"attempt", "published", "duplicate", "error",
                          "inbound-approved", "inbound-deferred"}:
            raise ValueError("invalid audit status")
        if commit is not None and (not isinstance(commit, str) or not COMMIT.fullmatch(commit)):
            raise ValueError("invalid audit commit")
        if status not in {"published", "duplicate"} and commit is not None:
            raise ValueError("unexpected audit commit")
        if status in {"published", "duplicate"} and commit is None:
            raise ValueError("missing audit commit")
        if not self.path.parent.is_dir():
            raise ValueError("audit directory missing")
        with closing(self._db()) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS events("
                       "seq INTEGER PRIMARY KEY, stamp TEXT NOT NULL, id TEXT NOT NULL, "
                       "sha256 TEXT NOT NULL, status TEXT NOT NULL, commit_sha TEXT, "
                       "previous_mac TEXT NOT NULL, mac TEXT NOT NULL)")
            entries = self._check(db)
            sequence = len(entries) + 1
            event = {
                "seq": sequence,
                "stamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "id": ident, "sha256": sha256, "status": status,
                "commit": commit, "previous_mac": entries[-1][-1] if entries else GENESIS,
            }
            signature = _mac(self.key, event)
            db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?)",
                       (event["seq"], event["stamp"], event["id"], event["sha256"],
                        event["status"], event["commit"], event["previous_mac"], signature))
            db.commit()
            return dict(event, mac=signature)

    def verify(self):
        if not self.path.is_file():
            return []
        # Read-only connection; opening a missing DB must not create one.
        uri = self.path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=15)) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            return [
                {"seq": seq, "stamp": stamp, "id": ident, "sha256": sha,
                 "status": status, "commit": commit_sha,
                 "previous_mac": parent, "mac": signature}
                for seq, stamp, ident, sha, status, commit_sha, parent, signature
                in self._check(db)
            ]
