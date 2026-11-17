import json
import pathlib
import subprocess
import tempfile
import unittest
from approval import approve
from outbound import publish

class OutboundTests(unittest.TestCase):
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
            receipt = approve(raw,"APPROVE PUBLIC RESEARCH")
            with self.assertRaises(ValueError):
                publish(raw,"invalid",str(remote))
            self.assertEqual(publish(raw,receipt,str(remote))["status"],"published")
            self.assertEqual(publish(raw,receipt,str(remote))["status"],"duplicate")
            path = "exchange/outbox/" + record["id"] + ".json"
            self.assertEqual(git("--git-dir",remote,"show","research-exchange:"+path),raw)
            changed = raw + b" "
            with self.assertRaises(ValueError):
                publish(changed,approve(changed,"APPROVE PUBLIC RESEARCH"),str(remote))
            self.assertEqual(git("--git-dir",remote,"show","research-exchange:"+path),raw)
