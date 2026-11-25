import json
import unittest
from signed_approval import approve_signed, verify_signed, CONFIRMATION


class SignedApprovalTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.dumps(dict(schema=1,
            id="00000000-0000-4000-8000-000000000001",
            kind="research_result", classification="public-topic",
            topic="Synthetic", summary="Test only", sources=[],
            synthetic=True)).encode()
        self.key = b"t" * 32
        self.receipt = approve_signed(self.raw, self.key, "outbound", CONFIRMATION)

    def test_exact_scope(self):
        self.assertTrue(verify_signed(self.raw, self.key, "outbound", self.receipt))
        self.assertFalse(verify_signed(self.raw, self.key, "inbound", self.receipt))
        self.assertFalse(verify_signed(self.raw + b" ", self.key, "outbound", self.receipt))
        self.assertFalse(verify_signed(self.raw, b"x" * 32, "outbound", self.receipt))

    def test_forgery(self):
        receipt = json.loads(self.receipt)
        receipt["mac"] = "0" * 64
        self.assertFalse(verify_signed(self.raw, self.key, "outbound", json.dumps(receipt)))

    def test_invalid_inputs(self):
        for receipt in (None, "{}", "\ud800", "x" * 2049):
            self.assertFalse(verify_signed(self.raw, self.key, "outbound", receipt))
        for raw, key, direction, confirmation in (
            (self.raw, self.key, "outbound", "yes"),
            (self.raw, b"short", "outbound", CONFIRMATION),
            (self.raw, self.key, "unknown", CONFIRMATION),
            (b"{}", self.key, "outbound", CONFIRMATION)):
            with self.assertRaises(ValueError):
                approve_signed(raw, key, direction, confirmation)
