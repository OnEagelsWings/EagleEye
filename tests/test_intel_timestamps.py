"""RFC 3161 timestamps against a real (local) OpenSSL timestamp authority."""
import hashlib
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509

from eagleeye.application.intel492 import timestamps

OPENSSL = shutil.which("openssl")
needs_openssl = pytest.mark.skipif(OPENSSL is None, reason="OpenSSL command line tool not installed")


def _run(*args, cwd):
    subprocess.run([OPENSSL, *args], cwd=cwd, check=True, capture_output=True)


def make_tsa(folder: Path, *, eku: str = "critical,timeStamping") -> dict:
    """A test root CA and a timestamp authority certificate, plus an OpenSSL TSA config."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ca.ext").write_text("basicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\n")
    _run("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "ca.key", "-out", "ca.crt", "-days", "30",
         "-subj", "/CN=EagleEye Test Root/O=EagleEye Test", "-addext", "basicConstraints=critical,CA:TRUE",
         "-addext", "keyUsage=critical,keyCertSign,cRLSign", cwd=folder)
    _run("req", "-newkey", "rsa:2048", "-nodes", "-keyout", "tsa.key", "-out", "tsa.csr",
         "-subj", "/CN=Test TSA/O=Test Zeitstempel GmbH", cwd=folder)
    (folder / "tsa.ext").write_text(f"extendedKeyUsage={eku}\nkeyUsage=critical,digitalSignature\n")
    _run("x509", "-req", "-in", "tsa.csr", "-CA", "ca.crt", "-CAkey", "ca.key", "-CAcreateserial", "-out", "tsa.crt",
         "-days", "20", "-extfile", "tsa.ext", cwd=folder)
    (folder / "tsaserial").write_text("01\n")
    (folder / "ts.cnf").write_text(f"""[ tsa ]
default_tsa = tsa1
[ tsa1 ]
dir = {folder.as_posix()}
serial = $dir/tsaserial
crypto_device = builtin
signer_cert = $dir/tsa.crt
certs = $dir/ca.crt
signer_key = $dir/tsa.key
signer_digest = sha256
default_policy = 1.2.3.4.1
digests = sha256
accuracy = secs:1
ordering = no
tsa_name = no
ess_cert_id_chain = no
ess_cert_id_alg = sha256
""")

    def send(der: bytes) -> bytes:
        (folder / "q.tsq").write_bytes(der)
        _run("ts", "-reply", "-queryfile", "q.tsq", "-config", "ts.cnf", "-out", "r.tsr", cwd=folder)
        return (folder / "r.tsr").read_bytes()
    root = x509.load_pem_x509_certificate((folder / "ca.crt").read_bytes())
    return {"send": send, "root": root, "folder": folder}


@needs_openssl
def test_valid_timestamp_is_verified_and_openssl_agrees(tmp_path):
    tsa = make_tsa(tmp_path / "tsa")
    manifest = b"EagleEye Beweismanifest\nwarc_sha256: abc\n"
    digest = hashlib.sha256(manifest).digest()
    result = timestamps.request("http://tsa.example", digest, send=tsa["send"])
    facts = timestamps.verify(result["response"], digest, nonce=result["nonce"], roots=[tsa["root"]])
    stamped = datetime.fromisoformat(facts["gen_time"])
    assert abs(stamped - datetime.now(timezone.utc)) < timedelta(minutes=2)
    assert facts["chain_trusted"] and facts["tsa"] == "Test Zeitstempel GmbH" and facts["policy"] == "1.2.3.4.1"
    assert len(facts["chain"]) == 2
    # Independent check with the OpenSSL command line tool.
    (tmp_path / "m.txt").write_bytes(manifest)
    (tmp_path / "s.tsr").write_bytes(result["response"])
    check = subprocess.run([OPENSSL, "ts", "-verify", "-data", "m.txt", "-in", "s.tsr", "-CAfile", str(tsa["folder"] / "ca.crt"),
                            "-untrusted", str(tsa["folder"] / "tsa.crt")], cwd=tmp_path, capture_output=True, text=True)
    assert "Verification: OK" in check.stdout, check.stdout + check.stderr
    # Without a trusted root the signature still verifies, the chain is reported as unchecked.
    assert not timestamps.verify(result["response"], digest, nonce=result["nonce"], roots=[])["chain_trusted"]


@needs_openssl
def test_wrong_digest_nonce_and_tampering_are_rejected(tmp_path):
    tsa = make_tsa(tmp_path / "tsa")
    digest = hashlib.sha256(b"original").digest()
    result = timestamps.request("http://tsa.example", digest, send=tsa["send"])
    with pytest.raises(timestamps.TimestampError, match="andere Prüfsumme"):
        timestamps.verify(result["response"], hashlib.sha256(b"anders").digest(), roots=[tsa["root"]])
    with pytest.raises(timestamps.TimestampError, match="Einmalwert"):
        timestamps.verify(result["response"], digest, nonce=result["nonce"] + 1, roots=[tsa["root"]])
    tampered = bytearray(result["response"])
    tampered[-10] ^= 0x01  # inside the signature value
    with pytest.raises(timestamps.TimestampError, match="ungültig|verändert|beschädigt"):
        timestamps.verify(bytes(tampered), digest, nonce=result["nonce"], roots=[tsa["root"]])
    with pytest.raises(timestamps.TimestampError):
        timestamps.verify(result["response"] + b"\x00", digest, roots=[tsa["root"]])
    with pytest.raises(timestamps.TimestampError):
        timestamps.verify(result["response"][:100], digest, roots=[tsa["root"]])


def test_rejected_status_and_request_encoding():
    rejected = bytes.fromhex("3005" "3003" "020102")  # TimeStampResp { status: rejection }
    with pytest.raises(timestamps.TimestampError, match="abgelehnt"):
        timestamps.verify(rejected, b"\x00" * 32)
    request = timestamps.build_request(b"\x11" * 32, 1234567)
    assert request.startswith(b"\x30") and b"\x11" * 32 in request and request.endswith(b"\x01\x01\xff")
    with pytest.raises(timestamps.TimestampError):
        timestamps.build_request(b"short", 1)
    with pytest.raises(timestamps.TimestampError, match="http"):
        timestamps.request("ftp://tsa.example", b"\x00" * 32, send=lambda der: b"")


# ---------------------------------------------------------------- pure-Python test authority
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa  # noqa: E402
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID  # noqa: E402

T = timestamps


def _cert(subject, issuer, key, issuer_key, *, ca=False, eku=None, days=(1, 30)):
    now = datetime.now(timezone.utc)
    builder = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject[0]),
                                                                 x509.NameAttribute(NameOID.ORGANIZATION_NAME, subject[1])]))
               .issuer_name(issuer).public_key(key.public_key()).serial_number(x509.random_serial_number())
               .not_valid_before(now - timedelta(days=days[0])).not_valid_after(now + timedelta(days=days[1]))
               .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
    if eku:
        builder = builder.add_extension(x509.ExtendedKeyUsage(eku), critical=True)
    return builder.sign(issuer_key, hashes.SHA256())


def python_tsa(*, key_type="rsa", eku=(ExtendedKeyUsageOID.TIME_STAMPING,), valid_days=(1, 30)):
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PyRoot"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Py")])
    root = _cert(("PyRoot", "Py"), root_name, root_key, root_key, ca=True)
    key = ec.generate_private_key(ec.SECP256R1()) if key_type == "ec" else rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = _cert(("PyTSA", "Python Zeitstempel"), root.subject, key, root_key, eku=list(eku), days=valid_days)

    def send(der: bytes) -> bytes:
        req = T._root(der).children()
        digest = req[1].children()[1].value
        nonce = T._as_int(req[2])
        alg = T._tlv(0x30, T._oid(T.OID_SHA256) + b"\x05\x00")
        gen = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%SZ").encode()
        tst = T._tlv(0x30, T._int(1) + T._oid("1.2.3.4.9") + T._tlv(0x30, alg + T._tlv(0x04, digest)) + T._int(77)
                     + T._tlv(0x18, gen) + T._int(nonce))
        md = hashlib.sha256(tst).digest()
        attrs = T._tlv(0x31, T._tlv(0x30, T._oid(T.OID_CONTENT_TYPE) + T._tlv(0x31, T._oid(T.OID_TST_INFO)))
                       + T._tlv(0x30, T._oid(T.OID_MESSAGE_DIGEST) + T._tlv(0x31, T._tlv(0x04, md))))
        if key_type == "ec":
            signature, sig_alg = key.sign(attrs, ec.ECDSA(hashes.SHA256())), T._tlv(0x30, T._oid("1.2.840.10045.4.3.2"))
        else:
            signature = key.sign(attrs, padding.PKCS1v15(), hashes.SHA256())
            sig_alg = T._tlv(0x30, T._oid("1.2.840.113549.1.1.11") + b"\x05\x00")
        sid = T._tlv(0x30, cert.issuer.public_bytes() + T._int(cert.serial_number))
        signer_info = T._tlv(0x30, T._int(1) + sid + alg + b"\xa0" + attrs[1:] + sig_alg + T._tlv(0x04, signature))
        certs = T._tlv(0xA0, cert.public_bytes(serialization.Encoding.DER))
        encap = T._tlv(0x30, T._oid(T.OID_TST_INFO) + T._tlv(0xA0, T._tlv(0x04, tst)))
        signed = T._tlv(0x30, T._int(3) + T._tlv(0x31, alg) + encap + certs + T._tlv(0x31, signer_info))
        return T._tlv(0x30, T._tlv(0x30, T._int(0)) + T._tlv(0x30, T._oid(T.OID_SIGNED_DATA) + T._tlv(0xA0, signed)))
    return {"send": send, "root": root}


@pytest.mark.parametrize("key_type", ["rsa", "ec"])
def test_python_authority_rsa_and_ecdsa(key_type):
    tsa = python_tsa(key_type=key_type)
    digest = hashlib.sha256(b"beleg").digest()
    result = T.request("http://tsa.example", digest, send=tsa["send"])
    facts = T.verify(result["response"], digest, nonce=result["nonce"], roots=[tsa["root"]])
    assert facts["chain_trusted"] and facts["tsa"] == "Python Zeitstempel" and facts["serial"] == "77"


def test_certificate_without_timestamp_purpose_is_rejected():
    tsa = python_tsa(eku=(ExtendedKeyUsageOID.SERVER_AUTH,))
    digest = hashlib.sha256(b"beleg").digest()
    result = T.request("http://tsa.example", digest, send=tsa["send"])
    with pytest.raises(T.TimestampError, match="nicht für Zeitstempel"):
        T.verify(result["response"], digest, nonce=result["nonce"], roots=[tsa["root"]])


def test_certificate_not_valid_at_stamp_time_is_rejected():
    tsa = python_tsa(valid_days=(30, -1))  # expired yesterday
    digest = hashlib.sha256(b"beleg").digest()
    result = T.request("http://tsa.example", digest, send=tsa["send"])
    with pytest.raises(T.TimestampError, match="nicht gültig"):
        T.verify(result["response"], digest, nonce=result["nonce"], roots=[tsa["root"]])
