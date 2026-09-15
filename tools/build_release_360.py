from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import stat
import zipfile
from pathlib import Path

BUILD = "360.0"
PREFIX = "EagleEye_PersonOSINT_Pro_Build_360_0"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _runtime_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for base in (root / "eagleeye_pro", root / "src/eagleeye", root / "alembic_104_1"):
        if base.exists():
            paths.extend(p for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    for rel in (
        "pyproject.toml", "requirements-runtime.txt", "requirements-windows.txt",
        "EAGLEEYE_PRO_360_0.py", "START_EAGLEEYE_PRO.bat", "START_EAGLEEYE_PRO_360_0.bat", "START_EAGLEEYE_PRO.sh",
    ):
        p = root / rel
        if p.is_file():
            paths.append(p)
    return sorted(set(paths), key=lambda p: p.relative_to(root).as_posix())


def write_runtime_manifest(root: Path) -> dict:
    files = []
    for path in _runtime_paths(root):
        rel = path.relative_to(root).as_posix()
        files.append({"path": rel, "size": path.stat().st_size, "sha256": _sha_file(path)})
    payload = {"build": BUILD, "profile": "runtime_integrity", "files": files}
    out = root / "RUNTIME_MANIFEST_BUILD_360_0.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _profile(root: Path) -> dict:
    return json.loads((root / "RELEASE_PROFILE_BUILD_360_0.json").read_text(encoding="utf-8"))


def selected_files(root: Path) -> list[Path]:
    profile = _profile(root)
    includes = profile["include"]
    excludes = profile["exclude"]
    selected: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(rel, pat) for pat in excludes):
            continue
        if any(fnmatch.fnmatch(rel, pat) for pat in includes):
            selected.append(path)
    return sorted(selected, key=lambda p: p.relative_to(root).as_posix())


def content_digest(root: Path, files: list[Path]) -> str:
    h = hashlib.sha256()
    for path in files:
        rel = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        h.update(rel); h.update(b"\0"); h.update(hashlib.sha256(data).digest()); h.update(b"\0")
    return h.hexdigest()


def build_zip(root: Path, output: Path) -> dict:
    files = selected_files(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            rel = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(f"{PREFIX}/{rel}", FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if path.suffix == ".sh" else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.create_system = 3
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return {
        "build": BUILD,
        "output": str(output),
        "file_count": len(files),
        "package_content_digest": content_digest(root, files),
        "zip_sha256": _sha_file(output),
        "zip_size": output.stat().st_size,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--write-runtime-manifest", action="store_true")
    ns = ap.parse_args()
    if ns.write_runtime_manifest:
        write_runtime_manifest(ns.root)
    result = build_zip(ns.root, ns.output)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
