"""Real Windows PowerShell install/update/uninstall tests using synthetic payload."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PACK = Path(__file__).resolve().parent / "packaging"


@unittest.skipUnless(os.name == "nt", "Native Windows package validation")
class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / "source"
        payload = self.package / "payload" / "ResearchBridge"
        payload.mkdir(parents=True)
        files = {
            "ResearchBridge.exe": b"synthetic-test-EXE-not-real",
            "_internal/data.txt": b"synthetic bundle contents",
        }
        manifest = []
        for name, contents in files.items():
            target = payload / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents)
            manifest.append({
                "path": "payload/ResearchBridge/" + name,
                "sha256": hashlib.sha256(contents).hexdigest(),
                "size": len(contents),
            })
        for script in ("Install-ResearchBridge.ps1", "Uninstall-ResearchBridge.ps1",
                       "Switch-ResearchBridge-Version.ps1", "Uninstall.cmd"):
            shutil.copy2(PACK / script, self.package / script)
        (self.package / "manifest.json").write_text(
            json.dumps(dict(
                app_id="eagleeye-public-research-bridge",
                version="1.0.0-rc1", files=manifest
            )), encoding="utf-8"
        )
        self.destination = self.root / "installed"
        self.data = self.root / "persistent-research-data"
        self.data.mkdir()
        (self.data / "never-delete.txt").write_text("synthetic-stay", encoding="utf-8")

    def run_script(self, script, *args, expected=0):
        run = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy",
             "Bypass", "-File", str(self.package / script),
             "-Destination", str(self.destination), *args],
            capture_output=True, text=True, timeout=45,
        )
        if expected == 0:
            self.assertEqual(run.returncode, 0, run.stdout + "\n" + run.stderr)
        else:
            self.assertNotEqual(run.returncode, 0, "unexpected success")
        return run

    def test_install_idempotent_uninstall_preserves_data(self):
        self.run_script("Install-ResearchBridge.ps1", "-NoShortcuts")
        self.run_script("Install-ResearchBridge.ps1", "-NoShortcuts")
        self.assertEqual((self.destination / "current-version.txt").read_text().strip(),
                         "1.0.0-rc1")
        self.assertEqual(
            (self.destination / "versions" / "1.0.0-rc1" /
             "ResearchBridge.exe").read_bytes(), b"synthetic-test-EXE-not-real"
        )
        self.run_script("Uninstall-ResearchBridge.ps1", "-NoShortcuts", expected=1)
        self.run_script("Uninstall-ResearchBridge.ps1", "-ConfirmRemoval", "-NoShortcuts")
        self.assertFalse(self.destination.exists())
        self.assertEqual((self.data / "never-delete.txt").read_text(), "synthetic-stay")

    def test_update_preserves_old_version_and_validated_rollback(self):
        self.run_script("Install-ResearchBridge.ps1", "-NoShortcuts")
        file = self.package / "payload" / "ResearchBridge" / "_internal" / "data.txt"
        file.write_bytes(b"synthetic-second-version")
        meta = json.loads((self.package / "manifest.json").read_text())
        meta["version"] = "1.0.0-rc2"
        for entry in meta["files"]:
            if entry["path"].endswith("/data.txt"):
                entry["size"] = len(file.read_bytes())
                entry["sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
        (self.package / "manifest.json").write_text(json.dumps(meta), encoding="utf-8")
        self.run_script("Install-ResearchBridge.ps1", "-NoShortcuts")
        self.assertEqual((self.destination / "current-version.txt").read_text().strip(),
                         "1.0.0-rc2")
        self.assertTrue((self.destination / "versions" / "1.0.0-rc1").is_dir())
        self.run_script("Switch-ResearchBridge-Version.ps1",
                        "-Version", "1.0.0-rc1", "-NoShortcuts")
        self.assertEqual((self.destination / "current-version.txt").read_text().strip(),
                         "1.0.0-rc1")
        self.assertEqual((self.data / "never-delete.txt").read_text(), "synthetic-stay")

    def test_payload_mutation_rejected_before_install(self):
        (self.package / "payload" / "ResearchBridge" /
         "ResearchBridge.exe").write_bytes(b"tampered")
        result = self.run_script("Install-ResearchBridge.ps1",
                                 "-NoShortcuts", expected=1)
        self.assertIn("integrity", result.stdout.lower() + result.stderr.lower())
        self.assertFalse(self.destination.exists())

    def test_unrecognized_existing_destination_refused(self):
        self.destination.mkdir()
        (self.destination / "unrelated.txt").write_text("preserve")
        self.run_script("Install-ResearchBridge.ps1", "-NoShortcuts", expected=1)
        self.assertEqual((self.destination / "unrelated.txt").read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
