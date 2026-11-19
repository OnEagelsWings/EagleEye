"""Trusted timestamps (RFC 3161) for web evidence.

Only a SHA-256 digest leaves the computer – never content. EagleEye checks the answer itself:

* status granted, and the token's message imprint is exactly our digest;
* our random nonce comes back unchanged (no replayed answer);
* the CMS signature over the signed attributes verifies with the signer certificate, and the
  signed message digest matches the timestamp content;
* the signer certificate is meant for timestamping (extended key usage) and was valid at the
  stated time; the chain up to a root is checked against the trust store (Mozilla roots via
  ``certifi``) – a missing root is reported, not hidden.

The response (``.tsr``) is stored unchanged, so anybody can check it independently, e.g.
``openssl ts -verify -data manifest.txt -in stamp.tsr -CAfile roots.pem``.

The DER reader below is deliberately small and strict: definite lengths only, no indefinite
encodings, bounds checked on every step.
"""
from __future__ import annotations

import functools
import hashlib
import secrets
import urllib.request
import warnings
from datetime import datetime, timezone

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

OID_SHA256 = "2.16.840.1.101.3.4.2.1"
OID_SIGNED_DATA = "1.2.840.113549.1.7.2"
OID_TST_INFO = "1.2.840.113549.1.9.16.1.4"
OID_MESSAGE_DIGEST = "1.2.840.113549.1.9.4"
OID_CONTENT_TYPE = "1.2.840.113549.1.9.3"
OID_TIMESTAMPING = "1.3.6.1.5.5.7.3.8"
HASHES = {"1.3.14.3.2.26": hashes.SHA1, "2.16.840.1.101.3.4.2.1": hashes.SHA256,
          "2.16.840.1.101.3.4.2.2": hashes.SHA384, "2.16.840.1.101.3.4.2.3": hashes.SHA512}
RSA_SIGS = {"1.2.840.113549.1.1.1": None, "1.2.840.113549.1.1.5": hashes.SHA1, "1.2.840.113549.1.1.11": hashes.SHA256,
            "1.2.840.113549.1.1.12": hashes.SHA384, "1.2.840.113549.1.1.13": hashes.SHA512}
EC_SIGS = {"1.2.840.10045.4.3.2": hashes.SHA256, "1.2.840.10045.4.3.3": hashes.SHA384, "1.2.840.10045.4.3.4": hashes.SHA512}
MAX_RESPONSE = 64 * 1024
DEFAULT_URL = "http://timestamp.digicert.com"
STATUS_TEXT = {0: "gewährt", 1: "gewährt mit Änderungen", 2: "abgelehnt", 3: "wartet", 4: "Widerruf angekündigt", 5: "widerrufen"}


class TimestampError(ValueError):
    """A timestamp could not be obtained or does not verify."""


# ---------------------------------------------------------------- DER

def _tlv(tag: int, content: bytes) -> bytes:
    n = len(content)
    if n < 0x80:
        length = bytes([n])
    else:
        raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
        length = bytes([0x80 | len(raw)]) + raw
    return bytes([tag]) + length + content


def _int(value: int) -> bytes:
    raw = value.to_bytes(max(1, (value.bit_length() + 8) // 8), "big", signed=True)
    return _tlv(0x02, raw)


def _oid(dotted: str) -> bytes:
    parts = [int(p) for p in dotted.split(".")]
    body = bytearray([40 * parts[0] + parts[1]])
    for part in parts[2:]:
        chunk = [part & 0x7F]
        part >>= 7
        while part:
            chunk.append(0x80 | (part & 0x7F))
            part >>= 7
        body.extend(reversed(chunk))
    return _tlv(0x06, bytes(body))


class _Node:
    __slots__ = ("data", "tag", "start", "body", "end")

    def __init__(self, data: bytes, tag: int, start: int, body: int, end: int):
        self.data, self.tag, self.start, self.body, self.end = data, tag, start, body, end

    @property
    def raw(self) -> bytes:
        return self.data[self.start:self.end]

    @property
    def value(self) -> bytes:
        return self.data[self.body:self.end]

    def children(self) -> list["_Node"]:
        return _parse_all(self.data, self.body, self.end)


def _parse(data: bytes, pos: int, limit: int) -> _Node:
    if pos + 2 > limit:
        raise TimestampError("Antwort beschädigt (abgeschnitten).")
    tag = data[pos]
    if tag & 0x1F == 0x1F:
        raise TimestampError("Antwort enthält nicht unterstützte Kennungen.")
    first = data[pos + 1]
    head = pos + 2
    if first < 0x80:
        length = first
    else:
        count = first & 0x7F
        if count == 0 or count > 4 or head + count > limit:
            raise TimestampError("Antwort beschädigt (Längenangabe).")
        length = int.from_bytes(data[head:head + count], "big")
        head += count
    end = head + length
    if end > limit:
        raise TimestampError("Antwort beschädigt (Länge).")
    return _Node(data, tag, pos, head, end)


def _parse_all(data: bytes, pos: int, limit: int) -> list[_Node]:
    out = []
    while pos < limit:
        node = _parse(data, pos, limit)
        out.append(node)
        pos = node.end
    return out


def _root(data: bytes) -> _Node:
    node = _parse(data, 0, len(data))
    if node.end != len(data):
        raise TimestampError("Antwort enthält überzählige Daten.")
    return node


def _as_int(node: _Node) -> int:
    if node.tag != 0x02:
        raise TimestampError("Antwort beschädigt (Zahl erwartet).")
    return int.from_bytes(node.value, "big", signed=True)


def _as_oid(node: _Node) -> str:
    if node.tag != 0x06 or not node.value:
        raise TimestampError("Antwort beschädigt (Kennung erwartet).")
    raw = node.value
    parts = [raw[0] // 40, raw[0] % 40]
    value = 0
    for byte in raw[1:]:
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            parts.append(value)
            value = 0
    return ".".join(str(p) for p in parts)


def _as_time(node: _Node) -> datetime:
    if node.tag != 0x18:
        raise TimestampError("Antwort beschädigt (Zeit erwartet).")
    text = node.value.decode("ascii")
    if not text.endswith("Z"):
        raise TimestampError("Zeitstempel ohne UTC-Angabe.")
    main = text[:-1]
    fraction = ""
    if "." in main:
        main, fraction = main.split(".", 1)
    stamp = datetime.strptime(main, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    if fraction:
        stamp = stamp.replace(microsecond=int((fraction + "000000")[:6]))
    return stamp


# ---------------------------------------------------------------- request

def build_request(digest: bytes, nonce: int) -> bytes:
    """TimeStampReq for a SHA-256 digest, asking for the signer certificate."""
    if len(digest) != 32:
        raise TimestampError("SHA-256-Prüfsumme erwartet.")
    algorithm = _tlv(0x30, _oid(OID_SHA256) + b"\x05\x00")
    imprint = _tlv(0x30, algorithm + _tlv(0x04, digest))
    return _tlv(0x30, _int(1) + imprint + _int(nonce) + b"\x01\x01\xff")


def request(url: str, digest: bytes, *, timeout: float = 20, send=None) -> dict:
    """Ask the timestamp service; returns request, response and the nonce used."""
    if not str(url).startswith(("http://", "https://")):
        raise TimestampError("Zeitstempeldienst: bitte eine http- oder https-Adresse angeben.")
    nonce = secrets.randbits(63)
    der = build_request(digest, nonce)
    if send is not None:
        answer = send(der)
    else:
        call = urllib.request.Request(url, data=der, method="POST", headers={
            "Content-Type": "application/timestamp-query", "Accept": "application/timestamp-reply",
            "User-Agent": "EagleEye-Timestamp/1"})
        try:
            with urllib.request.urlopen(call, timeout=timeout) as response:
                answer = response.read(MAX_RESPONSE + 1)
        except OSError as exc:
            raise TimestampError(f"Zeitstempeldienst nicht erreichbar ({type(exc).__name__}).") from None
    if len(answer) > MAX_RESPONSE:
        raise TimestampError("Antwort des Zeitstempeldienstes ist zu groß.")
    return {"request": der, "response": answer, "nonce": nonce}


# ---------------------------------------------------------------- verification

@functools.lru_cache(maxsize=1)
def _trust_roots() -> tuple[x509.Certificate, ...]:
    try:
        import certifi
        with open(certifi.where(), "rb") as handle, warnings.catch_warnings():
            warnings.simplefilter("ignore")  # a few old roots in the bundle have non-RFC serial numbers
            return tuple(x509.load_pem_x509_certificates(handle.read()))
    except Exception:  # no bundle available: chain is reported as unchecked
        return ()


def _verify_signature(cert: x509.Certificate, signature: bytes, data: bytes, sig_oid: str, digest_cls) -> None:
    key = cert.public_key()
    if isinstance(key, rsa.RSAPublicKey) and sig_oid in RSA_SIGS:
        key.verify(signature, data, padding.PKCS1v15(), (RSA_SIGS[sig_oid] or digest_cls)())
    elif isinstance(key, ec.EllipticCurvePublicKey) and sig_oid in EC_SIGS:
        key.verify(signature, data, ec.ECDSA(EC_SIGS[sig_oid]()))
    else:
        raise TimestampError("Signaturverfahren des Zeitstempels wird nicht unterstützt.")


def _chain(signer: x509.Certificate, pool: list[x509.Certificate], roots: list[x509.Certificate],
           at: datetime) -> tuple[bool, list[x509.Certificate]]:
    """Walk from the signer to a trusted root; returns (trusted, certificates from signer upwards)."""
    trusted = {c.fingerprint(hashes.SHA256()) for c in roots}
    candidates = list(pool) + list(roots)
    current, path = signer, [signer]
    for _ in range(8):
        if not current.not_valid_before_utc <= at <= current.not_valid_after_utc:
            raise TimestampError("Ein Zertifikat der Kette war zum Zeitpunkt des Stempels nicht gültig.")
        if current.fingerprint(hashes.SHA256()) in trusted:
            return True, path
        issuer = None
        for candidate in candidates:
            if candidate.subject == current.issuer:
                try:
                    current.verify_directly_issued_by(candidate)
                except (ValueError, TypeError, InvalidSignature):
                    continue
                issuer = candidate
                break
        if issuer is None or issuer.fingerprint(hashes.SHA256()) == current.fingerprint(hashes.SHA256()):
            return False, path
        current = issuer
        path.append(current)
    return False, path


def verify(response_der: bytes, digest: bytes, *, nonce: int | None = None,
           roots: list[x509.Certificate] | None = None) -> dict:
    """Check a TimeStampResp for ``digest``; raises TimestampError, returns the facts."""
    resp = _root(response_der).children()
    if not resp or resp[0].tag != 0x30:
        raise TimestampError("Antwort beschädigt.")
    status = _as_int(resp[0].children()[0])
    if status not in (0, 1):
        raise TimestampError("Zeitstempel " + STATUS_TEXT.get(status, f"Status {status}") + ".")
    if len(resp) < 2:
        raise TimestampError("Antwort ohne Zeitstempel.")
    token = resp[1].children()
    if _as_oid(token[0]) != OID_SIGNED_DATA or token[1].tag != 0xA0:
        raise TimestampError("Zeitstempel hat ein unbekanntes Format.")
    signed = token[1].children()[0].children()
    encap = signed[2].children()
    if _as_oid(encap[0]) != OID_TST_INFO:
        raise TimestampError("Zeitstempel enthält keine Zeitstempel-Daten.")
    econtent_node = encap[1].children()[0]
    if econtent_node.tag != 0x04:
        raise TimestampError("Zeitstempel-Daten beschädigt.")
    econtent = econtent_node.value
    certs, signer_infos = [], None
    for node in signed[3:]:
        if node.tag == 0xA0:
            certs = [x509.load_der_x509_certificate(c.raw) for c in node.children()]
        elif node.tag == 0x31:
            signer_infos = node.children()
    if not signer_infos:
        raise TimestampError("Zeitstempel ohne Signatur.")

    # TSTInfo
    tst = _root(econtent).children()
    policy = _as_oid(tst[1])
    imprint = tst[2].children()
    hash_oid = _as_oid(imprint[0].children()[0])
    stamped = imprint[1].value
    serial = _as_int(tst[3])
    gen_time = _as_time(tst[4])
    token_nonce = None
    for node in tst[5:]:
        if node.tag == 0x02:
            token_nonce = _as_int(node)
    if hash_oid != OID_SHA256 or stamped != digest:
        raise TimestampError("Der Zeitstempel gilt für eine andere Prüfsumme.")
    if nonce is not None and token_nonce != nonce:
        raise TimestampError("Der Zeitstempel passt nicht zu dieser Anfrage (Einmalwert abweichend).")

    # Signer
    info = signer_infos[0].children()
    sid, digest_alg = info[1], _as_oid(info[2].children()[0])
    index = 3
    signed_attrs = None
    if info[index].tag == 0xA0:
        signed_attrs = info[index]
        index += 1
    sig_oid = _as_oid(info[index].children()[0])
    signature = info[index + 1].value
    if digest_alg not in HASHES:
        raise TimestampError("Prüfsummenverfahren der Signatur wird nicht unterstützt.")
    digest_cls = HASHES[digest_alg]
    signer = None
    if sid.tag == 0x30:
        issuer_raw, serial_node = sid.children()
        for cert in certs:
            if cert.serial_number == _as_int(serial_node) and cert.issuer.public_bytes() == issuer_raw.raw:
                signer = cert
    elif sid.tag == 0x80:
        for cert in certs:
            try:
                ski = cert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest
            except x509.ExtensionNotFound:
                continue
            if ski == sid.value:
                signer = cert
    if signer is None:
        raise TimestampError("Das Zertifikat des Zeitstempeldienstes fehlt in der Antwort.")
    if signed_attrs is None:
        raise TimestampError("Zeitstempel ohne signierte Attribute.")
    message_digest = None
    for attribute in signed_attrs.children():
        parts = attribute.children()
        if _as_oid(parts[0]) == OID_MESSAGE_DIGEST:
            message_digest = parts[1].children()[0].value
    hasher = hashes.Hash(digest_cls())
    hasher.update(econtent)
    if message_digest != hasher.finalize():
        raise TimestampError("Signierte Prüfsumme passt nicht zum Zeitstempel – Antwort verändert.")
    to_verify = b"\x31" + signed_attrs.raw[1:]  # [0] IMPLICIT SET is signed as a plain SET
    try:
        _verify_signature(signer, signature, to_verify, sig_oid, digest_cls)
    except InvalidSignature:
        raise TimestampError("Signatur des Zeitstempels ist ungültig.") from None
    try:
        eku = signer.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        purposes = {p.dotted_string for p in eku}
    except x509.ExtensionNotFound:
        purposes = set()
    if OID_TIMESTAMPING not in purposes:
        raise TimestampError("Das Zertifikat ist nicht für Zeitstempel bestimmt.")
    trusted, path = _chain(signer, certs, list(_trust_roots()) if roots is None else roots, gen_time)
    names = signer.subject.get_attributes_for_oid(x509.NameOID.ORGANIZATION_NAME) or \
        signer.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
    return {"gen_time": gen_time.isoformat(timespec="seconds"), "serial": str(serial), "policy": policy,
            "tsa": names[0].value if names else signer.subject.rfc4514_string(), "signer": signer.subject.rfc4514_string(),
            "chain_trusted": trusted, "chain": [c.subject.rfc4514_string() for c in path], "status": STATUS_TEXT[status],
            "chain_pem": b"".join(c.public_bytes(serialization.Encoding.PEM) for c in path)}


def digest_of(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()
