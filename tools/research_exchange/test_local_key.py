"""Synthetic regression tests for local POSIX key provisioning."""
import os
from pathlib import Path
import tempfile
import unittest

from local_key import create_key, read_key


@unittest.skipUnless(os.name == "posix" and hasattr(os, "O_NOFOLLOW"), "POSIX only")
class LocalKeyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.path = self.root / "key"

    def test_roundtrip_and_no_overwrite(self):
        create_key(self.path)
        key = read_key(self.path)
        self.assertEqual(len(key), 32)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            create_key(self.path)
        self.assertEqual(read_key(self.path), key)

    def test_missing(self):
        with self.assertRaises(FileNotFoundError):
            read_key(self.path)

    def test_unsafe_permissions(self):
        create_key(self.path)
        self.path.chmod(0o644)
        with self.assertRaises(ValueError):
            read_key(self.path)

    def test_symlink(self):
        target = self.root / "target"
        target.write_bytes(b"x" * 32)
        target.chmod(0o600)
        self.path.symlink_to(target)
        with self.assertRaises(OSError):
            read_key(self.path)
        with self.assertRaises(OSError):
            create_key(self.path)

    def test_hardlink(self):
        create_key(self.path)
        os.link(self.path, self.root / "alias")
        with self.assertRaises(ValueError):
            read_key(self.path)

    def test_invalid_length(self):
        for size in (0, 31, 33, 100):
            self.path.write_bytes(b"x" * size)
            self.path.chmod(0o600)
            with self.subTest(size=size), self.assertRaises(ValueError):
                read_key(self.path)

    def test_unsafe_directory(self):
        create_key(self.path)
        self.root.chmod(0o755)
        try:
            with self.assertRaises(ValueError):
                read_key(self.path)
            with self.assertRaises(ValueError):
                create_key(self.root / "other")
        finally:
            self.root.chmod(0o700)

    def test_fifo_rejected_without_blocking(self):
        os.mkfifo(self.path, 0o600)
        with self.assertRaisesRegex(ValueError, "unsafe key file"):
            read_key(self.path)
        with self.assertRaises(FileExistsError):
            create_key(self.path)

    def test_symlink_directory_rejected(self):
        create_key(self.path)
        with tempfile.TemporaryDirectory() as other:
            alias = Path(other) / "alias"
            alias.symlink_to(self.root, target_is_directory=True)
            with self.assertRaises(OSError):
                read_key(alias / "key")
            with self.assertRaises(OSError):
                create_key(alias / "new")
        self.assertFalse((self.root / "new").exists())
