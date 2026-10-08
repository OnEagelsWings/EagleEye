from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import venv
from pathlib import Path

BUILD = "455.0"
PACKAGE = "eagleeye-personosint-pro"
PACKAGE_VERSION = "455.0.0"
RUNTIME_DIR = ".eagleeye-runtime"
RECEIPT = "install-receipt-455.json"


def _root() -> Path:
    return Path(__file__).resolve().parent


def _runtime_python(root: Path) -> Path:
    if os.name == "nt":
        return root / RUNTIME_DIR / "Scripts" / "python.exe"
    return root / RUNTIME_DIR / "bin" / "python"


def _source_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    roots = [
        root / "pyproject.toml",
        root / "EAGLEEYE_PRO_455_0.py",
        root / "RELEASE_MANIFEST_BUILD_455_0.json",
        root / "src" / "eagleeye",
        root / "eagleeye_pro",
        root / "alembic_104_1",
    ]
    files: list[Path] = []
    for item in roots:
        if item.is_file():
            files.append(item)
        elif item.is_dir():
            files.extend(
                p for p in item.rglob("*")
                if p.is_file()
                and "__pycache__" not in p.parts
                and not p.name.endswith((".pyc", ".pyo"))
            )
    for path in sorted(files, key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(rel).to_bytes(4, "big"))
        digest.update(rel)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _read_receipt(root: Path) -> dict:
    path = root / RUNTIME_DIR / RECEIPT
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _probe(root: Path) -> dict:
    runtime_python = _runtime_python(root)
    if not runtime_python.is_file():
        return {"ready": False, "reason": "runtime_python_missing"}

    code = r"""
import importlib.metadata
import json
from pathlib import Path
import eagleeye.interfaces.web.server as server

dist = importlib.metadata.distribution("eagleeye-personosint-pro")
raw = dist.read_text("direct_url.json")
editable = None
if raw:
    try:
        editable = bool((json.loads(raw).get("dir_info") or {}).get("editable", False))
    except Exception:
        editable = None
print(json.dumps({
    "version": dist.version,
    "editable": editable,
    "server_file": str(Path(server.__file__).resolve()),
}))
"""
    try:
        completed = subprocess.run(
            [str(runtime_python), "-I", "-c", code],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ready": False, "reason": type(exc).__name__}
    if completed.returncode != 0:
        return {
            "ready": False,
            "reason": "isolated_import_failed",
            "stderr": completed.stderr[-2000:],
        }
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError, json.JSONDecodeError):
        return {"ready": False, "reason": "probe_output_invalid"}
    server_file = Path(str(payload.get("server_file") or "")).resolve()
    runtime_root = (root / RUNTIME_DIR).resolve()
    try:
        in_runtime = server_file.is_relative_to(runtime_root)
    except ValueError:
        in_runtime = False
    ready = (
        payload.get("version") == PACKAGE_VERSION
        and payload.get("editable") is not True
        and in_runtime
    )
    return {
        "ready": ready,
        "reason": "ok" if ready else "runtime_contract_mismatch",
        **payload,
        "in_runtime": in_runtime,
    }


def _ensure_runtime(root: Path, *, quiet: bool = False) -> Path:
    runtime_python = _runtime_python(root)
    if runtime_python.is_file():
        return runtime_python
    runtime_dir = root / RUNTIME_DIR
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    if not quiet:
        print(f"[EagleEye {BUILD}] Creating isolated local runtime...")
    try:
        venv.EnvBuilder(with_pip=True, clear=False, symlinks=os.name != "nt").create(runtime_dir)
    except Exception:
        if runtime_dir.exists():
            shutil.rmtree(runtime_dir, ignore_errors=True)
        raise
    if not runtime_python.is_file():
        raise RuntimeError("runtime creation completed without a Python executable")
    return runtime_python


def _install(root: Path, runtime_python: Path, *, quiet: bool = False) -> None:
    if not quiet:
        print(f"[EagleEye {BUILD}] Installing package {PACKAGE_VERSION} into the local runtime...")
    command = [
        str(runtime_python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--upgrade",
        str(root),
    ]
    subprocess.run(command, cwd=str(root), check=True)


def _write_receipt(root: Path, *, fingerprint: str, probe: dict) -> Path:
    runtime_dir = root / RUNTIME_DIR
    path = runtime_dir / RECEIPT
    payload = {
        "build": BUILD,
        "package": PACKAGE,
        "package_version": PACKAGE_VERSION,
        "source_fingerprint_sha256": fingerprint,
        "installed_epoch": int(time.time()),
        "python": sys.version.split()[0],
        "runtime_python": str(_runtime_python(root).resolve()),
        "server_file": probe.get("server_file", ""),
        "editable": probe.get("editable"),
        "isolated_import": True,
    }
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        temp.chmod(0o600)
    except OSError:
        pass
    temp.replace(path)
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Install or verify the EagleEye Build 455 local runtime.")
    parser.add_argument("--check", action="store_true", help="verify without changing the runtime")
    parser.add_argument("--force", action="store_true", help="reinstall even when the receipt and runtime match")
    parser.add_argument("--quiet", action="store_true", help="suppress installer progress messages")
    args = parser.parse_args(argv)

    if sys.version_info < (3, 12):
        print("EagleEye Build 455 requires Python 3.12 or newer.", file=sys.stderr)
        return 2

    root = _root()
    fingerprint = _source_fingerprint(root)
    receipt = _read_receipt(root)
    probe = _probe(root)
    receipt_matches = (
        receipt.get("build") == BUILD
        and receipt.get("package_version") == PACKAGE_VERSION
        and receipt.get("source_fingerprint_sha256") == fingerprint
    )
    ready = bool(probe.get("ready") and receipt_matches)

    if args.check:
        if not args.quiet:
            print(json.dumps({
                "build": BUILD,
                "ready": ready,
                "receipt_matches": receipt_matches,
                "runtime": probe,
            }, ensure_ascii=False, indent=2))
        return 0 if ready else 2

    if args.force or not ready:
        try:
            runtime_python = _ensure_runtime(root, quiet=args.quiet)
            _install(root, runtime_python, quiet=args.quiet)
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"EagleEye Build 455 installation failed: {exc}", file=sys.stderr)
            return 1
        probe = _probe(root)
        if not probe.get("ready"):
            print(
                "EagleEye Build 455 installation did not satisfy the isolated runtime contract: "
                + str(probe.get("reason") or "unknown"),
                file=sys.stderr,
            )
            return 1
        _write_receipt(root, fingerprint=fingerprint, probe=probe)

    if not args.quiet:
        print(f"EagleEye Build {BUILD} runtime ready ({PACKAGE_VERSION}, non-editable, isolated import).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
