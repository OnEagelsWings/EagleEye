import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import closing
from staging_db import StagingDB

class StagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "staging.sqlite"
        self.db = StagingDB(self.path)
        self.record = dict(schema=1, id="00000000-0000-4000-8000-000000000001",
                           kind="research_result", classification="public-topic",
                           topic="Synthetic", summary="Test only", sources=[], synthetic=True)
        self.raw = json.dumps(self.record).encode()
        self.commit = "a" * 40

    def test_replay_and_conflict(self):
        self.assertEqual(self.db.stage(self.raw, self.commit), "staged")
        reopened = StagingDB(self.path)
        self.assertEqual(reopened.stage(self.raw, self.commit), "duplicate")
        self.assertEqual(reopened.stage(self.raw, self.commit), "duplicate")
        changed = self.raw.replace(b"Test only", b"Changed")
        self.assertEqual(reopened.stage(changed, self.commit), "conflict")
        self.assertEqual(reopened.read(self.record["id"]), self.raw)
        with closing(reopened.connect()) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM audit").fetchone()[0], 3)

    def test_audit_failure_rolls_back_record(self):
        with closing(self.db.connect()) as db, db:
            db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON audit BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.stage(self.raw, self.commit)
        self.assertIsNone(self.db.read(self.record["id"]))
        with closing(self.db.connect()) as db, db:
            db.execute("DROP TRIGGER fail_audit")
        self.assertEqual(self.db.stage(self.raw, self.commit), "staged")

    def test_detects_tampered_staged_record(self):
        self.assertEqual(self.db.stage(self.raw, self.commit), "staged")
        with closing(self.db.connect()) as db, db:
            db.execute("UPDATE records SET raw=? WHERE id=?",
                       (self.raw.replace(b"Test only", b"Altered"), self.record["id"]))
        with self.assertRaisesRegex(ValueError, "record digest mismatch"):
            self.db.read(self.record["id"])

    def test_detects_tampered_staged_digest(self):
        self.assertEqual(self.db.stage(self.raw, self.commit), "staged")
        with closing(self.db.connect()) as db, db:
            db.execute("UPDATE records SET digest=? WHERE id=?",
                       ("0" * 64, self.record["id"]))
        with self.assertRaisesRegex(ValueError, "record digest mismatch"):
            self.db.read(self.record["id"])

    def test_replay_rejects_tampered_existing_record_without_new_audit(self):
        self.assertEqual(self.db.stage(self.raw, self.commit), "staged")
        with closing(self.db.connect()) as db, db:
            db.execute("UPDATE records SET raw=? WHERE id=?",
                       (self.raw.replace(b"Test only", b"Altered"), self.record["id"]))
        with self.assertRaisesRegex(ValueError, "record digest mismatch"):
            self.db.stage(self.raw, "b" * 40)
        with closing(self.db.connect()) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM audit").fetchone()[0], 1)

    def test_conflict_rejects_tampered_existing_digest(self):
        self.assertEqual(self.db.stage(self.raw, self.commit), "staged")
        with closing(self.db.connect()) as db, db:
            db.execute("UPDATE records SET digest=? WHERE id=?",
                       ("0" * 64, self.record["id"]))
        changed = self.raw.replace(b"Test only", b"Changed")
        with self.assertRaisesRegex(ValueError, "record digest mismatch"):
            self.db.stage(changed, "b" * 40)
        with closing(self.db.connect()) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM audit").fetchone()[0], 1)

    def test_replay_rejects_recomputed_digest_without_matching_staged_audit(self):
        self.assertEqual(self.db.stage(self.raw, self.commit), "staged")
        altered = self.raw.replace(b"Test only", b"Altered")
        import hashlib
        with closing(self.db.connect()) as db, db:
            db.execute("UPDATE records SET raw=?, digest=? WHERE id=?",
                       (altered, hashlib.sha256(altered).hexdigest(), self.record["id"]))
        with self.assertRaisesRegex(ValueError, "staged audit anchor mismatch"):
            self.db.stage(altered, "b" * 40)
        with closing(self.db.connect()) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM audit").fetchone()[0], 1)

    def test_read_rejects_recomputed_digest_without_staged_anchor(self):
        self.assertEqual(self.db.stage(self.raw, self.commit), "staged")
        altered = self.raw.replace(b"Test only", b"Altered")
        import hashlib
        with closing(self.db.connect()) as db, db:
            db.execute("UPDATE records SET raw=?, digest=? WHERE id=?",
                       (altered, hashlib.sha256(altered).hexdigest(), self.record["id"]))
        with self.assertRaisesRegex(ValueError, "staged audit anchor mismatch"):
            self.db.read(self.record["id"])

    def test_read_rejects_missing_staged_anchor(self):
        self.assertEqual(self.db.stage(self.raw, self.commit), "staged")
        with closing(self.db.connect()) as db, db:
            db.execute("DELETE FROM audit WHERE id=? AND status='staged'",
                       (self.record["id"],))
        with self.assertRaisesRegex(ValueError, "staged audit anchor mismatch"):
            self.db.read(self.record["id"])

    def test_invalid_commit(self):
        with self.assertRaises(ValueError):
            self.db.stage(self.raw, "invalid")
        self.assertIsNone(self.db.read(self.record["id"]))

if __name__ == "__main__":
    unittest.main()
