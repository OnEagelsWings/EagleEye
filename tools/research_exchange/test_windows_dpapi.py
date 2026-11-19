"""Synthetic DPAPI tests; native cases require Windows."""
import os
import unittest

from windows_dpapi import protect_key, unprotect_key


class DPAPIValidationTests(unittest.TestCase):
    def test_invalid_key_lengths(self):
        for key in (b"", b"x" * 31, b"x" * 33, "x" * 32):
            with self.subTest(key=key), self.assertRaises(ValueError):
                protect_key(key)

    @unittest.skipIf(os.name == "nt", "non-Windows only")
    def test_unsupported_platform(self):
        with self.assertRaises(RuntimeError):
            protect_key(b"x" * 32)
        with self.assertRaises(RuntimeError):
            unprotect_key(b"x")


@unittest.skipUnless(os.name == "nt", "native Windows DPAPI required")
class NativeDPAPITests(unittest.TestCase):
    def test_roundtrip(self):
        key = b"x" * 32
        blob = protect_key(key)
        self.assertNotEqual(blob, key)
        self.assertEqual(unprotect_key(blob), key)

    def test_invalid_blob(self):
        for blob in (b"", b"x" * 65537):
            with self.subTest(size=len(blob)), self.assertRaises(ValueError):
                unprotect_key(blob)
        with self.assertRaises(OSError):
            unprotect_key(b"not a DPAPI blob")

    def test_tampered_blob(self):
        blob = bytearray(protect_key(b"x" * 32))
        blob[-1] ^= 1
        with self.assertRaises(OSError):
            unprotect_key(bytes(blob))


if __name__ == "__main__":
    unittest.main()
