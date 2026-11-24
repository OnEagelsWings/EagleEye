"""Native Windows DPAPI key-file tests with only ephemeral, synthetic keys."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from local_key import create_key, read_key
from windows_key_store import MAGIC, prepare_private_directory
from signed_approval import approve_signed, verify_signed, CONFIRMATION


@unittest.skipUnless(os.name == "nt", "native Windows ACL and DPAPI required")
class WindowsProtectedKeyStoreTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name) / "secrets"
        prepare_private_directory(self.folder)
        self.key_file = self.folder / "approval.dpapi"

    def test_create_read_and_encrypted_on_disk(self):
        create_key(self.key_file)
        secret = read_key(self.key_file)
        data = self.key_file.read_bytes()
        self.assertEqual(len(secret), 32)
        self.assertTrue(data.startswith(MAGIC))
        self.assertNotIn(secret, data)
        self.assertEqual(read_key(self.key_file), secret)

    def test_signed_outbound_receipt_with_persisted_key(self):
        create_key(self.key_file)
        record = json.dumps({
            'schema': 1,
            'id': '00000000-0000-4000-8000-000000000086',
            'kind': 'research_result',
            'classification': 'public-topic',
            'topic': 'Synthetic public research fixture',
            'summary': 'No people, secrets or case files',
            'sources': [],
            'synthetic': True,
        }).encode('utf-8')
        receipt = approve_signed(record, read_key(self.key_file),
                                'outbound', CONFIRMATION)
        self.assertTrue(verify_signed(record, read_key(self.key_file),
                                      'outbound', receipt))
        self.assertFalse(verify_signed(record + b' ', read_key(self.key_file),
                                       'outbound', receipt))

    def test_duplicate_creation_refused(self):
        create_key(self.key_file)
        original = self.key_file.read_bytes()
        with self.assertRaises(FileExistsError):
            create_key(self.key_file)
        self.assertEqual(self.key_file.read_bytes(), original)

    def test_cross_process_read(self):
        create_key(self.key_file)
        expected = hashlib.sha256(read_key(self.key_file)).hexdigest()
        script = ("import hashlib,sys; from local_key import read_key; "
                  "print(hashlib.sha256(read_key(sys.argv[1])).hexdigest())")
        result = subprocess.run(
            [sys.executable, "-c", script, str(self.key_file)],
            cwd=Path(__file__).parent, check=True, capture_output=True,
            text=True, timeout=20,
        )
        self.assertEqual(result.stdout.strip(), expected)

    def test_tampered_blob_rejected(self):
        create_key(self.key_file)
        altered = bytearray(self.key_file.read_bytes())
        altered[-1] ^= 1
        self.key_file.write_bytes(altered)
        with self.assertRaises(OSError):
            read_key(self.key_file)

    def test_invalid_header_rejected(self):
        create_key(self.key_file)
        self.key_file.write_bytes(b"plain-text-secret" * 3)
        with self.assertRaises(ValueError):
            read_key(self.key_file)

    def test_unprotected_parent_rejected(self):
        other = Path(self.folder).parent / "unsafe.dpapi"
        with self.assertRaises(ValueError):
            create_key(other)
        self.assertFalse(other.exists())

    def test_hardlink_rejected(self):
        create_key(self.key_file)
        alias = self.folder / "alias.dpapi"
        os.link(self.key_file, alias)
        with self.assertRaises(ValueError):
            read_key(self.key_file)

    def test_preexisting_directory_not_overwritten(self):
        with self.assertRaises(FileExistsError):
            prepare_private_directory(self.folder)


if __name__ == "__main__":
    unittest.main()
