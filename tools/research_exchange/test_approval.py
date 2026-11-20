import unittest
from approval import approve, verify


class ApprovalTests(unittest.TestCase):
    def test_explicit(self):
        with self.assertRaises(ValueError):
            approve(b'{}', 'yes')

    def test_exact_bytes(self):
        receipt = approve(b'{}', 'APPROVE PUBLIC RESEARCH')
        self.assertTrue(verify(b'{}', receipt))
        self.assertFalse(verify(b'{ }', receipt))

    def test_invalid_receipt(self):
        self.assertFalse(verify(b'{}', None))
        self.assertFalse(verify(b'{}', '{}'))
        self.assertFalse(verify(b'{}', 'invalid'))
