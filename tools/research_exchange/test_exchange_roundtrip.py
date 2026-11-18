"""End-to-end synthetic exchange against a disposable local Git remote."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from bridge import stage
from outbound import publish
from signed_approval import approve_signed, CONFIRMATION
from staging_db import StagingDB
from review import review


class ExchangeRoundtripTests(unittest.TestCase):
    def test_request_response_replay_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            inbound = root / "inbound"
            database = root / "staging.sqlite"

            def git(*args):
                return subprocess.run(["git", *map(str, args)], check=True,
                                      capture_output=True, timeout=30).stdout

            git("init", "--bare", remote)
            git("init", seed)
            git("-C", seed, "config", "user.name", "Synthetic Test")
            git("-C", seed, "config", "user.email", "test@localhost")
            git("-C", seed, "commit", "--allow-empty", "-m", "seed")
            git("-C", seed, "push", remote, "HEAD:refs/heads/research-exchange")
            git("init", inbound)

            request = dict(schema=1, id="00000000-0000-4000-8000-000000000010",
                           kind="research_request", classification="public-topic",
                           topic="Synthetic orbital mechanics", summary="Test only",
                           sources=[], synthetic=True)
            raw = json.dumps(request).encode()
            key = b"s" * 32
            receipt = approve_signed(raw, key, "outbound", CONFIRMATION)
            self.assertEqual(publish(raw, receipt, str(remote), key=key)["status"],
                             "published")
            git("-C", seed, "pull", "--ff-only", remote, "research-exchange")
            self.assertEqual((seed / "exchange" / "outbox" /
                              (request["id"] + ".json")).read_bytes(), raw)

            response = dict(request, id="00000000-0000-4000-8000-000000000011",
                            kind="research_result", summary="Synthetic response")
            result = json.dumps(response).encode()
            path = seed / "exchange" / "inbox" / (response["id"] + ".json")
            path.parent.mkdir(parents=True)
            path.write_bytes(result)
            git("-C", seed, "add", "exchange/inbox")
            git("-C", seed, "commit", "-m", "synthetic response")
            git("-C", seed, "push", remote, "HEAD:refs/heads/research-exchange")

            with patch("bridge.REMOTE", str(remote)):
                stage(inbound, root / "unused", database=database)
                stage(inbound, root / "unused", database=database)
                path.write_bytes(result.replace(b"Synthetic response", b"Changed"))
                git("-C", seed, "add", "exchange/inbox")
                git("-C", seed, "commit", "-m", "synthetic conflict")
                git("-C", seed, "push", remote, "HEAD:refs/heads/research-exchange")
                stage(inbound, root / "unused", database=database)

            self.assertEqual(StagingDB(database).read(response["id"]), result)
            detail = review(database, response["id"])
            self.assertEqual(detail["record"], response)
            self.assertEqual([event["status"] for event in detail["audit"]],
                             ["staged", "duplicate", "conflict"])
            self.assertFalse((root / "unused").exists())
            self.assertIsNone(StagingDB(database).read(request["id"]))
