"""Private Git audit-anchor tests using only disposable synthetic local Git repos."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

from audit_anchor import (
    CONFIRMATION, _identity, publish_remote_anchor, verify_remote_anchor
)
from audit_chain import AuditLedger


class AuditAnchorTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.remote = self.root / "remote.git"
        self.work = self.root / "initial"
        self.rootdb = self.root / "audit.sqlite"
        self.key = b"\x27" * 32
        self.audit = AuditLedger(self.rootdb, self.key)
        self.id = "00000000-0000-4000-8000-000000000077"
        self.digest = "a" * 64
        self.git("init", "--bare", self.remote)
        self.git("init", self.work)
        self.git("-C", self.work, "-c", "user.name=Fixture",
                 "-c", "user.email=fixture@localhost",
                 "commit", "--allow-empty", "-m", "synthetic private branch")
        self.git("-C", self.work, "push", self.remote,
                 "HEAD:refs/heads/research-exchange")

    @staticmethod
    def git(*args):
        return subprocess.run(["git", *map(str, args)], capture_output=True,
                              check=True, timeout=45).stdout

    def publish(self, confirmation=CONFIRMATION):
        return publish_remote_anchor(self.audit, confirmation,
                                     remote=str(self.remote))

    def verify(self):
        return verify_remote_anchor(self.audit, remote=str(self.remote))

    def test_independent_checkpoint_and_replay(self):
        self.audit.append(self.id, self.digest, "attempt")
        receipt = self.publish()
        self.assertEqual(receipt["status"], "published")
        self.assertEqual(receipt["sequence"], 1)
        check = self.verify()
        self.assertEqual(check["status"], "verified")
        self.assertEqual(check["latest_anchored_seq"], 1)
        self.assertEqual(check["pending_local_events"], 0)
        self.assertEqual(self.publish()["status"], "duplicate")
        self.audit.append(self.id, self.digest, "published", "b" * 40)
        self.assertEqual(self.verify()["pending_local_events"], 1)
        receipt2 = self.publish()
        self.assertEqual(receipt2["status"], "published")
        self.assertEqual(receipt2["sequence"], 2)
        self.assertEqual(self.verify()["pending_local_events"], 0)
        # The remote contains only public-identifier-free audit head metadata.
        raw = self.git("--git-dir", self.remote, "show",
                       "research-exchange:" + receipt2["path"])
        checkpoint = json.loads(raw)
        self.assertEqual(checkpoint["installation"], _identity(self.key))
        self.assertEqual(checkpoint["head_mac"], self.audit.verify()[1]["mac"])
        self.assertNotIn(self.id.encode(), raw)
        self.assertNotIn(self.key, raw)

    def test_local_tail_deletion_is_detected_against_private_checkpoint(self):
        self.audit.append(self.id, self.digest, "attempt")
        self.audit.append(self.id, self.digest, "published", "b" * 40)
        self.publish()
        # Local HMAC chain alone would accept this prefix after tail deletion.
        with closing(sqlite3.connect(self.rootdb)) as db, db:
            db.execute("DELETE FROM events WHERE seq=2")
        self.assertEqual(len(self.audit.verify()), 1)
        with self.assertRaisesRegex(ValueError, "truncated"):
            self.verify()
        with self.assertRaisesRegex(ValueError, "truncated"):
            self.publish()

    def test_mismatched_previously_anchored_chain_is_rejected(self):
        self.audit.append(self.id, self.digest, "attempt")
        self.publish()
        other_key = b"\x72" * 32
        # An attacker with the wrong key cannot validate this history.
        with self.assertRaisesRegex(ValueError, "integrity"):
            AuditLedger(self.rootdb, other_key).verify()

    def test_approval_and_empty_history_gate(self):
        with self.assertRaisesRegex(ValueError, "Explicit"):
            self.publish("YES")
        with self.assertRaisesRegex(ValueError, "empty"):
            self.publish()
        check = self.verify()
        self.assertEqual(check["status"], "unanchored")
        self.assertEqual(check["latest_anchored_seq"], 0)
        # No outgoing Git path was added by any refused action.
        tree = self.git("--git-dir", self.remote, "ls-tree", "-r",
                        "--name-only", "research-exchange")
        self.assertNotIn(b"audit-anchors", tree)


if __name__ == "__main__":
    unittest.main()
