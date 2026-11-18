"""Local authenticated receipts; keys never belong in exchange records.
HMAC authenticates possession of a local key, not a human identity.
Outbound publishing requires a v2 receipt.
"""
import hashlib
import hmac
import json
from bridge import validate

CONFIRMATION = "APPROVE PUBLIC RESEARCH"
DOMAIN = b"eagleeye/research-exchange/approval/v2\x00"


def _message(raw, key, direction):
    if not isinstance(raw, bytes):
        raise ValueError("expected bytes")
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("expected a 32-byte local key")
    if direction not in ("inbound", "outbound"):
        raise ValueError("invalid direction")
    record = validate(raw)
    return {"version": 2, "direction": direction, "id": record["id"],
            "sha256": hashlib.sha256(raw).hexdigest()}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def approve_signed(raw, key, direction, confirmation):
    if confirmation != CONFIRMATION:
        raise ValueError("explicit approval required")
    message = _message(raw, key, direction)
    signature = hmac.new(key, DOMAIN + _canonical(message).encode("ascii"),
                         hashlib.sha256).hexdigest()
    return _canonical(dict(message, mac=signature))


def verify_signed(raw, key, direction, receipt):
    if not isinstance(receipt, str) or len(receipt) > 2048:
        return False
    try:
        expected = approve_signed(raw, key, direction, CONFIRMATION)
        return hmac.compare_digest(receipt.encode("ascii"), expected.encode("ascii"))
    except (ValueError, TypeError, UnicodeError):
        return False
