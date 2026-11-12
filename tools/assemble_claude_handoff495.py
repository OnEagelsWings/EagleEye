"""Produce a reproducible, safety-filtered EagleEye + Claude Code source handoff.

This is NOT a binary installer or a clinical/legal/operational release.
From repo root:
  python tools/assemble_claude_handoff495.py --eagleeye . \
    --personosint ../ClaudePersonOSINT --output EagleEye-495-ClaudeCode-SourceHandoff.zip
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "secrets", "credentials",
    "logs", "data", ".eagleeye-runtime", ".pytest_cache"
}
EXCLUDED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".pem", ".key",
                     ".p12", ".pfx", ".eebak", ".zip", ".log"}
MAX_FILE_SIZE = 32 * 1024 * 1024
ZIP_TIME = (2026, 11, 10, 0, 0, 0)


def _git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args])


def _entries(root: Path, source: str) -> list[tuple[str, bytes]]:
    root = root.resolve(strict=True)
    if source == "EagleEye":
        names = _git(root, "ls-files", "-z").split(b"\0")
        prefix = ""
    else:
        names = _git(root, "ls-files", "-z", "--", "PersonOSINT/").split(b"\0")
        prefix = "ClaudePersonOSINT/"
    entries = []
    for name in names:
        if not name:
            continue
        rel = PurePosixPath(name.decode("utf-8"))
        parts = rel.parts
        if (rel.is_absolute() or ".." in parts or
                any(x in EXCLUDED_DIRS or x.startswith(".eagleeye-") for x in parts) or
                rel.suffix.lower() in EXCLUDED_SUFFIXES or
                rel.name == ".env" or (rel.name.startswith(".env.") and rel.name != ".env.example")):
            continue
        path = root.joinpath(*parts)
        if path.is_symlink() or not path.is_file():
            continue
        if path.stat().st_size > MAX_FILE_SIZE:
            raise ValueError(f"Source file unexpectedly large: {rel}")
        dest = source + "/" + prefix + rel.as_posix() if source == "EagleEye" else prefix + rel.as_posix()
        entries.append((dest, path.read_bytes()))
    return entries


def _write(z: ZipFile, name: str, content: bytes) -> None:
    info = ZipInfo(name, ZIP_TIME)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    z.writestr(info, content, compress_type=ZIP_DEFLATED, compresslevel=6)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--eagleeye", required=True, type=Path)
    p.add_argument("--personosint", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()

    current = _entries(args.eagleeye, "EagleEye")
    reference = _entries(args.personosint, "Reference")
    if not current or not reference:
        raise SystemExit("Both the EagleEye tree and separate Claude PersonOSINT tree are mandatory")
    entries = sorted(current + reference)
    if len(entries) != len(set(name for name, _ in entries)):
        raise SystemExit("Duplicate paths in handoff package")

    current_sha = _git(args.eagleeye, "rev-parse", "HEAD").decode().strip()
    reference_sha = _git(args.personosint, "rev-parse", "HEAD").decode().strip()
    files = {name: hashlib.sha256(data).hexdigest() for name, data in entries}
    manifest = {
        "type": "source-only-development-handoff",
        "status": "NOT AN INSTALLER / NOT PRODUCTION APPROVED",
        "base": "EagleEye installed package 490.0 with integration development layers 492-496",
        "eagleeye_commit": current_sha, "personosint_reference_commit": reference_sha,
        "eagleeye_files": len(current), "personosint_reference_files": len(reference),
        "separate_reference_no_auto_merge": True,
        "files_sha256": files,
    }
    instructions = (
        "# EagleEye – aktuelle Übergabe an Claude Code\n\n"
        "Diese ZIP ist eine vollständige QUELLCODE-Übergabe, kein freigegebenes Windows-Installationspaket.\n\n"
        "## Verzeichnisse\n"
        "- `EagleEye/`: aktueller gemeinsamer Integrationszweig\n"
        "- `ClaudePersonOSINT/PersonOSINT/`: Originalcode von Claude aus dem separaten Branch\n\n"
        "Die 492/493/494/495/496-Schichten sind bereits in der Startfabrik eingebunden. "
        "PersonOSINT-Fallexporte können als ungeprüfte HTTPS-Links und "
        "unbestätigte Entitätsvorschläge importiert werden. "
        "Die zweite Anwendung bleibt eine Code-Referenz, nicht eine zweite operative Datenbank.\n\n"
        "## Weiterentwicklung\n"
        "Bitte nur einen kanonischen Fall-/Evidence-/Benutzer-/OPSEC-Kern verwenden. "
        "Keine automatische Identitätsfusion. Änderungen über separate Feature-Branches und PRs.\n"
        "Die vollständig geprüfte Windows-Installation, der Live-Quellentest und "
        "die Freigabe des zusammengeführten Produktes stehen noch aus.\n\n"
        "## Tests\n"
        "`python -m pip install -e '.[test]'` innerhalb von EagleEye; "
        "dann `pytest -q tests/test_build493_personosint.py tests/test_build494_personosint.py "
        "tests/test_build496_plan.py tests/test_build490_server_selection.py`.\n"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.output, "w") as z:
        for name, data in entries:
            _write(z, name, data)
        _write(z, "HANDOFF_README_DE.md", instructions.encode("utf-8"))
        _write(z, "MANIFEST.sha256.json", json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, indent=2
        ).encode("utf-8"))
    with ZipFile(args.output) as z:
        if z.testzip() is not None:
            raise SystemExit("Handoff ZIP failed CRC test")
        assert "HANDOFF_README_DE.md" in z.namelist()
        assert len(z.namelist()) == len(files) + 2
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(
        digest + "  " + args.output.name + "\n", encoding="utf-8")
    print(f"Created {args.output}: {len(current)} EagleEye + {len(reference)} PersonOSINT files; SHA-256 {digest}")


if __name__ == "__main__":
    main()
