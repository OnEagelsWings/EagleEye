import json
import unittest
from bridge import validate

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

if __name__ == "__main__":
    unittest.main()
