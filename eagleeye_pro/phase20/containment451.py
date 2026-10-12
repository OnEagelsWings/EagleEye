"""Linux x86-64 worker confinement, applied only inside a disposable child.

No filesystem access is granted. TLS trust must be loaded before confinement.
The sole network capability is a parent-created, public-IP-pinned TCP socket.
Unsupported kernels/platforms fail closed; never silently downgrade this profile.
"""
import ctypes
import errno
import os
import platform
import sys


class IsolationUnavailable451(RuntimeError):
    pass


def confine_worker451():
    if sys.platform != "linux" or platform.machine() != "x86_64":
        raise IsolationUnavailable451("Linux x86-64 confinement required")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long

    def checked(result):
        if result < 0:
            raise IsolationUnavailable451("kernel confinement unavailable")
        return result

    abi = checked(libc.syscall(444, 0, 0, 1))
    if abi < 3:
        raise IsolationUnavailable451("Landlock ABI 3 required")
    # ABI 3 handles all filesystem rights through TRUNCATE (bits 0..14).
    # No allow rules: no file read, directory listing, execution or mutation.
    rights = ctypes.c_uint64((1 << 15) - 1)
    ruleset = checked(libc.syscall(444, ctypes.byref(rights), 8, 0))
    try:
        checked(libc.prctl(38, 1, 0, 0, 0))  # PR_SET_NO_NEW_PRIVS
        checked(libc.syscall(446, ruleset, 0))
    finally:
        os.close(ruleset)

    class Filter(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte),
                    ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]

    class Program(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(Filter))]

    # Check audit architecture and reject x32 syscall numbers before dispatch.
    # Deny new sockets/connections, process creation/control, SysV IPC,
    # io_uring (can bypass syscall-level network filtering), mounts and BPF.
    blocked = {41, 42, 43, 49, 50, 53, 56, 57, 58, 59, 62, 101,
               29, 30, 31, 64, 65, 66, 67, 68, 69, 70, 71,
               155, 165, 166, 200, 234, 272, 288, 298, 303, 304,
               308, 310, 311, 313, 321, 322, 323, 424, 425, 426,
               427, 428, 429, 430, 431, 432, 433, 434, 435, 438, 440}
    instructions = [(0x20, 0, 0, 4), (0x15, 1, 0, 0xC000003E),
                    (0x06, 0, 0, 0x80000000), (0x20, 0, 0, 0),
                    (0x35, 0, 1, 0x40000000), (0x06, 0, 0, 0x80000000)]
    for number in sorted(blocked):
        instructions.extend([(0x15, 0, 1, number),
                             (0x06, 0, 0, 0x00050000 | errno.EPERM)])
    instructions.append((0x06, 0, 0, 0x7FFF0000))
    filters = (Filter * len(instructions))(*(Filter(*entry) for entry in instructions))
    program = Program(len(filters), filters)
    checked(libc.prctl(22, 2, ctypes.byref(program), 0, 0))  # SECCOMP filter
    return {"profile": "linux451.landlock-seccomp.v1", "landlock_abi": abi,
            "filesystem_access": False, "new_network_connections": False}
