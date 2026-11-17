import json
import unittest
from bridge import validate, publish_record
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.record = dict(schema=1, id="00000000-0000-4000-8000-000000000001",
                           kind="research_result", classification="public-topic",
                           topic="Synthetic", summary="Test only", sources=[], synthetic=True)

    def encode(self):
        return json.dumps(self.record).encode("utf-8")

    def test_valid(self):
        self.assertEqual(validate(self.encode()), self.record)

    def test_duplicate_key(self):
        with self.assertRaises(ValueError):
            validate(self.encode().replace(b'"schema": 1', b'"schema": 2, "schema": 1'))

    def test_utf16(self):
        with self.assertRaises(ValueError):
            validate(json.dumps(self.record).encode("utf-16"))

    def test_nonfinite(self):
        with self.assertRaises(ValueError):
            validate(self.encode().replace(b'"synthetic": true', b'"synthetic": NaN'))

    def test_private(self):
        self.record["classification"] = "private"
        with self.assertRaises(ValueError):
            validate(self.encode())

    def test_boolean_schema(self):
        self.record["schema"] = True
        with self.assertRaises(ValueError):
            validate(self.encode())

    def test_url(self):
        for url in ("http://example.org", "https://user@example.org", "https://exa mple.org", "https://example.org\\x"):
            with self.subTest(url=url):
                self.record["sources"] = [{"title":"Test","url":url}]
                with self.assertRaises(ValueError):
                    validate(self.encode())

class PublicationTests(unittest.TestCase):
    def test_duplicate_and_conflict(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "record.json"
            self.assertEqual(publish_record(target, b"original"), "staged")
            self.assertEqual(publish_record(target, b"original"), "duplicate")
            self.assertEqual(publish_record(target, b"changed"), "conflict")
            self.assertEqual(target.read_bytes(), b"original")
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_failed_publication_leaves_no_partial_record(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "record.json"
            with patch("bridge.os.link", side_effect=OSError("synthetic failure")):
                with self.assertRaises(OSError):
                    publish_record(target, b"synthetic")
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertEqual(publish_record(target, b"synthetic"), "staged")

if __name__ == "__main__":
    unittest.main()
