"""Idempotent user-scoped Windows workspace setup, without copying source.

Only creates a private local research workspace. Does not merge anything into
the EagleEye case vault, start a service, or publish records automatically.
"""
import argparse
import os
from pathlib import Path
import stat
import subprocess

from local_key import read_key
from windows_key_store import _assert_private_acl, prepare_private_directory


def _normal_dir(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Directory symlink is forbidden: " + str(path))
    if path.exists():
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or (os.name == "nt" and
                info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError("Unsafe workspace folder: " + str(path))
    else:
        path.mkdir()
    return path


def prepare_local(root):
    """Set up a single local workspace, preserving all existing files/keys."""
    if os.name != "nt":
        raise RuntimeError("Windows workspace installer only")
    root = Path(root)
    if not root.parent.is_dir():
        raise FileNotFoundError("LocalAppData parent missing")
    _normal_dir(root)
    work = _normal_dir(root / "workspace")
    for sub in ("inbox", "outbox", "audit", "config", "git"):
        _normal_dir(work / sub)
    gitdir = work / "git"
    if not (gitdir / ".git").exists():
        # Never init Git into an unrelated non-empty workspace.
        if any(gitdir.iterdir()):
            raise ValueError("Git staging folder is non-empty and uninitialized")
        subprocess.run(["git", "-C", str(gitdir), "init", "--quiet"],
                       check=True, capture_output=True, timeout=30)
    if not (gitdir / ".git").is_dir():
        raise ValueError("Expected a local staging Git repository")
    secret_dir = root / "secrets"
    if not secret_dir.exists() and not secret_dir.is_symlink():
        prepare_private_directory(secret_dir)
    else:
        _assert_private_acl(secret_dir)
    keyfile = secret_dir / "approval.dpapi"
    if not keyfile.exists() and not keyfile.is_symlink():
        from local_key import create_key
        create_key(keyfile)
    if len(read_key(keyfile)) != 32:
        raise ValueError("Invalid local DPAPI key")
    return {"root": str(root), "status": "ready",
            "git_staging": str(gitdir),
            "key_status": "DPAPI-encrypted (never printed)"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--init", action="store_true",
                   help="Create or verify workspace and DPAPI key")
    args = p.parse_args()
    if not args.init:
        raise SystemExit("Explicit --init required; no changes made")
    root = Path(os.environ["LOCALAPPDATA"]) / "EagleEyeResearchBridge"
    result = prepare_local(root)
    print("EagleEye Research Bridge local workspace ready")
    print("Root:", result["root"])
    print("The signing key and Git branches were not exported or modified.")


if __name__ == "__main__":
    main()
