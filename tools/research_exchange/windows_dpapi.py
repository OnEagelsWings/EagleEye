"""User-scoped Windows DPAPI primitive; not yet wired into key storage."""
import ctypes
import os
from ctypes import wintypes


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _transform(data, decrypt):
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI unavailable")
    if not isinstance(data, bytes) or not 1 <= len(data) <= 65536:
        raise ValueError("invalid DPAPI input")
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p,
                   ctypes.POINTER(_Blob), ctypes.c_void_p,
                   ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
    fn.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = _Blob(len(data), buffer)
    result = _Blob()
    try:
        # UI forbidden; no machine-wide protection flag.
        if not fn(ctypes.byref(source), None, None, None, None, 1,
                  ctypes.byref(result)):
            raise ctypes.WinError(ctypes.get_last_error())
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        ctypes.memset(buffer, 0, len(data))
        if result.pbData:
            ctypes.memset(result.pbData, 0, result.cbData)
            kernel.LocalFree(result.pbData)


def protect_key(key):
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("invalid key length")
    return _transform(key, False)


def unprotect_key(blob):
    key = _transform(blob, True)
    if len(key) != 32:
        raise ValueError("invalid decrypted key length")
    return key
