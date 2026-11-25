"""Synthetic integrity and recovery tests for the local HMAC audit ledger."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from audit_chain import AuditLedger


class AuditLedgerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "ledger.sqlite"
        self.key = b"k" * 32
        self.ledger = AuditLedger(self.path, self.key)
        self.ident = "00000000-0000-4000-8000-000000000042"
        self.digest = "f" * 64
        self.commit = "b" * 40

    def _edit(self, sql, args=()):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(sql, args)

    def test_empty_verify_does_not_create_a_db(self):
        self.assertEqual(self.ledger.verify(), [])
        self.assertFalse(self.path.exists())

    def test_complete_chain_and_restart(self):
        self.ledger.append(self.ident, self.digest, "attempt")
        self.ledger.append(self.ident, self.digest, "published", self.commit)
        other = AuditLedger(self.path, self.key)
        events = other.verify()
        self.assertEqual([x["status"] for x in events], ["attempt", "published"])
        self.assertEqual([x["seq"] for x in events], [1, 2])
        self.assertEqual(events[1]["previous_mac"], events[0]["mac"])
        self.assertEqual(events[1]["commit"], self.commit)

    def test_replay_audit_after_crash(self):
        self.ledger.append(self.ident, self.digest, "attempt")
        reopened = AuditLedger(self.path, self.key)
        reopened.append(self.ident, self.digest, "attempt")
        reopened.append(self.ident, self.digest, "duplicate", self.commit)
        self.assertEqual([x["status"] for x in reopened.verify()],
                         ["attempt", "attempt", "duplicate"])

    def test_modification_blocks_future_write(self):
        self.ledger.append(self.ident, self.digest, "attempt")
        self._edit("UPDATE events SET sha256=? WHERE seq=1", ("0" * 64,))
        with self.assertRaisesRegex(ValueError, "integrity violation"):
            self.ledger.verify()
        with self.assertRaisesRegex(ValueError, "integrity violation"):
            self.ledger.append(self.ident, self.digest, "attempt")
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)

    def test_deletion_detected(self):
        self.ledger.append(self.ident, self.digest, "attempt")
        self.ledger.append(self.ident, self.digest, "published", self.commit)
        self._edit("DELETE FROM events WHERE seq=1")
        with self.assertRaisesRegex(ValueError, "integrity violation"):
            self.ledger.verify()

    def test_wrong_key_rejected(self):
        self.ledger.append(self.ident, self.digest, "attempt")
        with self.assertRaisesRegex(ValueError, "integrity violation"):
            AuditLedger(self.path, b"x" * 32).verify()

    def test_invalid_fields_rejected(self):
        cases = [
            ("bad-id", self.digest, "attempt", None),
            (self.ident, "bad", "attempt", None),
            (self.ident, self.digest, "import-private-data", None),
            (self.ident, self.digest, "published", None),
            (self.ident, self.digest, "attempt", self.commit),
        ]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.ledger.append(*args)
        self.assertFalse(self.path.exists())

    def test_ledger_requires_full_key(self):
        with self.assertRaises(ValueError):
            AuditLedger(self.path, b"small")


if __name__ == "__main__":
    unittest.main()
