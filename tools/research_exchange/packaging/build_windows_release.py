"""Build an unsigned Windows x64, Python-free-to-run Research Bridge RC bundle.

Requires Python 3.12 and PyInstaller at BUILD TIME only. The installed app
requires Windows + Git, but not a Python interpreter. No keys/case data included.
Writes build artifacts to D: to avoid burdening the Windows system drive.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

VERSION = "1.0.0-rc2"
APP = "eagleeye-public-research-bridge"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(output_dir):
    if sys.platform != "win32" or sys.maxsize < 2**32:
        raise RuntimeError("64-bit Windows required")
    here = Path(__file__).resolve().parent
    src = here.parent
    package = Path(output_dir).resolve() / ("EagleEyeResearchBridge-" + VERSION + "-Windows-x64")
    build_dir = Path(output_dir).resolve() / "build-intermediates"
    if package.exists():
        raise FileExistsError("Refusing to overwrite existing release candidate")
    if shutil.disk_usage(output_dir).free < 2_000_000_000:
        raise RuntimeError("At least 2 GB of free space required for the build")
    release_dist = build_dir / "dist"
    if (release_dist / "ResearchBridge").exists():
        raise FileExistsError("Build dist already exists; choose a fresh output location")
    release_dist.mkdir(parents=True, exist_ok=True)
    entry = src / "desktop_app_entry.py"
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onedir", "--windowed", "--noupx",
        "--name", "ResearchBridge",
        "--distpath", str(release_dist),
        "--workpath", str(build_dir / "work"),
        "--specpath", str(build_dir / "spec"), str(entry)
    ]
    result = subprocess.run(command, cwd=src, check=True, timeout=360,
                            capture_output=True, text=True)
    print("PYINSTALLER_BUILD_OK", result.returncode)
    frozen = release_dist / "ResearchBridge"
    exe = frozen / "ResearchBridge.exe"
    if not exe.is_file():
        raise FileNotFoundError(exe)
    pkg_payload = package / "payload" / "ResearchBridge"
    pkg_payload.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(frozen, pkg_payload)
    files = []
    for path in sorted(pkg_payload.rglob("*")):
        if path.is_symlink():
            raise RuntimeError("Refusing symlink in package")
        if path.is_file():
            files.append({
                "path": path.relative_to(package).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256(path),
            })
    root_commit = subprocess.run(
        ["git", "-C", str(src), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True, timeout=10
    ).stdout.strip()
    manifest = {
        "app_id": APP, "version": VERSION, "platform": "windows-x64",
        "source_commit": root_commit, "unsigned": True,
        "files": files,
    }
    (package / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for name in ("Install-ResearchBridge.ps1", "Uninstall-ResearchBridge.ps1",
                 "Switch-ResearchBridge-Version.ps1", "Install.cmd", "Uninstall.cmd"):
        shutil.copy2(here / name, package / name)
    (package / "READ_ME_FIRST.txt").write_text(
        "EAGLEEYE Research Bridge " + VERSION + " - UNSIGNED INTERNAL PREVIEW\n\n"
        "Allowed: public scientific, historical, technical and institutional facts.\n"
        "Forbidden: personal case data, credentials, surveillance, profiling.\n\n"
        "The package includes a self-contained Windows executable; it does not\n"
        "require Python after installation. Git must be installed for private\n"
        "research-exchange synchronization. No paid services are needed.\n\n"
        "1. Validate the ZIP SHA256 against the GitHub PR acceptance report.\n"
        "2. Extract all ZIP contents to a normal local directory.\n"
        "3. Double-click Install.cmd. Installation needs no administrator rights.\n"
        "4. Launch the desktop shortcut 'EagleEye Forschungs-Bruecke (Vorschau)'.\n"
        "5. Explicitly review each selected public research record and approve.\n\n"
        "For removal: run Uninstall.cmd (data and encrypted key are preserved).\n"
        "The signing key remains in %%LOCALAPPDATA%%\\EagleEyeResearchBridge\\secrets.\n"
        "To roll back: run the installed Switch-ResearchBridge-Version.ps1\n"
        "with -Version <installed-release-candidate>. Uninstall preserves research data.\n"
        "This is not the final 1.0 release; no signing certificate is included.\n",
        encoding="utf-8"
    )
    archive = package.parent / (package.name + ".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as zipfile_out:
        for file in sorted(package.rglob("*")):
            if file.is_file():
                zipfile_out.write(file, arcname=package.name + "/" +
                                   file.relative_to(package).as_posix())
    print("PACKAGE_DIR=" + str(package))
    print("ARCHIVE=" + str(archive))
    print("ARCHIVE_SHA256=" + sha256(archive))
    print("PAYLOAD_FILES=" + str(len(files)))
    print("ARCHIVE_BYTES=" + str(archive.stat().st_size))
    return package, archive


if __name__ == "__main__":
    directory = Path(sys.argv[1]) if len(sys.argv) >= 2 else Path(r"D:\EagleEyeResearchBuild\release")
    directory.mkdir(parents=True, exist_ok=True)
    build(directory)
