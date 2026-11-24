"""Explicit, repeatable Windows key provisioning; never prints key material."""
import os
from pathlib import Path

from local_key import create_key, read_key
from windows_key_store import _assert_private_acl, prepare_private_directory


def main():
    if os.name != "nt":
        raise SystemExit("Windows only")
    home = os.environ.get("LOCALAPPDATA")
    if not home:
        raise SystemExit("LOCALAPPDATA is not set")
    root = Path(home) / "EagleEyeResearchBridge"
    if not root.is_dir():
        raise SystemExit("Run the Phase A workspace installation first")
    folder = root / "secrets"
    if not folder.exists() and not folder.is_symlink():
        prepare_private_directory(folder)
    else:
        _assert_private_acl(folder)
    path = folder / "approval.dpapi"
    if not path.exists() and not path.is_symlink():
        create_key(path)
        status = "created"
    else:
        status = "existing"
    # Verify usability and ACLs without displaying or exporting the secret.
    if len(read_key(path)) != 32:
        raise SystemExit("invalid key")
    print("Windows DPAPI key", status, "- protected and readable by current user")
    print("Location:", path)
    print("No Git commit or data exchange has been performed")


if __name__ == "__main__":
    main()
