"""Synthetic Windows workspace installation and idempotence tests."""
import os
from pathlib import Path
import tempfile
import unittest

from install_local import prepare_local


@unittest.skipUnless(os.name == "nt", "Windows installer tests require NTFS and DPAPI")
class WindowsWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "test-bridge"

    def test_first_run_and_repeat_preserve_key(self):
        first = prepare_local(self.root)
        self.assertEqual(first["status"], "ready")
        key_path = self.root / "secrets" / "approval.dpapi"
        before = key_path.read_bytes()
        (self.root / "workspace" / "inbox" / "do-not-delete.txt").write_text(
            "synthetic local note", encoding="utf-8"
        )
        self.assertEqual(prepare_local(self.root)["status"], "ready")
        self.assertEqual(key_path.read_bytes(), before)
        self.assertEqual(
            (self.root / "workspace" / "inbox" / "do-not-delete.txt").read_text(
                encoding="utf-8"), "synthetic local note"
        )

    def test_reject_unrelated_git_directory(self):
        (self.root / "workspace" / "git").mkdir(parents=True)
        (self.root / "workspace" / "git" / "unrelated.txt").write_text("synthetic")
        with self.assertRaisesRegex(ValueError, "non-empty"):
            prepare_local(self.root)
        self.assertFalse((self.root / "secrets").exists())

    def test_reject_symlink_workspace(self):
        self.root.mkdir()
        other = Path(self.tmp.name) / "other"
        other.mkdir()
        try:
            (self.root / "workspace").symlink_to(other, target_is_directory=True)
        except OSError as exc:
            self.skipTest("Windows symlink privilege unavailable: " + str(exc.winerror))
        with self.assertRaisesRegex(ValueError, "symlink"):
            prepare_local(self.root)


if __name__ == "__main__":
    unittest.main()
