import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from outbound import main
from approval import approve
from signed_approval import approve_signed
from outbound import publish

class OutboundTests(unittest.TestCase):
    def test_cli_rejects_unsafe_key_before_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            record, receipt, audit, key = [root / name for name in ("record", "receipt", "audit", "key")]
            record.write_bytes(b"synthetic")
            receipt.write_text("synthetic", encoding="utf-8")
            with patch("sys.argv", ["outbound", str(record), str(receipt), str(audit), "--key-file", str(key)]), patch("outbound.read_key", side_effect=ValueError("unsafe key")) as reader, patch("outbound.publish") as publisher:
                with self.assertRaisesRegex(ValueError, "unsafe key"):
                    main()
                reader.assert_called_once_with(key)
                publisher.assert_not_called()
            self.assertFalse(audit.exists())

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            def git(*args):
                return subprocess.run(["git", *map(str,args)], check=True, capture_output=True).stdout
            git("init","--bare",remote)
            git("init",seed)
            git("-C",seed,"-c","user.name=Test","-c","user.email=test@localhost","commit","--allow-empty","-m","seed")
            git("-C",seed,"push",remote,"HEAD:refs/heads/research-exchange")
            record = dict(schema=1,id="00000000-0000-4000-8000-000000000002",kind="research_result",classification="public-topic",topic="Synthetic",summary="Test only",sources=[],synthetic=True)
            raw = json.dumps(record).encode()
            key = b"\x01" * 32  # synthetic test key
            receipt = approve_signed(raw,key,"outbound","APPROVE PUBLIC RESEARCH")
            with self.assertRaises(ValueError):
                publish(raw,"invalid",str(remote),key=key)
            with self.assertRaises(ValueError):
                publish(raw,approve(raw,"APPROVE PUBLIC RESEARCH"),str(remote),key=key)
            with self.assertRaises(ValueError):
                publish(raw,receipt,str(remote),key=b"\x02"*32)
            with self.assertRaises(ValueError):
                publish(raw,approve_signed(raw,key,"inbound","APPROVE PUBLIC RESEARCH"),str(remote),key=key)
            with self.assertRaises(ValueError):
                publish(raw+b" ",receipt,str(remote),key=key)
            self.assertEqual(git("--git-dir",remote,"ls-tree","research-exchange"),b"")
            self.assertEqual(publish(raw,receipt,str(remote),key=key)["status"],"published")
            self.assertEqual(publish(raw,receipt,str(remote),key=key)["status"],"duplicate")
            path = "exchange/outbox/" + record["id"] + ".json"
            self.assertEqual(git("--git-dir",remote,"show","research-exchange:"+path),raw)
            changed = raw + b" "
            with self.assertRaises(ValueError):
                publish(changed,approve_signed(changed,key,"outbound","APPROVE PUBLIC RESEARCH"),str(remote),key=key)
            self.assertEqual(git("--git-dir",remote,"show","research-exchange:"+path),raw)

            # Identical bytes in a symlink blob must not count as a published record.
            git("-C", seed, "fetch", remote, "refs/heads/research-exchange")
            git("-C", seed, "read-tree", "FETCH_HEAD")
            blob = git("-C", seed, "rev-parse", "FETCH_HEAD:" + path).decode().strip()
            git("-C", seed, "update-index", "--cacheinfo", "120000," + blob + "," + path)
            tree = git("-C", seed, "write-tree").decode().strip()
            commit = git("-C", seed, "-c", "user.name=Test", "-c", "user.email=test@localhost",
                         "commit-tree", tree, "-p", "FETCH_HEAD", "-m", "synthetic symlink").decode().strip()
            git("-C", seed, "push", remote, commit + ":refs/heads/research-exchange")
            with self.assertRaisesRegex(ValueError, "unexpected Git entry type"):
                publish(raw, receipt, str(remote), key=key)
            self.assertEqual(git("--git-dir", remote, "rev-parse", "research-exchange").decode().strip(), commit)
