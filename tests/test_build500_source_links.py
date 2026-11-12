"""Build 500: installer source fingerprint must not follow linked sources."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

INSTALLER = Path(__file__).resolve().parents[1] / "INSTALL_EAGLEEYE_500.py"
spec = importlib.util.spec_from_file_location("installer500_source_links", INSTALLER)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class SourceFingerprintLinksTest(unittest.TestCase):
    def test_linked_source_file_is_rejected_without_reading_external_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "release"
            root.mkdir()
            external = Path(tmp) / "legacy-project.toml"
            external.write_text("legacy confidential content", encoding="utf-8")
            try:
                (root / "pyproject.toml").symlink_to(external)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(str(exc))
            with self.assertRaisesRegex(RuntimeError, "Linked source paths"):
                installer._source_fingerprint(root)

    def test_linked_source_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "release"
            root.mkdir()
            external = Path(tmp) / "legacy-src"
            (external / "eagleeye").mkdir(parents=True)
            (external / "eagleeye" / "secret.py").write_text("secret = 1", encoding="utf-8")
            try:
                (root / "src").symlink_to(external, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(str(exc))
            with self.assertRaisesRegex(RuntimeError, "Linked source paths"):
                installer._source_fingerprint(root)


    def test_linked_release_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            real_root = Path(tmp) / "legacy-release"
            real_root.mkdir()
            linked_root = Path(tmp) / "build500"
            try:
                linked_root.symlink_to(real_root, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(str(exc))
            with self.assertRaisesRegex(RuntimeError, "Linked source paths"):
                installer._source_fingerprint(linked_root)

    def test_fresh_runtime_uses_no_linked_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python = installer._ensure_runtime(root, quiet=True)
            self.assertTrue(python.is_file())
            self.assertFalse(installer._runtime_path_linked(root))
            self.assertEqual(installer._ensure_runtime(root, quiet=True), python)

    def test_root_preserves_link_for_validation(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real"
            real.mkdir()
            link = Path(tmp) / "alias"
            try:
                link.symlink_to(real, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(str(exc))
            with patch.object(installer, "__file__", str(link / "INSTALL_EAGLEEYE_500.py")):
                self.assertEqual(installer._root(), link)
                with self.assertRaisesRegex(RuntimeError, "Linked source paths"):
                    installer._source_fingerprint(installer._root())

    def test_nested_directory_link_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "release"
            nested = root / "src" / "eagleeye"
            nested.mkdir(parents=True)
            external = Path(tmp) / "legacy"
            external.mkdir()
            (external / "private.py").write_text("private = 1", encoding="utf-8")
            try:
                (nested / "linked").symlink_to(external, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(str(exc))
            with self.assertRaisesRegex(RuntimeError, "Linked source paths"):
                installer._source_fingerprint(root)

    def test_dangling_nested_link_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "release"
            nested = root / "src" / "eagleeye"
            nested.mkdir(parents=True)
            try:
                (nested / "missing.py").symlink_to(Path(tmp) / "does-not-exist.py")
            except (OSError, NotImplementedError) as exc:
                self.skipTest(str(exc))
            with self.assertRaisesRegex(RuntimeError, "Linked source paths"):
                installer._source_fingerprint(root)


if __name__ == "__main__":
    unittest.main()
