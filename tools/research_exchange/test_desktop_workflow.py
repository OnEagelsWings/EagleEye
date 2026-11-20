"""Synthetic headless tests for manual desktop controls and local Git roundtrip."""
import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from bridge import validate
from desktop_workflow import DesktopWorkflow
from outbound import publish as git_publish
from signed_approval import CONFIRMATION, verify_signed
from staging_db import StagingDB
from audit_chain import AuditLedger


class DesktopWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for relative in ("workspace/outbox", "workspace/inbox",
                         "workspace/git", "workspace/audit", "secrets"):
            (self.root / relative).mkdir(parents=True)
        self.workspace = DesktopWorkflow(self.root)
        self.key = b"\x19" * 32

    def draft(self, *, synthetic=True):
        return self.workspace.create_draft(
            "Synthetic astronomical history",
            "Synthetic, not for evidence and contains no people or secrets",
            synthetic=synthetic)

    def test_draft_preview_preserves_schema(self):
        name = self.draft()
        value = self.workspace.outgoing_detail(name)
        self.assertEqual(value["record"]["classification"], "public-topic")
        self.assertEqual(value["record"]["kind"], "research_request")
        self.assertTrue(value["record"]["synthetic"])
        self.assertEqual(len(value["sha256"]), 64)
        self.assertEqual(self.workspace.list_outbound(), [name])
        self.assertEqual(validate((self.workspace.outbox / name).read_bytes())["id"],
                         name[:-5])

    def test_invalid_drafts_leave_no_files(self):
        for topic, summary, source in (
            ("", "text", []),
            ("Synthetic", "", []),
            ("Synthetic", "text", [{"title": "Bad URL", "url": "http://example.org/"}]),
        ):
            with self.subTest(topic=topic, summary=summary, source=source):
                with self.assertRaises(ValueError):
                    self.workspace.create_draft(topic, summary, sources=source)
        self.assertEqual(self.workspace.list_outbound(), [])

    def test_reject_outside_path_and_wrong_id(self):
        name = self.draft()
        with self.assertRaises(ValueError):
            self.workspace.outgoing_detail("../" + name)
        with self.assertRaises(ValueError):
            self.workspace.outgoing_detail("bad-name.json")
        data = self.workspace.outbox / name
        other = self.workspace.outbox / ("0" * 8 + "-0000-4000-8000-000000000019.json")
        data.rename(other)
        with self.assertRaises(ValueError):
            self.workspace.outgoing_detail(other.name)

    def test_outgoing_hardlink_rejected(self):
        name = self.draft()
        os.link(self.workspace.outbox / name, self.workspace.outbox / "alias")
        with self.assertRaises(ValueError):
            self.workspace.outgoing_detail(name)

    def test_no_signature_no_publish(self):
        name = self.draft()
        with patch("desktop_workflow.read_key", return_value=self.key), \
             patch("desktop_workflow.publish") as publisher:
            with self.assertRaisesRegex(ValueError, "Approval"):
                self.workspace.publish_outgoing(name, "wrong")
            publisher.assert_not_called()
            self.assertFalse(self.workspace.audit.exists())

    def test_sign_requires_exact_confirmation_and_detects_edits(self):
        name = self.draft()
        with patch("desktop_workflow.read_key", return_value=self.key), \
             patch("desktop_workflow.publish") as publisher:
            with self.assertRaisesRegex(ValueError, "explicit approval"):
                self.workspace.sign_outgoing(name, "YES")
            receipt, original_digest = self.workspace.sign_outgoing(name, CONFIRMATION)
            self.assertEqual(len(original_digest), 64)
            path = self.workspace.outbox / name
            d = json.loads(path.read_text(encoding="utf-8"))
            d["summary"] = "Edited after review"
            path.write_text(json.dumps(d), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Approval"):
                self.workspace.publish_outgoing(name, receipt)
            publisher.assert_not_called()
            self.assertFalse(self.workspace.audit.exists())

    def test_failed_publish_records_attempt_and_error_for_retry(self):
        name = self.draft()
        with patch("desktop_workflow.read_key", return_value=self.key), \
             patch("desktop_workflow.publish", side_effect=RuntimeError("offline")):
            receipt, digest = self.workspace.sign_outgoing(name, CONFIRMATION)
            with self.assertRaisesRegex(RuntimeError, "offline"):
                self.workspace.publish_outgoing(name, receipt)
            self.assertEqual([x["status"] for x in self.workspace.audit_events()],
                             ["attempt", "error"])
            self.assertEqual(self.workspace.audit_events()[0]["sha256"], digest)

    def test_corrupted_audit_blocks_publish_before_network(self):
        name = self.draft()
        AuditLedger(self.workspace.audit, self.key).append(
            name[:-5], self.workspace.outgoing_detail(name)["sha256"], "attempt")
        with closing(sqlite3.connect(self.workspace.audit)) as con, con:
            con.execute("UPDATE events SET sha256=? WHERE seq=1", ("0" * 64,))
        with patch("desktop_workflow.read_key", return_value=self.key), \
             patch("desktop_workflow.publish") as publisher:
            receipt, _ = self.workspace.sign_outgoing(name, CONFIRMATION)
            with self.assertRaisesRegex(ValueError, "integrity violation"):
                self.workspace.publish_outgoing(name, receipt)
            publisher.assert_not_called()

    def test_manual_inbound_decisions_are_local_and_signed(self):
        record = {
            "schema": 1, "id": "00000000-0000-4000-8000-000000000093",
            "kind": "research_result", "classification": "public-topic",
            "topic": "Synthetic algebra", "summary": "Test only",
            "sources": [], "synthetic": True,
        }
        raw = json.dumps(record).encode()
        StagingDB(self.workspace.database).stage(raw, "c" * 40)
        with patch("desktop_workflow.read_key", return_value=self.key):
            with self.assertRaises(ValueError):
                self.workspace.review_inbound(record["id"], "approved", "YES")
            with self.assertRaises(ValueError):
                self.workspace.review_inbound(record["id"], "deferred", CONFIRMATION)
            self.assertFalse(self.workspace.audit.exists())
            accepted = self.workspace.review_inbound(record["id"], "approved", CONFIRMATION)
            self.assertTrue(verify_signed(raw, self.key, "inbound", accepted["receipt"]))
            deferred = self.workspace.review_inbound(record["id"], "deferred", "DEFER PUBLIC RESEARCH")
            self.assertIsNone(deferred["receipt"])
            self.assertEqual([x["status"] for x in self.workspace.audit_events()],
                             ["inbound-approved", "inbound-deferred"])
            self.assertEqual(len(self.workspace.list_outbound()), 0)

    def test_reading_staged_record_validates_original_anchor(self):
        item = {
            "schema": 1, "id": "00000000-0000-4000-8000-000000000091",
            "kind": "research_result", "classification": "public-topic",
            "topic": "Synthetic geology", "summary": "Test only",
            "sources": [], "synthetic": True
        }
        raw = json.dumps(item).encode()
        db = StagingDB(self.workspace.database)
        db.stage(raw, "a" * 40)
        self.assertEqual(self.workspace.list_inbound()[0]["id"], item["id"])
        self.assertEqual(self.workspace.inbound_detail(item["id"])["record"], item)
        with closing(sqlite3.connect(self.workspace.database)) as con, con:
            con.execute("DELETE FROM audit WHERE id=?", (item["id"],))
        with self.assertRaisesRegex(ValueError, "anchor mismatch"):
            self.workspace.inbound_detail(item["id"])

    def test_publish_and_replay_against_disposable_local_git(self):
        def git(*arguments):
            return subprocess.run(["git", *map(str, arguments)], check=True,
                                  capture_output=True, timeout=30).stdout

        name = self.draft()
        bare = self.root / "remote.git"
        seed = self.root / "seed"
        git("init", "--bare", bare)
        git("init", seed)
        git("-C", seed, "-c", "user.name=Synthetic Test",
            "-c", "user.email=test@localhost",
            "commit", "--allow-empty", "-m", "seed")
        git("-C", seed, "push", bare, "HEAD:refs/heads/research-exchange")
        def local_publish(raw, receipt, *, key):
            return git_publish(raw, receipt, str(bare), key=key)

        with patch("desktop_workflow.read_key", return_value=self.key), \
             patch("desktop_workflow.publish", side_effect=local_publish):
            receipt, digest = self.workspace.sign_outgoing(name, CONFIRMATION)
            event = self.workspace.publish_outgoing(name, receipt)
            self.assertEqual(event["status"], "published")
            self.assertEqual(event["sha256"], digest)
            self.assertEqual(
                git("--git-dir", bare, "show",
                    "research-exchange:exchange/outbox/" + name),
                (self.workspace.outbox / name).read_bytes())
            again = self.workspace.publish_outgoing(name, receipt)
            self.assertEqual(again["status"], "duplicate")
        with patch("desktop_workflow.read_key", return_value=self.key):
            events = self.workspace.audit_events()
        self.assertEqual([x["status"] for x in events],
                         ["attempt", "published", "attempt", "duplicate"])
        self.assertEqual([x["seq"] for x in events], [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
