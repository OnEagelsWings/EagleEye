import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from staging_db import StagingDB
from review import review


class ReviewTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "staging #1.sqlite"
        self.db = StagingDB(self.path)
        self.record = dict(schema=1, id="00000000-0000-4000-8000-000000000001",
                           kind="research_result", classification="public-topic",
                           topic="Synthetic", summary="Test only", sources=[], synthetic=True)
        self.raw = json.dumps(self.record).encode()
        self.db.stage(self.raw, "a" * 40)

    def test_list_and_detail(self):
        ident = self.record["id"]
        self.db.stage(self.raw.replace(b"Test only", b"Changed"), "b" * 40)
        detail = review(self.path, ident)
        self.assertEqual(detail["record"], self.record)
        self.assertEqual(review(self.path), [{"id": ident, "sha256": detail["sha256"]}])
        self.assertEqual([e["status"] for e in detail["audit"]], ["staged", "conflict"])
        self.assertEqual(self.db.read(ident), self.raw)

    def test_missing_database_is_not_created(self):
        missing = self.path.with_name("missing.sqlite")
        with self.assertRaises(sqlite3.OperationalError):
            review(missing)
        self.assertFalse(missing.exists())

    def test_tampered_record_rejected(self):
        with closing(self.db.connect()) as db, db:
            db.execute("UPDATE records SET raw=?", (b"{}",))
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            review(self.path, self.record["id"])

    def test_unknown_id(self):
        with self.assertRaisesRegex(ValueError, "unknown"):
            review(self.path, "missing")
