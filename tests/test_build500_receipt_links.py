"""Focused Build 500 installer receipt symlink regression (no runtime installation)."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

INSTALLER = Path(__file__).resolve().parents[1] / "INSTALL_EAGLEEYE_500.py"
spec = importlib.util.spec_from_file_location("installer500_receipt", INSTALLER)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class ReceiptLinkIsolationTest(unittest.TestCase):
    def test_linked_receipt_is_not_read_or_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "package"
            runtime = root / installer.RUNTIME_DIR
            runtime.mkdir(parents=True)
            external = Path(temp) / "legacy-receipt.json"
            original = '{"build": "398", "secret": "do not touch"}'
            external.write_text(original, encoding="utf-8")
            receipt = runtime / installer.RECEIPT
            try:
                receipt.symlink_to(external)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            self.assertEqual(installer._read_receipt(root), {})
            with self.assertRaisesRegex(RuntimeError, "Linked installer receipt"):
                installer._write_receipt(root, fingerprint="test", probe={})
            self.assertEqual(external.read_text(encoding="utf-8"), original)

    def test_linked_temporary_receipt_is_not_written(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "package"
            runtime = root / installer.RUNTIME_DIR
            runtime.mkdir(parents=True)
            external = Path(temp) / "legacy-settings.json"
            external.write_text("unchanged", encoding="utf-8")
            temporary = (runtime / installer.RECEIPT).with_suffix(".tmp")
            try:
                temporary.symlink_to(external)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            with self.assertRaisesRegex(RuntimeError, "Linked installer receipt"):
                installer._write_receipt(root, fingerprint="test", probe={})
            self.assertEqual(external.read_text(encoding="utf-8"), "unchanged")


if __name__ == "__main__":
    unittest.main()
