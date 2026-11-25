"""Explicit, content-bound approval for public research exchange."""
import hashlib
import hmac
import json


def approve(raw, confirmation):
    if not isinstance(raw, bytes):
        raise ValueError('expected bytes')
    if confirmation != 'APPROVE PUBLIC RESEARCH':
        raise ValueError('explicit approval required')
    return json.dumps({'version': 1, 'sha256': hashlib.sha256(raw).hexdigest()}, sort_keys=True)


def verify(raw, receipt):
    if not isinstance(raw, bytes) or not isinstance(receipt, str):
        return False
    # Canonical receipt only; no permissive JSON parsing.
    expected = approve(raw, 'APPROVE PUBLIC RESEARCH')
    return hmac.compare_digest(receipt.encode('utf-8'), expected.encode('utf-8'))
