"""SHA-256 inventory for Windows Build 500 offline wheels."""
from pathlib import Path
import hashlib
import json
import sys

def main(root: Path):
    if not root.is_dir():raise RuntimeError("wheelhouse directory missing")
    if root.is_symlink():
        raise RuntimeError("Wheelhouse symlink is not allowed")
    if (root/"MANIFEST-SHA256.json").is_symlink():
        raise RuntimeError("Wheel manifest symlink is not allowed")
    wheels=sorted(root.glob("*.whl"))
    for wheel in wheels:
        if wheel.is_symlink() or not wheel.is_file():
            raise RuntimeError("Wheelhouse contains a linked or non-file wheel: "+wheel.name)
        if wheel.stat().st_nlink != 1:
            raise RuntimeError("Wheelhouse contains a hardlinked wheel: "+wheel.name)
    if not wheels:raise RuntimeError("Wheelhouse empty")
    if not any(p.name.lower().startswith("eagleeye_personosint_pro-500.0.0") for p in wheels):
        raise RuntimeError("Build 500 application wheel missing")
    data={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in wheels}
    (root/"MANIFEST-SHA256.json").write_text(json.dumps(data,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(f"Verified wheel manifest created for {len(wheels)} packages")

if __name__=="__main__":
    main(Path(sys.argv[1] if len(sys.argv)>1 else "wheelhouse"))
