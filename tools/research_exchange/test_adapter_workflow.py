"""Synthetic adapter-to-staging-to-approval integration regression."""
import hashlib
import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from bridge import validate
from staging_db import StagingDB
from signed_approval import approve_signed, verify_signed, CONFIRMATION
from outbound import publish
from worldbank_adapter import adapt
from test_worldbank_adapter import page, row


class AdapterWorkflowTests(unittest.TestCase):
    def test_stage_replay_and_explicit_approval(self):
        raw = adapt(page(row()), synthetic=True)
        ident = validate(raw)["id"]
        key = bytes(range(32))  # synthetic test key only
        with TemporaryDirectory() as directory:
            path = Path(directory) / "stage.sqlite"
            store = StagingDB(path)
            self.assertEqual(store.stage(raw, "a" * 40), "staged")
            self.assertEqual(store.stage(raw, "a" * 40), "duplicate")
            restored = StagingDB(path).read(ident)
            self.assertEqual(restored, raw)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute(
                    "SELECT digest, status FROM audit ORDER BY seq"
                ).fetchall(), [(hashlib.sha256(raw).hexdigest(), "staged"),
                               (hashlib.sha256(raw).hexdigest(), "duplicate")])
            with self.assertRaises(ValueError):
                approve_signed(restored, key, "outbound", "")
            with patch("outbound.subprocess.run") as run:
                with self.assertRaises(ValueError):
                    publish(restored, "", key=key)
                run.assert_not_called()
            receipt = approve_signed(restored, key, "outbound", CONFIRMATION)
            self.assertTrue(verify_signed(restored, key, "outbound", receipt))
            self.assertFalse(verify_signed(restored, key, "inbound", receipt))
            changed = validate(restored)
            changed["summary"] += "\\nSynthetic modification"
            changed_raw = json.dumps(changed).encode()
            self.assertEqual(store.stage(changed_raw, "b" * 40), "conflict")
            self.assertEqual(store.read(ident), raw)
            self.assertFalse(verify_signed(changed_raw, key, "outbound", receipt))


if __name__ == "__main__":
    unittest.main()
