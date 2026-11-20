"""Synthetic proof that inbound Git scanning reads only explicitly selected IDs."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from bridge import stage
from staging_db import StagingDB


class AllowlistTests(unittest.TestCase):
    def test_inbound_allowlist_does_not_read_other_blobs(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            bare, seed, client = (base / item for item in
                                  ("bare.git", "seed", "client"))
            def git(*parts):
                return subprocess.run(["git", *map(str, parts)], check=True,
                                      capture_output=True, timeout=30).stdout
            git("init", "--bare", bare)
            git("init", seed)
            git("-C", seed, "config", "user.email", "test@localhost")
            git("-C", seed, "config", "user.name", "Synthetic Test")
            folder = seed / "exchange" / "inbox"
            folder.mkdir(parents=True)
            ident = "00000000-0000-4000-8000-000000000088"
            other = "00000000-0000-4000-8000-000000000089"
            item = dict(schema=1, id=ident, kind="research_result",
                        classification="public-topic", topic="Synthetic",
                        summary="Isolated", sources=[], synthetic=True)
            (folder / (ident + ".json")).write_text(json.dumps(item), encoding="utf-8")
            # A forbidden unreadable/malformed blob in same Git branch
            # must not be accessed or persisted by a selected-ID import.
            (folder / (other + ".json")).write_bytes(b"\xffPRIVATE-UNREAD")
            git("-C", seed, "add", "exchange/inbox")
            git("-C", seed, "commit", "-m", "synthetic fixtures")
            git("-C", seed, "push", bare, "HEAD:refs/heads/research-exchange")
            git("init", client)
            database = base / "local.sqlite"
            with patch("bridge.REMOTE", str(bare)):
                stage(client, base / "unused", database=database,
                      allowed_ids={ident})
            records = StagingDB(database)
            self.assertEqual(records.read(ident), json.dumps(item).encode())
            self.assertIsNone(records.read(other))
            with patch("bridge.REMOTE", str(bare)), self.assertRaises(ValueError):
                stage(client, base / "unused", database=database,
                      allowed_ids={"bad-id"})


if __name__ == "__main__":
    unittest.main()
