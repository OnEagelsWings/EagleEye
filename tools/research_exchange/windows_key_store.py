"""Local, user-scoped Windows DPAPI signing-key store.

The signing key is never placed in Git and is stored encrypted with DPAPI.
A dedicated non-inheriting ACL directory is required; there is no fallback to
plaintext files. This is not a replacement for user review of outbound data.
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess

from windows_dpapi import protect_key, unprotect_key

MAGIC = b"EAGLEEYE-DPAPI-KEY-V1\x00"
MAX_BLOB = 65536


def _windows_only():
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI key store is available only on Windows")


def _current_sid():
    _windows_only()
    result = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        capture_output=True, check=True, timeout=10,
    )
    match = re.search(rb"S-1-\d+(?:-\d+)+", result.stdout)
    if match is None:
        raise RuntimeError("unable to resolve Windows user SID")
    return match.group().decode("ascii")


def _reject_reparse(path):
    info = path.lstat()
    if info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError("reparse point not permitted in key store")
    return info


def _sddl(path):
    """Retrieve OWNER and DACL SDDL using the Windows security API."""
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    adv.GetFileSecurityW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ]
    adv.GetFileSecurityW.restype = wintypes.BOOL
    adv.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD),
    ]
    adv.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    required = wintypes.DWORD()
    mask = 0x1 | 0x4  # OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION
    adv.GetFileSecurityW(str(path), mask, None, 0, ctypes.byref(required))
    if required.value == 0 or required.value > 65536:
        raise OSError("unable to read key store security descriptor")
    buf = ctypes.create_string_buffer(required.value)
    if not adv.GetFileSecurityW(str(path), mask, buf, required, ctypes.byref(required)):
        raise ctypes.WinError(ctypes.get_last_error())
    ptr = ctypes.c_void_p()
    count = wintypes.DWORD()
    if not adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(
        buf, 1, mask, ctypes.byref(ptr), ctypes.byref(count)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.wstring_at(ptr.value)
    finally:
        kernel.LocalFree(ptr)


def _canonical_sid(value):
    """Resolve SDDL aliases (LA/BA/SY) and raw SIDs to the same SID form."""
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    adv.ConvertStringSidToSidW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
    adv.ConvertStringSidToSidW.restype = wintypes.BOOL
    adv.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    adv.ConvertSidToStringSidW.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    sid_ptr = ctypes.c_void_p()
    if not adv.ConvertStringSidToSidW(value, ctypes.byref(sid_ptr)):
        raise ValueError("unrecognized SDDL trustee")
    try:
        result_ptr = ctypes.c_void_p()
        if not adv.ConvertSidToStringSidW(sid_ptr, ctypes.byref(result_ptr)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.wstring_at(result_ptr.value)
        finally:
            kernel.LocalFree(result_ptr)
    finally:
        kernel.LocalFree(sid_ptr)


def _assert_private_acl(path):
    """Fail closed for any inheritable, unknown or non-owner ACL entries."""
    _windows_only()
    info = _reject_reparse(path)
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
        raise ValueError("key-store entry must be a file or directory")
    sid = _current_sid()
    sddl = _sddl(path)
    owner = re.search(r"O:(.*?)(?=G:|D:)", sddl)
    if owner is None or _canonical_sid(owner.group(1)) != sid:
        raise ValueError("key-store entry must be owned by current user")
    marker = sddl.find("D:")
    if marker < 0:
        raise ValueError("key-store DACL is missing")
    dacl = sddl[marker + 2:]
    prefix = dacl.split("(", 1)[0]
    if "P" not in prefix:
        raise ValueError("key-store DACL must be protected from inheritance")
    aces = re.findall(r"\(([^()]*)\)", dacl)
    if not aces:
        raise ValueError("empty key-store DACL")
    have_user = False
    for ace in aces:
        fields = ace.split(";")
        if len(fields) != 6 or fields[0] != "A":
            raise ValueError("unsupported key-store ACL entry")
        flags, rights, trustee = fields[1], fields[2], fields[5]
        normalized_trustee = _canonical_sid(trustee)
        if "ID" in flags or normalized_trustee not in {"S-1-5-18", "S-1-5-32-544", sid}:
            raise ValueError("inherited or unexpected key-store ACL principal")
        if rights not in ("FA", "0x1f01ff", "0x1F01FF"):
            raise ValueError("unexpected key-store ACL permissions")
        have_user |= normalized_trustee == sid
    if not have_user:
        raise ValueError("current user has no explicit key-store permission")


def _lockdown_acl(path, *, directory):
    sid = _current_sid()
    rights = ":(OI)(CI)F" if directory else ":F"
    commands = [
        ["icacls", str(path), "/inheritance:r"],
        ["icacls", str(path), "/grant:r", "*" + sid + rights],
        ["icacls", str(path), "/grant:r", "*S-1-5-18" + rights],
        ["icacls", str(path), "/grant:r", "*S-1-5-32-544" + rights],
        # Elevated Windows service/CI tokens may default to Administrators
        # as owner even for newly created files. Normalize to the user SID.
        ["icacls", str(path), "/setowner", "*" + sid],
    ]
    for command in commands:
        subprocess.run(command, check=True, capture_output=True, timeout=15)
    _assert_private_acl(path)


def prepare_private_directory(path):
    """Create a new secrets directory, then remove inherited ACLs before use.

    Never modifies an existing directory's ACL, to avoid touching user data.
    """
    _windows_only()
    path = Path(path)
    if not path.parent.is_dir():
        raise FileNotFoundError("key-store parent directory must already exist")
    _reject_reparse(path.parent)
    path.mkdir()  # exclusive: do not reconfigure pre-existing folders
    try:
        _lockdown_acl(path, directory=True)
    except BaseException:
        try:
            path.rmdir()  # still empty; never delete an existing key
        except OSError:
            pass
        raise


def create_key(path):
    """Create an encrypted key exactly once; never overwrite existing keys."""
    _windows_only()
    path = Path(path)
    _assert_private_acl(path.parent)
    if path.exists() or path.is_symlink():
        raise FileExistsError("signing-key file already exists")
    encoded = MAGIC + protect_key(secrets.token_bytes(32))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_BINARY, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        _lockdown_acl(path, directory=False)
    except BaseException:
        # Never silently replace or delete an existing successfully written key.
        raise


def read_key(path):
    _windows_only()
    path = Path(path)
    _assert_private_acl(path.parent)
    info = _reject_reparse(path)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("unsafe key file")
    _assert_private_acl(path)
    with path.open("rb") as stream:
        raw = stream.read(len(MAGIC) + MAX_BLOB + 1)
    if len(raw) > len(MAGIC) + MAX_BLOB or not raw.startswith(MAGIC):
        raise ValueError("not a supported DPAPI signing-key file")
    return unprotect_key(raw[len(MAGIC):])
