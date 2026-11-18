"""POSIX-only local key provisioning; Windows ACL support is pending."""
import os
import secrets
import stat
from pathlib import Path


def _directory(path):
    if os.name != 'posix' or not hasattr(os, 'O_NOFOLLOW'):
        raise RuntimeError('secure key provisioning unavailable on this platform')
    fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        os.close(fd)
        raise ValueError('key directory must be owned by user and mode 0700')
    return fd


def create_key(path):
    path = Path(path)
    directory = _directory(path)
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(secrets.token_bytes(32))
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(directory)


def read_key(path):
    path = Path(path)
    directory = _directory(path)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
                raise ValueError('unsafe key file')
            key = stream.read(33)
            if len(key) != 32:
                raise ValueError('invalid key length')
            return key
    finally:
        os.close(directory)
