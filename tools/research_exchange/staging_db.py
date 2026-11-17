"""Local public-topic staging. No network, automatic import or approval."""
import hashlib
import sqlite3
from contextlib import closing
from bridge import validate

class StagingDB:
    def __init__(self, path):
        self.path = path
        with closing(self.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY, raw BLOB NOT NULL, digest TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS audit (
                seq INTEGER PRIMARY KEY, id TEXT NOT NULL, digest TEXT NOT NULL,
                source_commit TEXT NOT NULL, status TEXT NOT NULL,
                UNIQUE(id, digest, source_commit, status))""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def stage(self, raw, source_commit):
        record = validate(raw)
        if not isinstance(source_commit, str) or len(source_commit) not in (40, 64) or any(c not in "0123456789abcdef" for c in source_commit):
            raise ValueError("invalid source commit")
        ident = record["id"]
        digest = hashlib.sha256(raw).hexdigest()
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT raw FROM records WHERE id=?", (ident,)).fetchone()
            if old is None:
                db.execute("INSERT INTO records VALUES (?, ?, ?)", (ident, raw, digest))
                status = "staged"
            else:
                status = "duplicate" if old[0] == raw else "conflict"
            db.execute("INSERT OR IGNORE INTO audit(id,digest,source_commit,status) VALUES (?,?,?,?)",
                       (ident, digest, source_commit, status))
        return status

    def read(self, ident):
        with closing(self.connect()) as db:
            row = db.execute("SELECT raw,digest FROM records WHERE id=?", (ident,)).fetchone()
        if row is None:
            return None
        if hashlib.sha256(row[0]).hexdigest() != row[1]:
            raise ValueError("record digest mismatch")
        return row[0]
